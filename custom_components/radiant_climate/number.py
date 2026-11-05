"""Native editable profile values: the stored program is the only source."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN
from .core.control import temperature
from .core.program import PROFILES
from .entity import RadiantEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "zone":
        manager = hass.data[DOMAIN]
        async_add_entities(
            [
                HoldMinutes(manager, entry),
                *[
                    ProfileTemperature(manager, entry, m.value, p)
                    for m in manager.zones[entry.entry_id].settings.modes
                    for p in PROFILES
                ],
            ]
        )


class ProfileTemperature(RadiantEntity, NumberEntity):
    _attr_native_min_value = 5
    _attr_native_max_value = 40
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX

    def __init__(self, manager, entry, mode, profile):
        super().__init__(manager, entry, f"{mode}_{profile}")
        self.mode, self.profile = mode, profile
        self._attr_translation_key = f"{mode}_{profile}"

    @property
    def native_value(self):
        return self.manager.zones[self.entry.entry_id].program.profiles[self.mode][self.profile]

    async def async_set_native_value(self, value):
        target = temperature(value)

        def update():
            self.manager.zones[self.entry.entry_id].program.profiles[self.mode][self.profile] = (
                target
            )

        await self.manager.async_change(update)


class HoldMinutes(RadiantEntity, NumberEntity):
    _attr_translation_key = "hold_minutes"
    _attr_native_min_value = 1
    _attr_native_max_value = 1440
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "hold_minutes")

    @property
    def native_value(self):
        return self.manager.zones[self.entry.entry_id].program.minutes

    async def async_set_native_value(self, value):
        minutes = float(value)
        if not 1 <= minutes <= 1440:
            raise ValueError("Manual duration must be between 1 and 1440 minutes")
        await self.manager.async_change(
            lambda: setattr(self.manager.zones[self.entry.entry_id].program, "minutes", minutes)
        )
