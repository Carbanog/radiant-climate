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
    "general_closing": (
        "Estimated inlet closing time (seconds; 0 = unknown)",
        "Cierre estimado de general (segundos; 0 = desconocido)",
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
    "schedule_in_use": (
        "Switch off Use schedule before removing its last block.",
        "Desactiva Usar horario antes de eliminar su último bloque.",
    ),
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
    "retired_actuator_pending": (
        "Waiting for a retired actuator to be isolated",
        "Pendiente aislar un relé retirado",
    ),
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
    cooling_notice = (
        " Cooling requires independent condensation protection. This integration and optional water diagnostics do not provide it.",
        " El frío requiere protección anticondensación independiente. Ni la integración ni su diagnóstico opcional del agua la proporcionan.",
    )[language]
    result["config"]["step"]["zone"]["description"] += cooling_notice
    options = result["options"]
    options["step"]["hardware"] = options["step"]["init"].copy()
    options["step"]["hardware"]["description"] += cooling_notice
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
    options["step"]["init"]["menu_options"]["hydraulic"] = (
        "Hydraulic diagnostics",
        "Diagnóstico hidráulico",
    )[language]
    options["step"]["schedule_remove"] = {
        "title": ("Remove a block", "Eliminar un bloque")[language],
        "data": {"block": ("Block (1 = Monday)", "Bloque (1 = lunes)")[language]},
    }
    options["abort"] = {
        "installation_only": (
            "Configure this on the installation.",
            "Configúralo en la instalación.",
        )[language],
        "no_schedule": ("There are no schedule blocks.", "No hay bloques horarios configurados.")[
            language
        ],
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
    hydraulic_fields = {
        "hydraulic_enabled": (
            "Enable diagnostics (read only)",
            "Activar diagnóstico (solo lectura)",
        ),
        "hydraulic_supply": ("Supply water temperature", "Sensor de impulsión"),
        "hydraulic_return": ("Return water temperature", "Sensor de retorno"),
        "hydraulic_stale": (
            "Maximum report age (seconds)",
            "Antigüedad máxima de lecturas (segundos)",
        ),
        "hydraulic_settle": ("Stabilisation time (minutes)", "Tiempo de estabilización (minutos)"),
        "hydraulic_duration": ("Sustained deviation (minutes)", "Desviación sostenida (minutos)"),
        "hydraulic_heat_min": (
            "Optional heating supply minimum (°C)",
            "Referencia mínima de impulsión en calor (°C, opcional)",
        ),
        "hydraulic_cool_max": (
            "Optional cooling supply maximum (°C)",
            "Referencia máxima de impulsión en frío (°C, opcional)",
        ),
    }
    options["step"]["hydraulic"] = {
        "title": ("Optional hydraulic diagnostics", "Diagnóstico hidráulico opcional")[language],
        "description": (
            "Read only; never changes thermostats or learning. References must come from your installation, not universal tables. No flow or valve position feedback: observations are not proof of a community fault. Blank references disable supply threshold warnings. No automatic notifications.",
            "Solo lectura; nunca modifica termostatos ni aprendizaje. Las referencias deben corresponder a tu instalación, no a tablas universales. Sin caudal ni posición de válvulas medidos: las observaciones no prueban un fallo comunitario. Referencias vacías desactivan los avisos por umbral de impulsión. No envía notificaciones automáticas.",
        )[language],
        "data": {k: v[language] for k, v in hydraulic_fields.items()},
    }
    hydraulic_states = {
        "disabled": ("Disabled", "Desactivado"),
        "sensor_unavailable": (
            "Missing, stale or invalid water readings",
            "Lecturas de agua ausentes, caducadas o inválidas",
        ),
        "idle": ("No active demand", "Sin demanda activa"),
        "waiting_relays": (
            "Waiting for reported relay states",
            "Esperando estados comunicados de relés",
        ),
        "stabilizing": ("Waiting for stabilisation", "Esperando estabilización"),
        "observing": (
            "Observation; no sustained deviation detected",
            "Observación; sin desviación sostenida detectada",
        ),
        "reference_pending": ("Deviation under observation", "Desviación en observación"),
        "possible_low_supply": (
            "Supply below configured heating reference",
            "Impulsión inferior a la referencia de calor",
        ),
        "possible_high_supply": (
            "Supply above configured cooling reference",
            "Impulsión superior a la referencia de frío",
        ),
        "unexpected_delta": (
            "Unexpected temperature difference; check measurements",
            "Diferencia de temperatura inesperada; revisar mediciones",
        ),
    }
    entities["sensor"]["hydraulic"] = {
        "name": ("Hydraulic diagnostics", "Diagnóstico hidráulico")[language],
        "state": {k: v[language] for k, v in hydraulic_states.items()},
    }
    entities["switch"]["schedule"] = {"name": ("Use schedule", "Usar horario")[language]}
    entities["switch"]["hydraulic_enabled"] = {
        "name": ("Use hydraulic diagnostics", "Usar diagnóstico hidráulico")[language]
    }
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
            "Blank sources inherit installation defaults. Enable modules separately on the device. Geometry edits invalidate confirmation. Review and confirm the unchanged new values before Solar Active; geometry does not prove direct sun.",
            "Fuentes vacías heredan las de instalación. Activa los módulos por separado en el dispositivo. Cambiar la geometría invalida la confirmación. Revisa y confirma los nuevos valores sin modificarlos antes de Solar Activo; la geometría no demuestra sol directo.",
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
        "actuator_problem": {
            "name": ("Actuator review needed", "Revisión de relés pendiente")[language]
        },
        "solar_opportunity": {
            "name": ("General solar conditions", "Condiciones solares generales")[language]
        },
    }
    entities["sensor"]["learning_status"] = {
        "name": ("Thermal learning status", "Estado del aprendizaje térmico")[language],
        "state": {
            "disabled": ("Disabled", "Desactivado")[language],
            "collecting": ("Collecting", "Recopilando")[language],
            "paused": ("Paused", "En pausa")[language],
            "ready": ("Model ready", "Modelo listo")[language],
        },
    }
    entities["button"]["reset_learning"] = {
        "name": ("Reset thermal learning", "Restablecer aprendizaje térmico")[language]
    }
    entities["button"]["check_actuators"] = {
        "name": ("Check again", "Volver a comprobar")[language]
    }
    result["issues"] = {
        "actuator_attention": {
            "title": ("Actuator review needed", "Revisión de relés pendiente")[language],
            "description": (
                "Active faults: {faults}. Pending retired outputs: {retired}. Relays unavailable for at least five minutes: {unavailable}. Check the affected outputs in the actuator problem sensor, then check their connection and power. Assigned relays recover when their reported close is verified. For retired outputs, verify physical disconnection.",
                "Fallos activos: {faults}. Salidas retiradas pendientes: {retired}. Relés indisponibles durante al menos cinco minutos: {unavailable}. Consulta las salidas afectadas en el sensor Revisión de relés pendiente y comprueba su conexión y alimentación. Los relés asignados se recuperan cuando se verifica el cierre comunicado. Para salidas retiradas, comprueba su desconexión física.",
            )[language],
        },
        "storage_interrupted": {
            "title": ("Climate control paused for review", "Climatización detenida para revisión")[
                language
            ],
            "description": (
                "Radiant Climate could not save its state or detected an interruption while control was active. Check Home Assistant storage and the reported relay states. Then turn Climate on to resume control.",
                "Radiant Climate no pudo guardar su estado o detectó una interrupción con el control activo. Comprueba el almacenamiento de Home Assistant y el estado comunicado de los relés. Después activa Climatización para reanudar.",
            )[language],
        },
    }
    service_text = {
        "copy_settings": (
            ("Copy thermostat settings", "Copiar ajustes entre termostatos"),
            (
                "Copies selected settings. Blank targets selects the other zones. Does not copy hardware or enable off zones.",
                "Copia los ajustes elegidos. Sin destinos, se aplica al resto de zonas. No copia dispositivos ni enciende zonas apagadas.",
            ),
            {
                "source": ("Source thermostat", "Termostato de origen"),
                "targets": (
                    "Targets (blank for all other zones)",
                    "Destinos (vacío para todas las demás zonas)",
                ),
                "parts": ("Settings to copy", "Ajustes que copiar"),
            },
        ),
        "reset_actuator_faults": (
            ("Reset actuator faults after review", "Reconocer fallos de relés tras revisión"),
            (
                "With Climate enabled off, acknowledge reviewed faults. Selected outputs must report off and not be pending retirement. Does not enable control.",
                "Con Climatización apagada, reconoce los fallos revisados. Las salidas seleccionadas deben comunicar apagado y no tener una retirada pendiente. No enciende la instalación.",
            ),
            {
                "actuators": (
                    "Faulty actuators (blank for all)",
                    "Relés con fallo (vacío para todos)",
                ),
                "confirmed_review": (
                    "I reviewed the cause and reported states",
                    "He revisado la causa del fallo y los estados comunicados",
                ),
            },
        ),
        "acknowledge_retired_actuator": (
            (
                "Confirm physical removal of a retired actuator",
                "Confirmar retirada física de un relé antiguo",
            ),
            (
                "Only with Climate enabled off after checking physical disconnection. Releases an unassigned retired output; does not prove valve closure.",
                "Solo con Climatización apagada y tras comprobar la desconexión física. Libera una salida retirada pendiente que ya no está asignada; no acredita el cierre de una válvula.",
            ),
            {
                "actuator": (
                    "Old entity ID from retired_actuators",
                    "Entidad antigua de retired_actuators",
                ),
                "confirmed_disconnected": (
                    "I checked it is physically disconnected",
                    "He comprobado que está físicamente desconectado",
                ),
            },
        ),
    }
    result["services"] = {
        key: {
            "name": name[language],
            "description": description[language],
            "fields": {field: {"name": label[language]} for field, label in fields.items()},
        }
        for key, (name, description, fields) in service_text.items()
    }
    result["selector"]["copy_parts"] = {
        "options": {
            key: label[language]
            for key, label in {
                "temperatures": ("Profile temperatures", "Temperaturas de los perfiles"),
                "manual": ("Manual policy and duration", "Política y duración de Manual"),
                "schedule": ("Schedule blocks and activation", "Bloques y activación del horario"),
                "modules": (
                    "Module switches (not sources, geometry or learning)",
                    "Activación de módulos (sin fuentes, orientación ni aprendizaje)",
                ),
                "vacation": ("Absence and return", "Ausencia y fecha de vuelta"),
            }.items()
        }
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
