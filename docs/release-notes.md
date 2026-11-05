# Cambios y actualización

## v0.2.3

Correcciones tras contrastar la auditoría de v0.2.2 con el comportamiento previsto. No añade ayudantes ni automatizaciones externas.

- La apertura espera el estado comunicado dentro del límite total de cinco segundos de la maniobra. Un retraso breve se admite sin declarar avería; si no llega la confirmación, se enclava el fallo y se solicita cerrar el grupo y la general en esa revisión. Un apagado, cambio de configuración, fallo interior o apertura de ventana interrumpe la espera. Las órdenes tardías posteriores siguen supervisadas.
- Modificar orientación, elevación mínima o amplitud invalida la confirmación solar previa y devuelve Solar Activo a Observación. Desmarcar la confirmación también suspende la optimización. Para reactivarla hay que revisar los nuevos valores, guardarlos confirmados sin volver a cambiar geometría y seleccionar Activo expresamente.
- Elegir Normal, Eco o Noche con programación conserva su nombre en el selector nativo mientras el estado sigue siendo Manual. Una intervención numérica posterior se muestra sin preset, aunque coincida con su temperatura. El perfil retenido se conserva al reiniciar.
- El modelo aprendido guarda la identidad del sensor interior. Cambiarlo reinicia solo el modelo y conserva perfiles, agenda y controles; sustituir únicamente el relé conserva aprendizaje. Los cambios físicos de circuitos que no se puedan deducir de las entidades requieren el botón existente Restablecer aprendizaje térmico.
- README corregido y validación automática de coherencia entre su versión, manifiesto, constantes y proyecto. Ejemplos de orientación con datos ficticios independientes de instalaciones reales.

### Actualización y límites

Haz copia, apaga Climatización, instala **v0.2.3** y reinicia Home Assistant. Se conserva almacenamiento versión 1 con campos opcionales nuevos; no hay que recrear entidades. Al primer cambio de sensor se registra la procedencia del modelo antes de guardar la nueva selección, también al actualizar desde estados antiguos.

No reviertas con fallos o retiradas pendientes. Conserva código y configuración juntos y no restaures almacenamiento en caliente. La versión anterior permanece disponible para recuperación.

La confirmación es del estado del relé, no de posición de válvula ni caudal. Durante el plazo de comunicación puede existir un desfase entre canales; no se promete simultaneidad física. El suministro sigue declarado: sin una señal verificada no se inventa el estado del agua comunitaria. Protecciones eléctricas, recuperación de alimentación y anticondensación deben verificarse en cada instalación.

## v0.2.2

Mejora de fiabilidad sin cambiar regulación térmica, perfiles ni optimizaciones, y sin añadir ayudantes o automatizaciones externas.

- Apertura parcial: si falla un canal, se invalidan nuevas aperturas y se solicita cerrar los canales de esa zona y la general en la misma revisión, sin esperar al siguiente tick.
- Sustitución y retirada: el registro de salidas antiguas se persiste antes de maniobrar y antes de confirmar asignaciones nuevas. Una interrupción conserva la información para recuperar el bloqueo. Si falla el guardado, no se confirma la nueva asignación.
- Los ajustes lógicos de fuentes, orientación y regulación se aplican sin descargar entidades, retirar salidas ni sustituir el aprendizaje. Los cambios reales de dispositivos conservan la recarga segura.
- Apagar Climatización ya no borra averías. La acción administrativa **Reconocer fallos de relés tras revisión** (`radiant_climate.reset_actuator_faults`) exige instalación apagada, revisión confirmada y salidas comunicando Off, sin retiradas pendientes. No enciende la instalación. Confirmar retirada física también requiere administrador.

### Actualización y reversión

Conserva copia, apaga Climatización, instala **v0.2.2** y reinicia Home Assistant. No requiere recrear termostatos, perfiles, horarios ni ayudantes: se conserva el almacenamiento versión 1. Cambiar solo el relé sobre el mismo circuito y sensor conserva el aprendizaje; al dividir circuitos o cambiar sensor conviene restablecerlo.

El reconocimiento de fallos queda separado del apagado habitual: no lo automatices ni utilices Off/On para intentar borrar una avería. Consulta [el procedimiento](configuration.md#fiabilidad-y-recuperación-desde-v022). Conservamos v0.2.1 para recuperación, pero no reviertas con retiradas o fallos pendientes sin resolver; mantén Off y conserva código y configuración de respaldo juntos. Una restauración de estado debe hacerse con HA detenido.

### Validación

90 pruebas del motor y 77 del adaptador en cada Core 2026.10.4/2026.11.0, ruff, formato, privacidad y HACS/hassfest. La candidata funcional 32a86cc completó además 41 casos en Core 2026.11.0 con sensores y salidas ficticios, incluidos dos reinicios completos, Manual con reloj real, vacaciones, opciones sin cierres, fallos y ventilación. Las maniobras aceleradas del banco no son parámetros domésticos.

Los cierres son órdenes y estados comunicados, no una medición de posición ni caudal. Las comprobaciones eléctricas, tiempos físicos y protección anticondensación corresponden a cada instalación. Permanecen los avisos de API de temperatura cuya retirada anuncia HA 2027.11; esta entrega no declara compatibilidad con esa versión futura.

## v0.2.1

Correcciones de seguridad de salidas y configuración encontradas en la revisión de v0.2.0. Conserva la versión 1 del almacenamiento con campos aditivos para salidas retiradas y recuperación de cierre. No añade ayudantes externos.

- Un relé con fallo continúa bloqueando aperturas, pero admite hasta dos intentos de cierre de recuperación, espaciados 30 segundos y persistentes al reiniciar. El apagado explícito permite un nuevo intento acotado.
- Al retirar o reasignar relés de zona o de general, las salidas anteriores permanecen bajo supervisión hasta comunicar apagado y agotar la espera estimada. Las pendientes bloquean la instalación y sobreviven al reinicio. Se incorpora una acción de confirmación física de retirada, solo con Climatización apagada y para salidas no asignadas.
- Las órdenes pendientes de apagado o cambio invalidan nuevas aperturas de un plan anterior, incluidos varios relés de la misma zona. Una orden ya en curso no se puede deshacer; las llamadas están acotadas.
- Copiar Programación y Módulos valida los candidatos finales, después de componer ambas partes, y aplica todos los destinos solo si todos son válidos.
- El último bloque de una agenda activa no se elimina silenciosamente: primero hay que apagar Usar horario, conservando la consigna fija. Se muestra una explicación en el formulario.
- El tiempo de cierre de la general se configura separadamente de su apertura y se utiliza al retirar esa salida y en cambios de temporada; no se presume que ambos tiempos coincidan.

[Procedimiento de sustitución de relés](configuration.md#sustituir-un-relé-o-dividir-una-zona). Mantén respaldo, apaga Climatización antes de actualizar y reinicia según el aviso de HA. Los modelos y las consignas no se borran al cambiar un relé; restablece el aprendizaje cuando cambie el circuito o sensor. No reviertas a v0.2.0 con retiradas pendientes sin resolver.

El suministro sigue siendo declarado, no medido. Una señal externa de temporada solo debe utilizarse tras verificar su significado; esta entrega no inventa disponibilidad ni temperatura del agua comunitaria. La política de arranque conserva intenciones, pero exige estados utilizables y bloquea con retiradas pendientes. Los tiempos reales, comportamiento al recuperar alimentación y protecciones físicas siguen requiriendo comprobación en cada instalación.

## v0.2.0

Primera release normal, publicada fuera del canal de versiones preliminares. Incluye las correcciones de beta.2 y añade **Vacaciones de la vivienda**: un único control para aplicar Ausente a todas las zonas cargadas, con fecha/hora de regreso comunes desde Configuración general → Vacaciones y regreso.

Cada zona conserva su perfil Ausente, consigna fija/agenda y estado Apagado. Las intervenciones manuales posteriores tienen prioridad. Puedes finalizar una ausencia por zona; el control de vivienda indica ausencias parciales y permite terminarlas todas. La ausencia se conserva en los estados existentes de cada zona, sin crear ayudantes externos ni duplicar persistencia. Hay pruebas específicas de aplicación global, regreso programado, prioridad Manual, apagados y reinicio completo.

La [guía de programación y vacaciones](configuration.md#agenda-semanal) incorpora un ejemplo de bloques Normal/Noche y explica cómo compartir horarios y cómo actúa Manual al cruzar un cambio de perfil.

### Actualizar desde una beta

Conserva una copia, apaga Climatización, selecciona **v0.2.0** y reinicia según el aviso de HA. No necesitas activar versiones preliminares. Conserva las entradas, perfiles y agendas: el almacenamiento continúa en versión 1 y no requiere conversión. Configurar la instalación abre ahora un menú con Dispositivos y regulación y Vacaciones y regreso.

Revisa las asignaciones y motivos antes de habilitar. La nueva entidad Vacaciones de la vivienda puede añadirse al panel directamente. Si anteriormente intentaste quitar una fuente opcional en beta.1, vuelve a vaciar ese campo y guarda; se mantiene su corrección. Para revertir conserva código y configuración juntos según la [guía de reversión](installation.md#reversión).

### Validación y alcance

90 pruebas del motor, 46 del adaptador en cada Core 2026.10.4/2026.11.0, ruff, privacidad, HACS y hassfest. Las 37 comprobaciones incrementales del laboratorio de las candidatas anteriores siguen documentadas por separado; el control global nuevo se verifica en las pruebas Core, incluidas persistencia y prioridad.

El canal normal identifica la entrega mantenida de software. La incidencia solar, el aprendizaje y los tiempos físicos requieren ajuste en cada instalación; no certifica válvulas, caudal, anticondensación ni ahorro. La vuelta de Vacaciones reanuda el programa a la hora elegida, sin garantizar anticipación del confort para esa llegada. La espera después de ventilar continúa siendo configurable, no adaptativa. Permanecen los límites de miniatura de Marketplace y compatibilidad futura descritos a continuación.

## v0.2.0-beta.2

Entrega corregida de la beta, sin cambiar el formato de almacenamiento ni añadir dependencias. Mantiene termostatos propios calor/frío, perfiles, agendas, prioridades Manual, ventanas, módulos opcionales y coordinación de suministro compartido.

### Correcciones

- Ausente indefinido con agenda ya no intenta convertir una próxima transición inexistente: se publican correctamente los atributos, la prioridad Manual y el retorno al programa.
- Los selectores opcionales permiten quitar la fuente meteorológica, sensor exterior, contacto de ventana o válvula general. No reinsertan una selección vaciada ni bloquean otras opciones cuando desaparece la entidad anterior.
- El primer asistente se llama **Configuración general**. El alta de zona explica dónde configurar perfiles, horarios y funciones opcionales; se retira el mensaje obsoleto que decía que solo existía regulación básica.
- **Pausa por ventana** describe tanto la apertura como la espera configurada después de cerrar, sin presentar esa espera como un contacto físicamente abierto.

### Actualizar desde beta.1

1. Conserva una copia recuperable de Home Assistant y sus datos antes de actualizar.
2. Apaga **Climatización** y comprueba que las salidas comunican apagado. Un estado de relé no confirma el cierre físico.
3. Selecciona **v0.2.0-beta.2** en Marketplace/HACS, mostrando versiones preliminares si es necesario. Reinicia Home Assistant según su aviso para cargar el código actualizado.
4. Conserva las entradas existentes: no hace falta eliminar termostatos, perfiles ni agendas. El formato de almacenamiento permanece en versión 1.
5. Si beta.1 conservó una entidad que habías intentado quitar, vacía de nuevo ese campo y guarda. La actualización no puede deducir si la selección anterior era intencional.
6. Comprueba los motivos, los apagados y la política Manual antes de volver a habilitar **Climatización**. Prueba los módulos uno a uno.

Las actualizaciones pueden recuperar intenciones persistidas: apagar antes de actualizar evita que un reinicio reanude el control sin esa revisión. Para revertir, restaura juntos el código y la configuración de la copia previa, con Core detenido o mediante restauración de backup. No sobrescribas .storage con HA activo. Beta.1 conserva los defectos anteriores; [reversión al controlador previo](installation.md#reversión) es una alternativa cuando proceda.

### Validación y límites

El motor cuenta con 90 pruebas y el adaptador con 43 en cada Core 2026.10.4/2026.11.0, además de formato, privacidad, HACS y hassfest. La aceptación incremental de laboratorio completó 37 casos con salidas ficticias: calor/frío, apagados, Manual, ventanas y estabilización posterior, fallos, fuentes opcionales, rearme y reinicios completos. El resultado de CI de la entrega corresponde al commit de la etiqueta y es consultable en Actions.

Los tiempos de maniobra y el retardo tras ventilar necesitan ajuste por instalación. No hay reconocimiento adaptativo del rebote tras ventilar. Solar, aprendizaje y anticipación requieren observación real; las pruebas con modelos sintéticos no acreditan ahorro ni confort doméstico. La posición de válvulas, caudal y protección física anticondensación no se miden ni certifican mediante esta integración.

Los avisos de propiedades de temperatura retiradas en HA 2027.11 requieren adaptación antes de admitir esa versión futura. La miniatura de Marketplace depende de su catálogo aunque el icono esté incluido. Esta entrega sigue siendo preliminar; no supone aprobación de una migración doméstica.

## v0.2.0-beta.1

Primera entrega instalable. Su etiqueta y artefactos se mantienen como referencia histórica. Consulta los [defectos corregidos](troubleshooting.md#problemas-conocidos-de-v020-beta1) antes de reutilizarla.
