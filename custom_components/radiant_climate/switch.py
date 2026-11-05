"""Global enable switch: off is persisted and cannot be bypassed by a zone."""

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .entity import RadiantEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "installation":
        async_add_entities([InstallationEnabled(hass.data[DOMAIN], entry)])


class InstallationEnabled(RadiantEntity, SwitchEntity):
    _attr_translation_key = "enabled"
    _attr_icon = "mdi:hvac"

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "enabled")

    @property
    def is_on(self):
        return self.manager.enabled

    async def async_turn_on(self, **kwargs):
        await self.manager.async_enable(True)

    async def async_turn_off(self, **kwargs):
        await self.manager.async_enable(False)
