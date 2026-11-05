"""Native thermostat entity; all hardware writes remain in Installation."""

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .core.control import Mode, temperature
from .entity import RadiantEntity
from .runtime import indoor_temperature


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
        | ClimateEntityFeature.PRESET_MODE
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
        return indoor_temperature(sensor)

    @property
    def target_temperature(self):
        return self.zone.program.target(
            self.zone.intent, dt_util.utcnow(), self.hass.config.time_zone
        )

    @property
    def preset_modes(self):
        return ["none", "home", "eco", "sleep"]

    @property
    def preset_mode(self):
        z = self.zone
        if z.intent.hold:
            return "none"
        return (
            z.program.active(dt_util.utcnow(), self.hass.config.time_zone)
            if z.program.enabled
            else (z.program.selected or "none")
        )

    async def async_set_preset_mode(self, preset_mode):
        if preset_mode not in self.preset_modes:
            raise ValueError("Unsupported profile")

        def update():
            z = self.zone
            now = dt_util.utcnow()
            mode = z.intent.last_mode if z.intent.mode == Mode.OFF else z.intent.mode
            value = (
                self.target_temperature
                if preset_mode == "none"
                else z.program.profiles[mode.value][preset_mode]
            )
            z.program.set_manual(z.intent, z.settings, value, now, self.hass.config.time_zone)
            if not z.program.enabled:
                z.program.selected = None if preset_mode == "none" else preset_mode

        await self.manager.async_change(update)

    @property
    def extra_state_attributes(self):
        return {
            "requested_mode": self.zone.intent.mode.value,
            "control_state": "off"
            if self.zone.intent.mode == Mode.OFF
            else (
                "manual"
                if self.zone.intent.hold
                else ("scheduled" if self.zone.program.enabled else "fixed")
            ),
            "manual_until": self.zone.intent.hold.until.isoformat()
            if self.zone.intent.hold and self.zone.intent.hold.until
            else None,
            "manual_policy": self.zone.intent.hold.policy.value if self.zone.intent.hold else None,
            "next_schedule_change": self.zone.program.next_change(
                dt_util.utcnow(), self.hass.config.time_zone
            ).isoformat()
            if self.zone.program.blocks
            else None,
            "reason": self.zone.decision.reason if self.zone.decision else "not_ready",
            "valve_position": "not_measured",
        }

    async def async_set_hvac_mode(self, hvac_mode):
        mode = Mode(hvac_mode)
        await self.manager.async_change(lambda: self.zone.intent.set_mode(mode, self.zone.settings))

    async def async_set_temperature(self, **kwargs):
        value = temperature(kwargs[ATTR_TEMPERATURE])
        await self.manager.async_change(
            lambda: self.zone.program.set_manual(
                self.zone.intent,
                self.zone.settings,
                value,
                dt_util.utcnow(),
                self.hass.config.time_zone,
            )
        )

    async def async_turn_off(self):
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self):
        mode = self.manager.supply_mode
        if mode not in self.zone.settings.modes:
            mode = self.zone.settings.modes[0]
        await self.async_set_hvac_mode(HVACMode(mode.value))
