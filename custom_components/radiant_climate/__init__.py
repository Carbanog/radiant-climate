"""Local thermostats with integration-owned intent and shared supply control."""

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .hydraulic import DEFAULTS
from .runtime import Installation
from .services import async_register_services


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    async_register_services(hass)
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
    await manager.async_add(entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    manager = hass.data[DOMAIN]
    data = {**entry.data, **entry.options}
    old = manager.entries.get(entry.entry_id)
    if (
        old is not None
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
    if not manager.entries and not manager._retired:
        manager.async_stop()
        del hass.data[DOMAIN]
    return True
