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


def configured(entry):
    cfg = configuration(entry)
    return cfg["hydraulic_enabled"] or bool(cfg["hydraulic_supply"] and cfg["hydraulic_return"])


def reading(hass, entity, now, maximum):
    state = hass.states.get(entity) if entity else None
    return state_reading(state, now, maximum)


def state_reading(state, now, maximum):
    return describe_reading(state, now, maximum)[0]


def describe_reading(state, now, maximum):
    detail = {"status": "missing", "last_reported": None}
    if state is None:
        return None, detail
    age = (now - state.last_reported).total_seconds()
    detail["last_reported"] = state.last_reported.isoformat()
    if state.state in ("unknown", "unavailable"):
        return None, {**detail, "status": state.state}
    if age < -60 or (maximum is not None and age > maximum):
        return None, {**detail, "status": "future_timestamp" if age < -60 else "stale"}
    unit = state.attributes.get("unit_of_measurement")
    if unit not in ("°C", "°F", "K"):
        return None, {**detail, "status": "invalid_unit"}
    try:
        value = temperature(TemperatureConverter.convert(float(state.state), unit, "°C"), 0, 90)
    except (ValueError, TypeError, OverflowError):
        return None, {**detail, "status": "invalid_value"}
    return value, {**detail, "status": "valid"}


class HydraulicDiagnostic:
    def __init__(self, manager, entry):
        self.manager, self.entry = manager, entry
        self.observer = HydraulicObserver()
        self.state = "disabled"
        self.attributes = {}
        self._last_valid = {}

    @callback
    def update(self, _event=None):
        manager, hass = self.manager, self.manager.hass
        cfg = configuration(self.entry)
        now = dt_util.utcnow()
        maximum = cfg["hydraulic_stale"]
        readings = []
        ages = []
        values = []
        for key in ("hydraulic_supply", "hydraulic_return"):
            entity = cfg[key]
            state = hass.states.get(entity or "")
            if _event is not None and _event.data["entity_id"] == entity:
                # Preserve intervening unavailable events even if already recovered.
                state = _event.data.get("new_state")
            value, detail = describe_reading(state, now, None)
            previous = self._last_valid.get(key)
            if previous and previous[0] != entity:
                self._last_valid.pop(key)
            if value is not None:
                self._last_valid[key] = (entity, value, detail["last_reported"])
                ages.append(max(0, (now - state.last_reported).total_seconds()))
            saved = self._last_valid.get(key)
            detail["last_valid_report"] = saved[2] if saved else None
            readings.append(detail)
            values.append(value)
        supply, returning = values
        supply_detail, return_detail = readings
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
        if _event is not None and _event.data["entity_id"] in outputs:
            state = _event.data.get("new_state")
            ready &= state is not None and state.state == "on"
        ready &= not bool(
            manager.retired_actuators or manager.actuator_faults or manager.stop_requested
        )
        mode = manager.supply_mode.value
        observed = monotonic()
        self.state = self.observer.evaluate(
            now=observed,
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
            report_at=observed - max(ages) if len(ages) == 2 and max(ages) <= maximum else None,
        )
        shown_supply = self._last_valid.get("hydraulic_supply", (None, None, None))[1]
        shown_return = self._last_valid.get("hydraulic_return", (None, None, None))[1]
        self.attributes = {
            "supply_celsius": shown_supply,
            "return_celsius": shown_return,
            "supply_reading": supply_detail,
            "return_reading": return_detail,
            "maximum_reading_age_seconds": maximum,
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
            if not active:
                return
            cfg = configuration(self.entry)
            watched = {cfg["hydraulic_supply"], cfg["hydraulic_return"], self.manager.general}
            watched.update(a for z in self.manager.zones.values() for a in z.config["actuators"])
            if event.data["entity_id"] in watched:
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
