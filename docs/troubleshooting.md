# Problemas y soluciones

Antes de cambiar parámetros, consulta el sensor **Motivo de regulación** de la zona. En los atributos del termostato aparecen la intención solicitada, la consigna, `control_target`, la retención Manual y la disponibilidad de las funciones avanzadas. Un estado de relé es información comunicada, no una medición de posición o caudal.

## Problemas conocidos de v0.2.0-beta.1

**Los dos defectos siguientes están resueltos en v0.2.0-beta.2.** Si utilizas beta.1, sigue los [pasos de actualización](release-notes.md). La etiqueta original se conserva para trazabilidad.

Activar **Ausente sin fecha de regreso** con una agenda configurada provocaba un error al publicar los atributos del termostato. Podía devolver HTTP 500 y dejar diagnósticos sin actualizar. La corrección `ce64789` tiene una regresión ejecutada en Core 2026.10.4 y 2026.11.0.

Los avisos de Core 2026.11 sobre las propiedades de temperatura antiguas anuncian su retirada en 2027.11. No explican el error anterior; su adaptación sigue pendiente antes de admitir esa futura versión.

Al vaciar una selección opcional, el formulario de la primera beta podía reinsertar la entidad anterior. Afectaba a fuentes ambientales y asociaciones opcionales de ventana/general. Si esa entidad desaparecía, podía impedir guardar otras opciones. La corrección `c32d7e6` utiliza valores sugeridos, permite eliminar la asociación y dispone de una regresión en ambas versiones de Core.

## Instalación y configuración

### Pide calor justo después de ventilar

Con retardo de cierre cero, el termostato puede reanudar al cerrar si la temperatura ha caído. Para dejar un margen de recuperación del aire, configura **Retardo al cerrar ventana (segundos)** en las opciones de dispositivos de esa zona. La consigna se conserva: si al terminar el margen ya se satisface, no pide aporte; si sigue sin alcanzarse, vuelve a regular. El aprendizaje descarta las muestras durante la pausa y su retardo.

El margen admite 0–600 segundos y requiere ajuste según la estancia. No detecta automáticamente cuánto durará el rebote ni aplica un impulso de recuperación. El motivo «Pausa por ventana» engloba la apertura y ese retardo después de cerrar; consulta el contacto para distinguir ambas etapas. En beta.1 el mismo motivo se mostraba como «Ventana abierta».

### Se abre el asistente justo después de descargar

En HA 2026.11, Marketplace instala una integración nueva y abre directamente su asistente. Es el comportamiento esperado. «Configuración general» configura el sistema compartido; en beta.1 esa pantalla se llamaba «Instalación». La válvula general es opcional: déjala vacía si no existe o vas a asociarla después.

Tras crear esa entrada, añade otra por cada termostato. Todavía no se habilita el control por el mero hecho de instalar o crear una zona. [Procedimiento según versión](installation.md).

### HACS ya no aparece

En HA 2026.11 fue sustituido por **Configuración → Marketplace**. Una página antigua de HACS sin entradas no demuestra que falte configurarlo. No intentes reinstalarlo en esa versión. En 2026.10 y anteriores se mantiene el procedimiento de HACS.

### No encuentro la beta o aparece un código de siete caracteres

Habilita las versiones preliminares del repositorio y selecciona la release. El código corto identifica un commit: `7056482` corresponde al código publicado como `v0.2.0-beta.1`. Instalar una rama y elegir una release no son la misma política de actualización, aunque coincidan en ese momento. Consulta [Releases](https://github.com/Carbanog/radiant-climate/releases) para fijar una versión.

### No se muestra la miniatura de Marketplace

El icono está incluido en `custom_components/radiant_climate/brand/icon.png`. La miniatura del catálogo utiliza un servicio externo de Home Assistant; su índice se obtiene del catálogo oficial. Un repositorio personalizado no indexado puede aparecer sin miniatura aunque publique un PNG válido.

Reinstalar no añade el repositorio a ese índice, y refrescar la caché no garantiza resolver una ausencia de indexación. El icono local y la miniatura previa a instalar se distribuyen por rutas distintas. [Funcionamiento del servicio oficial](https://github.com/home-assistant/brands#marketplace-icons).

### Se rechaza un relé o una fuente

Comprueba que la entidad existe y pertenece al tipo esperado. Las salidas deben ser `switch`; un `input_boolean` no se selecciona directamente como si fuera un relé. Para un banco simulado puede exponerse mediante un switch de plantilla.

Una salida no puede pertenecer a dos zonas ni ser a la vez general y zona. Corrige la asignación; no dupliques entidades para evitar esa validación. No conectes otro controlador sobre la misma salida mientras Radiant Climate la gobierna.

## Regulación y apagados

### Hay demanda, pero una zona no abre

Revisa en este orden:

1. **Climatización** general habilitada y zona en Calor o Frío, no en Apagado.
2. Temporada declarada compatible con el modo de la zona.
3. Temperatura interior válida, en °C y dentro de su caducidad.
4. Ventana habilitada y estado/retardos del contacto.
5. Disponibilidad de salidas, tiempos mínimos y esperas estimadas.

Subir o bajar una décima dentro de la histéresis no obliga a conmutar. Si un actuador ya estaba activo, puede mantenerse dentro de esa banda. La seguridad y el Apagado sí pueden interrumpir el mínimo activo.

| Motivo técnico | Interpretación y comprobación |
|---|---|
| `global_off` / `zone_off` | Existe una parada explícita; el horario no la vence |
| `supply_mode_mismatch` | El modo no coincide con la temporada declarada |
| `temperature_invalid` / `temperature_missing` | Revisa valor, unidad y disponibilidad del sensor interior |
| `temperature_stale` | El informe interior ha caducado o su fecha es incoherente |
| `window_open` / `window_unavailable` | Pausa por contacto habilitado; desconocido también pausa |
| `minimum_cycle` | Espera o conservación del tiempo mínimo de maniobra |
| `general_opening_estimated` / `zone_closing_estimated` | Espera del tiempo configurado, sin confirmación física |
| `actuator_unavailable` / `supply_not_ready` | Salida no utilizable o suministro compartido no preparado |
| `setup_not_ready` | Faltan entradas registradas o no se puede aceptar su estado |
| `season_transition` | Cierre previo a un cambio real de temporada |
| `clock_changed` | Incoherencia de tiempo; revisa reloj y sincronización de HA |
| `satisfied` | La regulación no pide aporte en ese momento |

No reduzcas tiempos de maniobra ni aumentes la caducidad para ocultar un problema de dispositivo. Contrasta esos ajustes con el emisor, la cadencia real y los registros.

### Falla una habitación y se detienen otras

Un fallo interior detiene solo su zona cuando sus actuadores pueden aislarla. Con una entrada de agua común, una salida desconocida o potencialmente abierta impide garantizar ese aislamiento y puede bloquear el suministro compartido. Restablece la comunicación y revisa estados; no ignores la protección para forzar las demás zonas.

### Los relés cambian por su cuenta o quedan inhibidos

Busca automatizaciones anteriores, otra integración, mandos físicos o el comportamiento al volver la alimentación. Las discrepancias repetidas se enclavan para evitar una competencia ilimitada de órdenes. El diagnóstico no atribuye el cambio a una persona sin evidencia.

Desde v0.2.2, apagar **Climatización** conserva los fallos enclavados. Después de corregir la causa y confirmar apagado comunicado, utiliza **Reconocer fallos de relés tras revisión** antes de reactivar. Consulta el procedimiento de [configuración](configuration.md#fiabilidad-y-recuperación-desde-v022). Un corte de red o de alimentación puede impedir cualquier orden software; no se promete cierre físico.

Desde v0.2.5, **Revisión de relés pendiente** permite ver estos estados en el
panel y Reparaciones presenta el procedimiento. La acción de reconocimiento
ofrece un selector; dejar **Relés con fallo** vacío selecciona todos los fallos
revisados. No necesitas escribir sus identificadores. Confirmar una salida
retirada y desconectada físicamente sigue siendo una acción separada. Descartar
el aviso no rearma ni habilita control.

La detección observa discrepancias de estado, no sabe si alguien pulsó un botón.
Dos discrepancias contrarias al plan en cinco minutos pueden enclavar un fallo;
revisa otros controladores o mandos físicos. No uses la pulsación directa de un
relé para cambiar una consigna: utiliza el termostato.

### HA se detiene o pierde conexión

La parada normal solicita cierre, pero un proceso terminado abruptamente,
una pérdida de radio o un corte pueden impedirlo. El estado físico puede
permanecer como estaba. Revisa las protecciones hidráulicas independientes y
el comportamiento de los dispositivos sin HA. Un watchdog o corte independiente
solo aporta protección si está diseñado y probado para el conjunto real.

**No actives un autoapagado corto genérico en los relés**: esta integración no
implementa un latido periódico para renovar ese temporizador. Podría cortar una
demanda legítima y provocar discrepancias. Un watchdog con renovación requiere
diseño y pruebas específicos; no se considera resuelto por estas actualizaciones.

### Solar apagado y aprendizaje

Desactivar Solar detiene su optimización, pero no convierte una exposición solar
ya confirmada en muestras válidas del emisor. Desde v0.2.5 se excluyen esos periodos
en calor y frío. Sin orientación confirmada ni datos solares no se puede reconocer
toda ganancia ajena al suelo: el modelo sigue siendo estadístico, no causal.

## Manual, perfiles y vacaciones

### Manual termina antes de lo esperado

Comprueba `manual_policy` y `manual_until`. Hasta próximo bloque puede terminar en una frontera aunque dos perfiles tengan igual temperatura. Por duración debe atravesar los cambios de horario hasta su vencimiento. Un cambio real de temporada o una orden explícita de volver al programa también puede terminar la retención.

Una ventana o un fallo puede suspender aporte sin cancelar Manual. El reloj de la retención sigue transcurriendo durante una parada. Si el plazo vence, la recuperación utiliza el programa vigente. Repetir una consigna, aunque coincida con un preset, renueva su duración.

Si no coincide con estas reglas, conserva los pasos y atributos y comunica la incidencia; no añadas una automatización que sobrescriba consignas para compensarlo.

### Cambié un perfil y la temperatura del termostato no cambia

Una retención Manual tiene prioridad sobre los perfiles. Editar el valor del perfil no la cancela. En Fijo puede estar activa una consigna directa, en lugar de un perfil. Revisa `control_state`, el preset y las fechas antes de pulsar **Volver al horario**.

### Después de Ausente no vuelve a lo que esperaba

Revisa si la ausencia es indefinida o tiene regreso y si existe una retención posterior. Al vencer Manual, vuelve a Ausente si sigue vigente. Al terminar vacaciones, recupera el programa o ajuste fijo subyacente. Ninguna de esas transiciones enciende una zona individualmente apagada. [Interacciones completas](configuration.md).

## Fuentes y optimizaciones

### La meteo o el exterior están indisponibles

El control interior debe continuar. Comprueba fuente seleccionada, herencia de la fuente común, interruptor del módulo y datos disponibles. El proveedor meteorológico puede no ofrecer previsión horaria. La integración limita peticiones y caduca caché; no fabrica una temperatura para sustituirla.

Los módulos pueden quedar habilitados pero temporalmente sin aportación. Eso es distinto de que la zona esté averiada. Si falla el sensor **interior**, la zona sí se detiene.

### No aprende o no anticipa

Revisa **Aprender respuesta térmica**, `model_ready`, `model_hours`, `model_episodes` y rechazos. El modelo exige al menos doce intervalos, seis horas y tres episodios con filtros de calidad; cumplir solo el tiempo no garantiza que esté listo. Ventanas, fallos, saltos e incidencia solar candidata pueden excluir periodos.

La anticipación necesita además agenda activa y un próximo perfil más exigente. Durante Manual o Ausente no anticipa. Comprueba `advance_minutes` y `control_target`. No importes estadísticas de pruebas para saltarte la fase de observación.

### Solar no reduce demanda

**Observación no actúa**: muestra candidatos. Para Optimizar se requiere confirmar la incidencia/sombras de esa zona, geometría compatible, tendencia interior y proximidad al objetivo. Manual impide la pausa. Sin datos solares utilizables se recupera el control base.

La regla inicial solo pausa calefacción de forma acotada; no es una predicción de ganancias de varias horas ni se invierte para refrigeración. [Algoritmos y límites](intelligence.md).

## Si necesitas comunicar un defecto

Incluye versiones de HA e integración, pasos, resultado esperado, resultado observado y el motivo visible. El [diagnóstico local](tuning.md#plantilla-de-diagnóstico-local) ayuda a obtener una instantánea. Descarga también los diagnósticos desde HA si están disponibles y revisa su contenido antes de compartirlo.

Anonimiza nombres, entidades y preferencias que no quieras publicar. No adjuntes credenciales, exportaciones completas, copias de seguridad ni registros privados sin revisar. Una instantánea no sustituye un histórico cuando se evalúa inercia o confort.
