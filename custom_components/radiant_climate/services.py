"""Explicit, validated bulk configuration without copying actuators or on/off intent."""

from copy import deepcopy

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.util import dt as dt_util

from .const import DOMAIN


def async_register_services(hass):
    if hass.services.has_service(DOMAIN, "copy_settings"):
        return

    async def copy_settings(call):
        manager = hass.data.get(DOMAIN)
        if manager is None:
            raise HomeAssistantError("No Radiant Climate installation is loaded")

        def zone_id(entity_id):
            registered = er.async_get(hass).async_get(entity_id)
            if (
                registered is None
                or registered.domain != "climate"
                or registered.platform != DOMAIN
                or registered.config_entry_id not in manager.zones
            ):
                raise HomeAssistantError("Select only loaded Radiant Climate thermostats")
            return registered.config_entry_id

        source_id = zone_id(call.data["source"])
        targets = (
            [zone_id(e) for e in call.data["targets"]]
            if call.data["targets"]
            else list(manager.zones)
        )
        parts = call.data["parts"]

        def update():
            source = manager.zones[source_id].program
            now = dt_util.utcnow()
            planned = {}
            for key in set(targets) - {source_id}:
                z = deepcopy(manager.zones[key])
                current = z.program.target(z.intent, now, hass.config.time_zone)
                if "temperatures" in parts:
                    z.program.profiles = deepcopy(source.profiles)
                if "manual" in parts:
                    z.program.minutes, z.program.policy = source.minutes, source.policy
                if "modules" in parts:
                    z.intelligence.features = deepcopy(
                        manager.zones[source_id].intelligence.features
                    )
                    z.window_enabled = manager.zones[source_id].window_enabled
                if "vacation" in parts:
                    z.program.away, z.program.away_until = source.away, source.away_until
                    z.intent.resume()
                if "schedule" in parts:
                    z.program.blocks = list(source.blocks)
                    z.program.enabled = source.enabled
                    z.program.reconcile_edit(z.intent, now, hass.config.time_zone)
                    if not source.enabled:
                        z.program.selected = None
                        z.program.set_manual(
                            z.intent, z.settings, current, now, hass.config.time_zone
                        )
                if "modules" in parts:
                    for module, enabled in z.intelligence.dump()["features"].items():
                        manager.validate_feature(z, module, enabled)
                planned[key] = z
            # Validate every final candidate before publishing any of them.
            for key, candidate in planned.items():
                z = manager.zones[key]
                z.program, z.intent = candidate.program, candidate.intent
                z.intelligence.features = candidate.intelligence.features
                z.window_enabled = candidate.window_enabled

        await manager.async_change(update)

    hass.services.async_register(
        DOMAIN,
        "copy_settings",
        copy_settings,
        schema=vol.Schema(
            {
                vol.Required("source"): cv.entity_id,
                vol.Optional("targets", default=[]): cv.entity_ids,
                vol.Required("parts"): vol.All(
                    cv.ensure_list,
                    [vol.In(["temperatures", "manual", "schedule", "modules", "vacation"])],
                    vol.Length(min=1),
                ),
            }
        ),
    )

    async def acknowledge_retired(call):
        manager = hass.data.get(DOMAIN)
        if manager is None:
            raise HomeAssistantError("No Radiant Climate installation is loaded")
        await manager.async_acknowledge_retired(call.data["actuator"])

    async_register_admin_service(
        hass,
        DOMAIN,
        "acknowledge_retired_actuator",
        acknowledge_retired,
        schema=vol.Schema(
            {
                vol.Required("actuator"): cv.entity_id,
                vol.Required("confirmed_disconnected"): vol.All(cv.boolean, vol.In([True])),
            }
        ),
    )

    async def reset_actuator_faults(call):
        manager = hass.data.get(DOMAIN)
        if manager is None:
            raise HomeAssistantError("No Radiant Climate installation is loaded")
        await manager.async_reset_actuator_faults(call.data["actuators"])

    async_register_admin_service(
        hass,
        DOMAIN,
        "reset_actuator_faults",
        reset_actuator_faults,
        schema=vol.Schema(
            {
                vol.Optional("actuators", default=[]): cv.entity_ids,
                vol.Required("confirmed_review"): vol.All(cv.boolean, vol.In([True])),
            }
        ),
    )
