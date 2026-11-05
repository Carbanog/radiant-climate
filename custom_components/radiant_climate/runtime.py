"""Home Assistant I/O boundary and single writer for registered actuators."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STORAGE_VERSION
from .core.control import Decision, Intent, Mode, Settings, decide, temperature

_LOGGER = logging.getLogger(__name__)


@dataclass
class Zone:
    config: dict
    intent: Intent
    settings: Settings
    switched_at: object
    actual_on: bool = False
    decision: Decision | None = None


class Installation:
    """One installation with independent zones and an optional shared inlet.

    Service completion is not valve feedback. A requested open is issued to the
    general first; zone activation waits for its reported relay state. This is
    deliberately not described as a verified hydraulic opening sequence.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.entries: dict[str, dict] = {}
        self.zones: dict[str, Zone] = {}
        self.enabled = False
        self.supply_mode = Mode.HEAT
        self.hub: str | None = None
        self._saved: dict = {}
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.state")
        self._lock = asyncio.Lock()
        self._listeners: set[Callable] = set()
        self._pending: asyncio.Task | None = None
        self._closed = False
        self._last_command: dict[str, tuple[bool, object]] = {}
        self._command_faults: set[str] = set()
        self._unsub_state = hass.bus.async_listen(EVENT_STATE_CHANGED, self._state_changed)
        self._unsub_tick = async_track_time_interval(hass, self._tick, timedelta(seconds=15))
        self._unsub_stop = hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self._shutdown)

    async def async_load(self) -> None:
        raw = await self._store.async_load()
        if raw is None:
            return
        try:
            if not isinstance(raw, dict) or not isinstance(raw.get("enabled"), bool):
                raise ValueError("Invalid installation state")
            self.supply_mode = Mode(raw["supply_mode"])
            if self.supply_mode == Mode.OFF or not isinstance(raw["zones"], dict):
                raise ValueError("Invalid installation state")
            self._saved = raw["zones"]
            self.enabled = raw["enabled"]
        except (KeyError, TypeError, ValueError):
            self.enabled = False
            _LOGGER.error("Stored installation state is invalid; control remains disabled")

    async def async_add(self, entry: ConfigEntry) -> None:
        data = {**entry.data, **entry.options}
        used = {a for c in self.entries.values() for a in c.get("actuators", [])}
        used |= {c["general"] for c in self.entries.values() if c.get("general")}
        requested = data.get("actuators", []) if data["kind"] == "zone" else [data.get("general")]
        if used & set(filter(None, requested)):
            raise ConfigEntryError("An actuator is already assigned")
        if data["kind"] == "installation":
            if self.hub is not None:
                raise ConfigEntryError("Only one installation is supported")
            self.hub = entry.entry_id
        else:
            modes = tuple(Mode(m) for m in data["modes"])
            settings = Settings(
                modes=modes,
                hysteresis=data.get("hysteresis", 0.2),
                minimum_on=data.get("minimum_on", 180),
                minimum_off=data.get("minimum_off", 180),
                stale_after=data.get("stale_after", 3600),
            )
            intent = Intent(last_mode=modes[0])
            intent.targets[modes[0]] = temperature(data["target"])
            if entry.entry_id in self._saved:
                try:
                    intent = Intent.restore(self._saved[entry.entry_id])
                    if intent.mode != Mode.OFF and intent.mode not in modes:
                        intent.mode = Mode.OFF
                except (KeyError, TypeError, ValueError):
                    _LOGGER.error("Stored zone state is invalid; zone remains off")
            self.zones[entry.entry_id] = Zone(data, intent, settings, dt_util.utcnow())
        self.entries[entry.entry_id] = data
        await self.async_reconcile()

    async def async_remove(self, entry_id: str) -> None:
        async with self._lock:
            if zone := self.zones.pop(entry_id, None):
                self._saved[entry_id] = zone.intent.dump()
                for entity in zone.config["actuators"]:
                    await self._command(entity, False)
            if self.hub == entry_id:
                self.enabled = False
                await self._apply()
                self.hub = None
            self.entries.pop(entry_id, None)
            await self._apply()
            await self._save()
            self._notify()

    @property
    def general(self) -> str | None:
        return self.entries.get(self.hub, {}).get("general")

    @callback
    def async_subscribe(self, listener: Callable) -> Callable:
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    @callback
    def _state_changed(self, event) -> None:
        entity = event.data["entity_id"]
        watched = {self.general} | {
            e
            for z in self.zones.values()
            for e in [z.config["sensor"], z.config.get("window"), *z.config["actuators"]]
        }
        if entity in watched:
            self._request_update()

    @callback
    def _tick(self, _now) -> None:
        self._request_update()

    @callback
    def _request_update(self) -> None:
        if self._closed:
            return
        if self._pending is None or self._pending.done():
            self._pending = self.hass.async_create_task(self.async_reconcile())

    async def _command(self, entity: str, wanted: bool) -> bool:
        state = self.hass.states.get(entity)
        if state is None or state.state not in ("on", "off"):
            return False
        if (state.state == "on") == wanted:
            self._last_command.pop(entity, None)
            return True
        if entity in self._command_faults:
            return False
        now = dt_util.utcnow()
        previous = self._last_command.get(entity)
        if previous and previous[0] == wanted:
            if (now - previous[1]).total_seconds() > 30:
                self._command_faults.add(entity)
                _LOGGER.error("Actuator did not report the requested state; manual review required")
            return False
        self._last_command[entity] = (wanted, now)
        try:
            async with asyncio.timeout(5):
                await self.hass.services.async_call(
                    "switch",
                    "turn_on" if wanted else "turn_off",
                    {"entity_id": entity},
                    blocking=True,
                )
        except (HomeAssistantError, TimeoutError):
            self._command_faults.add(entity)
            _LOGGER.error("Actuator command failed; no automatic retry loop will be started")
            return False
        state = self.hass.states.get(entity)
        return state is not None and state.state == ("on" if wanted else "off")

    async def _apply(self) -> None:
        now = dt_util.utcnow()
        enabled = self.enabled and self.hub is not None and self.hass.is_running
        plan: dict[str, bool] = {}
        for key, z in self.zones.items():
            sensor = self.hass.states.get(z.config["sensor"])
            output = [self.hass.states.get(e) for e in z.config["actuators"]]
            available = all(s is not None and s.state in ("on", "off") for s in output)
            on = any(s is not None and s.state == "on" for s in output)
            if on != z.actual_on:
                z.switched_at = now
                z.actual_on = on
            window = self.hass.states.get(z.config["window"]) if z.config.get("window") else None
            opened = (
                (window.state == "on" if window and window.state in ("on", "off") else None)
                if z.config.get("window")
                else False
            )
            z.decision = decide(
                z.settings,
                z.intent,
                now,
                measured=sensor.state if sensor else None,
                measured_at=sensor.last_reported if sensor else None,
                actual_on=on,
                switched_at=z.switched_at,
                enabled=enabled,
                supply_mode=self.supply_mode,
                window_open=opened,
                actuator_available=available,
            )
            plan[key] = z.decision.demand
        # First close zones that must not receive water. If that cannot be
        # confirmed at relay level, opening a shared supply is not allowed.
        isolated = True
        for key, z in self.zones.items():
            if not plan[key]:
                for e in z.config["actuators"]:
                    isolated = await self._command(e, False) and isolated
        demand = any(plan.values()) and enabled
        if self.general:
            supply = await self._command(self.general, demand and isolated)
            allowed = demand and isolated and supply
        else:
            allowed = enabled
        for key, z in self.zones.items():
            if plan[key] and not allowed:
                z.decision = Decision(False, "supply_not_ready", z.decision.target)
            for e in z.config["actuators"]:
                if plan[key]:
                    await self._command(e, bool(allowed))

    async def async_reconcile(self) -> None:
        async with self._lock:
            await self._apply()
            self._notify()

    async def _save(self) -> None:
        self._saved.update({k: z.intent.dump() for k, z in self.zones.items()})
        await self._store.async_save(
            {"enabled": self.enabled, "supply_mode": self.supply_mode.value, "zones": self._saved}
        )

    async def async_change(self, change: Callable) -> None:
        async with self._lock:
            change()
            await self._apply()
            await self._save()
            self._notify()

    async def async_enable(self, value: bool) -> None:
        def update():
            self.enabled = value
            if not value:
                # Explicit global off authorises a fresh bounded close attempt.
                self._command_faults.clear()
                self._last_command.clear()

        await self.async_change(update)

    async def async_supply(self, value: str) -> None:
        mode = Mode(value)
        if mode == Mode.OFF:
            raise ValueError("Supply mode must be heating or cooling")

        def update():
            self.supply_mode = mode
            for z in self.zones.values():
                z.intent.resume()
                if z.intent.mode != Mode.OFF and mode in z.settings.modes:
                    z.intent.set_mode(mode, z.settings)

        await self.async_change(update)

    @callback
    def async_stop(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._unsub_state()
        self._unsub_tick()
        self._unsub_stop()
        if self._pending and not self._pending.done():
            self._pending.cancel()

    async def _shutdown(self, _event) -> None:
        # Best-effort graceful shutdown only. A power loss or process kill
        # cannot deliver commands; do not claim a hardware fail-safe.
        self.async_stop()
        async with self._lock:
            await self._apply()
