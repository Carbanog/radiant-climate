"""Surface persistent problems that need an operator's attention."""

from time import monotonic

from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

UNAVAILABLE_DELAY = 300


def async_setup_repairs(manager, entry):
    active = True
    issue_id = f"actuator_attention_{entry.entry_id}"
    storage_id = f"storage_interrupted_{entry.entry_id}"
    unavailable_since = {}

    @callback
    def refresh():
        if not active:
            return
        now = monotonic()
        unavailable = set(manager.unavailable_actuators)
        for entity in unavailable_since.keys() - unavailable:
            del unavailable_since[entity]
        for entity in unavailable:
            unavailable_since.setdefault(entity, now)
        persistent = sum(now - since >= UNAVAILABLE_DELAY for since in unavailable_since.values())
        if manager.actuator_faults or manager.retired_actuators or persistent:
            ir.async_create_issue(
                manager.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="actuator_attention",
                translation_placeholders={
                    "faults": str(len(manager.actuator_faults)),
                    "retired": str(len(manager.retired_actuators)),
                    "unavailable": str(persistent),
                },
                learn_more_url="https://github.com/Carbanog/radiant-climate/blob/main/docs/troubleshooting.md",
            )
        else:
            ir.async_delete_issue(manager.hass, DOMAIN, issue_id)
        if manager.storage_interrupted:
            ir.async_create_issue(
                manager.hass,
                DOMAIN,
                storage_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="storage_interrupted",
                learn_more_url="https://github.com/Carbanog/radiant-climate/blob/main/docs/troubleshooting.md#climatización-se-ha-detenido-tras-un-error-de-guardado",
            )
        else:
            ir.async_delete_issue(manager.hass, DOMAIN, storage_id)

    @callback
    def schedule():
        manager.hass.loop.call_soon(refresh)

    @callback
    def stop():
        nonlocal active
        active = False
        ir.async_delete_issue(manager.hass, DOMAIN, issue_id)
        ir.async_delete_issue(manager.hass, DOMAIN, storage_id)

    entry.async_on_unload(stop)
    entry.async_on_unload(manager.async_subscribe(schedule))
    refresh()
