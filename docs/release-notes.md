# Cambios y actualización

## v0.2.12 — parada segura ante fallos de almacenamiento

- Si falla una escritura de configuración o de incidencias, Radiant Climate
  apaga **Climatización**, solicita cerrar las salidas y conserva el diagnóstico.
  Un fallo al validar un ajuste restaura los valores previos.
- Un reinicio ordenado conserva la reanudación de Climatización. Tras una
  interrupción con el control activo, se inicia apagado y se explica el motivo
  en **Reparaciones**. Después de revisar almacenamiento y relés se puede
  reactivar desde el interruptor habitual.
- El panel avisa de inmediato si un relé deja de comunicar. Si lleva cinco
  minutos indisponible, aparece también en **Reparaciones**.
- Las acciones quedan registradas al cargar la integración, de modo que Home
  Assistant puede validar las automatizaciones incluso sin entradas activas.

**Validación.** 158 pruebas del núcleo y 247 en cada Core 2026.10.4 y 2026.11.0.
Se provocan errores reales de escritura en un almacenamiento aislado y se usan
relés simulados para comprobar las órdenes y el estado que comunican.

**Actualizar.** Conserva una copia recuperable y la v0.2.11 para revertir. Apaga
Climatización, instala la actualización y reinicia si Home Assistant lo pide.
Comprueba las salidas y reactiva. El archivo de estado conserva el formato y
los ajustes existentes.

## v0.2.11 — compatibilidad con Core y recuperación de incidencias

- El termostato usa la API nativa de temperatura de Core 2026.11 y sigue siendo
  compatible con Core 2026.10.4.
- **Revisión de relés pendiente** identifica una salida cuyo cierre aún sin
  confirmar bloquea el suministro a otra zona. La regulación se reevalúa cuando
  Home Assistant comunica el cierre.
- Una carga parcial que falla puede reintentarse sin reiniciar Home Assistant.
  Si falla el guardado de un cambio, se restauran los ajustes y se desactiva el
  control. Si falla el guardado al descargar una zona, se ordena el cierre y se
  bloquean nuevas aperturas mientras la entrada siga en estado de descarga fallida.
- Cancelar una orden en espera libera su bloqueo temporal. El apagado general
  aceptado se completa aunque se desconecte quien lo solicitó.
- Las guías de instalación y diagnóstico explican la recuperación automática
  y cómo revisar el relé afectado desde el panel.

**Validación.** 158 pruebas del núcleo y 239 en cada Core 2026.10.4 y 2026.11.0.
Las pruebas usan salidas simuladas. La posición física de la válvula y el
caudal se comprueban en la instalación.

**Actualizar.** Conserva una copia recuperable y la v0.2.10 para revertir. Apaga
Climatización, instala la actualización y reinicia si Home Assistant lo solicita.
Comprueba las salidas y reactiva Climatización. Se conservan las zonas, los perfiles
y los horarios existentes.

## v0.2.10 — recuperación sencilla de las válvulas

- Todos los fallos de relés que siguen asignados usan la comprobación automática de
  cierre. Esto incluye los bloqueos antiguos y repetidos. Un informe válido posterior
  a la orden y un cierre estable permiten recuperar el control según la demanda.
- La general espera si no puede confirmarse el aislamiento de una zona. Los intentos
  siguen espaciados y se conserva el apagado de las zonas y de Climatización.
- El aviso identifica la salida afectada, incluso ante una pérdida de comunicación
  que todavía no ha registrado un bloqueo. Muestra si el suministro está en pausa
  y cuándo puede volver a comprobarse, cuando se conoce esa hora.
- El botón **Volver a comprobar** aplica el plan habitual y respeta la espera entre
  intentos. La [tarjeta condicional](https://github.com/Carbanog/radiant-climate/blob/v0.2.10/docs/dashboard.md#aviso-de-recuperación-de-válvulas)
  reúne el aviso y el botón en el panel. La retirada física queda en mantenimiento.

**Validación.** 158 pruebas del núcleo y 232 en cada Core 2026.10.4 y 2026.11.0.
Se usan estados de relé simulados en Core real. La confirmación se refiere al estado
comunicado por Home Assistant. La respuesta física de los relés se comprueba en cada instalación.

**Actualizar.** Conserva una copia recuperable y v0.2.9, apaga Climatización,
actualiza y reinicia si Home Assistant lo solicita. Comprueba las salidas antes de
reactivar. Para mostrar el aviso en tu panel, añade la tarjeta y selecciona las
entidades de Climatización. No hace falta crear ayudantes ni automatizaciones.

## v0.2.9 — recuperación automática de relés y diagnósticos

Los fallos transitorios pueden recuperarse tras una orden de cierre aceptada y un
informe posterior de `off`, con 60 segundos de estabilidad. Radiant Climate vuelve
a evaluar la demanda y los bloqueos antes de abrir. Las recuperaciones repetidas
se espacian 15 minutos. Las tandas de cierre tienen dos intentos separados por
al menos 30 segundos. Si el cierre sigue pendiente, se protege el suministro
compartido. La confirmación corresponde al estado comunicado por Home Assistant.

- Los informes de atributos dejan de multiplicar una discrepancia de relé.
- Climatización muestra las incidencias y las últimas 16 resoluciones. Los conflictos
  repetidos y los fallos anteriores sin causa registrada requieren revisión. La
  confirmación de retirada física admite salidas huérfanas sin asignar.
- El diagnóstico hidráulico muestra la causa de invalidez por sonda, el último
  informe y el umbral configurado. Solar distingue condiciones generales y uso por zona.
- El estado del aprendizaje muestra calor, frío y criterios pendientes incluso con
  la zona apagada. Se conservan horarios, perfiles y estadísticas.

**Validación.** 158 pruebas del núcleo y 228 en cada Core 2026.10.4 y 2026.11.0,
con dispositivos simulados. También pasan los controles de metadatos y privacidad.

**Actualizar desde v0.2.8.** Conserva una copia recuperable, apaga Climatización,
instala v0.2.9 y reinicia si HA lo solicita. Comprueba las salidas y el diagnóstico
antes de reactivar. Conserva v0.2.8 para revertir. Los fallos heredados se conservan
para su revisión. Consulta la guía de problemas y soluciones para identificarlos.

## v0.2.8 — aprendizaje con lecturas irregulares

- Ventanas observadas de 30–90 minutos para aprender respuestas lentas en calor/frío.
  La separación máxima entre informes es el menor de 90 minutos y la caducidad
  interior configurada. No se interpolan temperaturas ni se amplía esa caducidad.
- Las interrupciones de relés de zona/general, ventanas habilitadas y sensores
  inválidos cortan la continuidad aun si llegan antes de reconciliar. Una lectura
  anterior al evento no puede iniciar otro periodo.
- Se excluye el entrenamiento en activación parcial o con una general no utilizable.
  Los cambios de atributos de relé sin cambio de estado no descartan el periodo.
- Diagnóstico con número de intervalos, velocidad observada y máximo hueco admisible.
- Estadísticas existentes conservadas, sin cambios del esquema ni entidades nuevas.
  Un reinicio conserva las estadísticas y no une muestras a través de la parada.

**Límite importante:** aprender con informes cada 45 minutos puede permitir
anticipar horarios, pero las pausas inmediatas por sol/inercia siguen requiriendo
una tendencia reciente suficiente. No se garantiza aprendizaje con cualquier cadencia,
una respuesta física concreta ni ahorro demostrado.

Validación: 158 pruebas del núcleo y 209 pruebas del adaptador por cada Core
2026.10.4 y 2026.11.0, con relojes/dispositivos de ensayo explícitos; también formato,
privacidad, HACS y hassfest. No son pruebas físicas de la instalación.

Actualización desde v0.2.7: conserva copia recuperable y versión anterior, apaga
**Climatización**, actualiza y reinicia si HA lo solicita. Revisa fuentes, temporada
y motivos antes de reactivar. No exige ayudantes ni automatizaciones nuevos,
no activa módulos ni borra modelos existentes. Puedes dejar Aprender activado y
mantener Anticipar horario e Inercia desactivados para observar la calidad real.
No aumentes la caducidad solo para obtener muestras: retrasa la protección por
pérdida de datos. Consulta la guía de reversión; no restaures `.storage` en caliente.

## v0.2.7

Correcciones de fiabilidad, sin cambiar la regulación térmica básica, los perfiles,
los identificadores de entidades ni el esquema de almacenamiento.

- La confirmación solar solo certifica la fuente mostrada al revisar la zona.
  Guardar una confirmación obsoleta no la renueva; cambiar la fuente con el formulario
  abierto obliga a revisarla. El motor aplica el mismo criterio incluso al arrancar
  con las zonas cargadas antes de la configuración general.
- Los bloques horarios de un solo día también detectan cambios concurrentes de perfil.
  El borrado distingue un bloque obsoleto del último bloque de una agenda habilitada.
- Las fuentes solares caducan a los quince minutos. Perderlas omite su optimización,
  sin bloquear la regulación interior ni cambiar la caducidad de los sensores interiores.
- Errores de validación de entidades presentados mediante ServiceValidationError;
  diagnósticos y mandos utilizan propiedades públicas del gestor.

Validación: 139 pruebas del núcleo y 199 pruebas del adaptador por cada Core
2026.10.4 y 2026.11.0, con dispositivos simulados, además de formato, metadatos y
privacidad. No equivalen a pruebas físicas de válvulas ni a certificación de la instalación.

Actualización desde v0.2.6: realiza una copia recuperable, apaga **Climatización**,
actualiza y reinicia cuando lo solicite HA. Revisa fuentes y motivos antes de reactivar.
No requiere ayudantes ni automatizaciones nuevos. Si habías cambiado la fuente solar,
revisa la exposición antes de confirmar y activar Optimizar. Conserva la versión anterior
para reversión; no restaures almacenamiento en caliente.

## v0.2.6 — edición de horarios y anticipación solar opcional

- Bloques agrupados y localizados, atajos Semana completa/Entre semana/Fin de semana,
  edición explícita precargada y eliminación parcial. Los cambios preservan excepciones
  y rechazan colisiones de edición; la agenda almacenada no cambia de formato.
- Corregido un fallo reproducido: las pausas opcionales respetan el mínimo de
  encendido incluso si el regulador básico todavía pide calor/frío. Las protecciones
  y los apagados siguen pudiendo cerrar inmediatamente.
- Manual indefinido se identifica como tal. Apagado individual sigue siendo persistente.
- Fuente de posición solar compartida configurable: Sol de HA, entidad con atributos
  o sensores separados en grados. Fuente ausente/inválida degrada solo la optimización.
- Adelanto solar por zona, desactivado por defecto: hasta 180 minutos antes de una
  incidencia estimada, solo en calor, con previsión explícitamente favorable, tendencia
  interior y temperatura próxima a consigna. Observación no cambia salidas; Manual,
  Apagado, ventanas, averías y mínimos de maniobra conservan prioridad.
- Cambiar la fuente solar requiere confirmar de nuevo la exposición antes de optimizar.
  Se utiliza la ubicación de HA para proyectar y se rechazan fuentes inconsistentes.
- Textos de configuración y explicación de elevación, orientación y ángulo revisados.
  La lista genérica del dispositivo la ordena HA; hay una guía de panel por secciones.

Actualización: conserva perfiles, horarios, aprendizaje, IDs y caducidades existentes.
No activa módulos ni instala ayudantes. El nuevo adelanto solar empieza a 0: revisa
sombras y previsión en Observación antes de Optimizar. Copia de seguridad y versión
anterior conservadas; no restaures almacenamiento en caliente ni reviertas con
averías/salidas retiradas pendientes.

## v0.2.5

Diagnóstico hidráulico **opcional y de solo lectura**. No cambia regulación,
perfiles, Manual, horarios, aprendizaje ni optimizaciones. No necesita ayudantes,
automatizaciones externas ni nuevas dependencias. Las instalaciones sin sondas
siguen funcionando y no reciben entidades hidráulicas hasta configurarlas.

- Selección de impulsión y retorno generales desde Opciones de la instalación.
  Un sensor enum de diagnóstico y un interruptor nativo para el panel.
- Temperaturas convertidas a °C, ΔT firmado y número de zonas demandantes.
  Valida unidades, valores finitos, rango, caducidad y ausencia de fuentes.
- Calor y frío tienen referencias opcionales independientes. No se inventa una
  curva climática ni se deduce energía sin caudal. Una diferencia de signo
  inesperado se comunica como observación que requiere revisión.
- Espera estabilización y desviación continua. Pierde la evidencia acumulada
  ante reinicio, desconexión, cambio de contexto o pausa larga de ejecución.
  Conserva eventos intermedios de pérdida/recuperación aunque lleguen en ráfaga.
- Editar solo estas opciones no ejecuta regulación, cancela confirmaciones,
  recarga termostatos ni retira salidas. Tampoco reconoce fallos de actuadores.

La revisión adicional de v0.2.4 reproduce y corrige dos casos en ambos Core:

- Una petición de apagado global aceptada termina y persiste aunque quien llamó
  al servicio cancele mientras espera el bloqueo. No queda una parada transitoria
  indefinida. Un encendido explícito posterior conserva su orden y prioridad.
- El aprendizaje excluye exposición solar ya confirmada aunque la optimización
  Solar esté apagada. Una geometría predeterminada sin confirmar no se considera
  evidencia de exposición. Se mantiene la limitación de modelo descriptivo: no
  se separan causalmente todas las cargas internas o ganancias desconocidas.

Se añade un sensor binario nativo **Revisión de relés pendiente** y un aviso en
Reparaciones, con las acciones existentes para revisión y recuperación. Descartar
el aviso o apagar no reconoce averías. La selección de relés es opcional: vacía
reconoce todos los fallos revisados, manteniendo las comprobaciones y permisos.
Servicios y selectores traducidos al inglés/español; textos históricos del README
corregidos. La configuración avisa de la protección anticondensación externa,
sin bloquear frío ni convertir sondas de diagnóstico en protecciones.

El filtro de aprendizaje también descarta el anclaje anterior si cambia la
elegibilidad sin que llegue una nueva medición interior; conserva la tendencia
observada. Se amplían las reglas de análisis estático, se fijan las Actions por
commit y se incorporan política de seguridad y plantilla de incidencias.

Consulta la [guía de diagnóstico](hydraulic-diagnostics.md) para configuración,
estados y límites. No envía notificaciones automáticas. Los estados On de relés
no confirman apertura o caudal; el retorno mezclado no permite repartir energía
por habitación ni identificar por sí solo un fallo comunitario.

### Actualización y recuperación

Con respaldo y Climatización apagada, actualiza a v0.2.5 y reinicia. El módulo
empieza desactivado. Se conservan entidades, perfiles, programas, modelos y
almacenamiento versión 1. No se requieren sondas para continuar usando los
termostatos. Para retirar únicamente esta función, usa su interruptor; no es
necesario desactivar la calefacción. Para revertir código, conserva v0.2.4 y el
respaldo; mantén Climatización apagada y no restaures almacenamiento en caliente
ni ignores retiradas o fallos pendientes.

No se borran estadísticas aprendidas. Si el modelo anterior se entrenó durante
ganancias solares conocidas sin filtrarlas, revisa sus datos y utiliza
**Restablecer aprendizaje térmico** en esa zona si procede. No se restablece
automáticamente el modelo de otras estancias.

## v0.2.4

Corrección del manejo de eventos y revisión propia de concurrencia, sin nuevos ayudantes, automatizaciones ni dependencias.

- Las mediciones interiores válidas, cambios de atributos y contactos deshabilitados no cancelan una confirmación en curso. Invalidan el plan y provocan su reevaluación antes de nuevas aperturas. Si la temperatura alcanza la consigna durante la espera, se confirma o vence la orden ya enviada y después se aplica el estado vigente.
- La interrupción inmediata se reserva para lecturas interiores inválidas o una pausa efectiva de ventana de una zona demandada, respetando habilitación y retardos. Una zona ya parada no cancela la apertura de otra por perder su termómetro. Off, configuración y parada de HA conservan prioridad; los informes no amplían el plazo de cinco segundos.
- Probadas las secuencias off → unknown/unavailable/ausente → on. Se conserva el aborto conservador sin convertir automáticamente cada pérdida transitoria en avería enclavada. La recuperación solo continúa si sigue autorizada la demanda; un On tardío no vence Off.
- Los cambios de módulos se componen y validan bajo el mismo bloqueo que los aplica: dos órdenes en cola ya no sobrescriben funciones independientes ni reutilizan una confirmación solar invalidada mientras esperaban.
- Programación y reanudación actúan sobre la instancia y estado actuales de la zona. La última selección manual de temporada en cola se respeta, y encender una zona utiliza la temporada vigente al aplicar la orden. Repetir una temporada sin cambios pendientes continúa siendo una operación sin efecto.

### Validación y actualización

Se han añadido reproducciones antes de corregir: siete fallos por eventos inocuos y cuatro carreras de estado en ambos Core. La batería final incluye secuencias mixtas reproducibles que comprueban apagado, temporada, sensores, ventanas, vacaciones y perfiles después de cada acción. Consulta los resultados del commit de entrega.

Copia de seguridad, Climatización apagada, actualizar a **v0.2.4** y reiniciar. Se mantienen entidades, perfiles, horarios, modelos y almacenamiento versión 1. No se automatiza el rearme de averías. Se conserva la release anterior para recuperación; no restaures estado en caliente ni reviertas con retiradas o averías pendientes sin resolver.

La temporada sigue siendo declarada manualmente. Los estados de relé no certifican válvulas, caudal ni seguridad eléctrica. Esta revisión no sustituye pruebas físicas ni declara compatibilidad con HA 2027.11.

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

El reconocimiento de fallos queda separado del apagado habitual: no lo automatices ni utilices Off/On para intentar borrar una avería. Consulta [el procedimiento](configuration.md#fiabilidad-y-recuperación). Conservamos v0.2.1 para recuperación, pero no reviertas con retiradas o fallos pendientes sin resolver; mantén Off y conserva código y configuración de respaldo juntos. Una restauración de estado debe hacerse con HA detenido.

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
