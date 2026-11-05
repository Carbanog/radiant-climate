"""Real HA lifecycle/services with explicitly simulated sensors and actuators.

This suite is skipped on the lightweight local core environment. CI installs
the exact supported Home Assistant version on Linux and must run it separately.
"""

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
async def house(tmp_path):
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
    house.states.async_set("sensor.fixture_a", "28")
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="cool")
    await service(house, "switch", "turn_on", global_entity(house))
    assert house.states.get("switch.fixture_a").state == "off"
    await house.data[DOMAIN].async_supply("cool")
    await settle(house)
    assert house.states.get("switch.fixture_a").state == "on"
