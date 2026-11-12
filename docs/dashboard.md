# Panel nativo por secciones

La ficha genérica del dispositivo la organiza Home Assistant. Para un uso diario claro,
añade una tarjeta Termostato por zona y tarjetas Entidades separadas por tarea.
No necesitas instalar tarjetas externas ni crear ayudantes. En cada tarjeta Entidades,
selecciona las entidades reales desde el editor visual; los identificadores dependen del
nombre y área de tu instalación, no copies identificadores de otra vivienda.

| Tarjeta | Controles existentes que incluir |
|---|---|
| Vivienda | Climatización, Temporada de suministro declarada, Vacaciones de la vivienda |
| Termostato de la zona | Entidad climate; el modo Apagado se mantiene hasta encender |
| Horario y Manual | Usar horario, Comportamiento de Manual, Duración de Manual, Reanudar programa |
| Perfiles de calor | Calor · Normal, Eco, Noche, Ausente |
| Perfiles de frío | Frío · Normal, Eco, Noche, Ausente |
| Funciones opcionales | Aprender respuesta térmica, Aprovechar inercia, Anticipar horario, Aporte solar, Usar previsión, Usar temperatura exterior |
| Ventanas | Pausar por ventana |
| Diagnóstico | Motivo de regulación y Revisión de relés pendiente; agua si está configurada |

Usa un panel con vistas de Salón/Habitación/Despacho o una vista por zona para no mostrar
los ocho perfiles de cada estancia a la vez. Los ajustes de dispositivos, agenda,
fuentes y ángulos se cambian desde Configurar en la entrada correspondiente.
En móvil, las tarjetas nativas se disponen verticalmente; en escritorio puedes usar
una vista Secciones y agruparlas por tarea. No cambia el control térmico ni sus datos.

Para copiar preferencias entre zonas utiliza la acción Copiar ajustes y selecciona
solo las partes que quieras compartir. La copia de módulos no copia orientación,
sensores, relés o modelos térmicos. Comprueba siempre los perfiles de destino.


## Aviso de recuperación de válvulas

Para el desarrollo posterior a v0.2.9. Añade una tarjeta condicional arriba en la
vista de climatización. El ejemplo utiliza entidades ficticias. Sustituye el sensor
de problema, el interruptor general y el botón por los de tu dispositivo Climatización.

```yaml
type: conditional
conditions:
  - condition: state
    entity: binary_sensor.climatizacion_revision_de_reles_pendiente
    state: 'on'
card:
  type: vertical-stack
  cards:
    - type: markdown
      title: Estado de la climatización
      content: |-
        {% set problem = 'binary_sensor.climatizacion_revision_de_reles_pendiente' %}
        {% set control = 'switch.climatizacion' %}
        {% set incidents = state_attr(control, 'actuator_incidents') or {} %}
        {% set unavailable = state_attr(problem, 'unavailable_actuators') or [] %}
        {% set retired = state_attr(control, 'retired_actuators') or [] %}
        {% if state_attr(problem, 'shared_supply_blocked') %}
        **Suministro en pausa mientras se comprueba el cierre.**
        {% elif is_state(control, 'off') %}
        **Climatización apagada.**
        {% else %}
        **Recuperación de una salida en curso.**
        {% endif %}

        {% for relay in state_attr(problem, 'affected_actuators') or [] %}
        {% set incident = incidents.get(relay, {}) %}
        - **{{ state_attr(relay, 'friendly_name') or incident.get('name') or relay }}**
          {% if relay in retired or incident.get('recovery') == 'review' %}
          · Salida retirada. Requiere revisión de mantenimiento.
          {% elif relay in unavailable %}
          · Sin conexión. Comprueba que tenga alimentación.
          {% elif incident.get('close_verified') %}
          · Cierre comunicado. Esperando que se estabilice.
          {% else %}
          · Comprobando cierre.
          {% endif %}
          {% if incident.get('next_check') and as_timestamp(incident.next_check) > as_timestamp(now()) %}
          Próxima comprobación a partir de las {{ as_local(as_datetime(incident.next_check)).strftime('%H:%M') }}.
          {% endif %}
        {% endfor %}
    - type: button
      name: Volver a comprobar
      icon: mdi:refresh
      entity: button.climatizacion_volver_a_comprobar
      tap_action:
        action: perform-action
        perform_action: button.press
        target:
          entity_id: button.climatizacion_volver_a_comprobar
```
