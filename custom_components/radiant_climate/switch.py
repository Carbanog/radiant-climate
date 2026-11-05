"""Global enable switch: off is persisted and cannot be bypassed by a zone."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import RadiantEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "installation":
        async_add_entities([InstallationEnabled(hass.data[DOMAIN], entry)])
    else:
        manager = hass.data[DOMAIN]
        entities = [
            ScheduleEnabled(manager, entry),
            AwayEnabled(manager, entry),
            *[
                ModuleEnabled(manager, entry, key)
                for key in ("weather", "outside", "learning", "anticipation", "predictive")
            ],
        ]
        if manager.zones[entry.entry_id].config.get("window"):
            entities.append(WindowEnabled(manager, entry))
        async_add_entities(entities)


class ModuleEnabled(RadiantEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager, entry, key):
        super().__init__(manager, entry, key)
        self.key = key
        self._attr_translation_key = key

    @property
    def is_on(self):
        return getattr(self.manager.zones[self.entry.entry_id].intelligence.features, self.key)

    @property
    def extra_state_attributes(self):
        z = self.manager.zones[self.entry.entry_id]
        if self.key in ("anticipation", "predictive"):
            return {"model_ready": z.intelligence.model.response(z.intent.last_mode).ready}
        return {}

    async def async_turn_on(self, **kwargs):
        await self.manager.async_feature(self.entry.entry_id, self.key, True)

    async def async_turn_off(self, **kwargs):
        await self.manager.async_feature(self.entry.entry_id, self.key, False)


class AwayEnabled(RadiantEntity, SwitchEntity):
    _attr_translation_key = "away"
    _attr_icon = "mdi:bag-suitcase"

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "away")

    @property
    def is_on(self):
        return self.manager.zones[self.entry.entry_id].program.away

    @property
    def extra_state_attributes(self):
        until = self.manager.zones[self.entry.entry_id].program.away_until
        return {"return_at": until.isoformat() if until else None}

    async def async_turn_on(self, **kwargs):
        await self.manager.async_away(self.entry.entry_id, True)

    async def async_turn_off(self, **kwargs):
        await self.manager.async_away(self.entry.entry_id, False)


class WindowEnabled(RadiantEntity, SwitchEntity):
    _attr_translation_key = "window_enabled"
    _attr_icon = "mdi:window-open-variant"

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "window_enabled")

    @property
    def is_on(self):
        return self.manager.zones[self.entry.entry_id].window_enabled

    async def async_turn_on(self, **kwargs):
        await self.manager.async_change(
            lambda: setattr(self.manager.zones[self.entry.entry_id], "window_enabled", True)
        )

    async def async_turn_off(self, **kwargs):
        await self.manager.async_change(
            lambda: setattr(self.manager.zones[self.entry.entry_id], "window_enabled", False)
        )


class ScheduleEnabled(RadiantEntity, SwitchEntity):
    _attr_translation_key = "schedule"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "schedule")

    @property
    def is_on(self):
        return self.manager.zones[self.entry.entry_id].program.enabled

    async def async_turn_on(self, **kwargs):
        await self.manager.async_schedule(self.entry.entry_id, True)

    async def async_turn_off(self, **kwargs):
        await self.manager.async_schedule(self.entry.entry_id, False)


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
