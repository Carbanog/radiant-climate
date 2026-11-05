"""Human-facing reason for each zone's current control decision."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import RadiantEntity

REASONS = [
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
