"""Expose existing actuator latches; never acknowledge or actuate from Repairs."""

from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


def async_setup_repairs(manager, entry):
    active = True
    issue_id = f"actuator_attention_{entry.entry_id}"

    @callback
    def refresh():
        if not active:
            return
        if manager.actuator_faults or manager.retired_actuators:
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
                },
                learn_more_url="https://github.com/Carbanog/radiant-climate/blob/main/docs/troubleshooting.md",
            )
        else:
            ir.async_delete_issue(manager.hass, DOMAIN, issue_id)

    @callback
    def schedule():
        manager.hass.loop.call_soon(refresh)

    @callback
    def stop():
        nonlocal active
        active = False

    entry.async_on_unload(stop)
    entry.async_on_unload(manager.async_subscribe(schedule))
    refresh()
