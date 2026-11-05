# Validación

Las pruebas separan cálculo, adaptación a Home Assistant y comportamiento físico. Una beta instalable no acredita calibración, apertura de válvulas ni ahorro.

## Comprobaciones automáticas

- Núcleo: regulación de calor/frío, histéresis, mínimos, prioridades, caducidad, almacenamiento, tres políticas Manual, agenda semanal, medianoche/cambios de hora y vacaciones.
- Inteligencia: temperaturas no inventadas, geometría con elevación y azimut, pérdida meteorológica, calidad de aprendizaje por temporada, rechazo de saltos, conservación de consigna y límites de pausa/adelanto.
- Core real 2026.10.4 y 2026.11.0: altas y opciones nativas, servicios climate, perfiles editables, Manual igual a preset, edición durante retención, copia de ajustes y apagados.
- Regresión de Ausente indefinido con agenda: publica una próxima transición nula, admite una intervención Manual y recupera el programa al terminar Ausente, sin errores de actualización de entidades.
- Regresión de campos opcionales: eliminar fuentes meteorológicas/exteriores, contacto de ventana y general, sin reinsertar selecciones antiguas ni bloquear otras opciones cuando desaparezca el proveedor anterior.
- Vacaciones de la vivienda: aplicación global atómica sin encender zonas apagadas, perfiles propios, prioridad Manual posterior, regreso común con fecha/hora, ausencias parciales y persistencia durante reinicio completo. Utiliza los estados de ausencia existentes por zona.
- Reasignación/retirada: relés de zona o general incomunicados siguen bloqueando suministro, recuperación posterior y estado pendiente persistido al reiniciar; confirmación física exige apagado y salida no asignada.
- Fallos enclavados: cierres limitados, aperturas prohibidas y presupuesto persistente. Servicios lentos: apagado global, individual y cambio de temporada durante una apertura no permiten activar el siguiente relé del plan antiguo.
- Configuración atómica: copia de horario más anticipación hacia una zona sin agenda, fallo en otro destino sin cambios parciales y rechazo explicado del último bloque mientras Usar horario permanece activo.
- Fallos: pérdida interior aislable, unidad incompatible, exterior y meteorología indisponibles, proveedor sin previsión, error meteorológico con reintento acotado, salida desconocida persistente y discrepancias repetidas con enclavamiento compartido.
- Optimización: solar Observación/Activo y prioridad Manual; anticipación y desactivación en calor/frío; pausa predictiva en refrigeración; espera estimada general.
- Reinicio completo de instancias Core: retención temporal, retención sin vencimiento, plazo vencido y apagado individual/general. No se presenta una recarga de entrada como si fuera un reinicio.
- Calidad: ruff, formato, revisión de privacidad, HACS y hassfest. Se consideran fallos los registros ERROR inesperados de arranque, uso o parada.

Los sensores, actuadores, previsiones y modelos preparados son fixtures explícitas de tests. Los modelos sintéticos nunca se empaquetan para entrenar una instalación. Los mínimos se aceleran a cero solo en el banco de integración de tests.

## Reproducción

Consulta los comandos de la [guía de desarrollo](development.md) y `.github/workflows/ci.yml`. El núcleo funciona con Python 3.12; las dos versiones de Core se prueban en Linux/Python 3.14. Una suite omitida por falta de HA no cuenta como compatibilidad. El estado exacto y los registros corresponden al commit de Actions, no al futuro contenido de main.

## Alcance físico pendiente

CI no reproduce cortes eléctricos, fallos mecánicos, comunicaciones reales, caudal, condensación, impulsión ni respuesta térmica de la vivienda. Reconciliaciones repetidas con un estado unavailable acreditan software, no una desconexión de radio durante horas. La geometría solar no mide sombras ni demuestra ganancia térmica.

El piloto doméstico y la calibración necesitan copia recuperable, circuitos comprobados, actores anteriores detenidos y aceptación del propietario. Las pruebas visuales y de instalación en su servidor deben documentarse separadamente. No se publican releases solo para ensayar: una beta entregada es una versión identificable para instalación voluntaria, sin aprobación de producción.

## Artefactos

Los ZIP de CI incluyen commit, BUILD.json y SHA-256, sin fixtures ni datos domésticos. Los artefactos temporales no son por sí mismos una publicación. Las releases adjuntan una candidata ya validada y mantienen identificador para recuperación. HACS obtiene el código de la etiqueta correspondiente; las betas deben elegirse expresamente.


## Regresiones de v0.2.2

- Zona de dos canales: primer canal abierto y fallo del segundo por excepción, timeout o confirmación vencida. Se comprueban las órdenes compensatorias de cierre sin permitir eventos ni ticks posteriores.
- Retirada de zona, general y sustitución mediante opciones: interrupción simulada en la primera orden de cierre; el registro ya debe existir en almacenamiento y recuperarse en un gestor nuevo.
- Opciones lógicas de zona e instalación: no descargan la entrada, no ordenan cierres artificiales y conservan la identidad del modelo aprendido.
- Off/On conserva la avería y su persistencia. El reconocimiento exige Off y estado comunicado apagado; estados on, unknown y unavailable se rechazan. El reconocimiento no habilita el control.


## Regresiones de v0.2.3

Confirmación inicial diferida, ausente e interrumpida por Off, fallo interior o ventana; cierre compensatorio sin depender de un tick posterior; informe tardío después de Off. Geometría modificada invalida autorización incluso si el formulario heredaba Confirmado. Presets home/eco/sleep en calor y frío conservan nombre y prioridad Manual, intervención numérica posterior no hereda perfil. Reinicio completo con preset retenido. Procedencia del modelo y cambio de sensor en almacenamiento actual/antiguo, conservación al sustituir relé y ante ajustes lógicos. Comprobación automática de versiones del README/manifiesto/constantes/paquete.
