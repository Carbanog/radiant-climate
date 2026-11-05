"""Explicitly resume the program without enabling a stopped thermostat."""

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import RadiantEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "zone":
        async_add_entities([ResumeSchedule(hass.data[DOMAIN], entry)])


class ResumeSchedule(RadiantEntity, ButtonEntity):
    _attr_translation_key = "resume"
    _attr_icon = "mdi:calendar-refresh"

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "resume")

    async def async_press(self):
        await self.manager.async_schedule(self.entry.entry_id, True)
