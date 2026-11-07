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
from .core.intelligence import ThermalModel, window_pause
from .core.program import Program, ScheduleInUseError
from .environment import Environment
from .intelligence import Intelligence
from .solar import confirmed

_LOGGER = logging.getLogger(__name__)
COMMAND_TIMEOUT = 5


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
        self._change_signal = asyncio.Event()
        self._last_command: dict[str, tuple[bool, object]] = {}
        self._command_faults: set[str] = set()
        self._close_recovery: dict[str, tuple[int, object]] = {}
        self._retired: dict[str, float] = {}
        self._hardware_pending: dict[str, set[str]] = {}
        self._stop_requested = False
        self._change_requested = 0
        self._change_applied = 0
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
            retired = raw.get("retired_actuators", {})
            recovery_states = raw.get("close_recovery", {})
            if not isinstance(retired, dict) or not isinstance(recovery_states, dict):
                raise ValueError("Invalid actuator recovery state")
            for entity, travel in retired.items():
                if (
                    not isinstance(entity, str)
                    or type(travel) not in (int, float)
                    or not 0 <= travel <= 900
                ):
                    raise ValueError("Invalid retired actuator")
                self._retired[entity] = float(travel)
            for entity, recovery in recovery_states.items():
                if not isinstance(recovery, dict):
                    raise ValueError("Invalid close recovery state")
                count = recovery["attempts"]
                when = dt_util.parse_datetime(recovery["last_attempt"])
                if (
                    not isinstance(entity, str)
                    or type(count) is not int
                    or not 0 <= count <= 2
                    or when is None
                    or when.tzinfo is None
                ):
                    raise ValueError("Invalid close recovery state")
                self._close_recovery[entity] = (count, when)
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
        async with self._lock:
            self._register(entry)
            await self._apply()
            self._notify()

    def _register(self, entry: ConfigEntry) -> None:
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
                    if (
                        self._saved[entry.entry_id].get("learning_sensor", data["sensor"])
                        != data["sensor"]
                    ):
                        self.zones[entry.entry_id].intelligence.model = ThermalModel()
                except (KeyError, TypeError, ValueError):
                    # Optional learning corruption must not destroy user setpoints.
                    self.zones[entry.entry_id].intelligence = Intelligence()
            raw_window = self._saved.get(entry.entry_id, {}).get("window_enabled", True)
            self.zones[entry.entry_id].window_enabled = (
                raw_window if isinstance(raw_window, bool) else True
            )
        self.entries[entry.entry_id] = data
        self._normalise_solar_confirmations()
        self._refresh_weather()

    def _normalise_solar_confirmations(self):
        # Entries can load in either order. Wait for the actual hub sources
        # rather than comparing a restored zone against temporary defaults.
        if self.hub not in self.entries:
            return
        source = self.entries[self.hub]
        for zone in self.zones.values():
            if zone.intelligence.features.solar == "active" and not confirmed(zone.config, source):
                zone.intelligence.features.solar = "observe"

    async def async_remove(self, entry_id: str) -> None:
        self._change_signal.set()
        self._change_signal = asyncio.Event()
        self._revision += 1
        async with self._lock:
            zone = self.zones.get(entry_id)
            if zone:
                self._saved[entry_id] = {
                    **zone.intent.dump(),
                    "program": zone.program.dump(),
                    "window_enabled": zone.window_enabled,
                    "intelligence": zone.intelligence.dump(),
                    "learning_sensor": zone.config["sensor"],
                }
                for entity in zone.config["actuators"]:
                    self._retired[entity] = max(
                        self._retired.get(entity, 0), zone.config.get("valve_travel", 0)
                    )
            if self.hub == entry_id:
                if self.general:
                    self._retired[self.general] = max(
                        self._retired.get(self.general, 0),
                        self.entries[self.hub].get("general_closing", 0),
                    )
                self.enabled = False
            # Write-ahead record: a stop/cancellation during the first close must
            # not lose ownership of an output no longer present in config entries.
            await self._save()
            self.zones.pop(entry_id, None)
            if zone:
                for entity in zone.config["actuators"]:
                    await self._command(entity, False)
            if self.hub == entry_id:
                await self._apply()
                self.hub = None
            self.entries.pop(entry_id, None)
            self._hardware_pending.pop(entry_id, None)
            await self._apply()
            await self._save()
            self._notify()

    async def async_prepare_hardware(self, entry_id: str, data: dict) -> None:
        """Journal removed outputs before HA commits their replacement options."""
        old = self.entries[entry_id]
        before = set(old.get("actuators", [])) | ({old["general"]} if old.get("general") else set())
        after = set(data.get("actuators", [])) | (
            {data["general"]} if data.get("general") else set()
        )
        removed = before - after
        if not removed:
            if old.get("sensor") != data.get("sensor"):
                # Stamp the previous model's sensor before options are committed,
                # including the first reconfiguration after upgrading old storage.
                await self.async_change(lambda: None)
            return

        def update():
            travel = (
                old.get("general_closing", 0)
                if old["kind"] == "installation"
                else old.get("valve_travel", 0)
            )
            for entity in removed:
                self._retired[entity] = max(self._retired.get(entity, 0), travel)
            # Until options are committed and the old entry is unloaded, its
            # outputs must not be released and reopened under the old config.
            self._hardware_pending[entry_id] = removed

        await self.async_change(update)

    async def async_update_options(self, entry: ConfigEntry) -> bool:
        """Apply logical options without unloading entities or retiring outputs."""
        data = {**entry.data, **entry.options}
        old = self.entries.get(entry.entry_id)
        hardware = ("kind", "sensor", "actuators", "modes", "window", "general")
        if old is None or any(old.get(key) != data.get(key) for key in hardware):
            return False

        def update():
            self.entries[entry.entry_id] = data
            if zone := self.zones.get(entry.entry_id):
                zone.config = data
                zone.settings = Settings(
                    modes=tuple(Mode(m) for m in data["modes"]),
                    **{
                        k: data[k]
                        for k in ("hysteresis", "minimum_on", "minimum_off", "stale_after")
                        if k in data
                    },
                )
            self._normalise_solar_confirmations()

        await self.async_change(update)
        return True

    @property
    def general(self) -> str | None:
        return self.entries.get(self.hub, {}).get("general")

    @property
    def actuator_faults(self) -> tuple[str, ...]:
        return tuple(sorted(self._command_faults))

    @property
    def retired_actuators(self) -> tuple[str, ...]:
        return tuple(sorted(self._retired))

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested

    @property
    def setup_ready(self) -> bool:
        return self._ready()

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
        state = event.data.get("new_state")
        old = event.data.get("old_state")
        now = dt_util.utcnow()
        changed = (old.state if old else None) != (state.state if state else None)
        for z in self.zones.values():
            model = z.intelligence.model
            # Preserve interruptions synchronously, including two opposite
            # events received before the asynchronous reconciliation runs.
            if entity == z.config["sensor"] and indoor_temperature(state) is None:
                model.reset_period(now)
            elif changed and entity == z.config.get("window") and z.window_enabled:
                model.reset_period(now)
            elif changed and (entity == self.general or entity in z.config["actuators"]):
                model.interrupt_training(now)
        unsafe = any(
            z.decision is not None
            and z.decision.demand
            and (
                (entity == z.config["sensor"] and indoor_temperature(state) is None)
                or (
                    entity == z.config.get("window")
                    and z.window_enabled
                    and window_pause(
                        state.state if state else None,
                        state.last_changed if state else None,
                        now,
                        z.config.get("window_open_delay", 0),
                        z.config.get("window_close_delay", 0),
                    )
                    is not False
                )
            )
            for z in self.zones.values()
        )
        # Valid samples still invalidate the plan below, but do not cancel an
        # in-flight acknowledgment. Re-evaluate before any additional opening.
        # Only unsafe feedback for a demanded zone interrupts the shared plan.
        if unsafe:
            self._change_signal.set()
            self._change_signal = asyncio.Event()
        watched = {self.general, *self.environment.sun_entities} | {
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
        watched |= self._retired.keys()
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
                        "Repeated actuator deviations; control inhibited until explicit fault review"
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
        if wanted and (
            entity in self._command_faults
            or self._stop_requested
            or self._change_requested != self._change_applied
        ):
            return False
        state = self.hass.states.get(entity)
        if state is None or state.state not in ("on", "off"):
            return False
        if (state.state == "on") == wanted:
            self._last_command.pop(entity, None)
            return True
        now = dt_util.utcnow()
        if entity in self._command_faults:
            # Open remains latched. Permit at most two recovery close commands,
            # spaced by 30 seconds; preserve the budget across restarts.
            count, last = self._close_recovery.get(entity, (0, None))
            if count >= 2 or (last is not None and (now - last).total_seconds() < 30):
                return False
            self._close_recovery[entity] = (count + 1, now)
            self._fault_dirty = True
            self._last_command.pop(entity, None)
        previous = self._last_command.get(entity)
        if previous and previous[0] == wanted:
            if (now - previous[1]).total_seconds() > 30:
                self._command_faults.add(entity)
                self._fault_dirty = True
                _LOGGER.error("Actuator did not report the requested state; manual review required")
            return False
        self._last_command[entity] = (wanted, now)
        confirmed = asyncio.Event()
        interrupted = self._change_signal

        @callback
        def reported(event):
            if event.data["entity_id"] == entity:
                current = event.data.get("new_state")
                if (
                    current is None
                    or current.state not in ("on", "off")
                    or current.state == ("on" if wanted else "off")
                ):
                    confirmed.set()

        unsubscribe = (
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, reported) if wanted else lambda: None
        )
        try:
            async with asyncio.timeout(COMMAND_TIMEOUT):
                await self.hass.services.async_call(
                    "switch",
                    "turn_on" if wanted else "turn_off",
                    {"entity_id": entity},
                    blocking=True,
                )
                state = self.hass.states.get(entity)
                if wanted and (state is None or state.state != "on"):
                    # An accepted service is not an acknowledgement. Allow a
                    # short radio delay within the same five-second I/O budget,
                    # while permitting queued user changes to cancel the wait.
                    tasks = [
                        asyncio.create_task(confirmed.wait()),
                        asyncio.create_task(interrupted.wait()),
                    ]
                    try:
                        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    finally:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                    if interrupted.is_set():
                        return False
        except (HomeAssistantError, TimeoutError):
            self._command_faults.add(entity)
            self._fault_dirty = True
            _LOGGER.error("Actuator command failed; opening inhibited and close recovery bounded")
            return False
        finally:
            unsubscribe()
        state = self.hass.states.get(entity)
        return state is not None and state.state == ("on" if wanted else "off")

    async def _abort_open(self, zone: Zone | None = None) -> None:
        """Compensate a failed opening in this pass, without waiting for a tick."""
        self._revision += 1
        if zone:
            zone.decision = Decision(False, "actuator_unavailable", zone.decision.target)
            for entity in zone.config["actuators"]:
                await self._command(entity, False)
        if self.general:
            await self._command(self.general, False)
        self._request_update()

    async def _apply(self) -> None:
        revision = self._revision
        now = dt_util.utcnow()
        # Retired outputs remain owned until they report off and their estimated
        # travel has elapsed. Unavailable is never accepted as physical removal.
        for entity, travel in list(self._retired.items()):
            closed = await self._command(entity, False)
            state = self.hass.states.get(entity)
            pending = any(entity in outputs for outputs in self._hardware_pending.values())
            if (
                not pending
                and closed
                and state
                and (now - state.last_changed).total_seconds() >= travel
            ):
                del self._retired[entity]
                self._fault_dirty = True
        enabled = (
            self.enabled
            and not self._stop_requested
            and not self._retired
            and self._ready()
            and self.hass.is_running
        )
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
                    "retired_actuator_pending"
                    if self._retired
                    else ("season_transition" if transition else "setup_not_ready"),
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
            inlet_healthy = self.general not in self._command_faults
            supply = await self._command(self.general, demand and isolated and inlet_healthy)
            if demand and isolated and inlet_healthy and self.general in self._command_faults:
                await self._abort_open()
                return
            general_state = self.hass.states.get(self.general)
            elapsed = (now - general_state.last_changed).total_seconds() if general_state else 0
            opening = elapsed >= self.entries.get(self.hub, {}).get("general_travel", 0)
            allowed = demand and isolated and inlet_healthy and supply and opening
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
                    if allowed and revision != self._revision:
                        self._request_update()
                        return
                    confirmed = await self._command(e, bool(allowed))
                    if allowed and not confirmed:
                        await self._abort_open(z)
                        return

    async def async_reconcile(self) -> None:
        async with self._lock:
            await self._apply()
            self._notify()
            if self._fault_dirty or (dt_util.utcnow() - self._checkpoint).total_seconds() >= 900:
                self._checkpoint = dt_util.utcnow()
                await self._save()
            if not self.entries and not self._retired:
                self.hass.loop.call_soon(self._dispose_if_unused)

    @callback
    def _dispose_if_unused(self):
        if not self.entries and not self._retired and self.hass.data.get(DOMAIN) is self:
            self.async_stop()
            del self.hass.data[DOMAIN]

    async def _save(self) -> None:
        self._saved.update(
            {
                k: {
                    **z.intent.dump(),
                    "program": z.program.dump(),
                    "window_enabled": z.window_enabled,
                    "intelligence": z.intelligence.dump(),
                    "learning_sensor": z.config["sensor"],
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
                "retired_actuators": dict(self._retired),
                "close_recovery": {
                    entity: {"attempts": count, "last_attempt": when.isoformat()}
                    for entity, (count, when) in self._close_recovery.items()
                },
                "transition_until": self._transition_until.isoformat()
                if self._transition_until
                else None,
            }
        )
        self._fault_dirty = False

    async def async_change(self, change: Callable) -> None:
        self._change_signal.set()
        self._change_signal = asyncio.Event()
        self._revision += 1
        self._change_requested += 1
        ticket = self._change_requested
        async with self._lock:
            self._change_applied = ticket
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
        if not value:
            self._stop_requested = True

        def update():
            self.enabled = value
            self._stop_requested = False

        if value:
            await self.async_change(update)
        else:
            # An accepted Off must finish/persist even if the service caller
            # disconnects while waiting for a lock or a physical command.
            # Eager start registers its queue ticket before another user action.
            task = self.hass.async_create_task(
                self.async_change(update),
                name="Radiant Climate accepted global off",
                eager_start=True,
            )
            await asyncio.shield(task)

    async def async_reset_actuator_faults(self, entities: list[str]) -> None:
        def update():
            if self.enabled:
                raise ValueError("Switch off the installation before reviewing actuator faults")
            selected = set(entities) if entities else set(self._command_faults)
            if not selected <= self._command_faults:
                raise ValueError("Select only actuators with a latched fault")
            for entity in selected:
                state = self.hass.states.get(entity)
                if entity in self._retired or state is None or state.state != "off":
                    raise ValueError(
                        "Resolve retired outputs and confirm reported off before resetting faults"
                    )
            for entity in selected:
                self._command_faults.discard(entity)
                self._last_command.pop(entity, None)
                self._deviations.pop(entity, None)
                self._close_recovery.pop(entity, None)

        await self.async_change(update)

    async def async_acknowledge_retired(self, entity: str) -> None:
        def update():
            if self.enabled:
                raise ValueError(
                    "Switch off the installation before acknowledging physical removal"
                )
            assigned = {
                output
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                for output in [
                    *{**entry.data, **entry.options}.get("actuators", []),
                    {**entry.data, **entry.options}.get("general"),
                ]
            }
            if entity not in self._retired or entity in assigned:
                raise ValueError("Only unassigned pending retired actuators can be acknowledged")
            del self._retired[entity]
            self._command_faults.discard(entity)
            self._last_command.pop(entity, None)
            self._close_recovery.pop(entity, None)
            self._deviations.pop(entity, None)
            self._fault_dirty = True

        await self.async_change(update)

    def validate_feature(self, z, key, value):
        if (
            key in ("weather", "outside")
            and value
            and not self.source(z, "weather" if key == "weather" else "outdoor")
        ):
            raise ValueError("Choose the corresponding optional source in Settings first")
        if (
            key == "solar"
            and value == "active"
            and not confirmed(z.config, self.environment.solar_config)
        ):
            raise ValueError(
                "Observe and confirm window exposure thresholds before enabling solar control"
            )
        if key == "anticipation" and value and not z.program.blocks:
            raise ValueError("Configure a weekly schedule before enabling anticipation")

    async def async_feature(self, zone_id, key, value):
        def update():
            z = self.zones[zone_id]
            candidate = z.intelligence.features.restore(
                {**z.intelligence.dump()["features"], key: value}
            )
            self.validate_feature(z, key, value)
            z.intelligence.features = candidate

        await self.async_change(update)

    async def async_away(self, zone_id, enabled, until=None):
        await self.async_change(lambda: self._set_away(self.zones[zone_id], enabled, until))

    @staticmethod
    def _set_away(zone, enabled, until):
        zone.program.away, zone.program.away_until = enabled, until if enabled else None
        if enabled:
            zone.intent.resume()

    async def async_away_all(self, enabled, until=None):
        # Broadcast one atomic change; each zone keeps its own profiles and off
        # intent. Persist existing zone programs rather than a competing overlay.
        def update():
            for zone in self.zones.values():
                self._set_away(zone, enabled, until)

        await self.async_change(update)

    async def async_resume(self, zone_id):
        def update():
            z = self.zones[zone_id]
            if not z.program.away and z.program.blocks:
                self._set_schedule(z, True)
            else:
                z.intent.resume()

        await self.async_change(update)

    async def async_schedule(self, zone_id: str, enabled: bool) -> None:
        await self.async_change(lambda: self._set_schedule(self.zones[zone_id], enabled))

    def _set_schedule(self, z: Zone, enabled: bool) -> None:
        now = dt_util.utcnow()
        current = z.program.target(z.intent, now, self.hass.config.time_zone)
        mode = z.intent.last_mode if z.intent.mode == Mode.OFF else z.intent.mode
        profile = (
            z.program.active(now, self.hass.config.time_zone)
            if z.program.enabled
            else z.program.selected
        )
        underlying = z.program.profiles[mode.value][profile] if profile else z.intent.targets[mode]
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

    async def async_edit_schedule(self, zone_id: str, edit: Callable) -> None:
        def update():
            z = self.zones[zone_id]
            now = dt_util.utcnow()
            program = Program.restore(z.program.dump())
            intent = Intent.restore(z.intent.dump())
            program.target(intent, now, self.hass.config.time_zone)
            edit(program)
            if program.enabled and not program.blocks:
                raise ScheduleInUseError("Disable the schedule before removing its last block")
            program.reconcile_edit(intent, now, self.hass.config.time_zone)
            z.program, z.intent = program, intent

        await self.async_change(update)

    async def async_supply(self, value: str) -> None:
        mode = Mode(value)
        if mode == Mode.OFF:
            raise ValueError("Supply mode must be heating or cooling")
        if mode == self.supply_mode and self._change_requested == self._change_applied:
            return
        self._stop_requested = True

        def update():
            self._stop_requested = False
            if mode == self.supply_mode:
                return
            self.supply_mode = mode
            delay = max(
                [
                    self.entries.get(self.hub, {}).get("general_travel", 0),
                    self.entries.get(self.hub, {}).get("general_closing", 0),
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
        self._change_signal.set()
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
