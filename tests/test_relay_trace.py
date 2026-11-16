"""Replay identical Home Assistant inputs in candidate and released code."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from test_homeassistant import DOMAIN, add_zone, global_entity, house, service, settle  # noqa: F401


async def test_relay_sequence_without_optimizations(house):  # noqa: F811
    entry, climate = await add_zone(house)
    manager = house.data[DOMAIN]
    window = "binary_sensor.fixture_window"
    house.states.async_set(window, "off")
    config = dict(manager.zones[entry.entry_id].config)
    config.pop("kind")
    config.pop("modes")
    config.update(window=window, available_modes="heat_cool")
    flow = await house.config_entries.options.async_init(entry.entry_id)
    flow = await house.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "hardware"}
    )
    assert (await house.config_entries.options.async_configure(flow["flow_id"], config))[
        "type"
    ] == "create_entry"
    await settle(house)
    await manager.async_edit_schedule(entry.entry_id, lambda p: p.set_blocks(range(7), 0, "home"))
    await manager.async_schedule(entry.entry_id, True)
    call = house.services.async_call
    trace = []

    async def record(domain, service, service_data=None, **kwargs):
        relay = (service_data or {}).get("entity_id")
        if domain == "switch" and relay in ("switch.fixture_a", "switch.fixture_general"):
            trace.append((service, relay))
        return await call(domain, service, service_data, **kwargs)

    with patch.object(type(house.services), "async_call", side_effect=record):
        await service(house, "climate", "set_hvac_mode", climate, hvac_mode="heat")
        await service(house, "switch", "turn_on", global_entity(house))
        assert house.states.get("switch.fixture_a").state == "on"
        for window_state, expected in (("on", "off"), ("off", "on")):
            house.states.async_set(window, window_state)
            await settle(house)
            assert house.states.get("switch.fixture_a").state == expected
        house.states.async_set("sensor.fixture_a", "unavailable")
        await settle(house)
        assert house.states.get("switch.fixture_a").state == "off"
        house.states.async_set("sensor.fixture_a", "19", {"unit_of_measurement": "°C"})
        await settle(house)
        assert house.states.get("switch.fixture_a").state == "on"
        await service(house, "climate", "set_temperature", climate, temperature=18)
        assert house.states.get("switch.fixture_a").state == "off"
        await service(house, "climate", "set_temperature", climate, temperature=22)
        assert house.states.get("switch.fixture_a").state == "on"
        await service(house, "switch", "turn_off", global_entity(house))
        assert house.states.get("switch.fixture_general").state == "off"
    if path := os.environ.get("RADIANT_RELAY_TRACE"):
        Path(path).write_text(json.dumps(trace), encoding="utf-8")
