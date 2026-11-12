"""Explicitly resume the program without enabling a stopped thermostat."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .core.intelligence import ThermalModel
from .entity import RadiantEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "zone":
        async_add_entities(
            [ResumeSchedule(hass.data[DOMAIN], entry), ResetLearning(hass.data[DOMAIN], entry)]
        )

    else:
        async_add_entities([CheckActuators(hass.data[DOMAIN], entry)])


class CheckActuators(RadiantEntity, ButtonEntity):
    _attr_translation_key = "check_actuators"
    _attr_icon = "mdi:refresh"

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "check_actuators")

    async def async_press(self):
        if (
            self.manager.actuator_faults
            or self.manager.retired_actuators
            or self.manager.unavailable_actuators
            or self.manager.pending_isolation
        ):
            await self.manager.async_reconcile()


class ResetLearning(RadiantEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "reset_learning"
    _attr_icon = "mdi:brain"

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "reset_learning")

    async def async_press(self):
        await self.manager.async_change(
            lambda: setattr(
                self.manager.zones[self.entry.entry_id].intelligence, "model", ThermalModel()
            )
        )


class ResumeSchedule(RadiantEntity, ButtonEntity):
    _attr_translation_key = "resume"
    _attr_icon = "mdi:calendar-refresh"

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "resume")

    async def async_press(self):
        await self.manager.async_resume(self.entry.entry_id)
