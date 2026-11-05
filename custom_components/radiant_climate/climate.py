"""Native thermostat entity; all hardware writes remain in Installation."""

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .core.control import Mode, temperature
from .entity import RadiantEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["kind"] == "zone":
        async_add_entities([RadiantThermostat(hass.data[DOMAIN], entry)])


class RadiantThermostat(RadiantEntity, ClimateEntity):
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.1
    _attr_min_temp = 5
    _attr_max_temp = 40
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, manager, entry):
        super().__init__(manager, entry, "thermostat")

    @property
    def zone(self):
        return self.manager.zones[self.entry.entry_id]

    @property
    def hvac_modes(self):
        return [HVACMode.OFF, *[HVACMode(m.value) for m in self.zone.settings.modes]]

    @property
    def hvac_mode(self):
        return HVACMode(self.zone.intent.mode.value) if self.manager.enabled else HVACMode.OFF

    @property
    def hvac_action(self):
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self.zone.decision and self.zone.decision.demand and self.zone.actual_on:
            return HVACAction.HEATING if self.zone.intent.mode == Mode.HEAT else HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def current_temperature(self):
        sensor = self.hass.states.get(self.zone.config["sensor"])
        try:
            return temperature(sensor.state if sensor else None, -30, 65)
        except ValueError:
            return None

    @property
    def target_temperature(self):
        return self.zone.intent.target(dt_util.utcnow())

    @property
    def extra_state_attributes(self):
        return {
            "requested_mode": self.zone.intent.mode.value,
            "control_state": "fixed",
            "reason": self.zone.decision.reason if self.zone.decision else "not_ready",
            "valve_position": "not_measured",
        }

    async def async_set_hvac_mode(self, hvac_mode):
        mode = Mode(hvac_mode)
        await self.manager.async_change(lambda: self.zone.intent.set_mode(mode, self.zone.settings))

    async def async_set_temperature(self, **kwargs):
        value = temperature(kwargs[ATTR_TEMPERATURE])
        await self.manager.async_change(
            lambda: self.zone.intent.set_target(value, dt_util.utcnow(), self.zone.settings)
        )

    async def async_turn_off(self):
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self):
        mode = self.manager.supply_mode
        if mode not in self.zone.settings.modes:
            mode = self.zone.settings.modes[0]
        await self.async_set_hvac_mode(HVACMode(mode.value))
