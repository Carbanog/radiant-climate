"""Generate the two native HA form translations from one reviewed vocabulary."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIELDS = {
    "weather": ("Weather source (optional)", "Fuente meteorológica (opcional)"),
    "outdoor": ("Outdoor sensor (optional)", "Sensor exterior (opcional)"),
    "general_travel": (
        "Estimated inlet opening time (seconds; 0 = unknown)",
        "Apertura estimada de general (segundos; 0 = desconocido)",
    ),
    "valve_travel": (
        "Estimated zone closing time (seconds; 0 = unknown)",
        "Cierre estimado de zona (segundos; 0 = desconocido)",
    ),
    "window_open_delay": ("Window opening delay (seconds)", "Retardo al abrir ventana (segundos)"),
    "window_close_delay": (
        "Window closing delay (seconds)",
        "Retardo al cerrar ventana (segundos)",
    ),
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
    "solar_pause": (
        "Solar opportunity with warming near target",
        "Oportunidad solar con calentamiento cerca de consigna",
    ),
    "predictive_pause": (
        "Residual thermal response near target",
        "Respuesta térmica residual cerca de consigna",
    ),
    "anticipation": (
        "Preparing the next scheduled profile",
        "Anticipando el próximo perfil horario",
    ),
    "setup_not_ready": (
        "Waiting for registered zones and outputs",
        "Esperando zonas y salidas registradas",
    ),
    "season_transition": ("Closing before changing season", "Cierre previo al cambio de temporada"),
    "zone_closing_estimated": (
        "Waiting for estimated zone closure",
        "Esperando cierre estimado de zona",
    ),
    "general_opening_estimated": (
        "Waiting for estimated inlet opening",
        "Esperando apertura estimada de general",
    ),
    "not_ready": ("Initialising", "Inicializando"),
    "global_off": ("Suspended by global switch", "Suspendido por interruptor general"),
    "zone_off": ("Zone switched off", "Zona apagada"),
    "unsupported_mode": ("Unsupported mode", "Modo no admitido"),
    "supply_mode_mismatch": (
        "Declared supply season does not match",
        "No coincide con la temporada de suministro declarada",
    ),
    "actuator_unavailable": ("Actuator unavailable", "Relé no disponible"),
    "window_open": ("Window pause (open or settling)", "Pausa por ventana"),
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
                    "title": ("General configuration", "Configuración general")[language],
                    "description": (
                        "Configure the shared system. Control starts disabled. Do not share outputs with another controller.",
                        "Configura el sistema compartido. El control comienza desactivado. No compartas las salidas con otro controlador.",
                    )[language],
                    "data": {"general": labels["general"]},
                },
                "zone": {
                    "title": ("Add thermostat", "Añadir termostato")[language],
                    "description": (
                        "Select the devices and initial temperature. The thermostat is created off. Profiles, schedules and optional features are available in its settings and controls.",
                        "Selecciona los dispositivos y la temperatura inicial. El termostato se crea apagado. Los perfiles, horarios y funciones opcionales están disponibles en su configuración y controles.",
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
        "title": ("Climate settings", "Configuración de climatización")[language],
        "menu_options": {
            "hardware": ("Devices and regulation", "Dispositivos y regulación")[language],
            "schedule_add": ("Add or replace schedule block", "Añadir o sustituir bloque horario")[
                language
            ],
            "schedule_remove": ("Remove schedule block", "Eliminar bloque horario")[language],
            "sources": ("Environment, solar and anticipation", "Entorno, sol y anticipación")[
                language
            ],
            "vacation": ("Vacation and return", "Vacaciones y regreso")[language],
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
            "away": ("Away", "Ausente")[language],
        }
    }
    entities = result["entity"]
    entities["switch"]["schedule"] = {"name": ("Use schedule", "Usar horario")[language]}
    entities["switch"]["window_enabled"] = {
        "name": ("Pause for window", "Pausar por ventana")[language]
    }
    entities["switch"]["household_away"] = {
        "name": ("Household vacation", "Vacaciones de la vivienda")[language]
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
    options["step"]["sources"] = {
        "title": ("Optional sources and optimisation", "Fuentes opcionales y optimización")[
            language
        ],
        "description": (
            "Blank sources inherit installation defaults. Enable modules separately on the device. Confirm actual exposure before Solar Active; geometry does not prove direct sun.",
            "Fuentes vacías heredan las de instalación. Activa los módulos por separado en el dispositivo. Comprueba la incidencia antes de Solar Activo; la geometría no demuestra sol directo.",
        )[language],
        "data": {
            **{k: v[language] for k, v in FIELDS.items() if k in ("weather", "outdoor")},
            "orientation": (
                "Window azimuth (degrees from north)",
                "Azimut de ventanas (grados desde norte)",
            )[language],
            "solar_elevation": (
                "Minimum observed solar elevation",
                "Elevación mínima de incidencia observada",
            )[language],
            "solar_width": (
                "Allowed azimuth deviation from facade",
                "Desviación máxima de azimut respecto a fachada",
            )[language],
            "solar_confirmed": (
                "Window exposure and shadows verified",
                "Incidencia y umbrales de sombra comprobados",
            )[language],
            "max_advance": ("Maximum advance (minutes)", "Adelanto máximo (minutos)")[language],
            "residual_minutes": (
                "Residual projection horizon (minutes)",
                "Horizonte de proyección residual (minutos)",
            )[language],
        },
    }
    options["step"]["vacation"] = {
        "title": ("Vacation", "Vacaciones")[language],
        "description": (
            "From General configuration this applies Away to all loaded zones; from a thermostat, only that zone. Off zones remain off. An optional return date ends the absence; blank means indefinite. Activating replaces previous manual holds; later manual changes take priority.",
            "Desde Configuración general aplica Ausente a todas las zonas cargadas; desde un termostato, solo a esa zona. No enciende zonas apagadas. La fecha de regreso es opcional; vacía significa indefinido. Activar sustituye retenciones anteriores; los cambios manuales posteriores tienen prioridad.",
        )[language],
        "data": {
            "enabled": ("Away enabled", "Activar Ausente")[language],
            "date": ("Return date (optional)", "Fecha de regreso (opcional)")[language],
            "time": ("Return time", "Hora de regreso")[language],
        },
    }
    for key, labels in {
        "weather": ("Use weather forecast", "Usar previsión meteorológica"),
        "outside": ("Use outdoor temperature", "Usar temperatura exterior"),
        "learning": ("Learn thermal response", "Aprender respuesta térmica"),
        "anticipation": ("Anticipate schedule", "Anticipar horario"),
        "predictive": ("Use residual response", "Aprovechar inercia térmica"),
        "away": ("Away", "Ausente"),
    }.items():
        entities["switch"][key] = {"name": labels[language]}
    entities["select"]["solar"] = {
        "name": ("Solar contribution", "Aporte solar")[language],
        "state": {
            "off": ("Disabled", "Desactivado")[language],
            "observe": ("Observation", "Observación")[language],
            "active": ("Optimise", "Optimizar")[language],
        },
    }
    entities["binary_sensor"] = {
        "solar_opportunity": {
            "name": ("Shared solar opportunity", "Oportunidad solar compartida")[language]
        }
    }
    entities["button"]["reset_learning"] = {
        "name": ("Reset thermal learning", "Restablecer aprendizaje térmico")[language]
    }
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
