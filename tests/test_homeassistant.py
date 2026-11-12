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

from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
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
        hass.data["radiant_fixture_boot_config"] = config
        # Use Core's real storage, registries, auth and setup. Its full bootstrap
        # also loads the default UI/voice/media stack, unrelated to these tests.
        hass.config_entries = ConfigEntries(hass, config)
        assert await async_load_base_functionality(hass)
        await async_process_ha_core_config(hass, {})
        for domain in ("homeassistant", "persistent_notification", "input_boolean", "template"):
            assert await async_setup_component(hass, domain, config)
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


async def test_indefinite_away_with_schedule_updates_state_and_resumes(house):
    entry, climate = await add_zone(house)
    await add_schedule(house, entry)
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "schedule"))
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "away"))
    state = house.states.get(climate)
    assert state.attributes["control_state"] == "away"
    assert state.attributes["next_schedule_change"] is None
    assert state.attributes["temperature"] == 17
    await service(house, "climate", "set_temperature", climate, temperature=22)
    assert house.states.get(climate).attributes["control_state"] == "manual"
    await service(house, "button", "press", zone_entity(house, entry, "button", "resume"))
    assert house.states.get(climate).attributes["control_state"] == "away"
    await service(house, "switch", "turn_off", zone_entity(house, entry, "switch", "away"))
    state = house.states.get(climate)
    assert state.attributes["control_state"] == "scheduled"
    assert state.attributes["next_schedule_change"] is not None
    assert state.attributes["temperature"] == 21


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
    original = type(house.services).async_call

    async def interrupted(registry, domain, service, service_data=None, *args, **kwargs):
        if (
            domain == "switch"
            and service == "turn_on"
            and service_data.get("entity_id") == "switch.fixture_general"
        ):
            house.states.async_set("sensor.fixture_a", "unavailable")
        return await original(registry, domain, service, service_data, *args, **kwargs)

    try:
        with patch.object(type(house.services), "async_call", new=interrupted):
            await house.data[DOMAIN].async_enable(True)
            await settle(house)
        assert "on" not in opened
        assert house.states.get("switch.fixture_general").state == "off"
        assert house.states.get("switch.fixture_a").state == "off"
    finally:
        unsubscribe()


async def configure_sources(hass, entry, **sources):
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "sources"}
    )
    result = await hass.config_entries.options.async_configure(flow["flow_id"], sources)
    assert result["type"] == "create_entry", result
    await settle(hass)


async def test_optional_entity_selectors_can_be_cleared(house):
    entry, _ = await add_zone(house)
    house.states.async_set("sensor.fixture_outside", "10", {"unit_of_measurement": "°C"})
    house.states.async_set("weather.fixture_optional", "sunny")
    house.states.async_set("binary_sensor.fixture_window", "off")
    await configure_sources(
        house, entry, outdoor="sensor.fixture_outside", weather="weather.fixture_optional"
    )
    await configure_sources(house, entry)
    assert entry.options["outdoor"] is None
    assert entry.options["weather"] is None
    # Removing the provider must not block later, unrelated hardware edits.
    house.states.async_remove("weather.fixture_optional")
    data = {
        "sensor": "sensor.fixture_a",
        "actuators": ["switch.fixture_a"],
        "available_modes": "heat_cool",
        "target": 21,
    }
    for optional in ({"window": "binary_sensor.fixture_window"}, {}):
        flow = await house.config_entries.options.async_init(entry.entry_id)
        flow = await house.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "hardware"}
        )
        result = await house.config_entries.options.async_configure(
            flow["flow_id"], {**data, **optional}
        )
        assert result["type"] == "create_entry", result
        await settle(house)
    assert entry.options["window"] is None
    hub = next(
        e for e in house.config_entries.async_entries(DOMAIN) if e.data["kind"] == "installation"
    )
    flow = await house.config_entries.options.async_init(hub.entry_id)
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "hardware"}
    )
    result = await house.config_entries.options.async_configure(flow["flow_id"], {})
    assert result["type"] == "create_entry", result
    await settle(house)
    assert hub.options["general"] is None
    assert house.data[DOMAIN].general is None


async def test_household_vacation_respects_off_manual_and_partial_return(house):
    a, ca = await add_zone(house, "a")
    b, cb = await add_zone(house, "b")
    await add_schedule(house, a)
    await service(house, "switch", "turn_on", zone_entity(house, a, "switch", "schedule"))
    await service(house, "climate", "set_hvac_mode", ca, hvac_mode="heat")
    await service(
        house, "number", "set_value", zone_entity(house, b, "number", "heat_away"), value=18
    )
    manager = house.data[DOMAIN]
    control = er.async_get(house).async_get_entity_id(
        "switch", DOMAIN, f"{manager.hub}_household_away"
    )
    await service(house, "switch", "turn_on", control)
    assert house.states.get(ca).attributes["temperature"] == 17
    assert house.states.get(cb).attributes["temperature"] == 18
    assert house.states.get(cb).attributes["requested_mode"] == "off"
    assert not manager.enabled
    assert house.states.get(control).state == "on"
    assert house.states.get(control).attributes["away_zones"] == 2
    await service(house, "climate", "set_temperature", ca, temperature=22)
    await service(house, "switch", "turn_off", zone_entity(house, b, "switch", "away"))
    assert house.states.get(control).state == "on"
    assert house.states.get(control).attributes["partially_active"]
    await service(house, "switch", "turn_off", control)
    assert not any(z.program.away for z in manager.zones.values())
    assert house.states.get(ca).attributes["control_state"] == "manual"
    assert house.states.get(ca).attributes["temperature"] == 22
    assert house.states.get(cb).attributes["requested_mode"] == "off"
    await service(house, "button", "press", zone_entity(house, a, "button", "resume"))
    assert house.states.get(ca).attributes["temperature"] == 21


async def test_household_vacation_return_form_and_expiry_preserve_control(house):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    a, ca = await add_zone(house, "a")
    b, cb = await add_zone(house, "b")
    for entry, climate in ((a, ca), (b, cb)):
        await add_schedule(house, entry)
        await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "schedule"))
        await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    manager = house.data[DOMAIN]
    until = dt_util.as_local(dt_util.utcnow() + timedelta(days=2)).replace(microsecond=0)
    flow = await house.config_entries.options.async_init(manager.hub)
    assert flow["type"] == "menu" and flow["menu_options"] == [
        "hardware",
        "solar_source",
        "hydraulic",
        "vacation",
    ]
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "vacation"}
    )
    result = await house.config_entries.options.async_configure(
        flow["flow_id"],
        {"enabled": True, "date": until.date().isoformat(), "time": until.strftime("%H:%M:%S")},
    )
    assert result["type"] == "create_entry", result
    await settle(house)
    assert manager.enabled
    assert all(z.program.away_until == dt_util.as_utc(until) for z in manager.zones.values())
    control = er.async_get(house).async_get_entity_id(
        "switch", DOMAIN, f"{manager.hub}_household_away"
    )
    assert house.states.get(control).attributes["return_at"] == dt_util.as_utc(until).isoformat()
    for zone in manager.zones.values():
        zone.program.away_until = dt_util.utcnow() - timedelta(seconds=1)
    await settle(house)
    assert house.states.get(control).state == "off"
    assert all(house.states.get(c).attributes["control_state"] == "scheduled" for c in (ca, cb))
    assert all(house.states.get(c).attributes["temperature"] == 21 for c in (ca, cb))
    assert manager.enabled


async def test_weather_and_outdoor_failure_degrade_to_interior_control(house):
    from datetime import timedelta

    from homeassistant.core import SupportsResponse
    from homeassistant.util import dt as dt_util

    calls = []

    async def forecast(call):
        calls.append(call.data["entity_id"])
        return {
            "weather.fixture": {
                "forecast": [
                    {
                        "datetime": (dt_util.utcnow() + timedelta(hours=1)).isoformat(),
                        "temperature": 12,
                        "cloud_coverage": 20,
                    }
                ]
            }
        }

    house.services.async_register(
        "weather", "get_forecasts", forecast, supports_response=SupportsResponse.ONLY
    )
    house.states.async_set(
        "weather.fixture",
        "sunny",
        {"temperature": 10, "temperature_unit": "°C", "supported_features": 2},
    )
    house.states.async_set("sensor.fixture_outdoor", "10", {"unit_of_measurement": "°C"})
    entry, climate = await add_zone(house)
    await configure_sources(
        house, entry, weather="weather.fixture", outdoor="sensor.fixture_outdoor"
    )
    for key in ("weather", "outside"):
        await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", key))
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    assert calls == ["weather.fixture"]
    assert house.states.get("switch.fixture_a").state == "on"
    house.states.async_set("weather.fixture", "unavailable")
    house.states.async_set("sensor.fixture_outdoor", "unavailable")
    await settle(house)
    assert house.states.get("switch.fixture_a").state == "on"
    assert house.states.get(climate).attributes["weather_status"] == "unavailable"
    assert not house.states.get(climate).attributes["outside_available"]
    for key in ("weather", "outside"):
        await service(house, "switch", "turn_off", zone_entity(house, entry, "switch", key))
    assert house.states.get("switch.fixture_a").state == "on"


async def test_provider_change_and_unsupported_hourly_forecast(house):
    house.states.async_set("weather.fixture_one", "cloudy", {"supported_features": 0})
    house.states.async_set("weather.fixture_two", "sunny", {"supported_features": 0})
    entry, climate = await add_zone(house)
    await configure_sources(house, entry, weather="weather.fixture_one")
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "weather"))
    assert house.states.get(climate).attributes["weather_status"] == "hourly_not_supported"
    await configure_sources(house, entry, weather="weather.fixture_two")
    assert (
        house.data[DOMAIN].source(house.data[DOMAIN].zones[entry.entry_id], "weather")
        == "weather.fixture_two"
    )
    assert house.states.get(climate).attributes["weather_status"] == "hourly_not_supported"


async def test_solar_observation_active_and_manual_priority(house):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    entry, climate = await add_zone(house)
    house.states.async_set("sun.sun", "above_horizon", {"azimuth": 135, "elevation": 30})
    await configure_sources(house, entry, orientation=135, solar_elevation=20, solar_confirmed=True)
    # Geometry changes require confirmation of the unchanged new values.
    await configure_sources(house, entry, solar_confirmed=True)
    await service(
        house,
        "select",
        "select_option",
        zone_entity(house, entry, "select", "solar"),
        option="observe",
    )
    await service(house, "climate", "set_temperature", climate, temperature=22)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    now = dt_util.utcnow()
    model = house.data[DOMAIN].zones[entry.entry_id].intelligence.model
    model.points = [
        (now - timedelta(minutes=30), 21.3),
        (now - timedelta(minutes=15), 21.6),
        (now - timedelta(seconds=1), 21.9),
    ]
    house.states.async_set("sensor.fixture_a", "21.9", {"unit_of_measurement": "°C"})
    await settle(house)
    assert house.states.get("switch.fixture_a").state == "on"
    assert house.states.get(climate).attributes["solar_candidate"]
    await service(
        house,
        "select",
        "select_option",
        zone_entity(house, entry, "select", "solar"),
        option="active",
    )
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get(climate).attributes["reason"] == "solar_pause"
    await add_schedule(house, entry)
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "schedule"))
    await service(house, "climate", "set_temperature", climate, temperature=22.5)
    assert house.states.get(climate).attributes["control_state"] == "manual"
    assert house.states.get(climate).attributes["temperature"] == 22.5
    assert house.states.get("switch.fixture_a").state == "on"


async def test_unconfirmed_solar_cannot_be_activated(house):
    entry, _ = await add_zone(house)
    with pytest.raises(ValueError, match="exposure"):
        await house.data[DOMAIN].async_feature(entry.entry_id, "solar", "active")
    assert house.data[DOMAIN].zones[entry.entry_id].intelligence.features.solar == "off"


@pytest.mark.parametrize(
    "mode,current,home,beyond", [("heat", 20, 22, 20.3), ("cool", 27, 25, 26.7)]
)
async def test_anticipation_requires_model_and_preserves_displayed_comfort_target(
    house, mode, current, home, beyond
):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    from custom_components.radiant_climate.core.intelligence import Statistics

    entry, climate = await add_zone(house)
    z = house.data[DOMAIN].zones[entry.entry_id]
    now = dt_util.as_local(dt_util.utcnow())
    later = now + timedelta(minutes=30)
    z.program.set_blocks([now.weekday()], now.hour * 60 + now.minute, "eco")
    z.program.set_blocks([later.weekday()], later.hour * 60 + later.minute, "home")
    z.program.profiles[mode].update(eco=current, home=home)
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "schedule"))
    house.states.async_set("sensor.fixture_a", str(current), {"unit_of_measurement": "°C"})
    await house.data[DOMAIN].async_supply(mode)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode=mode)
    await service(house, "switch", "turn_on", global_entity(house))
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "anticipation"))
    assert house.states.get("switch.fixture_a").state == "off"
    z.intelligence.model.statistics[f"{mode}_on"] = Statistics(
        count=12, hours=6, delta=3, rate_square=1.5, episodes=3
    )
    await settle(house)
    assert house.states.get(climate).attributes["temperature"] == current
    assert house.states.get(climate).attributes["control_target"] == home
    assert house.states.get(climate).attributes["reason"] == "anticipation"
    assert house.states.get("switch.fixture_a").state == "on"
    # Outside the base hysteresis band, disabling anticipation must close.
    house.states.async_set("sensor.fixture_a", str(beyond), {"unit_of_measurement": "°C"})
    await settle(house)
    await service(house, "switch", "turn_off", zone_entity(house, entry, "switch", "anticipation"))
    assert house.states.get("switch.fixture_a").state == "off"


async def test_away_manual_and_expiry_without_enabling_off_zone(house):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    entry, climate = await add_zone(house)
    await service(house, "climate", "set_preset_mode", climate, preset_mode="away")
    assert house.states.get(zone_entity(house, entry, "switch", "away")).state == "on"
    assert house.states.get(climate).state == "off"
    assert house.states.get(climate).attributes["temperature"] == 17
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "climate", "set_temperature", climate, temperature=22)
    assert house.states.get(climate).attributes["control_state"] == "manual"
    z = house.data[DOMAIN].zones[entry.entry_id]
    z.intent.hold.until = dt_util.utcnow() - timedelta(seconds=1)
    await settle(house)
    assert house.states.get(climate).attributes["temperature"] == 17
    await house.data[DOMAIN].async_away(
        entry.entry_id, True, dt_util.utcnow() - timedelta(seconds=1)
    )
    assert not z.program.away
    assert house.states.get(climate).attributes["control_state"] == "fixed"


async def test_estimated_inlet_opening_does_not_claim_physical_position(house):
    _, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    manager.entries[manager.hub]["general_travel"] = 120
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    assert house.states.get("switch.fixture_general").state == "on"
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get(climate).attributes["reason"] == "general_opening_estimated"
    assert house.states.get(climate).attributes["valve_position"] == "not_measured"


async def test_same_supply_mode_does_not_cancel_manual(house):
    entry, climate = await add_zone(house)
    await add_schedule(house, entry)
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "schedule"))
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "climate", "set_temperature", climate, temperature=22)
    deadline = house.states.get(climate).attributes["manual_until"]
    await house.data[DOMAIN].async_supply("heat")
    await settle(house)
    assert house.states.get(climate).attributes["manual_until"] == deadline


async def test_cooling_predictive_pause_and_disabling_returns_to_basic(house):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    from custom_components.radiant_climate.core.intelligence import Statistics

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    await manager.async_supply("cool")
    house.states.async_set("sensor.fixture_a", "28", {"unit_of_measurement": "°C"})
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="cool")
    await service(house, "switch", "turn_on", global_entity(house))
    z = manager.zones[entry.entry_id]
    z.intelligence.model.statistics["cool_on"] = Statistics(
        count=12, hours=6, delta=3, rate_square=1.5, episodes=3
    )
    now = dt_util.utcnow()
    z.intelligence.model.points = [
        (now - timedelta(minutes=30), 25.7),
        (now - timedelta(minutes=15), 25.4),
        (now - timedelta(seconds=1), 25.1),
    ]
    house.states.async_set("sensor.fixture_a", "25.1", {"unit_of_measurement": "°C"})
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "predictive"))
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get(climate).attributes["reason"] == "predictive_pause"
    house.states.async_set("sensor.fixture_a", "25.5", {"unit_of_measurement": "°C"})
    await service(house, "switch", "turn_off", zone_entity(house, entry, "switch", "predictive"))
    assert house.states.get("switch.fixture_a").state == "on"


async def test_repeated_output_deviations_isolate_zone_and_persist(house):
    from custom_components.radiant_climate.runtime import Installation

    await add_zone(house, "a")
    _, climate_b = await add_zone(house, "b")
    await service(house, "climate", "set_hvac_mode", climate_b, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    for attempt in range(2):
        await service(house, "input_boolean", "turn_on", "input_boolean.fixture_a")
        if attempt == 0:
            assert house.states.get("switch.fixture_a").state == "off"
    manager = house.data[DOMAIN]
    assert "switch.fixture_a" in manager._command_faults
    # Recovery can now confirm A off; B may continue once A is isolated.
    # The fault remains latched, so A cannot reopen without explicit review.
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get("switch.fixture_general").state == "on"
    assert house.states.get("switch.fixture_b").state == "on"
    restored = Installation(house)
    try:
        await restored.async_load()
        assert "switch.fixture_a" in restored._command_faults
    finally:
        restored.async_stop()
    await service(house, "switch", "turn_off", global_entity(house))
    assert "switch.fixture_a" in manager._command_faults
    assert house.states.get("switch.fixture_a").state == "off"
    await house.services.async_call(
        DOMAIN, "reset_actuator_faults", {"confirmed_review": True}, blocking=True
    )
    assert not manager._command_faults


async def test_sustained_unknown_zone_output_blocks_shared_supply_then_recovers(house):
    await add_zone(house, "a")
    _, climate_b = await add_zone(house, "b")
    await service(house, "climate", "set_hvac_mode", climate_b, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    house.states.async_set("switch.fixture_a", "unavailable")
    for _ in range(3):
        await settle(house)
        assert house.states.get("switch.fixture_general").state == "off"
        assert house.states.get("switch.fixture_b").state == "off"
    house.states.async_set("switch.fixture_a", "off")
    await settle(house)
    assert house.states.get("switch.fixture_b").state == "on"


async def test_forecast_failure_has_bounded_retry_without_blocking_control(house):
    from homeassistant.core import SupportsResponse
    from homeassistant.exceptions import HomeAssistantError

    calls = []

    async def failure(call):
        calls.append(True)
        raise HomeAssistantError("Explicit forecast failure fixture")

    house.services.async_register(
        "weather", "get_forecasts", failure, supports_response=SupportsResponse.ONLY
    )
    house.states.async_set("weather.fixture", "sunny", {"supported_features": 2})
    environment = house.data[DOMAIN].environment
    await environment.refresh({"weather.fixture"})
    await environment.refresh({"weather.fixture"})
    assert calls == [True]
    assert environment.status["weather.fixture"] == "forecast_unavailable"


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        (32, "°F", 0),
        (273.15, "K", 0),
        (10, "°C", 10),
        (None, "°C", None),
        (True, "°C", None),
        ("bad", "°C", None),
        (20, "unknown", None),
    ],
)
def test_optional_temperature_conversion_rejects_invalid_data(value, unit, expected):
    from custom_components.radiant_climate.environment import celsius

    assert celsius(value, unit) == expected


@pytest.mark.parametrize(
    "scenario",
    [
        "duration",
        "until_resume",
        "expired",
        "individual_off",
        "household_away",
        "retired",
        "preset",
        "sparse_learning",
    ],
)
async def test_full_core_restart_restores_control_without_bypassing_off(house, scenario):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    entry, climate = await add_zone(house)
    await add_schedule(house, entry)
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "schedule"))
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    if scenario == "until_resume":
        await service(
            house,
            "select",
            "select_option",
            zone_entity(house, entry, "select", "manual_policy"),
            option="until_resume",
        )
    await service(house, "climate", "set_temperature", climate, temperature=22)
    if scenario == "preset":
        house.data[DOMAIN].zones[entry.entry_id].program.profiles["heat"]["eco"] = 22
        await service(house, "climate", "set_preset_mode", climate, preset_mode="eco")
    if scenario == "household_away":
        await add_zone(house, "b")
        await house.data[DOMAIN].async_away_all(True)
        await service(house, "climate", "set_temperature", climate, temperature=22)
    if scenario == "retired":
        manager = house.data[DOMAIN]
        await manager.async_change(
            lambda: manager._retired.update({"switch.fixture_disconnected": 120})
        )
        await service(house, "switch", "turn_on", global_entity(house))
    if scenario == "expired":
        house.data[DOMAIN].zones[entry.entry_id].intent.hold.until = dt_util.utcnow() - timedelta(
            seconds=1
        )
    if scenario == "individual_off":
        await service(house, "climate", "turn_off", climate)
        await service(house, "switch", "turn_on", global_entity(house))
    if scenario == "sparse_learning":
        from custom_components.radiant_climate.core.control import Mode
        from custom_components.radiant_climate.core.intelligence import ThermalModel

        # An explicit synthetic response, persisted by Core's real Store.
        model = ThermalModel()
        now = dt_util.utcnow()
        for minutes, value in ((-45, 20), (0, 20.375)):
            model.observe(
                now + timedelta(minutes=minutes),
                value,
                Mode.HEAT,
                True,
                eligible=True,
                learning=True,
            )
        zone = house.data[DOMAIN].zones[entry.entry_id]
        zone.intelligence.model = model
        zone.intelligence.features.learning = True
        assert model.statistics["heat_on"].count == 1 and model.anchor is not None
    config = house.data["radiant_fixture_boot_config"]
    config_dir = house.config.config_dir
    await house.async_stop()
    restarted = HomeAssistant(config_dir)
    async_setup_loader(restarted)
    try:
        restarted.config_entries = ConfigEntries(restarted, config)
        assert await async_load_base_functionality(restarted)
        await async_process_ha_core_config(restarted, {})
        for domain in (
            "homeassistant",
            "persistent_notification",
            "input_boolean",
            "template",
            DOMAIN,
        ):
            assert await async_setup_component(restarted, domain, config)
        for key in ("a", "b"):
            restarted.states.async_set(f"sensor.fixture_{key}", "19", {"unit_of_measurement": "°C"})
        await restarted.async_block_till_done()
        for stored in restarted.config_entries.async_entries(DOMAIN):
            if stored.state.value != "loaded":
                assert await restarted.config_entries.async_setup(stored.entry_id)
        await restarted.async_start()
        await settle(restarted)
        state = restarted.states.get(climate)
        assert state is not None
        assert state.state == ("heat" if scenario == "retired" else "off")
        if scenario == "preset":
            assert state.attributes["preset_mode"] == "eco"
        assert restarted.states.get("switch.fixture_a").state == "off"
        assert restarted.states.get("switch.fixture_general").state == "off"
        if scenario == "sparse_learning":
            zone = restarted.data[DOMAIN].zones[entry.entry_id]
            model = zone.intelligence.model
            assert zone.intelligence.features.learning
            assert model.statistics["heat_on"].count == 1
            assert model.statistics["heat_on"].hours == pytest.approx(0.75)
            assert model.anchor is None and not model.points
        if scenario == "retired":
            assert restarted.data[DOMAIN]._retired == {"switch.fixture_disconnected": 120}
            assert state.attributes["reason"] == "retired_actuator_pending"
        if scenario == "household_away":
            manager = restarted.data[DOMAIN]
            assert all(z.program.away for z in manager.zones.values())
            assert (
                restarted.states.get(
                    er.async_get(restarted).async_get_entity_id(
                        "switch", DOMAIN, f"{manager.hub}_household_away"
                    )
                ).state
                == "on"
            )
            assert (
                next(
                    z for key, z in manager.zones.items() if key != entry.entry_id
                ).intent.mode.value
                == "off"
            )
        if scenario == "expired":
            assert state.attributes["temperature"] == 21
            assert state.attributes["control_state"] == "scheduled"
        elif scenario == "individual_off":
            assert restarted.data[DOMAIN].enabled
            assert state.attributes["control_state"] == "off"
        else:
            assert state.attributes["temperature"] == 22
            assert state.attributes["control_state"] == "manual"
            assert (state.attributes["manual_until"] is None) == (scenario == "until_resume")
    finally:
        await restarted.async_stop()


@pytest.mark.parametrize("output", ["a", "general"])
async def test_faulted_output_can_close_but_cannot_reopen(house, output):
    from unittest.mock import patch

    await add_zone(house)
    manager = house.data[DOMAIN]
    entity = f"switch.fixture_{output}"
    with patch.object(manager, "_request_update"):
        manager._command_faults.add(entity)
        await house.services.async_call(
            "input_boolean",
            "turn_on",
            {"entity_id": f"input_boolean.fixture_{output}"},
            blocking=True,
        )
        await house.async_block_till_done()
        assert await manager._command(entity, False)
        assert house.states.get(entity).state == "off"
        assert not await manager._command(entity, True)
        assert entity in manager._command_faults
    await manager.async_enable(False)


async def test_close_recovery_is_bounded_and_persisted(house):
    from datetime import timedelta
    from unittest.mock import patch

    from homeassistant.util import dt as dt_util

    from custom_components.radiant_climate.runtime import Installation

    await add_zone(house)
    manager = house.data[DOMAIN]
    original = type(house.services).async_call
    commands = []

    async def ignore_close(registry, domain, service, service_data=None, *args, **kwargs):
        if (
            domain == "switch"
            and service == "turn_off"
            and service_data["entity_id"] == "switch.fixture_a"
        ):
            commands.append(service)
            return None
        return await original(registry, domain, service, service_data, *args, **kwargs)

    with patch.object(manager, "_request_update"):
        await house.services.async_call(
            "input_boolean", "turn_on", {"entity_id": "input_boolean.fixture_a"}, blocking=True
        )
        await house.async_block_till_done()
        manager._command_faults.add("switch.fixture_a")
        with patch.object(type(house.services), "async_call", new=ignore_close):
            for _ in range(4):
                if previous := manager._close_recovery.get("switch.fixture_a"):
                    manager._close_recovery["switch.fixture_a"] = (
                        previous[0],
                        dt_util.utcnow() - timedelta(seconds=31),
                    )
                assert not await manager._command("switch.fixture_a", False)
        assert len(commands) == 2
        await manager._save()
        restored = Installation(house)
        try:
            await restored.async_load()
            assert restored._close_recovery["switch.fixture_a"][0] == 2
            assert "switch.fixture_a" in restored._command_faults
        finally:
            restored.async_stop()
    await manager.async_enable(False)


@pytest.mark.parametrize("operation", ["replace", "remove", "general"])
async def test_retired_output_blocks_supply_until_isolated(house, operation):
    a, ca = await add_zone(house)
    if operation == "remove":
        _, cb = await add_zone(house, "b")
        await service(house, "climate", "set_hvac_mode", cb, hvac_mode="heat")
    await service(house, "climate", "set_hvac_mode", ca, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    old = "switch.fixture_general" if operation == "general" else "switch.fixture_a"
    house.states.async_set(old, "unavailable")
    await settle(house)
    manager = house.data[DOMAIN]
    if operation == "remove":
        assert await house.config_entries.async_remove(a.entry_id)
    else:
        entry_id = manager.hub if operation == "general" else a.entry_id
        flow = await house.config_entries.options.async_init(entry_id)
        flow = await house.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "hardware"}
        )
        data = (
            {"general": "switch.fixture_b", "general_travel": 0}
            if operation == "general"
            else {
                "sensor": "sensor.fixture_a",
                "actuators": ["switch.fixture_b"],
                "available_modes": "heat_cool",
                "target": 21,
                "minimum_on": 0,
                "minimum_off": 0,
            }
        )
        result = await house.config_entries.options.async_configure(flow["flow_id"], data)
        assert result["type"] == "create_entry", result
    await settle(house)
    assert old in manager._retired
    assert house.states.get("switch.fixture_b").state == "off"
    assert house.states.get("switch.fixture_general").state in ("off", "unavailable")
    await manager.async_enable(True)
    assert house.states.get("switch.fixture_b").state == "off"
    await house.services.async_call(
        "input_boolean",
        "turn_off",
        {"entity_id": "input_boolean.fixture_" + ("general" if operation == "general" else "a")},
        blocking=True,
    )
    await settle(house)
    assert old not in manager._retired
    assert house.states.get("switch.fixture_b").state == "on"


async def test_retired_acknowledgment_requires_off_and_unassigned_output(house):
    await add_zone(house)
    manager = house.data[DOMAIN]
    await manager.async_change(lambda: manager._retired.update({"switch.fixture_missing": 0}))
    await manager.async_enable(True)
    with pytest.raises(ValueError, match="Switch off"):
        await manager.async_acknowledge_retired("switch.fixture_missing")
    await manager.async_enable(False)
    manager._retired["switch.fixture_a"] = 120
    with pytest.raises(ValueError, match="unassigned"):
        await manager.async_acknowledge_retired("switch.fixture_a")
    await house.services.async_call(
        DOMAIN,
        "acknowledge_retired_actuator",
        {"actuator": "switch.fixture_missing", "confirmed_disconnected": True},
        blocking=True,
    )
    assert "switch.fixture_missing" not in manager._retired


async def test_retired_general_waits_for_closing_time_before_reopening(house):
    from datetime import timedelta
    from unittest.mock import patch

    from homeassistant.util import dt as dt_util

    _, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await manager.async_enable(True)
    await settle(house)
    await manager.async_enable(False)
    await manager.async_change(lambda: manager._retired.update({"switch.fixture_general": 120}))
    await manager.async_enable(True)
    assert "switch.fixture_general" in manager._retired
    assert house.states.get("switch.fixture_general").state == "off"
    assert house.states.get(climate).attributes["reason"] == "retired_actuator_pending"
    later = dt_util.utcnow() + timedelta(seconds=121)
    with patch.object(dt_util, "utcnow", return_value=later):
        await settle(house)
        assert not manager._retired
        assert house.states.get("switch.fixture_general").state == "on"


async def test_faulted_inlet_is_closed_even_while_zones_request_heat(house):
    _, climate = await add_zone(house)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    manager = house.data[DOMAIN]
    manager._command_faults.add("switch.fixture_general")
    await settle(house)
    assert house.states.get("switch.fixture_general").state == "off"
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get(climate).attributes["requested_mode"] == "heat"
    assert "switch.fixture_general" in manager._command_faults
    await manager.async_enable(False)


@pytest.mark.parametrize("action", ["global_off", "season", "individual_off"])
async def test_queued_stop_prevents_additional_opens_after_slow_command(house, action):
    import asyncio
    from unittest.mock import patch

    from custom_components.radiant_climate.core.control import Mode

    a, ca = await add_zone(house)
    manager = house.data[DOMAIN]
    zone = manager.zones[a.entry_id]
    zone.config["actuators"].append("switch.fixture_b")  # Two genuine fixture switch entities.
    await service(house, "climate", "set_hvac_mode", ca, hvac_mode="heat")
    began, release = asyncio.Event(), asyncio.Event()
    original = type(house.services).async_call
    opened = []

    async def slow(registry, domain, service, service_data=None, *args, **kwargs):
        if domain == "switch" and service == "turn_on":
            opened.append(service_data["entity_id"])
            if service_data["entity_id"] == "switch.fixture_a":
                began.set()
                await release.wait()
        return await original(registry, domain, service, service_data, *args, **kwargs)

    with patch.object(type(house.services), "async_call", new=slow):
        start = house.async_create_task(manager.async_enable(True))
        await asyncio.wait_for(began.wait(), 2)
        command = (
            manager.async_enable(False)
            if action == "global_off"
            else (
                manager.async_supply("cool")
                if action == "season"
                else manager.async_change(lambda: zone.intent.set_mode(Mode.OFF, zone.settings))
            )
        )
        stop = house.async_create_task(command)
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(start, stop)
    await settle(house)
    assert "switch.fixture_b" not in opened
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get("switch.fixture_general").state == "off"


async def test_copy_schedule_and_anticipation_validate_final_candidate(house):
    a, ca = await add_zone(house)
    b, cb = await add_zone(house, "b")
    await add_schedule(house, a)
    await house.data[DOMAIN].async_feature(a.entry_id, "anticipation", True)
    await house.services.async_call(
        DOMAIN,
        "copy_settings",
        {"source": ca, "targets": [cb], "parts": ["schedule", "modules"]},
        blocking=True,
    )
    manager = house.data[DOMAIN]
    assert manager.zones[b.entry_id].program.blocks == manager.zones[a.entry_id].program.blocks
    assert manager.zones[b.entry_id].intelligence.features.anticipation


async def test_failed_multi_zone_copy_does_not_mutate_other_destinations(house):
    a, ca = await add_zone(house)
    b, cb = await add_zone(house, "b")
    house.states.async_set("sensor.fixture_c", "19", {"unit_of_measurement": "°C"})
    house.states.async_set("switch.fixture_c", "off")  # No commands: this fixture remains off.
    c, cc = await add_zone(house, "c")
    manager = house.data[DOMAIN]
    manager.zones[a.entry_id].config["solar_confirmed"] = True
    manager.zones[b.entry_id].config["solar_confirmed"] = True
    await manager.async_feature(a.entry_id, "solar", "active")
    manager.zones[a.entry_id].program.profiles["heat"]["home"] = 23
    before = {e.entry_id: manager.zones[e.entry_id].program.dump() for e in (b, c)}
    with pytest.raises(ValueError, match="exposure"):
        await house.services.async_call(
            DOMAIN,
            "copy_settings",
            {"source": ca, "targets": [cb, cc], "parts": ["temperatures", "modules"]},
            blocking=True,
        )
    assert all(manager.zones[e.entry_id].program.dump() == before[e.entry_id] for e in (b, c))


async def test_last_enabled_schedule_block_cannot_be_removed_silently(house):
    a, ca = await add_zone(house)
    manager = house.data[DOMAIN]
    await manager.async_edit_schedule(a.entry_id, lambda p: p.set_blocks([0], 0, "home"))
    await service(house, "switch", "turn_on", zone_entity(house, a, "switch", "schedule"))
    await service(house, "climate", "set_temperature", ca, temperature=22)
    flow = await house.config_entries.options.async_init(a.entry_id)
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "schedule_remove"}
    )
    token = next(
        value.config["options"][0]["value"]
        for key, value in flow["data_schema"].schema.items()
        if str(key) == "block"
    )
    result = await house.config_entries.options.async_configure(flow["flow_id"], {"block": token})
    assert result["type"] == "form" and result["errors"] == {"base": "schedule_in_use"}
    assert len(manager.zones[a.entry_id].program.blocks) == 1
    assert house.states.get(ca).attributes["temperature"] == 22
    await service(house, "switch", "turn_off", zone_entity(house, a, "switch", "schedule"))
    result = await house.config_entries.options.async_configure(flow["flow_id"], {"block": token})
    assert result["type"] == "create_entry", result
    await settle(house)
    assert not manager.zones[a.entry_id].program.blocks
    await service(house, "climate", "set_temperature", ca, temperature=23)
    assert house.states.get(ca).attributes["temperature"] == 23


@pytest.mark.parametrize("failure", ["exception", "timeout", "unconfirmed"])
async def test_second_zone_channel_failure_closes_partial_open_in_same_pass(house, caplog, failure):
    from datetime import timedelta
    from unittest.mock import patch

    from homeassistant.exceptions import HomeAssistantError
    from homeassistant.util import dt as dt_util

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    zone = manager.zones[entry.entry_id]
    zone.config["actuators"] = ["switch.fixture_a", "switch.fixture_b"]
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    original = type(house.services).async_call
    commands = []

    async def fail_second(registry, domain, service, service_data=None, *args, **kwargs):
        if domain == "switch":
            commands.append((service, service_data["entity_id"]))
            if service == "turn_on" and service_data["entity_id"] == "switch.fixture_b":
                raise (
                    HomeAssistantError("Simulated second-channel failure")
                    if failure == "exception"
                    else TimeoutError()
                )
        return await original(registry, domain, service, service_data, *args, **kwargs)

    # A already opened in the previous pass. Suppress event-driven retries so
    # this assertion cannot accidentally pass because of a subsequent tick.
    with patch.object(manager, "_request_update"):
        await house.services.async_call(
            "input_boolean",
            "turn_on",
            {"entity_id": ["input_boolean.fixture_a", "input_boolean.fixture_general"]},
            blocking=True,
        )
        await house.async_block_till_done()
        manager.enabled = True
        if failure == "unconfirmed":
            manager._last_command["switch.fixture_b"] = (
                True,
                dt_util.utcnow() - timedelta(seconds=31),
            )
        with patch.object(type(house.services), "async_call", new=fail_second):
            await manager._apply()
        assert ("turn_off", "switch.fixture_a") in commands
        assert ("turn_off", "switch.fixture_general") in commands
        assert "switch.fixture_b" in manager._command_faults
        assert not zone.decision.demand
        assert house.states.get("switch.fixture_a").state == "off"
        assert house.states.get("switch.fixture_general").state == "off"
    expected = "did not report" if failure == "unconfirmed" else "command failed"
    assert expected in caplog.text
    caplog.clear()  # The simulated command failure above is the expected error.
    await manager.async_enable(False)


@pytest.mark.parametrize("operation", ["zone", "general", "replacement"])
async def test_retirement_is_durable_before_first_close_even_if_interrupted(house, operation):
    import asyncio
    from unittest.mock import patch

    from custom_components.radiant_climate.const import PLATFORMS
    from custom_components.radiant_climate.runtime import Installation

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    manager.zones[entry.entry_id].config["valve_travel"] = 120
    manager.entries[manager.hub]["general_closing"] = 120
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    old = "switch.fixture_general" if operation == "general" else "switch.fixture_a"
    if operation == "zone":
        # Match HA's actual lifecycle: entity listeners are unloaded before the
        # manager removes a zone. This test interrupts the following I/O step.
        assert await house.config_entries.async_unload_platforms(entry, PLATFORMS)

    async def interrupted(entity, wanted):
        assert not wanted
        saved = await manager._store.async_load()
        assert old in saved["retired_actuators"]
        raise asyncio.CancelledError

    with (
        patch.object(manager, "_request_update"),
        patch.object(manager, "_command", new=interrupted),
    ):
        with pytest.raises(asyncio.CancelledError):
            if operation == "replacement":
                flow = await house.config_entries.options.async_init(entry.entry_id)
                flow = await house.config_entries.options.async_configure(
                    flow["flow_id"], {"next_step_id": "hardware"}
                )
                await house.config_entries.options.async_configure(
                    flow["flow_id"],
                    {
                        "sensor": "sensor.fixture_a",
                        "actuators": ["switch.fixture_b"],
                        "available_modes": "heat_cool",
                        "target": 21,
                    },
                )
            else:
                await manager.async_remove(
                    manager.hub if operation == "general" else entry.entry_id
                )
    manager.enabled = False
    restored = Installation(house)
    try:
        await restored.async_load()
        assert restored._retired[old] == 120
        # A fresh process retains the guard even if the original entry is gone.
        assert restored._retired
        for configured in house.config_entries.async_entries(DOMAIN):
            await restored.async_add(configured)
        await restored.async_reconcile()
        assert house.states.get("switch.fixture_a").state == "off"
        assert house.states.get("switch.fixture_b").state == "off"
        assert house.states.get("switch.fixture_general").state == "off"
        assert old in restored._retired
    finally:
        restored.async_stop()
    manager.enabled = False


@pytest.mark.parametrize("kind", ["sources", "regulation", "installation"])
async def test_logical_options_keep_entities_learning_and_outputs_running(house, kind):
    from unittest.mock import patch

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    zone = manager.zones[entry.entry_id]
    model = zone.intelligence.model
    await manager.async_change(lambda: setattr(model, "rejected", 7))
    flow = await house.config_entries.options.async_init(
        manager.hub if kind == "installation" else entry.entry_id
    )
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "sources" if kind == "sources" else "hardware"}
    )
    data = (
        {
            "orientation": 120,
            "solar_elevation": 20,
            "solar_width": 60,
            "max_advance": 90,
            "residual_minutes": 15,
            "solar_confirmed": False,
        }
        if kind == "sources"
        else (
            {"general": "switch.fixture_general", "general_travel": 0, "general_closing": 120}
            if kind == "installation"
            else {
                "sensor": "sensor.fixture_a",
                "actuators": ["switch.fixture_a"],
                "available_modes": "heat_cool",
                "target": 21,
                "minimum_on": 0,
                "minimum_off": 0,
                "hysteresis": 0.3,
            }
        )
    )
    original = type(house.services).async_call
    closes = []

    async def record(registry, domain, service, service_data=None, *args, **kwargs):
        if domain == "switch" and service == "turn_off":
            closes.append(service_data)
        return await original(registry, domain, service, service_data, *args, **kwargs)

    with (
        patch.object(manager, "async_remove", wraps=manager.async_remove) as remove,
        patch.object(type(house.services), "async_call", new=record),
    ):
        result = await house.config_entries.options.async_configure(flow["flow_id"], data)
        assert result["type"] == "create_entry", result
        await settle(house)
        remove.assert_not_called()
        assert not closes
    assert manager.zones[entry.entry_id] is zone
    assert zone.intelligence.model is model and model.rejected == 7
    assert not manager._retired and manager.enabled
    assert house.states.get("switch.fixture_a").state == "on"
    assert house.states.get("switch.fixture_general").state == "on"
    if kind == "regulation":
        assert zone.settings.hysteresis == 0.3


async def test_normal_off_does_not_acknowledge_faults_and_review_never_opens(house):
    from custom_components.radiant_climate.runtime import Installation

    _, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await manager.async_change(lambda: manager._command_faults.add("switch.fixture_a"))
    await manager.async_enable(False)
    await manager.async_enable(True)
    await settle(house)
    assert "switch.fixture_a" in manager._command_faults
    assert house.states.get("switch.fixture_a").state == "off"
    with pytest.raises(ValueError, match="Switch off"):
        await manager.async_reset_actuator_faults([])
    await manager.async_enable(False)
    restored = Installation(house)
    try:
        await restored.async_load()
        assert "switch.fixture_a" in restored._command_faults
    finally:
        restored.async_stop()
    await house.services.async_call(
        DOMAIN, "reset_actuator_faults", {"confirmed_review": True}, blocking=True
    )
    assert not manager._command_faults
    assert not manager.enabled
    assert house.states.get("switch.fixture_a").state == "off"
    await manager.async_enable(True)
    await settle(house)
    assert house.states.get("switch.fixture_a").state == "on"


@pytest.mark.parametrize("state", ["on", "unavailable", "unknown"])
async def test_fault_review_requires_reported_off(house, state):
    from unittest.mock import patch

    await add_zone(house)
    manager = house.data[DOMAIN]
    with patch.object(manager, "_request_update"):
        house.states.async_set("switch.fixture_a", state)
        manager._command_faults.add("switch.fixture_a")
        with pytest.raises(ValueError, match="reported off"):
            await manager.async_reset_actuator_faults([])
        assert "switch.fixture_a" in manager._command_faults


async def test_failed_retirement_journal_does_not_commit_new_assignment(house):
    from unittest.mock import patch

    entry, _ = await add_zone(house)
    manager = house.data[DOMAIN]
    before = dict(entry.options)
    flow = await house.config_entries.options.async_init(entry.entry_id)
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "hardware"}
    )
    with patch.object(
        manager._store, "async_save", side_effect=OSError("Simulated storage failure")
    ):
        with pytest.raises(OSError, match="storage failure"):
            await house.config_entries.options.async_configure(
                flow["flow_id"],
                {
                    "sensor": "sensor.fixture_a",
                    "actuators": ["switch.fixture_b"],
                    "available_modes": "heat_cool",
                    "target": 21,
                },
            )
    assert dict(entry.options) == before
    assert not manager.enabled
    assert house.states.get("switch.fixture_b").state == "off"


async def test_fault_acknowledgment_is_admin_only(house):
    from homeassistant.core import Context
    from homeassistant.exceptions import Unauthorized

    await add_zone(house)
    manager = house.data[DOMAIN]
    await manager.async_change(lambda: manager._command_faults.add("switch.fixture_a"))
    await house.auth.async_create_user("Fixture owner")
    user = await house.auth.async_create_user("Fixture non-admin")
    assert not user.is_admin
    with pytest.raises(Unauthorized):
        await house.services.async_call(
            DOMAIN,
            "reset_actuator_faults",
            {"confirmed_review": True},
            blocking=True,
            context=Context(user_id=user.id),
        )
    assert "switch.fixture_a" in manager._command_faults


@pytest.mark.parametrize(
    "outcome",
    [
        "delayed",
        "missing",
        "missing_reports",
        "global_off",
        "sensor_loss",
        "window_open",
        "shutdown",
    ],
)
async def test_initial_unconfirmed_second_channel_is_bounded_and_interruptible(
    house, caplog, outcome
):
    import asyncio
    from unittest.mock import patch

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    zone = manager.zones[entry.entry_id]
    zone.config["actuators"] = ["switch.fixture_a", "switch.fixture_b"]
    house.states.async_set("binary_sensor.fixture_window", "off")
    zone.config["window"] = "binary_sensor.fixture_window"
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    original = type(house.services).async_call
    began = asyncio.Event()
    commands = []

    async def delayed(registry, domain, service, service_data=None, *args, **kwargs):
        if domain == "switch":
            commands.append((service, service_data["entity_id"]))
            if service == "turn_on" and service_data["entity_id"] == "switch.fixture_b":
                began.set()
                return None  # Accepted, with no reported change yet.
        return await original(registry, domain, service, service_data, *args, **kwargs)

    with (
        patch.object(manager, "_request_update"),
        patch.object(type(house.services), "async_call", new=delayed),
        patch("custom_components.radiant_climate.runtime.COMMAND_TIMEOUT", 0.3),
    ):
        # First channel was confirmed in the preceding pass. No timer/event
        # retry is allowed to compensate on behalf of this explicit pass.
        await house.services.async_call(
            "input_boolean",
            "turn_on",
            {"entity_id": ["input_boolean.fixture_a", "input_boolean.fixture_general"]},
            blocking=True,
        )
        await house.async_block_till_done()
        manager.enabled = True
        opening = house.async_create_task(manager.async_reconcile())
        await asyncio.wait_for(began.wait(), 1)
        assert not opening.done()
        assert "switch.fixture_b" not in manager._command_faults
        if outcome == "delayed":
            await house.services.async_call(
                "input_boolean", "turn_on", {"entity_id": "input_boolean.fixture_b"}, blocking=True
            )
        elif outcome == "global_off":
            stop = house.async_create_task(manager.async_enable(False))
            await asyncio.sleep(0)
        elif outcome == "sensor_loss":
            house.states.async_set("sensor.fixture_a", "unavailable")
        elif outcome == "window_open":
            house.states.async_set("binary_sensor.fixture_window", "on")
        elif outcome == "shutdown":
            manager.async_stop()
        elif outcome == "missing_reports":
            for index in range(8):
                house.states.async_set(
                    "sensor.fixture_a", str(19.1 + index / 100), {"unit_of_measurement": "°C"}
                )
                await asyncio.sleep(0.01)
        await asyncio.wait_for(opening, 1)
        if outcome == "global_off":
            await stop
        if outcome == "delayed":
            assert "switch.fixture_b" not in manager._command_faults
            assert house.states.get("switch.fixture_b").state == "on"
        else:
            assert ("turn_off", "switch.fixture_a") in commands
            assert ("turn_off", "switch.fixture_general") in commands
            assert house.states.get("switch.fixture_a").state == "off"
            assert house.states.get("switch.fixture_general").state == "off"
        assert ("switch.fixture_b" in manager._command_faults) == (
            outcome in ("missing", "missing_reports")
        )
    if outcome in ("missing", "missing_reports"):
        errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
        assert errors == [
            "Actuator command failed for switch.fixture_b (command_timeout, requested on)"
        ]
        caplog.clear()
    await manager.async_enable(False)
    if outcome == "global_off":
        # A delayed report arriving after cancellation must not reopen supply.
        await service(house, "input_boolean", "turn_on", "input_boolean.fixture_b")
        assert house.states.get("switch.fixture_b").state == "off"
        assert house.states.get("switch.fixture_general").state == "off"


@pytest.mark.parametrize(
    "key,value", [("orientation", 90), ("solar_elevation", 30), ("solar_width", 40)]
)
async def test_geometry_edit_invalidates_confirmation_and_downgrades_solar(house, key, value):
    entry, _ = await add_zone(house)
    manager = house.data[DOMAIN]
    await configure_sources(house, entry, solar_confirmed=True)
    await manager.async_feature(entry.entry_id, "solar", "active")
    await configure_sources(house, entry, **{key: value}, solar_confirmed=True)
    zone = manager.zones[entry.entry_id]
    assert not zone.config["solar_confirmed"]
    assert zone.intelligence.features.solar == "observe"
    with pytest.raises(ValueError, match="exposure"):
        await manager.async_feature(entry.entry_id, "solar", "active")
    await configure_sources(house, entry, solar_confirmed=True)
    await manager.async_feature(entry.entry_id, "solar", "active")
    assert zone.intelligence.features.solar == "active"
    await configure_sources(house, entry, solar_confirmed=False)
    assert zone.intelligence.features.solar == "observe"


@pytest.mark.parametrize("mode", ["heat", "cool"])
@pytest.mark.parametrize("profile", ["home", "eco", "sleep"])
async def test_native_profile_keeps_its_name_during_manual_hold(house, mode, profile):
    from custom_components.radiant_climate.core.control import Intent

    entry, climate = await add_zone(house)
    await add_schedule(house, entry)
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "schedule"))
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode=mode)
    await service(house, "climate", "set_preset_mode", climate, preset_mode=profile)
    state = house.states.get(climate)
    zone = house.data[DOMAIN].zones[entry.entry_id]
    assert state.attributes["control_state"] == "manual"
    assert state.attributes["preset_mode"] == profile
    assert state.attributes["temperature"] == zone.program.profiles[mode][profile]
    assert Intent.restore(zone.intent.dump()).hold.profile == profile
    # A numeric intervention, even at the same temperature, has no profile.
    await service(
        house, "climate", "set_temperature", climate, temperature=state.attributes["temperature"]
    )
    assert house.states.get(climate).attributes["preset_mode"] == "none"
    assert house.states.get(climate).attributes["control_state"] == "manual"
    await service(house, "button", "press", zone_entity(house, entry, "button", "resume"))
    assert house.states.get(climate).attributes["control_state"] == "scheduled"


@pytest.mark.parametrize("change", ["sensor", "sensor_legacy", "relay", "logical"])
async def test_model_follows_sensor_but_not_relay_identity(house, change):
    from custom_components.radiant_climate.core.intelligence import Statistics

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    zone = manager.zones[entry.entry_id]
    await manager.async_change(
        lambda: zone.intelligence.model.statistics.update(
            {"heat_on": Statistics(count=12, hours=6, delta=3, rate_square=1.5, episodes=3)}
        )
    )
    await service(house, "climate", "set_temperature", climate, temperature=22.5)
    if change == "sensor_legacy":
        raw = await manager._store.async_load()
        raw["zones"][entry.entry_id].pop("learning_sensor")
        await manager._store.async_save(raw)
        manager._saved = raw["zones"]
    if change == "logical":
        await configure_sources(house, entry, orientation=100)
    else:
        flow = await house.config_entries.options.async_init(entry.entry_id)
        flow = await house.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "hardware"}
        )
        result = await house.config_entries.options.async_configure(
            flow["flow_id"],
            {
                "sensor": "sensor.fixture_b" if change.startswith("sensor") else "sensor.fixture_a",
                "actuators": ["switch.fixture_b" if change == "relay" else "switch.fixture_a"],
                "available_modes": "heat_cool",
                "target": 21,
                "minimum_on": 0,
                "minimum_off": 0,
            },
        )
        assert result["type"] == "create_entry", result
        await settle(house)
    restored = manager.zones[entry.entry_id]
    assert restored.intelligence.model.response(restored.intent.last_mode).ready == (
        not change.startswith("sensor")
    )
    assert house.states.get(climate).attributes["temperature"] == 22.5


@pytest.mark.parametrize(
    "event_kind",
    [
        "temperature",
        "attributes",
        "other_zone",
        "other_zone_invalid",
        "window_disabled",
        "window_attributes",
        "window_delay",
        "target_reached",
        "same_season",
        "hydraulic_options",
    ],
)
async def test_ordinary_reports_do_not_cancel_acknowledgment(house, event_kind):
    import asyncio
    from unittest.mock import patch

    entry, climate = await add_zone(house)
    await add_zone(house, "b")  # Independent room remains off.
    manager = house.data[DOMAIN]
    zone = manager.zones[entry.entry_id]
    house.states.async_set("binary_sensor.fixture_window", "off")
    zone.config["window"] = "binary_sensor.fixture_window"
    zone.window_enabled = event_kind != "window_disabled"
    if event_kind == "window_delay":
        zone.config["window_open_delay"] = 60
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    original = type(house.services).async_call
    began = asyncio.Event()
    commands = []

    async def delayed(registry, domain, service, service_data=None, *args, **kwargs):
        if domain == "switch":
            commands.append((service, service_data["entity_id"]))
            if service == "turn_on" and service_data["entity_id"] == "switch.fixture_a":
                began.set()
                return None
        return await original(registry, domain, service, service_data, *args, **kwargs)

    with (
        patch.object(manager, "_request_update"),
        patch.object(type(house.services), "async_call", new=delayed),
    ):
        await house.services.async_call(
            "input_boolean",
            "turn_on",
            {"entity_id": "input_boolean.fixture_general"},
            blocking=True,
        )
        await house.async_block_till_done()
        manager.enabled = True
        opening = house.async_create_task(manager.async_reconcile())
        await asyncio.wait_for(began.wait(), 1)
        for index in range(4):
            if event_kind in ("temperature", "target_reached"):
                house.states.async_set(
                    "sensor.fixture_a",
                    "22" if event_kind == "target_reached" else str(19.1 + index / 10),
                    {"unit_of_measurement": "°C"},
                )
            elif event_kind == "attributes":
                house.states.async_set(
                    "sensor.fixture_a", "19", {"unit_of_measurement": "°C", "sample": index}
                )
            elif event_kind == "same_season":
                await manager.async_supply("heat")
            elif event_kind == "hydraulic_options":
                water_fixtures(house)
                revision = manager._revision
                result = await configure_hydraulic(house, hydraulic_heat_min=30 + index)
                assert result["type"] == "create_entry", result
            elif event_kind == "other_zone_invalid":
                house.states.async_set("sensor.fixture_b", "unavailable", {"sample": index})
            elif event_kind == "other_zone":
                house.states.async_set(
                    "sensor.fixture_b", str(19.1 + index / 10), {"unit_of_measurement": "°C"}
                )
            else:
                house.states.async_set(
                    "binary_sensor.fixture_window",
                    "off" if event_kind == "window_attributes" else "on",
                    {"sample": index},
                )
            await asyncio.sleep(0.01)
            if event_kind == "hydraulic_options":
                assert manager._revision == revision
            assert not opening.done(), "Ordinary input cancelled the pending acknowledgment"
        assert not any(service == "turn_off" for service, _ in commands)
        await house.services.async_call(
            "input_boolean", "turn_on", {"entity_id": "input_boolean.fixture_a"}, blocking=True
        )
        await asyncio.wait_for(opening, 1)
        assert not manager._command_faults
    await settle(house)
    assert house.states.get("switch.fixture_a").state == (
        "off" if event_kind == "target_reached" else "on"
    )
    assert house.states.get("switch.fixture_b").state == "off"
    await manager.async_enable(False)


@pytest.mark.parametrize("intermediate", ["unknown", "unavailable", "removed"])
@pytest.mark.parametrize("stop", [False, True])
async def test_transient_output_loss_aborts_safely_and_recovers_only_if_requested(
    house, intermediate, stop
):
    import asyncio
    from unittest.mock import patch

    _, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    original = type(house.services).async_call
    began = asyncio.Event()

    async def delayed(registry, domain, service, service_data=None, *args, **kwargs):
        if (
            domain == "switch"
            and service == "turn_on"
            and service_data["entity_id"] == "switch.fixture_a"
        ):
            began.set()
            return None
        return await original(registry, domain, service, service_data, *args, **kwargs)

    with (
        patch.object(manager, "_request_update"),
        patch.object(type(house.services), "async_call", new=delayed),
    ):
        await house.services.async_call(
            "input_boolean",
            "turn_on",
            {"entity_id": "input_boolean.fixture_general"},
            blocking=True,
        )
        await house.async_block_till_done()
        manager.enabled = True
        opening = house.async_create_task(manager.async_reconcile())
        await asyncio.wait_for(began.wait(), 1)
        if intermediate == "removed":
            house.states.async_remove("switch.fixture_a")
        else:
            house.states.async_set("switch.fixture_a", intermediate)
        await asyncio.wait_for(opening, 1)
        assert house.states.get("switch.fixture_general").state == "off"
        assert not manager._command_faults  # Loss of feedback is not a rejected command.
        if stop:
            await manager.async_enable(False)
    # Delayed ON arrives after compensation. It may resume a still-requested
    # demand, but never overrides a global stop.
    await service(house, "input_boolean", "turn_on", "input_boolean.fixture_a")
    await settle(house)
    assert house.states.get("switch.fixture_a").state == ("off" if stop else "on")
    assert house.states.get("switch.fixture_general").state == ("off" if stop else "on")
    assert not manager._command_faults
    await manager.async_enable(False)


async def test_queued_module_updates_do_not_overwrite_each_other(house):
    import asyncio

    entry, _ = await add_zone(house)
    manager = house.data[DOMAIN]
    await manager._lock.acquire()
    try:
        first = house.async_create_task(manager.async_feature(entry.entry_id, "learning", True))
        second = house.async_create_task(manager.async_feature(entry.entry_id, "predictive", True))
        await asyncio.sleep(0)
    finally:
        manager._lock.release()
    await asyncio.gather(first, second)
    features = manager.zones[entry.entry_id].intelligence.features
    assert features.learning and features.predictive


async def test_queued_solar_activation_rechecks_current_confirmation(house):
    import asyncio

    entry, _ = await add_zone(house)
    manager = house.data[DOMAIN]
    await configure_sources(house, entry, solar_confirmed=True)
    await manager._lock.acquire()
    try:
        activation = house.async_create_task(
            manager.async_feature(entry.entry_id, "solar", "active")
        )
        await asyncio.sleep(0)
        manager.zones[entry.entry_id].config["solar_confirmed"] = False
    finally:
        manager._lock.release()
    with pytest.raises(ValueError, match="exposure"):
        await activation
    assert manager.zones[entry.entry_id].intelligence.features.solar != "active"


@pytest.mark.parametrize("action", ["schedule", "resume"])
async def test_queued_zone_action_uses_the_current_zone_instance(house, action):
    import asyncio
    from copy import deepcopy

    from custom_components.radiant_climate.core.control import Hold, HoldPolicy

    entry, _ = await add_zone(house)
    manager = house.data[DOMAIN]
    if action == "schedule":
        await add_schedule(house, entry)
    else:
        await manager.async_change(
            lambda: setattr(
                manager.zones[entry.entry_id].intent,
                "hold",
                Hold(22, HoldPolicy.UNTIL_RESUME, None),
            )
        )
    await manager._lock.acquire()
    try:
        command = house.async_create_task(
            manager.async_schedule(entry.entry_id, True)
            if action == "schedule"
            else manager.async_resume(entry.entry_id)
        )
        await asyncio.sleep(0)
        # Same logical zone, reloaded while the command was queued.
        manager.zones[entry.entry_id] = deepcopy(manager.zones[entry.entry_id])
    finally:
        manager._lock.release()
    await command
    current = manager.zones[entry.entry_id]
    if action == "schedule":
        assert current.program.enabled
    else:
        assert current.intent.hold is None


async def test_queued_season_changes_keep_the_last_explicit_choice(house):
    import asyncio

    await add_zone(house)
    manager = house.data[DOMAIN]
    await manager._lock.acquire()
    try:
        cooling = house.async_create_task(manager.async_supply("cool"))
        await asyncio.sleep(0)
        heating = house.async_create_task(manager.async_supply("heat"))
        await asyncio.sleep(0)
    finally:
        manager._lock.release()
    await asyncio.gather(cooling, heating)
    assert manager.supply_mode.value == "heat"
    assert not manager._stop_requested
    assert house.states.get("switch.fixture_general").state == "off"


async def test_queued_turn_on_uses_the_current_declared_season(house):
    import asyncio

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    await manager._lock.acquire()
    try:
        cooling = house.async_create_task(manager.async_supply("cool"))
        await asyncio.sleep(0)
        turn_on = house.async_create_task(
            house.services.async_call("climate", "turn_on", {"entity_id": climate}, blocking=True)
        )
        await asyncio.sleep(0)
    finally:
        manager._lock.release()
    await asyncio.gather(cooling, turn_on)
    assert manager.zones[entry.entry_id].intent.mode.value == "cool"
    assert not manager.enabled
    assert house.states.get("switch.fixture_a").state == "off"


async def test_queued_resume_rechecks_away_before_enabling_schedule(house):
    import asyncio

    from custom_components.radiant_climate.core.control import Hold, HoldPolicy

    entry, _ = await add_zone(house)
    manager = house.data[DOMAIN]
    await add_schedule(house, entry)
    await manager._lock.acquire()
    try:
        resume = house.async_create_task(manager.async_resume(entry.entry_id))
        await asyncio.sleep(0)
        z = manager.zones[entry.entry_id]
        z.program.away = True
        z.intent.hold = Hold(22, HoldPolicy.UNTIL_RESUME, None)
    finally:
        manager._lock.release()
    await resume
    assert z.program.away
    assert z.intent.hold is None
    assert not z.program.enabled


@pytest.mark.parametrize("seed", [7, 42])
async def test_control_invariants_across_mixed_user_and_sensor_sequences(house, seed):
    import random

    a, ca = await add_zone(house)
    b, cb = await add_zone(house, "b")
    manager = house.data[DOMAIN]
    house.states.async_set("binary_sensor.fixture_window", "off")
    manager.zones[a.entry_id].config["window"] = "binary_sensor.fixture_window"
    for entry in (a, b):
        await add_schedule(house, entry)
        await manager.async_schedule(entry.entry_id, True)
    generator = random.Random(seed)
    for step in range(50):
        action = generator.randrange(9)
        if action == 0:
            await manager.async_enable(generator.choice([True, False]))
        elif action == 1:
            await manager.async_supply(generator.choice(["heat", "cool"]))
        elif action in (2, 3):
            await service(
                house,
                "climate",
                generator.choice(["turn_on", "turn_off"]),
                ca if action == 2 else cb,
            )
        elif action == 4:
            house.states.async_set(
                "sensor.fixture_a", generator.choice(["19", "28"]), {"unit_of_measurement": "°C"}
            )
        elif action == 5:
            house.states.async_set(
                "sensor.fixture_b",
                generator.choice(["19", "28", "unavailable"]),
                {"unit_of_measurement": "°C"},
            )
        elif action == 6:
            house.states.async_set("binary_sensor.fixture_window", generator.choice(["on", "off"]))
        elif action == 7:
            await manager.async_away_all(generator.choice([True, False]))
        else:
            await service(
                house,
                "climate",
                "set_preset_mode",
                ca,
                preset_mode=generator.choice(["home", "eco", "sleep"]),
            )
        await settle(house)
        for entry, key in ((a, "a"), (b, "b")):
            on = house.states.get("switch.fixture_" + key).state == "on"
            zone = manager.zones[entry.entry_id]
            if on:
                assert manager.enabled, (seed, step, action)
                assert zone.intent.mode.value == manager.supply_mode.value
                assert house.states.get("switch.fixture_general").state == "on"
                assert house.states.get(zone.config["sensor"]).state not in (
                    "unknown",
                    "unavailable",
                )
                if key == "a":
                    assert house.states.get("binary_sensor.fixture_window").state == "off"
            if not manager.enabled or zone.intent.mode.value == "off":
                assert not on, (seed, step, action)
        if not manager.enabled:
            assert house.states.get("switch.fixture_general").state == "off"
        assert not manager._command_faults
    await manager.async_enable(False)


async def configure_hydraulic(hass, **changes):
    manager = hass.data[DOMAIN]
    flow = await hass.config_entries.options.async_init(manager.hub)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "hydraulic"}
    )
    data = {
        "hydraulic_enabled": True,
        "hydraulic_supply": "sensor.fixture_supply",
        "hydraulic_return": "sensor.fixture_return",
        "hydraulic_stale": 900,
        "hydraulic_settle": 5,
        "hydraulic_duration": 5,
        **changes,
    }
    # Cleared optional HA selectors are omitted, rather than submitted as None.
    return await hass.config_entries.options.async_configure(
        flow["flow_id"], {key: value for key, value in data.items() if value is not None}
    )


def water_fixtures(hass):
    for key, value in (("supply", 30), ("return", 25)):
        hass.states.async_set(f"sensor.fixture_{key}", str(value), {"unit_of_measurement": "°C"})


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        ("32", "°F", 0),
        ("303.15", "K", 30),
        ("30", "°C", 30),
        ("nan", "°C", None),
        ("inf", "°C", None),
        ("-1", "°C", None),
        ("91", "°C", None),
        ("unknown", "°C", None),
        ("unavailable", "°C", None),
        ("30", "%", None),
        ("30", None, None),
        ("True", "°C", None),
    ],
)
async def test_water_reading_validates_units_range_and_freshness(house, value, unit, expected):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    from custom_components.radiant_climate.hydraulic import reading

    house.states.async_set("sensor.fixture_water", value, {"unit_of_measurement": unit})
    now = dt_util.utcnow()
    assert reading(house, "sensor.fixture_water", now, 900) == expected
    assert reading(house, "sensor.fixture_water", now + timedelta(seconds=901), 900) is None
    assert reading(house, "sensor.fixture_water", now - timedelta(seconds=61), 900) is None
    assert reading(house, "sensor.does_not_exist", now, 900) is None


async def test_optional_hydraulic_lifecycle_is_read_only_and_preserves_control(house):
    from unittest.mock import patch

    from custom_components.radiant_climate.sensor import HydraulicStatus

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    registry = er.async_get(house)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{manager.hub}_hydraulic") is None
    water_fixtures(house)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await manager.async_enable(True)
    await settle(house)
    zone = manager.zones[entry.entry_id]
    intent, model, revision = zone.intent.dump(), zone.intelligence.model.dump(), manager._revision
    with patch.object(
        manager, "async_update_options", side_effect=AssertionError("Control touched")
    ):
        result = await configure_hydraulic(house, hydraulic_heat_min=35)
        assert result["type"] == "create_entry", result
        await house.async_block_till_done()
    assert manager._revision == revision
    entity = registry.async_get_entity_id("sensor", DOMAIN, f"{manager.hub}_hydraulic")
    assert entity is not None
    assert house.states.get(entity).state == "stabilizing"
    assert house.states.get(entity).attributes["delta_celsius"] == 5
    # Retrieve the real platform entity; advance only this observer's monotonic clock.
    component = house.data["sensor"]
    diagnostic = next(e.diagnostic for e in component.entities if isinstance(e, HydraulicStatus))
    with patch("custom_components.radiant_climate.hydraulic.monotonic", return_value=0):
        diagnostic.observer.last = None
        diagnostic.observer.signature = None
        diagnostic.update()
    with patch("custom_components.radiant_climate.hydraulic.monotonic") as clock:
        for now in range(15, 601, 15):
            clock.return_value = now
            diagnostic.update()
        assert diagnostic.state == "possible_low_supply"
    revision = manager._revision
    house.states.async_set("sensor.fixture_supply", "unavailable")
    await house.async_block_till_done()
    assert house.states.get(entity).state == "sensor_unavailable"
    assert manager._revision == revision
    assert zone.intent.dump() == intent
    assert zone.intelligence.model.dump() == model
    assert house.states.get("switch.fixture_a").state == "on"
    assert house.states.get("switch.fixture_general").state == "on"
    toggle = registry.async_get_entity_id("switch", DOMAIN, f"{manager.hub}_hydraulic_enabled")
    assert toggle is not None
    with patch.object(
        manager, "async_update_options", side_effect=AssertionError("Control touched")
    ):
        for action, expected in (("turn_off", "disabled"), ("turn_on", "sensor_unavailable")):
            await house.services.async_call("switch", action, {"entity_id": toggle}, blocking=True)
            await house.async_block_till_done()
            assert house.states.get(entity).state == expected
            assert manager._revision == revision
    assert house.config_entries.async_get_entry(manager.hub).options["hydraulic_heat_min"] == 35
    # Clearing references and disabling does not retire or reconcile hardware.
    assert (await configure_hydraulic(house, hydraulic_enabled=False))["type"] == "create_entry"
    await house.async_block_till_done()
    assert house.states.get(entity).state == "disabled"
    hub = house.config_entries.async_get_entry(manager.hub)
    assert hub.options["hydraulic_heat_min"] is None
    assert not manager._retired and not manager._command_faults
    await manager.async_enable(False)


@pytest.mark.parametrize(
    "changes",
    [
        {"hydraulic_supply": "sensor.absent"},
        {"hydraulic_return": "sensor.fixture_supply"},
        {"hydraulic_supply": None},
        {"hydraulic_heat_min": float("nan")},
        {"hydraulic_duration": 0},
    ],
)
async def test_hydraulic_options_reject_incomplete_or_invalid_configuration(house, changes):
    from homeassistant.data_entry_flow import InvalidData

    water_fixtures(house)
    if changes.get("hydraulic_duration") == 0:
        with pytest.raises(InvalidData):
            await configure_hydraulic(house, **changes)
        return
    result = await configure_hydraulic(house, **changes)
    assert result["type"] == "form"
    assert result["errors"]
    assert not house.data[DOMAIN].enabled


@pytest.mark.parametrize("enabled", [False, True])
async def test_hydraulic_options_survive_unload_and_reload_without_enabling_control(house, enabled):
    water_fixtures(house)
    assert (await configure_hydraulic(house, hydraulic_enabled=enabled))["type"] == "create_entry"
    await house.async_block_till_done()
    manager = house.data[DOMAIN]
    hub_id = manager.hub
    entity = er.async_get(house).async_get_entity_id("sensor", DOMAIN, f"{hub_id}_hydraulic")
    assert house.states.get(entity).state == ("idle" if enabled else "disabled")
    assert await house.config_entries.async_reload(hub_id)
    await house.async_block_till_done()
    assert house.states.get(entity).state == ("idle" if enabled else "disabled")
    assert not house.data[DOMAIN].enabled
    assert house.states.get("switch.fixture_general").state == "off"


@pytest.mark.parametrize("intermediate", ["sensor_loss", "reference_recovered", "relay_off"])
async def test_hydraulic_burst_preserves_intervening_loss_or_recovery(house, intermediate):
    from unittest.mock import patch

    from custom_components.radiant_climate.sensor import HydraulicStatus

    _, climate = await add_zone(house)
    water_fixtures(house)
    manager = house.data[DOMAIN]
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await manager.async_enable(True)
    await settle(house)
    assert (await configure_hydraulic(house, hydraulic_heat_min=35))["type"] == "create_entry"
    await house.async_block_till_done()
    diagnostic = next(
        e.diagnostic for e in house.data["sensor"].entities if isinstance(e, HydraulicStatus)
    )
    with patch("custom_components.radiant_climate.hydraulic.monotonic") as clock:
        diagnostic.observer.signature = None
        diagnostic.observer.last = None
        for now in range(0, 601, 15):
            clock.return_value = now
            diagnostic.update()
        assert diagnostic.state == "possible_low_supply"
        clock.return_value = 615
        if intermediate == "relay_off":
            entity, first, final, attrs = "switch.fixture_a", "off", "on", {}
        else:
            entity, first, final, attrs = (
                "sensor.fixture_supply",
                "unavailable" if intermediate == "sensor_loss" else "36",
                "30",
                {"unit_of_measurement": "°C"},
            )
        house.states.async_set(entity, first, attrs)
        house.states.async_set(entity, final, attrs)
        await house.async_block_till_done()
        assert diagnostic.state == (
            "reference_pending" if intermediate == "reference_recovered" else "stabilizing"
        )
        assert diagnostic.observer.concern_since in (None, 615)
    await manager.async_enable(False)


async def test_hydraulic_cooling_observation_does_not_block_real_cooling_control(house):
    from unittest.mock import patch

    from custom_components.radiant_climate.sensor import HydraulicStatus

    _, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    house.states.async_set("sensor.fixture_a", "28", {"unit_of_measurement": "°C"})
    await manager.async_supply("cool")
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="cool")
    await manager.async_enable(True)
    await settle(house)
    house.states.async_set("sensor.fixture_supply", "23", {"unit_of_measurement": "°C"})
    house.states.async_set("sensor.fixture_return", "25", {"unit_of_measurement": "°C"})
    assert (await configure_hydraulic(house, hydraulic_cool_max=20))["type"] == "create_entry"
    await house.async_block_till_done()
    diagnostic = next(
        e.diagnostic for e in house.data["sensor"].entities if isinstance(e, HydraulicStatus)
    )
    with patch("custom_components.radiant_climate.hydraulic.monotonic") as clock:
        diagnostic.observer.signature = None
        diagnostic.observer.last = None
        for now in range(0, 601, 15):
            clock.return_value = now
            diagnostic.update()
        assert diagnostic.state == "possible_high_supply"
        assert diagnostic.attributes["delta_celsius"] == -2
    house.states.async_set("sensor.fixture_return", "unavailable")
    await house.async_block_till_done()
    assert diagnostic.state == "sensor_unavailable"
    assert house.states.get(climate).state == "cool"
    assert house.states.get("switch.fixture_a").state == "on"
    assert house.states.get("switch.fixture_general").state == "on"
    assert not manager._command_faults
    await manager.async_enable(False)


async def test_cancelled_global_off_waiting_for_lock_still_completes_and_persists(house):
    import asyncio

    _, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await manager.async_enable(True)
    await settle(house)
    await manager._lock.acquire()
    try:
        off = house.async_create_task(manager.async_enable(False))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert manager._stop_requested
        off.cancel()
        with pytest.raises(asyncio.CancelledError):
            await off
    finally:
        manager._lock.release()
    await house.async_block_till_done()
    await settle(house)
    assert not manager.enabled
    assert not manager._stop_requested
    assert not (await manager._store.async_load())["enabled"]
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get("switch.fixture_general").state == "off"


@pytest.mark.parametrize("mode", ["heat", "cool"])
@pytest.mark.parametrize("confirmed,sun_visible", [(True, True), (False, True), (True, False)])
async def test_learning_excludes_known_sun_even_when_solar_optimisation_is_off(
    house, mode, confirmed, sun_visible
):
    from unittest.mock import patch

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    if mode == "cool":
        house.states.async_set("sensor.fixture_a", "28", {"unit_of_measurement": "°C"})
        await manager.async_supply("cool")
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode=mode)
    await manager.async_enable(True)
    await manager.async_feature(entry.entry_id, "learning", True)
    zone = manager.zones[entry.entry_id]
    zone.config.update(
        orientation=125, solar_elevation=20, solar_width=40, solar_confirmed=confirmed
    )
    house.states.async_set(
        "sun.sun", "above_horizon", {"azimuth": 125 if sun_visible else 300, "elevation": 30}
    )
    await settle(house)
    assert zone.intelligence.features.solar == "off"
    with patch.object(zone.intelligence.model, "observe") as observe:
        await manager.async_reconcile()
        assert observe.called
        assert observe.call_args.kwargs["learning"] is not (confirmed and sun_visible)
    await manager.async_enable(False)


async def test_actuator_problem_and_repairs_follow_existing_latches_without_resetting(house):
    from homeassistant.helpers import issue_registry as ir

    await add_zone(house)
    manager = house.data[DOMAIN]
    problem = er.async_get(house).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{manager.hub}_actuator_problem"
    )
    issue_id = f"actuator_attention_{manager.hub}"
    assert house.states.get(problem).state == "off"
    assert ir.async_get(house).async_get_issue(DOMAIN, issue_id) is None

    def simulated_latches():
        manager._command_faults.add("switch.fixture_a")
        manager._retired["switch.fixture_b"] = 900

    await manager.async_change(simulated_latches)
    await house.async_block_till_done()
    assert house.states.get(problem).state == "on"
    issue = ir.async_get(house).async_get_issue(DOMAIN, issue_id)
    assert issue.translation_placeholders == {"faults": "1", "retired": "1"}
    await manager.async_enable(False)
    await house.async_block_till_done()
    assert manager.actuator_faults == ("switch.fixture_a",)
    await manager.async_reset_actuator_faults([])  # Existing empty selection = all faults.
    await house.async_block_till_done()
    assert house.states.get(problem).state == "on"
    assert ir.async_get(house).async_get_issue(DOMAIN, issue_id).translation_placeholders == {
        "faults": "0",
        "retired": "1",
    }
    await manager.async_acknowledge_retired("switch.fixture_b")
    await house.async_block_till_done()
    assert house.states.get(problem).state == "off"
    assert ir.async_get(house).async_get_issue(DOMAIN, issue_id) is None
    assert not manager.enabled
    assert house.states.get("switch.fixture_a").state == "off"


async def test_cancelled_off_does_not_override_a_later_explicit_on(house):
    import asyncio

    manager = house.data[DOMAIN]
    await manager._lock.acquire()
    try:
        off = house.async_create_task(manager.async_enable(False))
        await asyncio.sleep(0)
        off.cancel()
        with pytest.raises(asyncio.CancelledError):
            await off
        on = house.async_create_task(manager.async_enable(True))
        await asyncio.sleep(0)
    finally:
        manager._lock.release()
    await on
    await house.async_block_till_done()
    assert manager.enabled
    assert not manager._stop_requested
    await manager.async_enable(False)


@pytest.mark.parametrize("language", ["en", "es"])
async def test_services_and_issue_strings_exist_in_shipped_languages(house, language):
    from homeassistant.helpers import translation

    translated = await translation.async_get_translations(house, language, "services", {DOMAIN})
    assert translated[f"component.{DOMAIN}.services.reset_actuator_faults.name"] == (
        "Reset actuator faults after review"
        if language == "en"
        else "Reconocer fallos de relés tras revisión"
    )


async def test_grouped_schedule_editor_localised_partial_edit_and_collision(house):
    from homeassistant.util import dt as dt_util

    house.config.language = "es"
    entry, _ = await add_zone(house)
    manager = house.data[DOMAIN]
    await add_schedule(house, entry)
    await manager.async_edit_schedule(
        entry.entry_id, lambda p: p.set_blocks(list(range(7)), 1380, "sleep")
    )
    flow = await house.config_entries.options.async_init(entry.entry_id)
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "schedule_choose"}
    )
    schema = flow["data_schema"].schema
    selected = next(v for k, v in schema.items() if str(k) == "block")
    options = selected.config["options"]
    assert len(options) == 2
    assert any("Semana completa" in o["label"] and "Noche" in o["label"] for o in options)
    block = next(o["value"] for o in options if "23:00" in o["label"])
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"block": block, "scope": ["weekdays"]}
    )
    assert flow["step_id"] == "schedule_edit"
    defaults = {
        str(k): k.default()
        for k in flow["data_schema"].schema
        if k.default is not __import__("voluptuous").UNDEFINED
    }
    assert defaults["time"] == "23:00:00"
    assert defaults["days"] == ["0", "1", "2", "3", "4"]
    before = manager.zones[entry.entry_id].program.dump()
    conflict = await house.config_entries.options.async_configure(
        flow["flow_id"], {"days": ["weekdays"], "time": "00:00:00", "profile": "eco"}
    )
    assert conflict["errors"] == {"base": "schedule_conflict"}
    assert manager.zones[entry.entry_id].program.dump() == before
    result = await house.config_entries.options.async_configure(
        flow["flow_id"], {"days": ["weekdays"], "time": "22:00:00", "profile": "sleep"}
    )
    assert result["type"] == "create_entry"
    await settle(house)
    program = manager.zones[entry.entry_id].program
    assert len(program.blocks) == 14
    assert all(
        b.minute == (1320 if b.day < 5 else 1380) for b in program.blocks if b.profile == "sleep"
    )
    assert manager.retired_actuators == ()
    assert not manager.enabled
    assert program.next_change(dt_util.utcnow(), house.config.time_zone) is not None


@pytest.mark.parametrize("mode", ["standard", "entity", "sensors"])
async def test_selectable_solar_sources_and_optional_failure(house, mode):
    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    house.states.async_set("sun.sun", "above_horizon", {"azimuth": 140, "elevation": 26})
    house.states.async_set("sensor.fixture_sun", "ok", {"azimuth": 140, "elevation": 26})
    for name, value in (("elevation", 26), ("azimuth", 140)):
        house.states.async_set(f"sensor.fixture_{name}", str(value), {"unit_of_measurement": "°"})
    flow = await house.config_entries.options.async_init(manager.hub)
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "solar_source"}
    )
    result = await house.config_entries.options.async_configure(
        flow["flow_id"],
        {
            "solar_source": mode,
            "sun_entity": "sensor.fixture_sun",
            "sun_elevation": "sensor.fixture_elevation",
            "sun_azimuth": "sensor.fixture_azimuth",
        },
    )
    assert result["type"] == "create_entry"
    await settle(house)
    assert manager.environment.sun == (140, 26)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    source = manager.environment.sun_entities[0]
    house.states.async_set(source, "unavailable")
    await settle(house)
    assert manager.environment.sun == (None, None)
    assert house.states.get("switch.fixture_a").state == "on"
    assert manager.enabled
    house.states.async_set(
        source,
        "26" if mode == "sensors" else "above_horizon",
        {"unit_of_measurement": "°", "azimuth": 140, "elevation": 26},
    )
    await settle(house)
    assert manager.environment.sun == (140, 26)


@pytest.mark.parametrize(
    "case",
    [
        "active",
        "observe",
        "manual",
        "off",
        "window",
        "sensor",
        "cool",
        "cloudy",
        "missing",
        "cold",
        "minimum_cycle",
        "schedule",
        "zone_off",
    ],
)
async def test_solar_lead_before_exposure_keeps_regulation_priorities(house, monkeypatch, case):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    house.states.async_set("weather.fixture_solar", "sunny")
    house.states.async_set("sun.sun", "above_horizon", {"azimuth": 130, "elevation": 10})
    await configure_sources(
        house,
        entry,
        weather="weather.fixture_solar",
        orientation=133.5,
        solar_elevation=26,
        solar_lead=90,
    )
    await configure_sources(house, entry, weather="weather.fixture_solar", solar_confirmed=True)
    await manager.async_feature(entry.entry_id, "weather", True)
    await manager.async_feature(
        entry.entry_id, "solar", "observe" if case == "observe" else "active"
    )
    await service(
        house, "climate", "set_hvac_mode", climate, hvac_mode="cool" if case == "cool" else "heat"
    )
    if case == "cool":
        await manager.async_supply("cool")
    await service(house, "switch", "turn_on", global_entity(house))
    zone = manager.zones[entry.entry_id]
    now = dt_util.utcnow()
    monkeypatch.setattr(
        manager.environment.projection, "arrival", lambda *_: now + timedelta(minutes=60)
    )
    monkeypatch.setattr(
        manager.environment,
        "future",
        lambda *_: None
        if case == "missing"
        else {"condition": "cloudy" if case == "cloudy" else "sunny"},
    )
    value = 20 if case == "cold" else 20.9
    house.states.async_set("sensor.fixture_a", str(value), {"unit_of_measurement": "°C"})
    await settle(house)
    if case == "manual":
        await add_schedule(house, entry)
        await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "schedule"))
        await service(house, "climate", "set_temperature", climate, temperature=21)
    if case == "off":
        await service(house, "switch", "turn_off", global_entity(house))
    if case == "window":
        zone.config["window"] = "binary_sensor.fixture_solar_window"
        house.states.async_set("binary_sensor.fixture_solar_window", "on")
    if case == "sensor":
        house.states.async_set("sensor.fixture_a", "unavailable")
    if case == "minimum_cycle":
        from dataclasses import replace

        zone.settings = replace(zone.settings, minimum_on=180)
        zone.switched_at = now
    if case == "zone_off":
        await service(house, "climate", "turn_off", climate)
    if case == "schedule":
        from custom_components.radiant_climate.core.intelligence import Statistics

        local = dt_util.as_local(now)
        later = local + timedelta(minutes=30)
        await manager.async_edit_schedule(
            entry.entry_id,
            lambda p: (
                p.set_blocks(list(range(7)), 0, "eco"),
                p.set_blocks([later.weekday()], later.hour * 60 + later.minute, "home"),
            ),
        )
        zone.program.profiles["heat"].update(eco=21, home=22)
        await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "schedule"))
        await manager.async_feature(entry.entry_id, "anticipation", True)
        zone.intelligence.model.statistics["heat_on"] = Statistics(
            count=12, hours=6, delta=3, rate_square=1.5, episodes=3
        )
    zone.intelligence.model.points = [
        (now - timedelta(minutes=30), value - 0.1),
        (now - timedelta(minutes=15), value - 0.05),
        (now, value),
    ]
    await settle(house)
    attrs = house.states.get(climate).attributes
    assert (
        attrs["reason"] == "solar_anticipation"
        if case == "active"
        else attrs["reason"] != "solar_anticipation"
    )
    if case == "active":
        assert not attrs["solar_candidate"]
        assert attrs["solar_lead_candidate"]
        assert attrs["temperature"] == 21
        assert house.states.get("switch.fixture_a").state == "off"
    if case == "schedule":
        assert attrs["reason"] == "anticipation"
        assert attrs["control_target"] == 22
    if case in ("observe", "manual", "cloudy", "missing", "cold", "minimum_cycle", "schedule"):
        assert house.states.get("switch.fixture_a").state == "on"


async def test_solar_projection_matches_location_and_rejects_inconsistent_source(house):
    from datetime import UTC, datetime, timedelta

    from astral.sun import azimuth, elevation
    from homeassistant.helpers.sun import get_astral_observer

    from custom_components.radiant_climate.solar import SolarProjection

    projection = SolarProjection(house)
    now = datetime(2026, 11, 6, 10, tzinfo=UTC)
    observer = get_astral_observer(house)
    current = (azimuth(observer, now), elevation(observer, now))
    points = projection.positions(now, current)
    assert len(points) == 91
    assert projection.positions(now + timedelta(seconds=1), current) is points
    assert not projection.positions(now, ((current[0] + 90) % 360, current[1]))
    assert not projection.positions(now, (None, None))
    config = {
        "solar_lead": 90,
        "orientation": (current[0] + 5) % 360,
        "solar_width": 1,
        "solar_elevation": 0,
    }
    arrival = projection.arrival(now, current, config)
    if arrival is not None:
        assert now < arrival <= now + timedelta(minutes=90)


@pytest.mark.parametrize("policy", ["solar", "predictive_heat", "predictive_cool"])
async def test_all_optional_pauses_preserve_minimum_on_even_when_base_demands(house, policy):
    from dataclasses import replace
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    from custom_components.radiant_climate.core.intelligence import Statistics

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    cool = policy == "predictive_cool"
    if cool:
        await manager.async_supply("cool")
        house.states.async_set("sensor.fixture_a", "28", {"unit_of_measurement": "°C"})
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="cool" if cool else "heat")
    await service(house, "switch", "turn_on", global_entity(house))
    if policy == "solar":
        house.states.async_set("sun.sun", "above_horizon", {"azimuth": 135, "elevation": 30})
        await configure_sources(house, entry, orientation=135, solar_elevation=20)
        await configure_sources(house, entry, solar_confirmed=True)
        await manager.async_feature(entry.entry_id, "solar", "active")
    else:
        await manager.async_feature(entry.entry_id, "predictive", True)
    z = manager.zones[entry.entry_id]
    z.settings = replace(z.settings, minimum_on=180)
    now = dt_util.utcnow()
    z.switched_at = now
    current = 25.1 if cool else 20.9
    house.states.async_set("sensor.fixture_a", str(current), {"unit_of_measurement": "°C"})
    direction = -1 if cool else 1
    z.intelligence.model.points = [
        (now - timedelta(minutes=30), current - 0.6 * direction),
        (now - timedelta(minutes=15), current - 0.3 * direction),
        (now, current),
    ]
    z.intelligence.model.statistics["cool_on" if cool else "heat_on"] = Statistics(
        count=12, hours=6, delta=3, rate_square=1.5, episodes=3
    )
    await settle(house)
    assert house.states.get("switch.fixture_a").state == "on"
    assert house.states.get(climate).attributes["reason"] not in ("solar_pause", "predictive_pause")
    z.switched_at = now - timedelta(seconds=181)
    await settle(house)
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get(climate).attributes["reason"] == (
        "solar_pause" if policy == "solar" else "predictive_pause"
    )


@pytest.mark.parametrize("case", ["nan", "range", "unit", "stale", "skew", "missing"])
async def test_solar_angle_validation_fails_optional(house, case):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    from custom_components.radiant_climate.solar import angles

    config = {
        "solar_source": "sensors",
        "sun_elevation": "sensor.fixture_el",
        "sun_azimuth": "sensor.fixture_az",
    }
    house.states.async_set("sensor.fixture_el", "26", {"unit_of_measurement": "°"})
    house.states.async_set("sensor.fixture_az", "140", {"unit_of_measurement": "°"})
    now = dt_util.utcnow()
    if case == "skew":
        from types import SimpleNamespace

        # Explicit synthetic timestamps: Core's state machine stamps reports
        # from its own clock, independently of dt_util.utcnow.
        states = {
            name: SimpleNamespace(
                state=value, attributes={"unit_of_measurement": "°"}, last_reported=when
            )
            for name, value, when in (
                ("sensor.fixture_el", "26", now - timedelta(minutes=6)),
                ("sensor.fixture_az", "140", now),
            )
        }
        assert angles(SimpleNamespace(states=SimpleNamespace(get=states.get)), config, now) == (
            None,
            None,
        )
        return
    if case == "stale":
        now += timedelta(minutes=31)
    if case == "missing":
        house.states.async_remove("sensor.fixture_el")
    if case in ("nan", "range", "unit"):
        house.states.async_set(
            "sensor.fixture_el",
            "nan" if case == "nan" else "100" if case == "range" else "26",
            {"unit_of_measurement": "radians" if case == "unit" else "°"},
        )
    assert angles(house, config, now) == (None, None)


async def test_source_change_requires_new_confirmation_and_preserves_running_output(house):
    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    house.states.async_set("sun.sun", "above_horizon", {"azimuth": 135, "elevation": 30})
    house.states.async_set("sensor.fixture_sun", "ok", {"azimuth": 135, "elevation": 30})
    await configure_sources(house, entry, solar_confirmed=True)
    await manager.async_feature(entry.entry_id, "solar", "active")
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    await service(house, "switch", "turn_on", global_entity(house))
    flow = await house.config_entries.options.async_init(manager.hub)
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "solar_source"}
    )
    result = await house.config_entries.options.async_configure(
        flow["flow_id"], {"solar_source": "entity", "sun_entity": "sensor.fixture_sun"}
    )
    assert result["type"] == "create_entry"
    await settle(house)
    assert house.states.get("switch.fixture_a").state == "on"
    assert manager.retired_actuators == ()
    assert manager.zones[entry.entry_id].intelligence.features.solar == "observe"
    with pytest.raises(ValueError, match="exposure"):
        await manager.async_feature(entry.entry_id, "solar", "active")
    await configure_sources(house, entry, solar_confirmed=True)
    await manager.async_feature(entry.entry_id, "solar", "active")
    assert manager.zones[entry.entry_id].intelligence.features.solar == "active"


async def solar_source_options(hass, entity):
    manager = hass.data[DOMAIN]
    flow = await hass.config_entries.options.async_init(manager.hub)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "solar_source"}
    )
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"solar_source": "entity", "sun_entity": entity}
    )
    assert result["type"] == "create_entry", result
    await settle(hass)


def confirmation_default(flow):
    return next(
        key.default() for key in flow["data_schema"].schema if str(key) == "solar_confirmed"
    )


@pytest.mark.parametrize("timing", ["before_open", "while_open", "queued_runtime"])
async def test_source_confirmation_requires_review_of_the_displayed_source(house, timing):
    import asyncio

    from custom_components.radiant_climate.solar import confirmed

    entry, _ = await add_zone(house)
    manager = house.data[DOMAIN]
    alternative = "sensor.fixture_reviewed_sun"
    house.states.async_set(alternative, "ok", {"azimuth": 135, "elevation": 30})
    await configure_sources(house, entry, solar_confirmed=True)
    await manager.async_feature(entry.entry_id, "solar", "active")
    if timing == "before_open":
        await solar_source_options(house, alternative)
    flow = await house.config_entries.options.async_init(entry.entry_id)
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "sources"}
    )
    assert confirmation_default(flow) == (timing != "before_open")
    if timing == "while_open":
        await solar_source_options(house, alternative)
    if timing == "queued_runtime":
        async with manager._lock:
            hub = house.config_entries.async_get_entry(manager.hub)
            house.config_entries.async_update_entry(
                hub, options={**hub.options, "solar_source": "entity", "sun_entity": alternative}
            )
            async with asyncio.timeout(3):
                result = await house.config_entries.options.async_configure(
                    flow["flow_id"], {"solar_confirmed": True}
                )
        await settle(house)
    elif timing == "while_open":
        result = await house.config_entries.options.async_configure(
            flow["flow_id"], {"solar_confirmed": True}
        )
    else:
        result = flow
    if timing != "before_open":
        assert result["type"] == "form" and result["errors"] == {"base": "solar_source_changed"}
        assert not confirmation_default(result)
    result = await house.config_entries.options.async_configure(
        flow["flow_id"], {"solar_confirmed": False}
    )
    assert result["type"] == "create_entry", result
    await settle(house)
    assert not confirmed(manager.zones[entry.entry_id].config, manager.environment.solar_config)
    assert manager.zones[entry.entry_id].intelligence.features.solar == "observe"
    with pytest.raises(ValueError, match="exposure"):
        await manager.async_feature(entry.entry_id, "solar", "active")
    await configure_sources(house, entry, solar_confirmed=True)
    assert confirmed(manager.zones[entry.entry_id].config, manager.environment.solar_config)
    assert manager.zones[entry.entry_id].intelligence.features.solar == "observe"
    await manager.async_feature(entry.entry_id, "solar", "active")
    assert manager.zones[entry.entry_id].intelligence.features.solar == "active"


async def test_unchanged_confirmed_source_remains_valid_and_does_not_copy_entry_data(house):
    from custom_components.radiant_climate.solar import confirmed

    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    await configure_sources(house, entry, solar_confirmed=True)
    await manager.async_feature(entry.entry_id, "solar", "active")
    await configure_sources(house, entry, solar_confirmed=True)
    assert confirmed(manager.zones[entry.entry_id].config, manager.environment.solar_config)
    assert manager.zones[entry.entry_id].intelligence.features.solar == "active"
    assert house.states.get(climate).state == "off"
    house.states.async_set("sensor.fixture_settings_sun", "ok", {"azimuth": 135, "elevation": 30})
    await solar_source_options(house, "sensor.fixture_settings_sun")
    hub = house.config_entries.async_get_entry(manager.hub)
    assert "general" not in hub.options and "kind" not in hub.options
    assert manager.general == "switch.fixture_general"


@pytest.mark.parametrize("step", ["schedule_choose", "schedule_remove"])
async def test_single_day_schedule_ui_rejects_changed_profile_before_selection(house, step):
    entry, _ = await add_zone(house)
    manager = house.data[DOMAIN]
    await manager.async_edit_schedule(entry.entry_id, lambda p: p.set_blocks([0], 420, "home"))
    flow = await house.config_entries.options.async_init(entry.entry_id)
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": step}
    )
    token = next(
        value.config["options"][0]["value"]
        for key, value in flow["data_schema"].schema.items()
        if str(key) == "block"
    )
    assert token == "0|420|home"
    await manager.async_edit_schedule(entry.entry_id, lambda p: p.set_blocks([0], 420, "eco"))
    before = manager.zones[entry.entry_id].program.dump()
    result = await house.config_entries.options.async_configure(flow["flow_id"], {"block": token})
    assert result["type"] == "form" and result["errors"] == {"base": "schedule_changed"}
    assert manager.zones[entry.entry_id].program.dump() == before


@pytest.mark.parametrize("hub_first", [True, False])
@pytest.mark.parametrize("valid", [True, False])
async def test_solar_confirmation_normalisation_waits_for_hub_in_either_load_order(
    house, hub_first, valid
):
    from custom_components.radiant_climate.runtime import Installation

    entry, _ = await add_zone(house)
    current = house.data[DOMAIN]
    alternative = "sensor.fixture_boot_sun"
    house.states.async_set(alternative, "ok", {"azimuth": 135, "elevation": 30})
    await solar_source_options(house, alternative)
    await configure_sources(house, entry, solar_confirmed=True)
    await current.async_feature(entry.entry_id, "solar", "active")
    if not valid:
        house.config_entries.async_update_entry(
            entry, options={**entry.options, "solar_source_signature": ["standard", "sun.sun"]}
        )
        await settle(house)
    z = current.zones[entry.entry_id]
    saved = {**z.intent.dump(), "program": z.program.dump(), "intelligence": z.intelligence.dump()}
    saved["intelligence"]["features"]["solar"] = "active"
    manager = Installation(house)
    manager._saved[entry.entry_id] = saved
    hub = house.config_entries.async_get_entry(current.hub)
    try:
        first, second = (hub, entry) if hub_first else (entry, hub)
        manager._register(first)
        if not hub_first:
            assert manager.zones[entry.entry_id].intelligence.features.solar == "active"
        manager._register(second)
        assert manager.zones[entry.entry_id].intelligence.features.solar == (
            "active" if valid else "observe"
        )
    finally:
        manager.async_stop()


@pytest.mark.parametrize("age,valid", [(899, True), (901, False)])
async def test_solar_position_expires_after_fifteen_minutes(house, age, valid):
    from datetime import timedelta

    from custom_components.radiant_climate.solar import angles

    house.states.async_set("sun.sun", "above_horizon", {"azimuth": 140, "elevation": 26})
    state = house.states.get("sun.sun")
    result = angles(house, {}, state.last_reported + timedelta(seconds=age))
    assert result == ((140, 26) if valid else (None, None))


async def test_entity_validation_errors_are_presented_as_service_validation(house):
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.radiant_climate.climate import RadiantThermostat
    from custom_components.radiant_climate.number import HoldMinutes

    entry, _ = await add_zone(house)
    manager = house.data[DOMAIN]
    entity = RadiantThermostat(manager, entry)
    with pytest.raises(ServiceValidationError):
        await entity.async_set_preset_mode("unsupported")
    with pytest.raises(ServiceValidationError):
        await HoldMinutes(manager, entry).async_set_native_value(0)


async def sparse_learning_zone(hass, monkeypatch, mode="heat", stale_after=10800):
    """Real Core services with an explicitly advanced clock and synthetic reports."""
    from datetime import timedelta
    from types import SimpleNamespace

    from homeassistant.util import dt as dt_util

    entry, climate = await add_zone(hass)
    hass.states.async_set("binary_sensor.fixture_window", "off")
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "hardware"}
    )
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {
            "sensor": "sensor.fixture_a",
            "actuators": ["switch.fixture_a"],
            "available_modes": "heat_cool",
            "target": 21,
            "window": "binary_sensor.fixture_window",
            "minimum_on": 0,
            "minimum_off": 0,
            "stale_after": stale_after,
        },
    )
    assert result["type"] == "create_entry", result
    await settle(hass)
    manager = hass.data[DOMAIN]
    await manager.async_supply(mode)
    await service(
        hass, "climate", "set_temperature", climate, temperature=30 if mode == "heat" else 18
    )
    await service(hass, "switch", "turn_on", zone_entity(hass, entry, "switch", "learning"))
    baseline = 19 if mode == "heat" else 27
    hass.states.async_set("sensor.fixture_a", str(baseline), {"unit_of_measurement": "°C"})
    await service(hass, "climate", "set_hvac_mode", climate, hvac_mode=mode)
    await service(hass, "switch", "turn_on", global_entity(hass))
    clock = SimpleNamespace(now=dt_util.utcnow() + timedelta(minutes=1))
    monkeypatch.setattr(dt_util, "utcnow", lambda: clock.now)
    hass.states.async_set(
        "sensor.fixture_a",
        str(baseline),
        {"unit_of_measurement": "°C"},
        timestamp=clock.now.timestamp(),
    )
    await settle(hass)
    assert hass.states.get("switch.fixture_a").state == "on"
    assert manager.zones[entry.entry_id].intelligence.model.anchor is not None
    return entry, climate, clock


@pytest.mark.parametrize("mode,direction", [("heat", 1), ("cool", -1)])
async def test_real_adapter_learns_from_sparse_reports_without_enabling_predictions(
    house, monkeypatch, mode, direction
):
    from datetime import timedelta

    from custom_components.radiant_climate.core.control import Mode

    entry, climate, clock = await sparse_learning_zone(house, monkeypatch, mode)
    manager = house.data[DOMAIN]
    initial = clock.now
    baseline = 19 if mode == "heat" else 27
    for episode in range(3):
        if episode:
            await service(house, "climate", "set_hvac_mode", climate, hvac_mode="off")
            clock.now = initial + timedelta(days=episode)
            house.states.async_set(
                "sensor.fixture_a",
                str(baseline),
                {"unit_of_measurement": "°C"},
                timestamp=clock.now.timestamp(),
            )
            await service(house, "climate", "set_hvac_mode", climate, hvac_mode=mode)
            clock.now += timedelta(minutes=1)
            house.states.async_set(
                "sensor.fixture_a",
                str(baseline),
                {"unit_of_measurement": "°C"},
                timestamp=clock.now.timestamp(),
            )
            await settle(house)
        for sample in range(1, 5):
            clock.now += timedelta(minutes=45)
            house.states.async_set(
                "sensor.fixture_a",
                str(baseline + direction * sample * 0.375),
                {"unit_of_measurement": "°C"},
                timestamp=clock.now.timestamp(),
            )
            await settle(house)
    response = manager.zones[entry.entry_id].intelligence.model.response(Mode(mode))
    assert response.ready and response.episodes == 3
    assert response.count == 12 and response.hours == pytest.approx(9)
    assert response.rate == pytest.approx(0.5)
    attrs = house.states.get(climate).attributes
    assert attrs["model_ready"] and attrs["model_intervals"] == 12
    assert attrs["model_rate_c_per_hour"] == 0.5
    assert attrs["trend_c_per_hour"] is None
    features = manager.zones[entry.entry_id].intelligence.features
    assert not features.anticipation and not features.predictive
    assert house.states.get("switch.fixture_a").state == "on"


@pytest.mark.parametrize(
    "entity", ["switch.fixture_a", "switch.fixture_general", "binary_sensor.fixture_window"]
)
async def test_intervening_events_break_sparse_learning_even_before_reconciliation(
    house, monkeypatch, entity
):
    import asyncio
    from datetime import timedelta

    entry, _, clock = await sparse_learning_zone(house, monkeypatch)
    manager = house.data[DOMAIN]
    model = manager.zones[entry.entry_id].intelligence.model
    start = clock.now
    clock.now += timedelta(minutes=15)
    house.states.async_set(
        "sensor.fixture_a", "19.125", {"unit_of_measurement": "°C"}, timestamp=clock.now.timestamp()
    )
    await settle(house)
    assert model.anchor is not None
    clock.now += timedelta(minutes=5)
    first, last = ("on", "off") if entity.startswith("binary_sensor") else ("off", "on")
    async with manager._lock:
        house.states.async_set(entity, first, timestamp=clock.now.timestamp())
        house.states.async_set(entity, last, timestamp=clock.now.timestamp())
        await asyncio.sleep(0)
        assert model.anchor is None
    await settle(house)
    assert model.anchor is None  # The cached t+15 reading predates both events.
    clock.now = start + timedelta(minutes=45)
    house.states.async_set(
        "sensor.fixture_a", "19.375", {"unit_of_measurement": "°C"}, timestamp=clock.now.timestamp()
    )
    await settle(house)
    assert not model.statistics
    clock.now = start + timedelta(minutes=90)
    house.states.async_set(
        "sensor.fixture_a", "19.75", {"unit_of_measurement": "°C"}, timestamp=clock.now.timestamp()
    )
    await settle(house)
    assert model.statistics["heat_on"].count == 1
    assert model.statistics["heat_on"].hours == pytest.approx(0.75)


async def test_learning_does_not_extend_temperature_safety_expiry(house, monkeypatch):
    from datetime import timedelta

    entry, climate, clock = await sparse_learning_zone(house, monkeypatch, stale_after=3600)
    model = house.data[DOMAIN].zones[entry.entry_id].intelligence.model
    clock.now += timedelta(minutes=45)
    house.states.async_set(
        "sensor.fixture_a", "19.375", {"unit_of_measurement": "°C"}, timestamp=clock.now.timestamp()
    )
    await settle(house)
    assert model.statistics["heat_on"].count == 1
    clock.now += timedelta(minutes=61)
    await settle(house)
    assert house.states.get(climate).attributes["reason"] == "temperature_stale"
    assert house.states.get("switch.fixture_a").state == "off"
    assert house.states.get("switch.fixture_general").state == "off"
    assert model.anchor is None
    assert model.statistics["heat_on"].count == 1


@pytest.mark.parametrize("entity", ["switch.fixture_a", "switch.fixture_general"])
async def test_relay_attribute_changes_do_not_discard_stable_training(house, monkeypatch, entity):
    from datetime import timedelta

    entry, _, clock = await sparse_learning_zone(house, monkeypatch)
    model = house.data[DOMAIN].zones[entry.entry_id].intelligence.model
    anchor = model.anchor
    clock.now += timedelta(minutes=15)
    state = house.states.get(entity)
    house.states.async_set(
        entity,
        state.state,
        {**state.attributes, "fixture_signal": 80},
        timestamp=clock.now.timestamp(),
    )
    await settle(house)
    assert model.anchor == anchor
    clock.now += timedelta(minutes=30)
    house.states.async_set(
        "sensor.fixture_a", "19.375", {"unit_of_measurement": "°C"}, timestamp=clock.now.timestamp()
    )
    await settle(house)
    assert model.statistics["heat_on"].count == 1
    assert model.statistics["heat_on"].hours == pytest.approx(0.75)


async def test_transient_invalid_measurement_cannot_be_hidden_from_learning(house, monkeypatch):
    import asyncio
    from datetime import timedelta

    entry, _, clock = await sparse_learning_zone(house, monkeypatch)
    manager = house.data[DOMAIN]
    model = manager.zones[entry.entry_id].intelligence.model
    clock.now += timedelta(minutes=20)
    async with manager._lock:
        house.states.async_set("sensor.fixture_a", "unavailable", timestamp=clock.now.timestamp())
        house.states.async_set(
            "sensor.fixture_a",
            str(19 + 20 / 120),
            {"unit_of_measurement": "°C"},
            timestamp=clock.now.timestamp(),
        )
        await asyncio.sleep(0)
        assert model.anchor is None
    await settle(house)
    assert not model.statistics
    assert model.anchor[0] == clock.now
    clock.now += timedelta(minutes=45)
    house.states.async_set(
        "sensor.fixture_a",
        str(19 + 65 / 120),
        {"unit_of_measurement": "°C"},
        timestamp=clock.now.timestamp(),
    )
    await settle(house)
    assert model.statistics["heat_on"].count == 1
    assert model.statistics["heat_on"].hours == pytest.approx(0.75)


async def test_attribute_updates_and_reconnect_do_not_duplicate_one_relay_incident(house):
    from unittest.mock import patch

    await add_zone(house)
    manager = house.data[DOMAIN]
    entity = "switch.fixture_a"
    with patch.object(manager, "_request_update"):
        manager._desired[entity] = False
        for value, signal in (("on", 1), ("on", 2), ("on", 3), ("unavailable", 4), ("on", 5)):
            house.states.async_set(entity, value, {"fixture_signal": signal})
        await house.async_block_till_done()
        assert len(manager._deviations[entity]) == 1
        assert not manager.actuator_faults
        house.states.async_set(entity, "off")
        house.states.async_set(entity, "on")
        await house.async_block_till_done()
        assert manager.actuator_incidents[entity]["reason"] == "repeated_disagreement"
        assert manager.actuator_incidents[entity]["recovery"] == "review"
        house.states.async_set(entity, "off")
    await settle(house)


@pytest.mark.parametrize(
    "source,output", [("transition", "a"), ("same_state", "a"), ("transition", "general")]
)
@pytest.mark.parametrize("stop", [False, True])
async def test_transient_actuator_recovers_only_after_verified_close(
    house, monkeypatch, source, output, stop
):
    from datetime import timedelta
    from unittest.mock import patch

    from homeassistant.util import dt as dt_util

    from custom_components.radiant_climate.runtime import RECOVERY_STABLE

    _, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    entity = f"switch.fixture_{output}"
    now = dt_util.utcnow()
    clock = now
    monkeypatch.setattr(dt_util, "utcnow", lambda: clock)
    await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
    with patch.object(manager, "_request_update"):
        manager.enabled = not stop
        manager._record_fault(entity, "command_timeout", True)
        original = type(house.services).async_call
        attempts = []

        async def close_probe(registry, domain, action, data=None, *args, **kwargs):
            if domain == "switch" and action == "turn_off" and data["entity_id"] == entity:
                attempts.append(action)
                return None
            return await original(registry, domain, action, data, *args, **kwargs)

        with patch.object(type(house.services), "async_call", new=close_probe):
            await manager.async_reconcile()
            assert len(attempts) == 1
            assert house.states.get("switch.fixture_general").state == "off"
            clock += timedelta(seconds=1)
            house.states.async_set(
                entity, "off", {"fixture_signal": 2}, timestamp=clock.timestamp()
            )
            await house.async_block_till_done()
            assert not manager.actuator_incidents[entity]["close_verified"]
            assert not await manager._command(entity, True)
            if source == "transition":
                # A late ON invalidates the previous close verification.
                clock += timedelta(seconds=2)
                house.states.async_set(entity, "on", timestamp=clock.timestamp())
                await house.async_block_till_done()
                assert entity not in manager._close_probe
                clock = now + timedelta(seconds=31)
                await manager.async_reconcile()
                assert len(attempts) == 2
                clock += timedelta(seconds=1)
                house.states.async_set(entity, "off", timestamp=clock.timestamp())
            else:
                clock += timedelta(seconds=1)
                house.states.async_set(
                    entity, "off", {"fixture_signal": 2}, timestamp=clock.timestamp()
                )
            await house.async_block_till_done()
            assert manager.actuator_incidents[entity]["close_verified"]
            await manager.async_reconcile()
            assert entity in manager.actuator_faults
        clock += timedelta(seconds=RECOVERY_STABLE + 1)
        await settle(house)
        assert entity not in manager.actuator_faults
        assert manager.recent_recoveries[-1]["resolution"] == "verified_close"
        assert house.states.get(entity).state == ("off" if stop else "on")
        assert house.states.get("switch.fixture_general").state == ("off" if stop else "on")
    await manager.async_enable(False)


async def test_transient_fault_budget_and_incident_survive_restart_without_cached_proof(house):
    from datetime import timedelta
    from unittest.mock import patch

    from homeassistant.util import dt as dt_util

    from custom_components.radiant_climate.runtime import RECOVERY_COOLDOWN, Installation

    await add_zone(house)
    manager = house.data[DOMAIN]
    entity = "switch.fixture_a"
    now = dt_util.utcnow()
    with patch.object(manager, "_request_update"):
        manager._record_fault(entity, "command_timeout", True)
        manager._close_recovery[entity] = (2, now)
        manager._close_probe[entity] = now - timedelta(minutes=2)
        await manager._save()
        restored = Installation(house)
        try:
            await restored.async_load()
            assert restored.actuator_incidents[entity]["reason"] == "command_timeout"
            assert restored.actuator_incidents[entity]["close_attempts"] == 2
            assert not restored.actuator_incidents[entity]["close_verified"]
            with patch.object(type(house.services), "async_call") as call:
                assert not await restored._command(entity, False)
                call.assert_not_called()
            with patch.object(
                dt_util, "utcnow", return_value=now + timedelta(seconds=RECOVERY_COOLDOWN)
            ):
                assert not await restored._command(entity, False)
                assert restored.actuator_incidents[entity]["close_attempts"] == 1
                assert not restored.actuator_incidents[entity]["close_verified"]
        finally:
            restored.async_stop()
        await manager.async_reset_actuator_faults([entity])


@pytest.mark.parametrize("complete", [False, True])
async def test_unassigned_removed_relay_fault_has_a_resolution(house, complete):
    from unittest.mock import patch

    manager = house.data[DOMAIN]
    entity = "switch.fixture_old"
    with patch.object(manager, "_request_update"):
        manager._command_faults.add(entity)
        if complete:
            manager._retired[entity] = 0
            house.states.async_set(entity, "off")
            await manager.async_reconcile()
            assert entity not in manager.retired_actuators
            assert manager.recent_recoveries[-1]["resolution"] == "retired_closed"
        else:
            await manager.async_acknowledge_retired(entity)
            assert manager.recent_recoveries[-1]["resolution"] == "physical_removal_confirmed"
        assert entity not in manager.actuator_faults


async def test_learning_status_keeps_both_models_visible_with_zone_off(house):
    from custom_components.radiant_climate.core.intelligence import Statistics

    entry, climate = await add_zone(house)
    model = house.data[DOMAIN].zones[entry.entry_id].intelligence.model
    model.statistics["heat_on"] = Statistics(
        count=12, hours=6, delta=3, rate_square=1.5, episodes=3
    )
    await settle(house)
    status = house.states.get(zone_entity(house, entry, "sensor", "learning_status"))
    assert house.states.get(climate).state == "off"
    assert house.states.get(climate).attributes["model_ready"]
    assert status.state == "ready"
    assert status.attributes["heating"]["ready"]
    assert "intervals" in status.attributes["cooling"]["missing_requirements"]
    assert not status.attributes["collecting"]


@pytest.mark.parametrize(
    "value,unit,age,expected",
    [
        ("30", "°C", 899, "valid"),
        ("30", "°C", 901, "stale"),
        ("30", "%", 10, "invalid_unit"),
        ("nan", "°C", 10, "invalid_value"),
        ("unavailable", "°C", 10, "unavailable"),
        ("30", "°C", -61, "future_timestamp"),
    ],
)
def test_hydraulic_source_diagnostics_explain_rejection(value, unit, age, expected):
    from datetime import timedelta
    from types import SimpleNamespace

    from homeassistant.util import dt as dt_util

    from custom_components.radiant_climate.hydraulic import describe_reading

    now = dt_util.utcnow()
    state = SimpleNamespace(
        state=value,
        attributes={"unit_of_measurement": unit},
        last_reported=now - timedelta(seconds=age),
        last_changed=now - timedelta(hours=5),
    )
    result, details = describe_reading(state, now, 900)
    assert details["status"] == expected
    assert details["last_reported"] == state.last_reported.isoformat()
    assert (result is not None) == (expected == "valid")


async def test_second_verified_recovery_waits_for_cooldown(house, monkeypatch):
    from datetime import timedelta
    from unittest.mock import patch

    from homeassistant.util import dt as dt_util

    from custom_components.radiant_climate.runtime import RECOVERY_COOLDOWN, RECOVERY_STABLE

    await add_zone(house)
    manager = house.data[DOMAIN]
    entity = "switch.fixture_a"
    clock = dt_util.utcnow()
    monkeypatch.setattr(dt_util, "utcnow", lambda: clock)
    with patch.object(manager, "_request_update"):
        for attempt in range(2):
            manager._record_fault(entity, "command_timeout", True)
            manager._close_probe[entity] = clock
            clock += timedelta(seconds=1)
            house.states.async_set(
                entity, "off", house.states.get(entity).attributes, timestamp=clock.timestamp()
            )
            await house.async_block_till_done()
            clock += timedelta(seconds=RECOVERY_STABLE + 1)
            manager._recover_transient_faults(clock)
            if not attempt:
                assert entity not in manager.actuator_faults
        assert entity in manager.actuator_faults
        clock += timedelta(seconds=RECOVERY_COOLDOWN)
        manager._recover_transient_faults(clock)
        assert entity not in manager.actuator_faults
        assert len(manager.recent_recoveries) == 2


async def test_fault_arriving_during_store_write_is_still_pending(house):
    from unittest.mock import patch

    await add_zone(house)
    manager = house.data[DOMAIN]
    manager._record_fault("switch.fixture_a", "command_timeout", True)
    saved = []

    async def store_write(snapshot):
        saved.append(snapshot["command_faults"])
        if len(saved) == 1:
            manager._record_fault("switch.fixture_general", "command_error", False)

    with patch.object(manager._store, "async_save", new=store_write):
        await manager._save()
        assert manager._fault_dirty
        assert saved[0] == ["switch.fixture_a"]
        await manager._save()
        assert not manager._fault_dirty
        assert saved[1] == ["switch.fixture_a", "switch.fixture_general"]
