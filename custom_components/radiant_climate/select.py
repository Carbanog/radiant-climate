"""Declared supply season, not a measurement of water temperature or flow."""

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .core.control import HoldPolicy
from .entity import RadiantEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "installation":
        async_add_entities([SupplyMode(hass.data[DOMAIN], entry)])
    else:
        async_add_entities([ManualPolicy(hass.data[DOMAIN], entry)])


class ManualPolicy(RadiantEntity, SelectEntity):
    _attr_translation_key = "manual_policy"
    _attr_options = [p.value for p in HoldPolicy]

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "manual_policy")

    @property
    def current_option(self):
        return self.manager.zones[self.entry.entry_id].program.policy.value

    async def async_select_option(self, option):
        policy = HoldPolicy(option)
        await self.manager.async_change(
            lambda: setattr(self.manager.zones[self.entry.entry_id].program, "policy", policy)
        )


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
