"""Surface persistent problems that need an operator's attention."""

from time import monotonic

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers import selector

from .const import DOMAIN

UNAVAILABLE_DELAY = 300


async def async_create_fix_flow(hass, issue_id, data):
    return ActuatorReviewFlow(issue_id, hass.data.get(DOMAIN))


class ActuatorReviewFlow(RepairsFlow):
    """Review one affected output at a time without a developer action."""

    def __init__(self, issue_id, manager):
        self.review_issue_id = issue_id
        self.manager = manager
        self.selected = None

    def _current(self):
        return (
            self.manager is not None
            and self.hass.data.get(DOMAIN) is self.manager
            and self.review_issue_id == f"actuator_attention_{self.manager.hub}"
        )

    def _name(self, entity):
        state = self.hass.states.get(entity)
        registered = er.async_get(self.hass).async_get(entity)
        return (
            (state.name if state else None)
            or (registered and (registered.name or registered.original_name))
            or entity
        )

    async def async_step_init(self, user_input=None):
        return await self.async_step_choose()

    async def async_step_stop(self, user_input=None):
        if not self._current():
            return self.async_abort(reason="installation_changed")
        if not self.manager.enabled:
            return await self.async_step_choose()
        if user_input is not None:
            try:
                await self.manager.async_enable(False)
            except (HomeAssistantError, OSError):
                return self.async_abort(reason="storage_error")
            return await self.async_step_choose()
        return self.async_show_form(step_id="stop", data_schema=vol.Schema({}))

    async def async_step_choose(self, user_input=None):
        if not self._current():
            return self.async_abort(reason="installation_changed")
        choices = self.manager.reviewable_actuators
        if not choices:
            # Core deletes the issue on successful completion. Leave it visible
            # when another output still requires connectivity or isolation.
            if self.manager.unavailable_actuators or self.manager.retired_actuators:
                return self.async_abort(reason="check_remaining")
            return self.async_create_entry(data={})
        if self.manager.enabled:
            return await self.async_step_stop()
        error = None
        if user_input is not None:
            self.selected = user_input["actuator"]
            if choices.get(self.selected) == "fault":
                return await self.async_step_fault()
            if choices.get(self.selected) == "retired":
                return await self.async_step_retired()
            error = "actuator_changed"
        return self.async_show_form(
            step_id="choose",
            data_schema=vol.Schema(
                {
                    vol.Required("actuator", default=next(iter(choices))): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": entity, "label": self._name(entity)} for entity in choices
                            ]
                        )
                    )
                }
            ),
            errors={"base": error} if error else {},
        )

    async def async_step_fault(self, user_input=None):
        return await self._async_confirm("fault", user_input)

    async def async_step_retired(self, user_input=None):
        return await self._async_confirm("retired", user_input)

    async def _async_confirm(self, kind, user_input):
        if not self._current():
            return self.async_abort(reason="installation_changed")
        if self.manager.reviewable_actuators.get(self.selected) != kind:
            return await self.async_step_choose()
        if self.manager.enabled:
            return await self.async_step_stop()
        errors = {}
        if user_input is not None:
            if not user_input.get("confirmed"):
                errors["confirmed"] = "confirmation_required"
            else:
                try:
                    if kind == "fault":
                        await self.manager.async_reset_actuator_faults(
                            [self.selected], assigned_only=True
                        )
                    else:
                        await self.manager.async_acknowledge_retired(self.selected)
                except ValueError:
                    errors["base"] = "relay_not_off" if kind == "fault" else "actuator_changed"
                except (HomeAssistantError, OSError):
                    return self.async_abort(reason="storage_error")
                else:
                    self.selected = None
                    return await self.async_step_choose()
        return self.async_show_form(
            step_id=kind,
            data_schema=vol.Schema(
                {vol.Required("confirmed", default=False): selector.BooleanSelector()}
            ),
            description_placeholders={"actuator": self._name(self.selected)},
            errors=errors,
        )


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
            can_review = bool(manager.reviewable_actuators)
            ir.async_create_issue(
                manager.hass,
                DOMAIN,
                issue_id,
                is_fixable=can_review,
                severity=ir.IssueSeverity.WARNING,
                translation_key="actuator_review" if can_review else "actuator_attention",
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
