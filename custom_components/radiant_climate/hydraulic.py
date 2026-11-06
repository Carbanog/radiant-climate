"""Optional, isolated observer. Never sends services or mutates control state."""

from datetime import timedelta
from time import monotonic

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .core.control import temperature
from .core.hydraulic import HydraulicObserver
from .environment import fresh

DEFAULTS = {
    "hydraulic_enabled": False,
    "hydraulic_supply": None,
    "hydraulic_return": None,
    "hydraulic_stale": 900,
    "hydraulic_settle": 30,
    "hydraulic_duration": 30,
    "hydraulic_heat_min": None,
    "hydraulic_cool_max": None,
}


def configuration(entry):
    return {k: {**entry.data, **entry.options}.get(k, v) for k, v in DEFAULTS.items()}


def reading(hass, entity, now, maximum):
    state = hass.states.get(entity) if entity else None
    return state_reading(state, now, maximum)


def state_reading(state, now, maximum):
    if not fresh(state, now, maximum):
        return None
    unit = state.attributes.get("unit_of_measurement")
    if unit not in ("°C", "°F", "K"):
        return None
    try:
        return temperature(TemperatureConverter.convert(float(state.state), unit, "°C"), 0, 90)
    except (ValueError, TypeError, OverflowError):
        return None


class HydraulicDiagnostic:
    def __init__(self, manager, entry):
        self.manager, self.entry = manager, entry
        self.observer = HydraulicObserver()
        self.state = "disabled"
        self.attributes = {}

    @callback
    def update(self, _event=None):
        manager, hass = self.manager, self.manager.hass
        cfg = configuration(self.entry)
        now = dt_util.utcnow()
        supply = reading(hass, cfg["hydraulic_supply"], now, cfg["hydraulic_stale"])
        returning = reading(hass, cfg["hydraulic_return"], now, cfg["hydraulic_stale"])
        if _event is not None:
            # Do not lose an intervening invalid or recovered sample when HA
            # dispatches several state events after the source has changed again.
            value = state_reading(_event.data.get("new_state"), now, cfg["hydraulic_stale"])
            if _event.data["entity_id"] == cfg["hydraulic_supply"]:
                supply = value
            elif _event.data["entity_id"] == cfg["hydraulic_return"]:
                returning = value
        active = tuple(
            sorted(
                key
                for key, zone in manager.zones.items()
                if manager.enabled and zone.decision and zone.decision.demand
            )
        )
        outputs = {a for key in active for a in manager.zones[key].config["actuators"]}
        if manager.general:
            outputs.add(manager.general)
        ready = all((s := hass.states.get(a)) is not None and s.state == "on" for a in outputs)
        ready &= not bool(manager._retired or manager._command_faults or manager._stop_requested)
        mode = manager.supply_mode.value
        self.state = self.observer.evaluate(
            now=monotonic(),
            enabled=cfg["hydraulic_enabled"],
            supply=supply,
            returning=returning,
            active=active,
            relays_ready=ready,
            mode=mode,
            config=(tuple(cfg.items()), tuple(sorted(outputs))),
            settle=max(
                cfg["hydraulic_settle"] * 60,
                manager.entries.get(manager.hub, {}).get("general_travel", 0),
                *(manager.zones[key].config.get("valve_travel", 0) for key in active),
            ),
            duration=cfg["hydraulic_duration"] * 60,
            reference=cfg["hydraulic_heat_min" if mode == "heat" else "hydraulic_cool_max"],
        )
        self.attributes = {
            "supply_celsius": supply,
            "return_celsius": returning,
            "delta_celsius": round(supply - returning, 2)
            if supply is not None and returning is not None
            else None,
            "declared_season": mode,
            "demanding_zones": len(active),
            "relay_states_reported_on": bool(active) and ready,
            "flow_measured": False,
            "valve_position_measured": False,
            "reference_celsius": cfg[
                "hydraulic_heat_min" if mode == "heat" else "hydraulic_cool_max"
            ],
        }

    def subscribe(self, notify):
        active = True

        @callback
        def update(event=None):
            if not active:
                return
            self.update()
            notify()

        @callback
        def schedule():
            # A diagnostic callback must not execute in the control transaction.
            self.manager.hass.loop.call_soon(update)

        @callback
        def stop():
            nonlocal active
            active = False

        @callback
        def source_changed(event):
            cfg = configuration(self.entry)
            if event.data["entity_id"] in (cfg["hydraulic_supply"], cfg["hydraulic_return"]):
                self.update(event)
                notify()

        self.update()
        return [
            stop,
            self.manager.async_subscribe(schedule),
            self.entry.add_update_listener(lambda *_: self._options_update(update)),
            self.manager.hass.bus.async_listen(EVENT_STATE_CHANGED, source_changed),
            async_track_time_interval(self.manager.hass, update, timedelta(seconds=15)),
        ]

    async def _options_update(self, update):
        update()
