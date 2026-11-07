# Observación y ajuste durante el uso

Empieza con módulos predictivos desactivados, horarios y perfiles cómodos y tiempos compatibles con los actuadores. Activa Aprender respuesta térmica para recopilar datos válidos. El controlador base sigue funcionando si el modelo no llega a ser utilizable. No importes un modelo de otra habitación ni confundas una curva sintética de pruebas con tu losa.

## Qué revisar

Observa temperatura interior, consigna de confort, control_target, motivo, estado comunicado del actuador, ventanas y temporada declarada. El número de órdenes o la potencia eléctrica del actuador no mide energía térmica consumida. Compara periodos con condiciones semejantes y anota cambios de suministro, ventilación y uso.

Revisa sobreoscilación, cuánto tarda en recuperarse el confort y si aparecen ciclos innecesarios. Una consigna nocturna muy distinta puede exigir recuperar durante horas. Ajusta primero horarios y temperaturas, después parámetros de regulación. Cambia una cosa cada vez y conserva una forma de revertir.

Solar debe permanecer en Observación hasta medir incidencia y sombras por zona. Registra cuándo empieza/termina sol directo y posición solar; una elevación única no sirve para todas las fachadas y fechas. La meteorología puede fallar: revisa que la zona continúe con regulación interior y que el diagnóstico explique la degradación.

## Plantilla de diagnóstico local

En Herramientas → Plantilla puedes pegar lo siguiente. Produce una instantánea; no cambia estados ni lee credenciales. La salida puede contener nombres de entidades y preferencias domésticas: consérvala privadamente y anonimízala antes de compartir.

```jinja
{% for entity in integration_entities('radiant_climate') | sort %}
{% if entity.startswith('climate.') %}
{{ entity }}:
  estado: {{ states(entity) }}
  interior: {{ state_attr(entity, 'current_temperature') }}
  consigna: {{ state_attr(entity, 'temperature') }}
  objetivo_regulacion: {{ state_attr(entity, 'control_target') }}
  control: {{ state_attr(entity, 'control_state') }}
  motivo: {{ state_attr(entity, 'reason') }}
  manual_hasta: {{ state_attr(entity, 'manual_until') }}
  proximo_cambio: {{ state_attr(entity, 'next_schedule_change') }}
  modelo_listo: {{ state_attr(entity, 'model_ready') }}
  horas_validas: {{ state_attr(entity, 'model_hours') }}
  intervalos_validos: {{ state_attr(entity, 'model_intervals') }}
  velocidad_observada: {{ state_attr(entity, 'model_rate_c_per_hour') }}
  separacion_maxima_informes_min: {{ state_attr(entity, 'learning_max_gap_minutes') }}
  episodios: {{ state_attr(entity, 'model_episodes') }}
  tendencia: {{ state_attr(entity, 'trend_c_per_hour') }}
  solar: {{ state_attr(entity, 'solar_mode') }}
  candidato_solar: {{ state_attr(entity, 'solar_candidate') }}
  meteo: {{ state_attr(entity, 'weather_status') }}
{% endif %}
{% endfor %}
```

Para evaluar semanas o meses utiliza Historial de HA con esas entidades y los sensores originales. La instantánea no sustituye una serie temporal. Retén resolución y tiempo suficientes en Recorder y comprueba que no se excluyen esas entidades. Un diagnóstico de modelo listo indica que pasó los filtros del algoritmo; no acredita por sí solo mejor confort o eficiencia.

Si una optimización no mejora el resultado, desactívala en su zona o copia los módulos desactivados al resto. Se recupera la regulación básica sin dejar una consigna artificial. Restablece aprendizaje cuando cambien de forma importante sensores, circuitos o emisores; revisa de nuevo la respuesta por temporada.


## Sensores a pilas y cadencia

En el desarrollo posterior a v0.2.7 se han ampliado las ventanas de aprendizaje
sin ampliar la caducidad de seguridad; véase [lecturas irregulares](intelligence.md#lecturas-irregulares--desarrollo-posterior-a-v027).
Los atributos nuevos de la plantilla aparecerán como `None` en versiones anteriores.
Comprueba la cadencia de los informes durante demandas reales, no solo en una sala
estable. No aumentes la caducidad únicamente para obtener un modelo: también retrasa
el cierre por pérdida de datos. Puedes dejar Aprender activado y mantener Anticipar
horario y Aprovechar inercia desactivados mientras observas si se acumulan intervalos.
Un modelo listo con tendencia no disponible permite ciertas anticipaciones de agenda,
pero no las pausas inmediatas que dependen de tendencia. No es necesario aumentar
la frecuencia de transmisión para aparentar muestras ni renovar datos con mensajes
de batería.
