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
        return bool(
            self.manager.actuator_faults
            or self.manager.retired_actuators
            or self.manager.unavailable_actuators
            or self.manager.pending_isolation
        )

    @property
    def extra_state_attributes(self):
        manager = self.manager
        unavailable = manager.unavailable_actuators
        incidents = manager.actuator_incidents
        pending = manager.pending_isolation
        affected = (
            set(unavailable) | incidents.keys() | set(manager.retired_actuators) | set(pending)
        )
        return {
            "fault_count": len(incidents),
            "retired_count": len(manager.retired_actuators),
            "unavailable_actuators": list(unavailable),
            "pending_isolation": list(pending),
            "affected_actuators": sorted(affected),
            "shared_supply_blocked": bool(
                manager.enabled
                and manager.general
                and (
                    manager.retired_actuators
                    or unavailable
                    or pending
                    or manager.general in incidents
                    or any(
                        item["recovery"] == "automatic" and not item["close_verified"]
                        for item in incidents.values()
                    )
                )
            ),
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
        zones = tuple(self.manager.zones.values())
        return {
            "basis": "weather_and_sun" if condition else "sun_only",
            "direct_sun_verified": False,
            "zones_observing": sum(z.intelligence.features.solar == "observe" for z in zones),
            "zones_optimising": sum(z.intelligence.features.solar == "active" for z in zones),
            "zones_paused_by_solar": sum(
                z.decision is not None
                and z.decision.reason in ("solar_pause", "solar_anticipation")
                for z in zones
            ),
        }
