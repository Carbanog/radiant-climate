"""One shared solar opportunity; window geometry and comfort remain zone policy."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import RadiantEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "installation":
        async_add_entities(
            [SolarOpportunity(hass.data[DOMAIN], entry), ActuatorProblem(hass.data[DOMAIN], entry)]
        )


class ActuatorProblem(RadiantEntity, BinarySensorEntity):
    _attr_translation_key = "actuator_problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "actuator_problem")

    @property
    def is_on(self):
        return bool(self.manager.actuator_faults or self.manager.retired_actuators)

    @property
    def extra_state_attributes(self):
        return {
            "fault_count": len(self.manager.actuator_faults),
            "retired_count": len(self.manager.retired_actuators),
        }


class SolarOpportunity(RadiantEntity, BinarySensorEntity):
    _attr_translation_key = "solar_opportunity"
    _attr_icon = "mdi:white-balance-sunny"

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "solar_opportunity")

    @property
    def weather(self):
        return (
            self.manager.entries.get(self.manager.hub, {}).get("weather")
            if any(z.intelligence.features.weather for z in self.manager.zones.values())
            else None
        )

    @property
    def available(self):
        return self.manager.environment.opportunity(self.weather, dt_util.utcnow()) is not None

    @property
    def is_on(self):
        return self.manager.environment.opportunity(self.weather, dt_util.utcnow())

    @property
    def extra_state_attributes(self):
        condition, _ = self.manager.environment.weather(self.weather, dt_util.utcnow())
        return {
            "basis": "weather_and_sun" if condition else "sun_only",
            "direct_sun_verified": False,
        }
