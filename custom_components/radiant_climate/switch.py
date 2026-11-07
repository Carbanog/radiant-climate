"""Global enable switch: off is persisted and cannot be bypassed by a zone."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .entity import RadiantEntity
from .hydraulic import configuration, configured


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "installation":
        async_add_entities(
            [InstallationEnabled(hass.data[DOMAIN], entry), HouseholdAway(hass.data[DOMAIN], entry)]
        )
        added = False

        async def discover(*_):
            nonlocal added
            if not added and configured(entry):
                added = True
                async_add_entities([HydraulicEnabled(hass.data[DOMAIN], entry)])

        entry.async_on_unload(entry.add_update_listener(discover))
        await discover()
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


class HydraulicEnabled(RadiantEntity, SwitchEntity):
    _attr_translation_key = "hydraulic_enabled"
    _attr_icon = "mdi:pipe"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "hydraulic_enabled")

    async def async_added_to_hass(self):
        await SwitchEntity.async_added_to_hass(self)

        async def changed(*_):
            self.async_write_ha_state()

        self.async_on_remove(self.entry.add_update_listener(changed))

    @property
    def is_on(self):
        return configuration(self.entry)["hydraulic_enabled"]

    @property
    def available(self):
        cfg = configuration(self.entry)
        return bool(
            cfg["hydraulic_supply"]
            and cfg["hydraulic_return"]
            and cfg["hydraulic_supply"] != cfg["hydraulic_return"]
        )

    async def async_turn_on(self, **kwargs):
        if not self.available:
            raise ServiceValidationError("Configure distinct supply and return sensors first")
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, "hydraulic_enabled": True}
        )

    async def async_turn_off(self, **kwargs):
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, "hydraulic_enabled": False}
        )


class HouseholdAway(RadiantEntity, SwitchEntity):
    _attr_translation_key = "household_away"
    _attr_icon = "mdi:bag-suitcase"

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "household_away")

    @property
    def available(self):
        return bool(self.manager.zones) and self.manager.setup_ready

    @property
    def is_on(self):
        # Like a switch group, any active member keeps the shared off action
        # available, even after a room has been taken out of Away individually.
        return any(z.program.away for z in self.manager.zones.values())

    @property
    def extra_state_attributes(self):
        zones = list(self.manager.zones.values())
        active = [z for z in zones if z.program.away]
        returns = {z.program.away_until for z in active}
        until = next(iter(returns)) if len(returns) == 1 else None
        return {
            "zones": len(zones),
            "away_zones": len(active),
            "partially_active": 0 < len(active) < len(zones),
            "mixed_return_times": len(returns) > 1,
            "return_at": until.isoformat() if until else None,
        }

    async def async_turn_on(self, **kwargs):
        await self.manager.async_away_all(True)

    async def async_turn_off(self, **kwargs):
        await self.manager.async_away_all(False)


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

    @property
    def extra_state_attributes(self):
        return {
            "retired_actuators": list(self.manager.retired_actuators),
            "command_faults": list(self.manager.actuator_faults),
            "stop_requested": self.manager.stop_requested,
        }

    async def async_turn_on(self, **kwargs):
        await self.manager.async_enable(True)

    async def async_turn_off(self, **kwargs):
        await self.manager.async_enable(False)
