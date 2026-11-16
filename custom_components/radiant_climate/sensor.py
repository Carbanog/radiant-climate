"""Human-facing reason for each zone's current control decision."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .core.control import Mode
from .core.hydraulic import STATES
from .entity import RadiantEntity
from .hydraulic import HydraulicDiagnostic, configured

REASONS = [
    "retired_actuator_pending",
    "zone_closing_estimated",
    "general_opening_estimated",
    "solar_pause",
    "solar_anticipation",
    "predictive_pause",
    "anticipation",
    "setup_not_ready",
    "season_transition",
    "not_ready",
    "global_off",
    "zone_off",
    "unsupported_mode",
    "supply_mode_mismatch",
    "actuator_unavailable",
    "window_open",
    "window_unavailable",
    "temperature_invalid",
    "minimum_cycle",
    "clock_changed",
    "demand",
    "satisfied",
    "supply_not_ready",
]


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "zone":
        manager = hass.data[DOMAIN]
        async_add_entities([ControlReason(manager, entry), LearningStatus(manager, entry)])
    else:
        added = False

        async def discover(*_):
            nonlocal added
            if not added and configured(entry):
                added = True
                async_add_entities([HydraulicStatus(hass.data[DOMAIN], entry)])

        entry.async_on_unload(entry.add_update_listener(discover))
        await discover()


class HydraulicStatus(RadiantEntity, SensorEntity):
    _attr_translation_key = "hydraulic"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = STATES

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "hydraulic")
        self.diagnostic = HydraulicDiagnostic(manager, entry)

    async def async_added_to_hass(self):
        # Deliberately uses its own observer; there is no actuator/control update.
        await SensorEntity.async_added_to_hass(self)
        for unsubscribe in self.diagnostic.subscribe(self.async_write_ha_state):
            self.async_on_remove(unsubscribe)

    @property
    def native_value(self):
        return self.diagnostic.state

    @property
    def extra_state_attributes(self):
        return self.diagnostic.attributes


class ControlReason(RadiantEntity, SensorEntity):
    _attr_translation_key = "reason"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = REASONS

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "reason")

    @property
    def native_value(self):
        zone = self.manager.zones[self.entry.entry_id]
        return zone.decision.reason if zone.decision else "not_ready"


class LearningStatus(RadiantEntity, SensorEntity):
    _attr_translation_key = "learning_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = [
        "disabled",
        "waiting_circuit",
        "waiting_reading",
        "paused",
        "solar_excluded",
        "provisional",
        "ready",
    ]

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "learning_status")

    @property
    def native_value(self):
        zone = self.manager.zones[self.entry.entry_id]
        learning = zone.intelligence
        if learning.model.response(zone.intent.last_mode).ready:
            return "ready"
        if not learning.features.learning:
            return "disabled"
        if learning.diagnostics.get("learning_solar_exclusion"):
            return "solar_excluded"
        if not learning.diagnostics.get("learning_collecting"):
            return "paused"
        if not learning.diagnostics.get("learning_circuit_active"):
            return "waiting_circuit"
        if learning.model.sparse.get(zone.intent.last_mode.value):
            return "provisional"
        return "waiting_reading"

    @property
    def extra_state_attributes(self):
        zone = self.manager.zones[self.entry.entry_id]
        learning = zone.intelligence
        mode = zone.intent.last_mode
        response = learning.model.response(mode)
        sparse = learning.model.sparse.get(mode.value)
        return {
            "model_mode": zone.intent.last_mode.value,
            "learning_enabled": learning.features.learning,
            "collecting": learning.diagnostics.get("learning_collecting", False),
            "regulation_reason": zone.decision.reason if zone.decision else "not_ready",
            "solar_exclusion": learning.diagnostics.get("learning_solar_exclusion", False),
            "rejected_intervals": learning.model.rejected,
            "circuit_active_hours": round(learning.circuit_seconds.get(mode.value, 0) / 3600, 2),
            "valid_learning_hours": round(response.hours, 2),
            "learning_confidence": "ready"
            if response.ready
            else "provisional"
            if sparse or response.count
            else "insufficient",
            "provisional_hours": round(sparse.hours, 2) if sparse else 0,
            "provisional_comparisons": sparse.count if sparse else 0,
            "provisional_rate_c_per_hour": round(sparse.rate, 3) if sparse else None,
            "heating": learning.model.response(Mode.HEAT).summary(),
            "cooling": learning.model.response(Mode.COOL).summary(),
        }
