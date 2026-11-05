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


def complete_document(language):
    result = document(language)
    options = result["options"]
    options["step"]["hardware"] = options["step"]["init"].copy()
    options["step"]["init"] = {
        "title": ("Thermostat settings", "Configuración del termostato")[language],
        "menu_options": {
            "hardware": ("Devices and regulation", "Dispositivos y regulación")[language],
            "schedule_add": ("Add or replace schedule block", "Añadir o sustituir bloque horario")[
                language
            ],
            "schedule_remove": ("Remove schedule block", "Eliminar bloque horario")[language],
        },
    }
    options["step"]["schedule_add"] = {
        "title": ("Weekly schedule", "Programación semanal")[language],
        "description": (
            "The profile remains active until the next block, including overnight. Reusing a day and time replaces that block.",
            "El perfil se mantiene hasta el siguiente bloque, también de un día a otro. Repetir día y hora sustituye ese bloque.",
        )[language],
        "data": {
            "days": ("Weekdays", "Días de la semana")[language],
            "time": ("Start time", "Hora de inicio")[language],
            "profile": ("Profile", "Perfil")[language],
        },
    }
    options["step"]["schedule_remove"] = {
        "title": ("Remove a block", "Eliminar un bloque")[language],
        "data": {"block": ("Block (1 = Monday)", "Bloque (1 = lunes)")[language]},
    }
    options["abort"] = {
        "no_schedule": ("There are no schedule blocks.", "No hay bloques horarios configurados.")[
            language
        ]
    }
    result["config"]["step"]["zone"]["description"] = (
        "Select devices. The thermostat starts off. Profiles and scheduling can be configured afterwards.",
        "Selecciona los dispositivos. El termostato se crea apagado. Los perfiles y horarios se configuran después.",
    )[language]
    result["selector"]["days"] = {
        "options": {
            str(n): names[language]
            for n, names in enumerate(
                [
                    ("Monday", "Lunes"),
                    ("Tuesday", "Martes"),
                    ("Wednesday", "Miércoles"),
                    ("Thursday", "Jueves"),
                    ("Friday", "Viernes"),
                    ("Saturday", "Sábado"),
                    ("Sunday", "Domingo"),
                ]
            )
        }
    }
    result["selector"]["profile"] = {
        "options": {
            "home": ("Normal", "Normal")[language],
            "eco": "Eco",
            "sleep": ("Sleep", "Noche")[language],
        }
    }
    entities = result["entity"]
    entities["switch"]["schedule"] = {"name": ("Use schedule", "Usar horario")[language]}
    entities["switch"]["window_enabled"] = {
        "name": ("Pause for window", "Pausar por ventana")[language]
    }
    entities["button"] = {"resume": {"name": ("Resume schedule", "Volver al horario")[language]}}
    entities["select"]["manual_policy"] = {
        "name": ("Manual hold behavior", "Comportamiento de Manual")[language],
        "state": {
            "duration": ("For the configured duration", "Durante el tiempo configurado")[language],
            "next_change": ("Until the next schedule block", "Hasta el próximo bloque horario")[
                language
            ],
            "until_resume": ("Until resume schedule", "Hasta volver al horario")[language],
        },
    }
    entities["number"] = {
        "hold_minutes": {"name": ("Manual duration", "Duración de Manual")[language]}
    }
    for mode, names in [("heat", ("Heating", "Calor")), ("cool", ("Cooling", "Frío"))]:
        for profile, title in result["selector"]["profile"]["options"].items():
            entities["number"][f"{mode}_{profile}"] = {"name": f"{names[language]} · {title}"}
    return result


if __name__ == "__main__":
    destination = ROOT / "custom_components/radiant_climate"
    (destination / "translations").mkdir(exist_ok=True)
    for name, language in [
        ("strings.json", 0),
        ("translations/en.json", 0),
        ("translations/es.json", 1),
    ]:
        (destination / name).write_text(
            json.dumps(complete_document(language), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
