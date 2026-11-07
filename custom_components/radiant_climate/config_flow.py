"""Minimal setup with explicit, separate advanced controls."""

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN
from .core.control import Settings, temperature
from .core.program import PROFILES, ScheduleInUseError
from .core.schedule_editor import groups, replace_blocks, selection, weekdays
from .hydraulic import DEFAULTS, configuration
from .solar import confirmed, source_entities, source_signature


def _entity(domain: str, multiple: bool = False):
    return selector.EntitySelector(selector.EntitySelectorConfig(domain=domain, multiple=multiple))


def _number(minimum, maximum, step=1):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX
        )
    )


def _days_selector():
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=["week", "weekdays", "weekend", *map(str, range(7))],
            multiple=True,
            translation_key="days",
        )
    )


def _optional_entity(key: str, data: Mapping):
    # A default is reinserted when the UI omits a cleared optional selector.
    # Suggested values display the current entity without making it sticky.
    return vol.Optional(key, description={"suggested_value": data[key]} if data.get(key) else {})


def _schema(data: Mapping, *, installation=False, advanced=False) -> vol.Schema:
    if installation:
        key = _optional_entity("general", data)
        fields = {key: _entity("switch")}
        if advanced:
            for source, domain in [("outdoor", "sensor"), ("weather", "weather")]:
                fields[_optional_entity(source, data)] = _entity(domain)
            fields[vol.Required("general_travel", default=data.get("general_travel", 0))] = _number(
                0, 900
            )
            fields[vol.Required("general_closing", default=data.get("general_closing", 0))] = (
                _number(0, 900)
            )
        return vol.Schema(fields)
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
        key = _optional_entity("window", data)
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
                vol.Required(
                    "window_open_delay", default=data.get("window_open_delay", 0)
                ): _number(0, 600),
                vol.Required(
                    "window_close_delay", default=data.get("window_close_delay", 0)
                ): _number(0, 600),
                vol.Required("valve_travel", default=data.get("valve_travel", 0)): _number(0, 900),
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
    for entity in outputs | {
        data[k] for k in ["sensor", "window", "outdoor", "weather"] if data.get(k)
    }:
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
            return self.async_show_menu(
                step_id="init", menu_options=["hardware", "solar_source", "hydraulic", "vacation"]
            )
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "hardware",
                "schedule_add",
                "schedule_choose",
                "schedule_remove",
                "sources",
                "vacation",
            ],
        )

    async def async_step_solar_source(self, user_input=None):
        if self.config_entry.data["kind"] != "installation":
            return self.async_abort(reason="installation_only")
        previous = {**self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            data = {**self.config_entry.options, **user_input}
            for key in ("sun_entity", "sun_elevation", "sun_azimuth"):
                data[key] = user_input.get(key)
            entities = source_entities(data)
            if (
                not entities
                or any(not e or self.hass.states.get(e) is None for e in entities)
                or (data["solar_source"] == "sensors" and len(set(entities)) != 2)
            ):
                errors["base"] = "invalid_configuration"
            else:
                return self.async_create_entry(title="", data=data)
        fields = {
            vol.Required(
                "solar_source", default=previous.get("solar_source", "standard")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["standard", "entity", "sensors"], translation_key="solar_source"
                )
            )
        }
        fields[_optional_entity("sun_entity", previous)] = selector.EntitySelector()
        for key in ("sun_elevation", "sun_azimuth"):
            fields[_optional_entity(key, previous)] = _entity("sensor")
        return self.async_show_form(
            step_id="solar_source", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_hydraulic(self, user_input=None):
        if self.config_entry.data["kind"] != "installation":
            return self.async_abort(reason="installation_only")
        previous = configuration(self.config_entry)
        errors = {}
        if user_input is not None:
            data = {**DEFAULTS, **user_input}
            try:
                if not isinstance(data["hydraulic_enabled"], bool):
                    raise ValueError
                for key in ("hydraulic_supply", "hydraulic_return"):
                    entity = data[key]
                    if entity and (
                        not entity.startswith("sensor.") or self.hass.states.get(entity) is None
                    ):
                        raise ValueError
                if data["hydraulic_enabled"] and (
                    not data["hydraulic_supply"]
                    or not data["hydraulic_return"]
                    or data["hydraulic_supply"] == data["hydraulic_return"]
                ):
                    raise ValueError
                for key, low, high in (
                    ("hydraulic_stale", 60, 3600),
                    ("hydraulic_settle", 5, 120),
                    ("hydraulic_duration", 5, 240),
                ):
                    data[key] = temperature(data[key], low, high)
                for key in ("hydraulic_heat_min", "hydraulic_cool_max"):
                    if data[key] is not None:
                        data[key] = temperature(data[key], 0, 90)
            except (ValueError, TypeError, AttributeError):
                errors["base"] = "invalid_configuration"
            else:
                return self.async_create_entry(title="", data={**self.config_entry.options, **data})
        fields = {
            vol.Required(
                "hydraulic_enabled", default=previous["hydraulic_enabled"]
            ): selector.BooleanSelector()
        }
        for key in ("hydraulic_supply", "hydraulic_return"):
            fields[_optional_entity(key, previous)] = _entity("sensor")
        for key, low, high in (
            ("hydraulic_stale", 60, 3600),
            ("hydraulic_settle", 5, 120),
            ("hydraulic_duration", 5, 240),
        ):
            fields[vol.Required(key, default=previous[key])] = _number(low, high)
        for key in ("hydraulic_heat_min", "hydraulic_cool_max"):
            fields[
                vol.Optional(
                    key,
                    description={"suggested_value": previous[key]}
                    if previous[key] is not None
                    else {},
                )
            ] = _number(0, 90, 0.1)
        return self.async_show_form(
            step_id="hydraulic", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_sources(self, user_input=None):
        previous = {**self.config_entry.data, **self.config_entry.options}
        manager = self.hass.data[DOMAIN]
        # Read the committed entry, not a possibly queued runtime update.
        installation = self.hass.config_entries.async_get_entry(manager.hub)
        solar_config = {**installation.data, **installation.options} if installation else {}
        signature = source_signature(solar_config)
        errors = {}
        if user_input is not None:
            data = {
                **previous,
                **user_input,
                "weather": user_input.get("weather"),
                "outdoor": user_input.get("outdoor"),
            }
            data["solar_confirmed"] = user_input.get("solar_confirmed") is True
            if getattr(self, "_reviewed_solar_source", None) != signature:
                # A checked box from the old page cannot certify a new source.
                errors["base"] = "solar_source_changed"
            if any(
                data.get(key, default) != previous.get(key, default)
                for key, default in (
                    ("orientation", 180),
                    ("solar_elevation", 15),
                    ("solar_width", 75),
                )
            ):
                data["solar_confirmed"] = False
            if data["solar_confirmed"] and not errors:
                data["solar_source_signature"] = list(self._reviewed_solar_source)
            try:
                _validate(self.hass, data, self.config_entry.entry_id)
            except ValueError:
                errors["base"] = "entity_missing"
            else:
                if not errors:
                    options = {**self.config_entry.options, **user_input}
                    for key in ("weather", "outdoor", "solar_confirmed", "solar_source_signature"):
                        if key in data:
                            options[key] = data[key]
                    return self.async_create_entry(title="", data=options)
        fields = {}
        for source, domain in [("outdoor", "sensor"), ("weather", "weather")]:
            fields[_optional_entity(source, previous)] = _entity(domain)
        for key, default, minimum, maximum in [
            ("orientation", 180, 0, 360),
            ("solar_elevation", 15, 0, 90),
            ("solar_width", 75, 1, 90),
            ("max_advance", 120, 0, 360),
            ("residual_minutes", 15, 5, 60),
            ("solar_lead", 0, 0, 180),
        ]:
            fields[vol.Required(key, default=previous.get(key, default))] = _number(
                minimum, maximum
            )
        fields[vol.Required("solar_confirmed", default=confirmed(previous, solar_config))] = (
            selector.BooleanSelector()
        )
        self._reviewed_solar_source = signature
        return self.async_show_form(
            step_id="sources",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={
                "solar_source": ", ".join(filter(None, source_entities(solar_config)))
            },
        )

    async def async_step_vacation(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                from datetime import datetime
                from zoneinfo import ZoneInfo

                from homeassistant.util import dt as dt_util

                until = None
                if user_input.get("date"):
                    until = datetime.fromisoformat(
                        user_input["date"] + "T" + user_input["time"]
                    ).replace(tzinfo=ZoneInfo(self.hass.config.time_zone))
                    until = dt_util.as_utc(until)
                    if until <= dt_util.utcnow():
                        raise ValueError("Return must be in the future")
                manager = self.hass.data[DOMAIN]
                if self.config_entry.data["kind"] == "installation":
                    await manager.async_away_all(user_input["enabled"], until)
                else:
                    await manager.async_away(
                        self.config_entry.entry_id, user_input["enabled"], until
                    )
            except ValueError:
                errors["base"] = "invalid_configuration"
            else:
                return self.async_create_entry(title="", data=dict(self.config_entry.options))
        return self.async_show_form(
            step_id="vacation",
            data_schema=vol.Schema(
                {
                    vol.Required("enabled", default=True): selector.BooleanSelector(),
                    vol.Optional("date"): selector.DateSelector(),
                    vol.Required("time", default="12:00:00"): selector.TimeSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_schedule_add(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                from datetime import time

                clock = time.fromisoformat(user_input["time"])
                days = weekdays(user_input["days"])
                manager = self.hass.data[DOMAIN]
                await manager.async_edit_schedule(
                    self.config_entry.entry_id,
                    lambda program: program.set_blocks(
                        days, clock.hour * 60 + clock.minute, user_input["profile"]
                    ),
                )
            except ValueError:
                errors["base"] = "invalid_configuration"
            else:
                return self.async_create_entry(title="", data=dict(self.config_entry.options))
        return self.async_show_form(
            step_id="schedule_add",
            data_schema=vol.Schema(
                {
                    vol.Required("days"): _days_selector(),
                    vol.Required("time"): selector.TimeSelector(),
                    vol.Required("profile", default="home"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(PROFILES), translation_key="profile"
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def _schedule_selection(self, step_id, errors):
        program = self.hass.data[DOMAIN].zones[self.config_entry.entry_id].program
        labels = await async_get_translations(
            self.hass, self.hass.config.language, "selector", {DOMAIN}
        )

        def label(selector_key, value):
            return labels.get(f"component.{DOMAIN}.selector.{selector_key}.options.{value}", value)

        options = []
        for key, days, minute, profile in groups(program.blocks):
            group = next(
                (
                    name
                    for name, values in (
                        ("week", list(range(7))),
                        ("weekdays", list(range(5))),
                        ("weekend", [5, 6]),
                    )
                    if days == values
                ),
                None,
            )
            day_label = (
                label("days", group) if group else ", ".join(label("days", str(d)) for d in days)
            )
            options.append(
                {
                    "value": key,
                    "label": f"{day_label} · {minute // 60:02d}:{minute % 60:02d} · {label('profile', profile)}",
                }
            )
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required("block"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    ),
                    vol.Optional("scope"): _days_selector(),
                }
            ),
            errors=errors,
        )

    async def async_step_schedule_choose(self, user_input=None):
        program = self.hass.data[DOMAIN].zones[self.config_entry.entry_id].program
        if not program.blocks:
            return self.async_abort(reason="no_schedule")
        errors = {}
        if user_input is not None:
            try:
                self._editing = selection(
                    program.blocks, user_input["block"], user_input.get("scope", [])
                )
            except ValueError:
                errors["base"] = "schedule_changed"
            else:
                return await self.async_step_schedule_edit()
        return await self._schedule_selection("schedule_choose", errors)

    async def async_step_schedule_edit(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                from datetime import time

                clock = time.fromisoformat(user_input["time"])
                days = weekdays(user_input["days"])
                await self.hass.data[DOMAIN].async_edit_schedule(
                    self.config_entry.entry_id,
                    lambda current: replace_blocks(
                        current,
                        self._editing,
                        days,
                        clock.hour * 60 + clock.minute,
                        user_input["profile"],
                    ),
                )
            except ValueError as exc:
                errors["base"] = (
                    str(exc)
                    if str(exc) in {"schedule_changed", "schedule_conflict"}
                    else "invalid_configuration"
                )
            else:
                return self.async_create_entry(title="", data=dict(self.config_entry.options))
        first = self._editing[0]
        defaults = user_input or {
            "days": [str(b.day) for b in self._editing],
            "time": f"{first.minute // 60:02d}:{first.minute % 60:02d}:00",
            "profile": first.profile,
        }
        return self.async_show_form(
            step_id="schedule_edit",
            data_schema=vol.Schema(
                {
                    vol.Required("days", default=defaults["days"]): _days_selector(),
                    vol.Required("time", default=defaults["time"]): selector.TimeSelector(),
                    vol.Required("profile", default=defaults["profile"]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(PROFILES), translation_key="profile"
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
        errors = {}
        if user_input is not None:
            try:
                original = selection(
                    program.blocks, user_input["block"], user_input.get("scope", [])
                )
                await self.hass.data[DOMAIN].async_edit_schedule(
                    self.config_entry.entry_id,
                    lambda current: replace_blocks(current, original),
                )
            except ScheduleInUseError:
                errors["base"] = "schedule_in_use"
            except ValueError as exc:
                errors["base"] = (
                    "schedule_changed"
                    if str(exc) == "schedule_changed"
                    else "invalid_configuration"
                )
            else:
                return self.async_create_entry(title="", data=dict(self.config_entry.options))
        return await self._schedule_selection("schedule_remove", errors)

    async def async_step_hardware(self, user_input=None):
        previous = {**self.config_entry.data, **self.config_entry.options}
        installation = previous["kind"] == "installation"
        errors = {}
        if user_input is not None:
            try:
                merged = {**previous, **user_input}
                merged["general" if installation else "window"] = user_input.get(
                    "general" if installation else "window"
                )
                if installation:
                    for source in ("outdoor", "weather"):
                        merged[source] = user_input.get(source)
                data = _normalise(merged, installation=installation)
                _validate(self.hass, data, self.config_entry.entry_id)
            except ValueError as exc:
                errors["base"] = (
                    str(exc)
                    if str(exc) in {"invalid_actuators", "actuator_assigned", "entity_missing"}
                    else "invalid_configuration"
                )
            else:
                await self.hass.data[DOMAIN].async_prepare_hardware(
                    self.config_entry.entry_id, data
                )
                return self.async_create_entry(title="", data=data)
        return self.async_show_form(
            step_id="hardware",
            data_schema=_schema(previous, installation=installation, advanced=True),
            errors=errors,
        )
