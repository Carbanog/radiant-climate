# Validación

Las pruebas separan cálculo, adaptación a Home Assistant y comportamiento físico. Una beta instalable no acredita calibración, apertura de válvulas ni ahorro.

## Comprobaciones automáticas

- Núcleo: regulación de calor/frío, histéresis, mínimos, prioridades, caducidad, almacenamiento, tres políticas Manual, agenda semanal, medianoche/cambios de hora y vacaciones.
- Inteligencia: temperaturas no inventadas, geometría con elevación y azimut, pérdida meteorológica, calidad de aprendizaje por temporada, rechazo de saltos, conservación de consigna y límites de pausa/adelanto.
- Core real 2026.10.4 y 2026.11.0: altas y opciones nativas, servicios climate, perfiles editables, Manual igual a preset, edición durante retención, copia de ajustes y apagados.
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
