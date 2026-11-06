"""Human-facing reason for each zone's current control decision."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .core.hydraulic import STATES
from .entity import RadiantEntity
from .hydraulic import HydraulicDiagnostic, configured

REASONS = [
    "retired_actuator_pending",
    "zone_closing_estimated",
    "general_opening_estimated",
    "solar_pause",
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
    "temperature_missing",
    "temperature_stale",
    "minimum_cycle",
    "clock_changed",
    "demand",
    "satisfied",
    "supply_not_ready",
]


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "zone":
        async_add_entities([ControlReason(hass.data[DOMAIN], entry)])
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
