"""Real HA lifecycle/services with explicitly simulated sensors and actuators.

This suite is skipped on the lightweight local core environment. CI installs
the exact supported Home Assistant version on Linux and must run it separately.
"""

import logging
import shutil
from pathlib import Path

import pytest
import pytest_asyncio

pytest.importorskip("homeassistant")

from homeassistant.bootstrap import async_from_config_dict
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_setup as async_setup_loader
from homeassistant.setup import async_setup_component

DOMAIN = "radiant_climate"
SOURCE = Path(__file__).resolve().parents[1] / "custom_components/radiant_climate"


@pytest_asyncio.fixture
async def house(tmp_path, caplog):
    shutil.copytree(SOURCE, tmp_path / "custom_components/radiant_climate")
    hass = HomeAssistant(str(tmp_path))
    async_setup_loader(hass)
    try:
        switches = []
        for key in ["a", "b", "general"]:
            switches.append(
                {
                    "name": f"Fixture {key}",
                    "unique_id": f"fixture_{key}",
                    "state": "{{ is_state('input_boolean.fixture_" + key + "','on') }}",
                    "turn_on": [
                        {
                            "action": "input_boolean.turn_on",
                            "target": {"entity_id": f"input_boolean.fixture_{key}"},
                        }
                    ],
                    "turn_off": [
                        {
                            "action": "input_boolean.turn_off",
                            "target": {"entity_id": f"input_boolean.fixture_{key}"},
                        }
                    ],
                }
            )
        config = {
            "homeassistant": {},
            "input_boolean": {f"fixture_{x}": {} for x in ["a", "b", "general"]},
            "template": [{"switch": switches}],
        }
        assert await async_from_config_dict(config, hass) is hass
        for key in ["a", "b"]:
            hass.states.async_set(
                f"sensor.fixture_{key}",
                "19",
                {"unit_of_measurement": "°C", "device_class": "temperature"},
            )
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_start()
        await hass.async_block_till_done()
        for key in ["a", "b", "general"]:
            assert hass.states.get(f"input_boolean.fixture_{key}") is not None
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["step_id"] == "installation"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"general": "switch.fixture_general"}
        )
        assert result["type"] == "create_entry", result
        await hass.async_block_till_done()
        yield hass
    finally:
        await hass.async_stop()
        errors = [
            record
            for phase in ("setup", "call", "teardown")
            for record in caplog.get_records(phase)
            if record.levelno >= logging.ERROR
        ]
        assert not errors, [(r.name, r.getMessage()) for r in errors]


async def add_zone(hass, key="a"):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["step_id"] == "zone"
    data = {
        "sensor": f"sensor.fixture_{key}",
        "actuators": [f"switch.fixture_{key}"],
        "available_modes": "heat_cool",
        "target": 21,
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] == "create_entry", result
    entry = result["result"]
    await hass.async_block_till_done()
    # Explicitly accelerated cycle-time fixture; never a production default.
    options = await hass.config_entries.options.async_init(entry.entry_id)
    options = await hass.config_entries.options.async_configure(
        options["flow_id"], {"next_step_id": "hardware"}
    )
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            **data,
            "hysteresis": 0.2,
            "minimum_on": 0,
            "minimum_off": 0,
            "stale_after": 3600,
        },
    )
    assert options["type"] == "create_entry", options
    await hass.async_block_till_done()
    entity = er.async_get(hass).async_get_entity_id(
        "climate", DOMAIN, f"{entry.entry_id}_thermostat"
    )
    assert entity is not None
    return entry, entity


async def settle(hass):
    await hass.async_block_till_done()
    await hass.data[DOMAIN].async_reconcile()
    await hass.async_block_till_done()
    await hass.data[DOMAIN].async_reconcile()
    await hass.async_block_till_done()


async def service(hass, domain, name, entity, **data):
    await hass.services.async_call(domain, name, {"entity_id": entity, **data}, blocking=True)
    await settle(hass)


def global_entity(hass):
    manager = hass.data[DOMAIN]
    return er.async_get(hass).async_get_entity_id("switch", DOMAIN, f"{manager.hub}_enabled")


async def test_basic_setup_is_off_and_requires_no_outdoor_or_weather(house):
    _, climate = await add_zone(house)
    assert house.states.get(climate).state == "off"
    assert house.states.get("switch.fixture_a").state == "off"
    assert not house.data[DOMAIN].enabled


async def test_global_off_preserves_intent_and_blocks_temperature_changes(house):
    entry, climate = await add_zone(house)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    assert house.states.get("switch.fixture_a").state == "off"
    await service(house, "switch", "turn_on", global_entity(house))
    assert house.states.get("switch.fixture_a").state == "on"
    await service(house, "switch", "turn_off", global_entity(house))
    await service(house, "climate", "set_temperature", climate, temperature=22)
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get("switch.fixture_general").state == "off"
    assert house.data[DOMAIN].zones[entry.entry_id].intent.mode.value == "heat"
    await service(house, "switch", "turn_on", global_entity(house))
    assert house.states.get("switch.fixture_a").state == "on"


async def test_individual_off_is_preserved_through_global_toggle(house):
    _, climate = await add_zone(house)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    await service(house, "climate", "turn_off", climate)
    await service(house, "switch", "turn_off", global_entity(house))
    await service(house, "switch", "turn_on", global_entity(house))
    assert house.states.get(climate).state == "off"
    assert house.states.get("switch.fixture_a").state == "off"


async def test_invalid_indoor_sensor_isolates_zone_with_reported_closed_relay(house):
    _, first = await add_zone(house, "a")
    _, second = await add_zone(house, "b")
    for entity in [first, second]:
        await service(house, "climate", "set_hvac_mode", entity, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    house.states.async_set("sensor.fixture_a", "unavailable")
    await settle(house)
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get("switch.fixture_b").state == "on"


async def test_duplicate_actuator_rejected_in_native_flow(house):
    await add_zone(house)
    flow = await house.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await house.config_entries.flow.async_configure(
        flow["flow_id"],
        {
            "sensor": "sensor.fixture_b",
            "actuators": ["switch.fixture_a"],
            "available_modes": "heat",
            "target": 21,
        },
    )
    assert result["errors"]["base"] == "actuator_assigned"


async def test_state_roundtrip_through_real_storage(house):
    entry, climate = await add_zone(house)
    await service(house, "climate", "set_temperature", climate, temperature=22.5)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_off", global_entity(house))
    from custom_components.radiant_climate.runtime import Installation

    restored = Installation(house)
    try:
        await restored.async_load()
        assert not restored.enabled
        assert restored._saved[entry.entry_id]["targets"]["heat"] == 22.5
    finally:
        restored.async_stop()


async def test_cooling_without_weather_and_mismatched_season(house):
    _, climate = await add_zone(house)
    house.states.async_set("sensor.fixture_a", "28", {"unit_of_measurement": "°C"})
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="cool")
    await service(house, "switch", "turn_on", global_entity(house))
    assert house.states.get("switch.fixture_a").state == "off"
    await house.data[DOMAIN].async_supply("cool")
    await settle(house)
    assert house.states.get("switch.fixture_a").state == "on"


def zone_entity(hass, entry, platform, key):
    result = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert result is not None
    return result


async def add_schedule(hass, entry):
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "schedule_add"}
    )
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"days": [str(n) for n in range(7)], "time": "00:00:00", "profile": "home"}
    )
    assert result["type"] == "create_entry", result
    await settle(hass)


async def test_native_schedule_and_manual_hold_ignore_profile_changes(house):
    entry, climate = await add_zone(house)
    await add_schedule(house, entry)
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "schedule"))
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "climate", "set_temperature", climate, temperature=22)
    assert house.states.get(climate).attributes["control_state"] == "manual"
    assert house.states.get(climate).attributes["manual_until"] is not None
    await service(
        house, "number", "set_value", zone_entity(house, entry, "number", "heat_home"), value=20
    )
    assert house.states.get(climate).attributes["temperature"] == 22
    await service(house, "button", "press", zone_entity(house, entry, "button", "resume"))
    assert house.states.get(climate).attributes["temperature"] == 20
    assert house.states.get(climate).attributes["control_state"] == "scheduled"


async def test_same_as_profile_manual_persists_across_entry_reload(house):
    entry, climate = await add_zone(house)
    await add_schedule(house, entry)
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "schedule"))
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "climate", "set_temperature", climate, temperature=21)
    deadline = house.states.get(climate).attributes["manual_until"]
    await house.config_entries.async_reload(entry.entry_id)
    await settle(house)
    assert house.states.get(climate).attributes["manual_until"] == deadline
    assert house.states.get(climate).attributes["control_state"] == "manual"


async def test_disable_schedule_retains_current_value_without_expiry(house):
    entry, climate = await add_zone(house)
    await add_schedule(house, entry)
    switch = zone_entity(house, entry, "switch", "schedule")
    await service(house, "switch", "turn_on", switch)
    await service(house, "climate", "set_temperature", climate, temperature=22)
    await service(house, "switch", "turn_off", switch)
    assert house.states.get(climate).attributes["temperature"] == 22
    assert house.data[DOMAIN].zones[entry.entry_id].intent.hold is None


async def test_unsupported_temperature_units_stop_zone(house):
    _, climate = await add_zone(house)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    house.states.async_set("sensor.fixture_a", "30", {"unit_of_measurement": "°F"})
    await settle(house)
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get(climate).attributes["current_temperature"] is None


async def test_general_unavailable_blocks_all_zones(house):
    _, climate = await add_zone(house)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    house.states.async_set("switch.fixture_general", "unavailable")
    await settle(house)
    assert house.states.get("switch.fixture_a").state == "off"


async def test_bulk_copy_is_explicit_and_preserves_off(house):
    first, climate_a = await add_zone(house, "a")
    second, climate_b = await add_zone(house, "b")
    await add_schedule(house, first)
    await service(
        house, "number", "set_value", zone_entity(house, first, "number", "heat_home"), value=22
    )
    await house.services.async_call(
        DOMAIN,
        "copy_settings",
        {"source": climate_a, "parts": ["schedule", "temperatures", "manual"]},
        blocking=True,
    )
    await settle(house)
    z = house.data[DOMAIN].zones[second.entry_id]
    assert z.program.profiles["heat"]["home"] == 22
    assert len(z.program.blocks) == 7
    assert z.intent.mode.value == "off"
    assert house.states.get(climate_b).state == "off"
    assert house.states.get("switch.fixture_b").state == "off"


async def test_combined_mode_and_temperature_service_is_respected(house):
    _, climate = await add_zone(house)
    await service(house, "climate", "set_temperature", climate, temperature=24, hvac_mode="cool")
    assert house.states.get(climate).attributes["requested_mode"] == "cool"
    assert house.states.get(climate).attributes["temperature"] == 24
    assert house.states.get("switch.fixture_a").state == "off"


async def test_storage_failure_does_not_enable_outputs(house):
    from unittest.mock import AsyncMock, patch

    from homeassistant.exceptions import HomeAssistantError

    _, climate = await add_zone(house)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    manager = house.data[DOMAIN]
    with patch.object(
        manager._store,
        "async_save",
        AsyncMock(side_effect=HomeAssistantError("fixture storage failure")),
    ):
        with pytest.raises(HomeAssistantError):
            await manager.async_enable(True)
    assert not manager.enabled
    assert house.states.get("switch.fixture_a").state == "off"


async def test_window_unavailable_blocks_only_when_feature_enabled(house):
    entry, climate = await add_zone(house)
    house.states.async_set("binary_sensor.fixture_window", "unavailable")
    config = dict(house.data[DOMAIN].zones[entry.entry_id].config)
    config.pop("kind")
    config["available_modes"] = "heat_cool"
    config.pop("modes")
    config["window"] = "binary_sensor.fixture_window"
    flow = await house.config_entries.options.async_init(entry.entry_id)
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "hardware"}
    )
    flow = await house.config_entries.options.async_configure(flow["flow_id"], config)
    assert flow["type"] == "create_entry", flow
    await settle(house)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    assert house.states.get("switch.fixture_a").state == "off"
    await service(
        house, "switch", "turn_off", zone_entity(house, entry, "switch", "window_enabled")
    )
    assert house.states.get("switch.fixture_a").state == "on"


async def test_sensor_failure_while_general_opens_never_opens_zone(house):
    from unittest.mock import patch

    _, climate = await add_zone(house)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    opened = []
    unsubscribe = house.bus.async_listen(
        "state_changed",
        lambda event: opened.append(event.data["new_state"].state)
        if event.data["entity_id"] == "input_boolean.fixture_a" and event.data["new_state"]
        else None,
    )
    original = house.services.async_call

    async def interrupted(domain, action, data=None, *args, **kwargs):
        if (
            domain == "switch"
            and action == "turn_on"
            and data.get("entity_id") == "switch.fixture_general"
        ):
            house.states.async_set("sensor.fixture_a", "unavailable")
        return await original(domain, action, data, *args, **kwargs)

    try:
        with patch.object(house.services, "async_call", side_effect=interrupted):
            await house.data[DOMAIN].async_enable(True)
            await settle(house)
        assert "on" not in opened
        assert house.states.get("switch.fixture_general").state == "off"
        assert house.states.get("switch.fixture_a").state == "off"
    finally:
        unsubscribe()
