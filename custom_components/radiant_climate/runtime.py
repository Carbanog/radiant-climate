"""Home Assistant I/O boundary and single writer for registered actuators."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STORAGE_VERSION
from .core.control import Decision, Intent, Mode, Settings, temperature
from .core.intelligence import window_pause
from .core.program import Program
from .environment import Environment
from .intelligence import Intelligence

_LOGGER = logging.getLogger(__name__)


def indoor_temperature(state) -> float | None:
    """Reject unsupported units instead of treating a Fahrenheit value as Celsius."""
    if state is None or state.attributes.get("unit_of_measurement") != UnitOfTemperature.CELSIUS:
        return None
    try:
        return temperature(state.state, -30, 65)
    except ValueError:
        return None


@dataclass
class Zone:
    config: dict
    intent: Intent
    settings: Settings
    switched_at: object
    program: Program
    window_enabled: bool = True
    actual_on: bool = False
    decision: Decision | None = None
    intelligence: Intelligence = field(default_factory=Intelligence)


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
        self._dirty = False
        self._revision = 0
        self._last_command: dict[str, tuple[bool, object]] = {}
        self._command_faults: set[str] = set()
        self._desired: dict[str, bool] = {}
        self._deviations: dict[str, list] = {}
        self._fault_dirty = False
        self.environment = Environment(hass)
        self._weather_task: asyncio.Task | None = None
        self._checkpoint = dt_util.utcnow()
        self._transition_until = None
        self._unsub_state = hass.bus.async_listen(EVENT_STATE_CHANGED, self._state_changed)
        self._unsub_tick = async_track_time_interval(hass, self._tick, timedelta(seconds=15))
        self._unsub_stop = hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self._shutdown)
        self._unsub_start = hass.bus.async_listen(EVENT_HOMEASSISTANT_STARTED, self._tick)

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
            self._command_faults = set(raw.get("command_faults", []))
            if any(not isinstance(e, str) for e in self._command_faults):
                raise ValueError("Invalid command fault state")
            self._transition_until = (
                dt_util.parse_datetime(raw["transition_until"])
                if raw.get("transition_until")
                else None
            )
            if self._transition_until and self._transition_until.tzinfo is None:
                raise ValueError("Invalid transition state")
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
            program = Program()
            intent.targets[modes[0]] = temperature(data["target"])
            if entry.entry_id in self._saved:
                try:
                    intent = Intent.restore(self._saved[entry.entry_id])
                    if raw_program := self._saved[entry.entry_id].get("program"):
                        program = Program.restore(raw_program)
                    if intent.mode != Mode.OFF and intent.mode not in modes:
                        intent.mode = Mode.OFF
                except (KeyError, TypeError, ValueError):
                    intent = Intent(last_mode=modes[0])
                    program = Program()
                    _LOGGER.error("Stored zone state is invalid; zone remains off")
            self.zones[entry.entry_id] = Zone(data, intent, settings, dt_util.utcnow(), program)
            if entry.entry_id in self._saved:
                try:
                    self.zones[entry.entry_id].intelligence = Intelligence.restore(
                        self._saved[entry.entry_id].get("intelligence", {})
                    )
                except (KeyError, TypeError, ValueError):
                    # Optional learning corruption must not destroy user setpoints.
                    self.zones[entry.entry_id].intelligence = Intelligence()
            raw_window = self._saved.get(entry.entry_id, {}).get("window_enabled", True)
            self.zones[entry.entry_id].window_enabled = (
                raw_window if isinstance(raw_window, bool) else True
            )
        self.entries[entry.entry_id] = data
        self._refresh_weather()
        await self.async_reconcile()

    async def async_remove(self, entry_id: str) -> None:
        async with self._lock:
            if zone := self.zones.pop(entry_id, None):
                self._saved[entry_id] = {
                    **zone.intent.dump(),
                    "program": zone.program.dump(),
                    "window_enabled": zone.window_enabled,
                    "intelligence": zone.intelligence.dump(),
                }
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

    def source(self, zone, key):
        return zone.config.get(key) or self.entries.get(self.hub, {}).get(key)

    def _ready(self):
        all_entries = self.hass.config_entries.async_entries(DOMAIN)
        expected = {e.entry_id for e in all_entries if e.disabled_by is None}
        for entry in all_entries:
            if entry.disabled_by is not None:
                for entity in {**entry.data, **entry.options}.get("actuators", []):
                    state = self.hass.states.get(entity)
                    if state is None or state.state != "off":
                        return False
        return self.hub is not None and expected <= self.entries.keys()

    @callback
    def _refresh_weather(self):
        if self._closed or (self._weather_task and not self._weather_task.done()):
            return
        entities = {
            self.source(z, "weather")
            for z in self.zones.values()
            if z.intelligence.features.weather
        }
        if not any(entities):
            return

        async def update():
            await self.environment.refresh(entities)
            self._request_update()

        self._weather_task = self.hass.async_create_task(update())

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
        watched = {self.general, "sun.sun"} | {
            e
            for z in self.zones.values()
            for e in [
                z.config["sensor"],
                z.config.get("window"),
                self.source(z, "weather"),
                self.source(z, "outdoor"),
                *z.config["actuators"],
            ]
        }
        watched |= {
            a
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            for a in {**entry.data, **entry.options}.get("actuators", [])
        }
        if entity in watched:
            state = event.data.get("new_state")
            if (
                entity in self._desired
                and state is not None
                and state.state in ("on", "off")
                and (state.state == "on") != self._desired[entity]
                and entity not in self._last_command
            ):
                now = dt_util.utcnow()
                history = [
                    t for t in self._deviations.get(entity, []) if (now - t).total_seconds() < 300
                ]
                history.append(now)
                self._deviations[entity] = history
                if len(history) >= 2:
                    self._command_faults.add(entity)
                    self._fault_dirty = True
                    _LOGGER.warning(
                        "Repeated actuator deviations; control inhibited until explicit global off and review"
                    )
            self._revision += 1
            self._request_update()

    @callback
    def _tick(self, _now) -> None:
        self._refresh_weather()
        self._request_update()

    @callback
    def _request_update(self) -> None:
        if self._closed:
            return
        self._dirty = True
        if self._pending is None or self._pending.done():
            self._pending = self.hass.async_create_task(self._drain_updates())

    async def _drain_updates(self) -> None:
        # Events received while a service is awaited must not be lost. The next
        # pass revalidates safety before permitting any new opening.
        while self._dirty and not self._closed:
            self._dirty = False
            await self.async_reconcile()

    async def _command(self, entity: str, wanted: bool) -> bool:
        self._desired[entity] = wanted
        if wanted and entity in self._command_faults:
            return False
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
                self._fault_dirty = True
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
            self._fault_dirty = True
            _LOGGER.error("Actuator command failed; no automatic retry loop will be started")
            return False
        state = self.hass.states.get(entity)
        return state is not None and state.state == ("on" if wanted else "off")

    async def _apply(self) -> None:
        revision = self._revision
        now = dt_util.utcnow()
        enabled = self.enabled and self._ready() and self.hass.is_running
        transition = self._transition_until is not None and now < self._transition_until
        if transition:
            enabled = False
        plan: dict[str, bool] = {}
        for key, z in self.zones.items():
            sensor = self.hass.states.get(z.config["sensor"])
            output = [self.hass.states.get(e) for e in z.config["actuators"]]
            available = all(s is not None and s.state in ("on", "off") for s in output) and not any(
                e in self._command_faults for e in z.config["actuators"]
            )
            on = any(s is not None and s.state == "on" for s in output)
            if on != z.actual_on:
                z.switched_at = now
                z.actual_on = on
            window = self.hass.states.get(z.config["window"]) if z.config.get("window") else None
            opened = (
                window_pause(
                    window.state if window else None,
                    window.last_changed if window else None,
                    now,
                    z.config.get("window_open_delay", 0),
                    z.config.get("window_close_delay", 0),
                )
                if z.config.get("window") and z.window_enabled
                else False
            )
            z.decision = z.intelligence.evaluate(
                z, self, now, sensor, indoor_temperature(sensor), on, opened, enabled, available
            )
            if self.enabled and not enabled and self.hass.is_running:
                z.decision = Decision(
                    False,
                    "season_transition" if transition else "setup_not_ready",
                    z.decision.target,
                )
            plan[key] = z.decision.demand
        # First close zones that must not receive water. If that cannot be
        # confirmed at relay level, opening a shared supply is not allowed.
        isolated = True
        closing_wait = False
        for key, z in self.zones.items():
            if not plan[key]:
                for e in z.config["actuators"]:
                    isolated = await self._command(e, False) and isolated
                    state = self.hass.states.get(e)
                    if (
                        state is not None
                        and state.state == "off"
                        and (now - state.last_changed).total_seconds()
                        < z.config.get("valve_travel", 0)
                    ):
                        isolated = False
                        closing_wait = True
        if any(plan.values()) and revision != self._revision:
            self._request_update()
            return
        demand = any(plan.values()) and enabled
        if self.general:
            supply = await self._command(self.general, demand and isolated)
            general_state = self.hass.states.get(self.general)
            elapsed = (now - general_state.last_changed).total_seconds() if general_state else 0
            opening = elapsed >= self.entries.get(self.hub, {}).get("general_travel", 0)
            allowed = demand and isolated and supply and opening
        else:
            allowed = enabled
        for key, z in self.zones.items():
            if plan[key] and allowed and revision != self._revision:
                self._request_update()
                return
            if plan[key] and not allowed:
                reason = (
                    "zone_closing_estimated"
                    if closing_wait
                    else (
                        "general_opening_estimated"
                        if self.general and supply and not opening
                        else "supply_not_ready"
                    )
                )
                z.decision = Decision(False, reason, z.decision.target)
            for e in z.config["actuators"]:
                if plan[key]:
                    await self._command(e, bool(allowed))

    async def async_reconcile(self) -> None:
        async with self._lock:
            await self._apply()
            self._notify()
            if self._fault_dirty or (dt_util.utcnow() - self._checkpoint).total_seconds() >= 900:
                self._checkpoint = dt_util.utcnow()
                await self._save()

    async def _save(self) -> None:
        self._saved.update(
            {
                k: {
                    **z.intent.dump(),
                    "program": z.program.dump(),
                    "window_enabled": z.window_enabled,
                    "intelligence": z.intelligence.dump(),
                }
                for k, z in self.zones.items()
            }
        )
        await self._store.async_save(
            {
                "enabled": self.enabled,
                "supply_mode": self.supply_mode.value,
                "zones": self._saved,
                "command_faults": sorted(self._command_faults),
                "transition_until": self._transition_until.isoformat()
                if self._transition_until
                else None,
            }
        )
        self._fault_dirty = False

    async def async_change(self, change: Callable) -> None:
        async with self._lock:
            change()
            try:
                await self._save()
            except (HomeAssistantError, OSError):
                self.enabled = False
                await self._apply()
                self._notify()
                raise
            await self._apply()
            if self._fault_dirty:
                await self._save()
            self._refresh_weather()
            self._notify()

    async def async_enable(self, value: bool) -> None:
        def update():
            self.enabled = value
            if not value:
                # Explicit global off authorises a fresh bounded close attempt.
                self._command_faults.clear()
                self._last_command.clear()
                self._deviations.clear()

        await self.async_change(update)

    def validate_feature(self, z, key, value):
        if (
            key in ("weather", "outside")
            and value
            and not self.source(z, "weather" if key == "weather" else "outdoor")
        ):
            raise ValueError("Choose the corresponding optional source in Settings first")
        if key == "solar" and value == "active" and not z.config.get("solar_confirmed", False):
            raise ValueError(
                "Observe and confirm window exposure thresholds before enabling solar control"
            )
        if key == "anticipation" and value and not z.program.blocks:
            raise ValueError("Configure a weekly schedule before enabling anticipation")

    async def async_feature(self, zone_id, key, value):
        z = self.zones[zone_id]
        candidate = z.intelligence.features.restore(
            {**z.intelligence.dump()["features"], key: value}
        )
        self.validate_feature(z, key, value)
        await self.async_change(lambda: setattr(z.intelligence, "features", candidate))

    async def async_away(self, zone_id, enabled, until=None):
        def update():
            z = self.zones[zone_id]
            z.program.away, z.program.away_until = enabled, until if enabled else None
            if enabled:
                z.intent.resume()

        await self.async_change(update)

    async def async_resume(self, zone_id):
        z = self.zones[zone_id]
        if not z.program.away and z.program.blocks:
            await self.async_schedule(zone_id, True)
        else:
            await self.async_change(z.intent.resume)

    async def async_schedule(self, zone_id: str, enabled: bool) -> None:
        z = self.zones[zone_id]

        def update():
            now = dt_util.utcnow()
            current = z.program.target(z.intent, now, self.hass.config.time_zone)
            mode = z.intent.last_mode if z.intent.mode == Mode.OFF else z.intent.mode
            profile = (
                z.program.active(now, self.hass.config.time_zone)
                if z.program.enabled
                else z.program.selected
            )
            underlying = (
                z.program.profiles[mode.value][profile] if profile else z.intent.targets[mode]
            )
            if enabled and not z.program.blocks:
                raise ValueError("Configure at least one weekly block before enabling the schedule")
            z.program.enabled = enabled
            z.program.selected = None
            if z.program.away:
                if not enabled:
                    z.intent.targets[mode] = underlying
                return
            z.intent.resume()
            if not enabled:
                z.program.set_manual(z.intent, z.settings, current, now, self.hass.config.time_zone)

        await self.async_change(update)

    async def async_edit_schedule(self, zone_id: str, edit: Callable) -> None:
        def update():
            z = self.zones[zone_id]
            now = dt_util.utcnow()
            z.program.target(z.intent, now, self.hass.config.time_zone)
            edit(z.program)
            z.program.reconcile_edit(z.intent, now, self.hass.config.time_zone)

        await self.async_change(update)

    async def async_supply(self, value: str) -> None:
        mode = Mode(value)
        if mode == Mode.OFF:
            raise ValueError("Supply mode must be heating or cooling")
        if mode == self.supply_mode:
            return

        def update():
            self.supply_mode = mode
            delay = max(
                [
                    self.entries.get(self.hub, {}).get("general_travel", 0),
                    *[
                        max(z.settings.minimum_off, z.config.get("valve_travel", 0))
                        for z in self.zones.values()
                    ],
                ]
            )
            self._transition_until = dt_util.utcnow() + timedelta(seconds=delay)
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
        self._unsub_start()
        if self._pending and not self._pending.done():
            self._pending.cancel()
        if self._weather_task and not self._weather_task.done():
            self._weather_task.cancel()

    async def _shutdown(self, _event) -> None:
        # Best-effort graceful shutdown only. A power loss or process kill
        # cannot deliver commands; do not claim a hardware fail-safe.
        self.async_stop()
        async with self._lock:
            try:
                await self._save()
            finally:
                await self._apply()
