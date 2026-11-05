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
    await service(house, "switch", "turn_on", zone_entity(house, entry, "switch", "away"))
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


async def test_repeated_output_deviations_inhibit_shared_supply_and_persist(house):
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
    assert house.states.get("switch.fixture_general").state == "off"
    assert house.states.get("switch.fixture_b").state == "off"
    restored = Installation(house)
    try:
        await restored.async_load()
        assert "switch.fixture_a" in restored._command_faults
    finally:
        restored.async_stop()
    await service(house, "switch", "turn_off", global_entity(house))
    assert not manager._command_faults
    assert house.states.get("switch.fixture_a").state == "off"


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


@pytest.mark.parametrize("scenario", ["duration", "until_resume", "expired", "individual_off"])
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
    if scenario == "expired":
        house.data[DOMAIN].zones[entry.entry_id].intent.hold.until = dt_util.utcnow() - timedelta(
            seconds=1
        )
    if scenario == "individual_off":
        await service(house, "climate", "turn_off", climate)
        await service(house, "switch", "turn_on", global_entity(house))
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
        for stored in restarted.config_entries.async_entries(DOMAIN):
            if stored.state.value != "loaded":
                assert await restarted.config_entries.async_setup(stored.entry_id)
        await restarted.async_start()
        await settle(restarted)
        state = restarted.states.get(climate)
        assert state is not None
        assert state.state == "off"
        assert restarted.states.get("switch.fixture_a").state == "off"
        assert restarted.states.get("switch.fixture_general").state == "off"
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
