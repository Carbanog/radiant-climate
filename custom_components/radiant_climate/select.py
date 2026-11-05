"""Declared supply season, not a measurement of water temperature or flow."""

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import RadiantEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "installation":
        async_add_entities([SupplyMode(hass.data[DOMAIN], entry)])


class SupplyMode(RadiantEntity, SelectEntity):
    _attr_translation_key = "supply_mode"
    _attr_options = ["heat", "cool"]
    _attr_icon = "mdi:sun-snowflake"

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "supply_mode")

    @property
    def current_option(self):
        return self.manager.supply_mode.value

    async def async_select_option(self, option):
        await self.manager.async_supply(option)
