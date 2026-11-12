"""Diagnostics omit names, source entity IDs, installation paths and identifiers."""

from .const import DOMAIN, VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    manager = hass.data[DOMAIN]
    zone = manager.zones.get(entry.entry_id)
    return {
        "version": VERSION,
        "kind": entry.data["kind"],
        "installation_enabled": manager.enabled,
        "supply_mode": manager.supply_mode.value,
        "requested_mode": zone.intent.mode.value if zone else None,
        "target": zone.decision.target if zone and zone.decision else None,
        "reason": zone.decision.reason if zone and zone.decision else None,
        "actuator_count": len(zone.config["actuators"]) if zone else None,
        "optional_modules": zone.intelligence.dump()["features"] if zone else None,
        "model": zone.intelligence.model.dump() if zone else None,
        "optimisation": zone.intelligence.diagnostics if zone else None,
        "valve_position_measured": False,
        "command_fault_count": len(manager.actuator_faults),
        "actuator_incidents": [
            {
                key: item[key]
                for key in (
                    "reason",
                    "recovery",
                    "current_state",
                    "close_attempts",
                    "close_verified",
                )
            }
            for item in manager.actuator_incidents.values()
        ],
    }
