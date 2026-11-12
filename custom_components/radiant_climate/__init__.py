"""Local thermostats with integration-owned intent and shared supply control."""

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS
from .hydraulic import DEFAULTS
from .repairs import async_setup_repairs
from .runtime import Installation
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Core loads stored config entries concurrently at boot. Publish exactly one
    # fully loaded manager, including when the first storage read yields.
    lock = hass.data.setdefault(f"{DOMAIN}_setup_lock", asyncio.Lock())
    async with lock:
        manager = hass.data.get(DOMAIN)
        if manager is None:
            manager = Installation(hass)
            try:
                await manager.async_load()
            except (Exception, asyncio.CancelledError):
                manager.async_stop()
                raise
            hass.data[DOMAIN] = manager
    try:
        await manager.async_add(entry, platforms_pending=True)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except (Exception, asyncio.CancelledError):
        try:
            await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        finally:
            await manager.async_abort_setup(entry.entry_id)
        raise
    manager.async_finish_setup(entry.entry_id)
    if entry.data["kind"] == "installation":
        async_setup_repairs(manager, entry)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    manager = hass.data[DOMAIN]
    data = {**entry.data, **entry.options}
    old = manager.entries.get(entry.entry_id)
    if (
        entry.data["kind"] == "installation"
        and old is not None
        and data != old
        and all(old.get(k) == data.get(k) for k in (old.keys() | data.keys()) - DEFAULTS.keys())
    ):
        # Purely observational changes must not invalidate an opening plan or
        # reconcile actuators, even during a pending relay acknowledgment.
        manager.entries[entry.entry_id] = data
        return
    if await hass.data[DOMAIN].async_update_options(entry):
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    manager = hass.data[DOMAIN]
    await manager.async_remove(entry.entry_id)
    if not manager.entries and not manager.retired_actuators:
        manager.async_stop()
        del hass.data[DOMAIN]
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    if entry.data["kind"] == "installation":
        from homeassistant.helpers import issue_registry as ir

        ir.async_delete_issue(hass, DOMAIN, f"actuator_attention_{entry.entry_id}")
        ir.async_delete_issue(hass, DOMAIN, f"storage_interrupted_{entry.entry_id}")
