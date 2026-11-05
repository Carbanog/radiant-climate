"""Minimal setup with explicit, separate advanced controls."""

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN
from .core.control import Settings, temperature


def _entity(domain: str, multiple: bool = False):
    return selector.EntitySelector(selector.EntitySelectorConfig(domain=domain, multiple=multiple))


def _number(minimum, maximum, step=1):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX
        )
    )


def _schema(data: Mapping, *, installation=False, advanced=False) -> vol.Schema:
    if installation:
        key = (
            vol.Optional("general", default=data["general"])
            if data.get("general")
            else vol.Optional("general")
        )
        return vol.Schema({key: _entity("switch")})
    modes = data.get("modes", ["heat", "cool"])
    selected = "heat_cool" if len(modes) == 2 else modes[0]
    fields = {
        vol.Required("sensor", default=data.get("sensor", vol.UNDEFINED)): _entity("sensor"),
        vol.Required("actuators", default=data.get("actuators", vol.UNDEFINED)): _entity(
            "switch", True
        ),
        vol.Required("available_modes", default=selected): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["heat", "cool", "heat_cool"], translation_key="available_modes"
            )
        ),
        vol.Required("target", default=data.get("target", 21)): _number(5, 40, 0.1),
    }
    if advanced:
        key = (
            vol.Optional("window", default=data["window"])
            if data.get("window")
            else vol.Optional("window")
        )
        fields.update(
            {
                key: _entity("binary_sensor"),
                vol.Required("hysteresis", default=data.get("hysteresis", 0.2)): _number(
                    0.05, 2, 0.05
                ),
                vol.Required("minimum_on", default=data.get("minimum_on", 180)): _number(0, 3600),
                vol.Required("minimum_off", default=data.get("minimum_off", 180)): _number(0, 3600),
                vol.Required("stale_after", default=data.get("stale_after", 3600)): _number(
                    60, 86400
                ),
            }
        )
    return vol.Schema(fields)


def _normalise(data: Mapping, *, installation=False) -> dict:
    result = dict(data)
    result["kind"] = "installation" if installation else "zone"
    if installation:
        result["general"] = result.get("general") or None
        return result
    choice = result.pop("available_modes")
    result["modes"] = ["heat", "cool"] if choice == "heat_cool" else [choice]
    result["target"] = temperature(result["target"])
    if not result["actuators"] or len(result["actuators"]) != len(set(result["actuators"])):
        raise ValueError("invalid_actuators")
    Settings(
        **{
            k: result[k]
            for k in ["hysteresis", "minimum_on", "minimum_off", "stale_after"]
            if k in result
        }
    )
    result["window"] = result.get("window") or None
    return result


def _validate(hass, data: dict, exclude: str | None = None) -> None:
    outputs = set(data.get("actuators", [])) | ({data["general"]} if data.get("general") else set())
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude:
            continue
        other = {**entry.data, **entry.options}
        assigned = set(other.get("actuators", [])) | (
            {other["general"]} if other.get("general") else set()
        )
        if outputs & assigned:
            raise ValueError("actuator_assigned")
    for entity in outputs | {data[k] for k in ["sensor", "window"] if data.get(k)}:
        if hass.states.get(entity) is None:
            raise ValueError("entity_missing")


class RadiantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if not self._async_current_entries():
            return await self.async_step_installation(user_input)
        return await self.async_step_zone(user_input)

    async def async_step_installation(self, user_input=None):
        await self.async_set_unique_id("installation")
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            try:
                data = _normalise(user_input, installation=True)
                _validate(self.hass, data)
            except ValueError as exc:
                errors["base"] = str(exc)
            else:
                return self.async_create_entry(title="Radiant Climate", data=data)
        return self.async_show_form(
            step_id="installation",
            data_schema=_schema(user_input or {}, installation=True),
            errors=errors,
        )

    async def async_step_zone(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                data = _normalise(user_input)
                _validate(self.hass, data)
            except ValueError as exc:
                errors["base"] = (
                    str(exc)
                    if str(exc) in {"invalid_actuators", "actuator_assigned", "entity_missing"}
                    else "invalid_configuration"
                )
            else:
                sensor = self.hass.states.get(data["sensor"])
                title = sensor.name if sensor else "Thermostat"
                return self.async_create_entry(title=title, data=data)
        return self.async_show_form(step_id="zone", data_schema=_schema({}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return RadiantOptionsFlow()


class RadiantOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if self.config_entry.data["kind"] == "installation":
            return await self.async_step_hardware(user_input)
        return self.async_show_menu(
            step_id="init", menu_options=["hardware", "schedule_add", "schedule_remove"]
        )

    async def async_step_schedule_add(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                from datetime import time

                clock = time.fromisoformat(user_input["time"])
                days = [int(d) for d in user_input["days"]]
                manager = self.hass.data[DOMAIN]
                await manager.async_change(
                    lambda: manager.zones[self.config_entry.entry_id].program.set_blocks(
                        days, clock.hour * 60 + clock.minute, user_input["profile"]
                    )
                )
            except ValueError:
                errors["base"] = "invalid_configuration"
            else:
                return self.async_create_entry(title="", data=dict(self.config_entry.options))
        return self.async_show_form(
            step_id="schedule_add",
            data_schema=vol.Schema(
                {
                    vol.Required("days"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[str(n) for n in range(7)],
                            multiple=True,
                            translation_key="days",
                        )
                    ),
                    vol.Required("time"): selector.TimeSelector(),
                    vol.Required("profile", default="home"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["home", "eco", "sleep"], translation_key="profile"
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_schedule_remove(self, user_input=None):
        program = self.hass.data[DOMAIN].zones[self.config_entry.entry_id].program
        if not program.blocks:
            return self.async_abort(reason="no_schedule")
        if user_input is not None:
            remove = int(user_input["block"])

            def update():
                program.blocks.pop(remove)
                if not program.blocks:
                    # Preserve the current effective target instead of silently reverting.
                    from homeassistant.util import dt as dt_util

                    z = self.hass.data[DOMAIN].zones[self.config_entry.entry_id]
                    program.enabled = False
                    program.selected = None
                    z.intent.set_target(z.decision.target, dt_util.utcnow(), z.settings)

            await self.hass.data[DOMAIN].async_change(update)
            return self.async_create_entry(title="", data=dict(self.config_entry.options))
        options = [
            {
                "value": str(i),
                "label": f"{b.day + 1} · {b.minute // 60:02d}:{b.minute % 60:02d} · {b.profile}",
            }
            for i, b in enumerate(program.blocks)
        ]
        return self.async_show_form(
            step_id="schedule_remove",
            data_schema=vol.Schema(
                {
                    vol.Required("block"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    async def async_step_hardware(self, user_input=None):
        previous = {**self.config_entry.data, **self.config_entry.options}
        installation = previous["kind"] == "installation"
        errors = {}
        if user_input is not None:
            try:
                data = _normalise(user_input, installation=installation)
                _validate(self.hass, data, self.config_entry.entry_id)
            except ValueError as exc:
                errors["base"] = (
                    str(exc)
                    if str(exc) in {"invalid_actuators", "actuator_assigned", "entity_missing"}
                    else "invalid_configuration"
                )
            else:
                return self.async_create_entry(title="", data=data)
        return self.async_show_form(
            step_id="hardware",
            data_schema=_schema(previous, installation=installation, advanced=True),
            errors=errors,
        )
