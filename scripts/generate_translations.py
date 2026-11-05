"""Generate the two native HA form translations from one reviewed vocabulary."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIELDS = {
    "general": ("Shared inlet valve (optional)", "Válvula general (opcional)"),
    "sensor": ("Indoor temperature sensor", "Sensor de temperatura interior"),
    "actuators": ("Actuator switches", "Relé o relés"),
    "available_modes": ("Available operating modes", "Modos disponibles"),
    "target": ("Initial target temperature", "Temperatura deseada inicial"),
    "window": ("Window contact (optional)", "Contacto de ventana (opcional)"),
    "hysteresis": ("Control hysteresis (°C)", "Histéresis de regulación (°C)"),
    "minimum_on": ("Minimum on period (seconds)", "Tiempo mínimo activo (segundos)"),
    "minimum_off": ("Minimum off period (seconds)", "Tiempo mínimo inactivo (segundos)"),
    "stale_after": (
        "Maximum temperature report age (seconds)",
        "Antigüedad máxima del dato interior (segundos)",
    ),
}
ERRORS = {
    "invalid_actuators": (
        "Choose at least one actuator, without duplicates.",
        "Selecciona al menos un relé, sin duplicados.",
    ),
    "actuator_assigned": (
        "This actuator is already assigned to another zone or the inlet.",
        "Este relé ya está asignado a otra zona o a la general.",
    ),
    "entity_missing": ("A selected entity does not exist.", "Una entidad seleccionada no existe."),
    "invalid_configuration": (
        "Check the values and required fields.",
        "Comprueba los valores y campos obligatorios.",
    ),
}
REASONS = {
    "not_ready": ("Initialising", "Inicializando"),
    "global_off": ("Suspended by global switch", "Suspendido por interruptor general"),
    "zone_off": ("Zone switched off", "Zona apagada"),
    "unsupported_mode": ("Unsupported mode", "Modo no admitido"),
    "supply_mode_mismatch": (
        "Declared supply season does not match",
        "No coincide con la temporada de suministro declarada",
    ),
    "actuator_unavailable": ("Actuator unavailable", "Relé no disponible"),
    "window_open": ("Window open", "Ventana abierta"),
    "window_unavailable": ("Window contact unavailable", "Contacto de ventana no disponible"),
    "temperature_invalid": ("Indoor temperature invalid", "Temperatura interior inválida"),
    "temperature_missing": ("No indoor temperature report", "Sin dato de temperatura interior"),
    "temperature_stale": ("Indoor report expired", "Dato interior caducado"),
    "minimum_cycle": ("Minimum cycle period", "Tiempo mínimo de maniobra"),
    "clock_changed": ("Clock change under review", "Cambio de reloj pendiente de reconciliar"),
    "demand": ("Temperature demand", "Demanda térmica"),
    "satisfied": ("Target satisfied", "Consigna satisfecha"),
    "supply_not_ready": (
        "Shared supply relay not ready",
        "Relé de suministro compartido no preparado",
    ),
}


def document(language: int) -> dict:
    labels = {k: v[language] for k, v in FIELDS.items()}
    errors = {k: v[language] for k, v in ERRORS.items()}
    return {
        "title": "Radiant Climate",
        "config": {
            "step": {
                "installation": {
                    "title": ("Installation", "Instalación")[language],
                    "description": (
                        "Development build. Control starts disabled. Do not share outputs with another controller.",
                        "Versión de desarrollo. El control comienza desactivado. No compartas las salidas con otro controlador.",
                    )[language],
                    "data": {"general": labels["general"]},
                },
                "zone": {
                    "title": ("Add thermostat", "Añadir termostato")[language],
                    "description": (
                        "Only basic control is implemented in this development version. The thermostat is created off.",
                        "Esta versión de desarrollo implementa solo el control básico. El termostato se crea apagado.",
                    )[language],
                    "data": {
                        k: labels[k] for k in ["sensor", "actuators", "available_modes", "target"]
                    },
                },
            },
            "error": errors,
            "abort": {
                "already_configured": (
                    "The installation already exists.",
                    "La instalación ya existe.",
                )[language]
            },
        },
        "options": {
            "step": {
                "init": {
                    "title": ("Settings", "Configuración")[language],
                    "description": (
                        "Changes reload this entry. Editing the installation disables global control; explicitly enable it after reviewing outputs.",
                        "Los cambios recargan esta entrada. Editar la instalación desactiva el control general; reactívalo expresamente tras revisar las salidas.",
                    )[language],
                    "data": labels,
                }
            },
            "error": errors,
        },
        "selector": {
            "available_modes": {
                "options": {
                    "heat": ("Heating", "Calor")[language],
                    "cool": ("Cooling", "Frío")[language],
                    "heat_cool": ("Heating and cooling", "Calor y frío")[language],
                }
            }
        },
        "entity": {
            "switch": {"enabled": {"name": ("Climate enabled", "Climatización")[language]}},
            "select": {
                "supply_mode": {
                    "name": ("Declared supply season", "Temporada de suministro declarada")[
                        language
                    ],
                    "state": {
                        "heat": ("Heating", "Calor")[language],
                        "cool": ("Cooling", "Frío")[language],
                    },
                }
            },
            "sensor": {
                "reason": {
                    "name": ("Control reason", "Motivo de regulación")[language],
                    "state": {k: v[language] for k, v in REASONS.items()},
                }
            },
        },
    }


if __name__ == "__main__":
    destination = ROOT / "custom_components/radiant_climate"
    (destination / "translations").mkdir(exist_ok=True)
    for name, language in [
        ("strings.json", 0),
        ("translations/en.json", 0),
        ("translations/es.json", 1),
    ]:
        (destination / name).write_text(
            json.dumps(document(language), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
