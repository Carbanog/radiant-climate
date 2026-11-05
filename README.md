<p><img src="https://raw.githubusercontent.com/Carbanog/radiant-climate/main/custom_components/radiant_climate/brand/icon.png" alt="Icono de Radiant Climate: un circuito radiante en colores cálido y frío" width="72" height="72"></p>

# Radiant Climate

**Termostatos de calor y frío. Configuración nativa. Inteligencia opcional por zona.**

Crea termostatos de Home Assistant a partir de tus sensores y relés. Utiliza una consigna fija o añade perfiles, horarios, ventanas y optimización térmica según lo que necesite cada estancia. Diseñado con especial atención al suelo radiante/refrescante y a las válvulas compartidas.

[Última release](https://github.com/Carbanog/radiant-climate/releases/latest) · [Instalación](#instalación) · [Primer arranque](#primer-arranque) · [Resolver problemas](docs/troubleshooting.md) · [Cambios y actualización](docs/release-notes.md) · [Licencia MIT](LICENSE)

[![Pruebas de software](https://github.com/Carbanog/radiant-climate/actions/workflows/ci.yml/badge.svg)](https://github.com/Carbanog/radiant-climate/actions/workflows/ci.yml)
[![Metadatos de integración](https://github.com/Carbanog/radiant-climate/actions/workflows/metadata.yml/badge.svg)](https://github.com/Carbanog/radiant-climate/actions/workflows/metadata.yml)

> **Versión: v0.2.3.** Release normal de un proyecto personal, original y de código abierto. Incluye correcciones para cierres tras fallo y sustitución de actuadores; actualiza antes de cambiar salidas respecto a v0.2.0. El software tiene pruebas automatizadas; su respuesta térmica necesita ajuste en cada instalación. No se presenta como un controlador certificado ni como ahorro demostrado.

¿Ya lo has instalado? Consulta los [cambios y la actualización desde las betas](docs/release-notes.md) y continúa en [Primer arranque](#primer-arranque).

## Qué ofrece

| Necesidad | Función |
|---|---|
| Un termostato normal | Calefacción, refrigeración, consigna fija y Apagado |
| Temperaturas según el uso | Normal, Eco, Noche y Ausente, editables y separados por temporada |
| Programar cada estancia | Agenda semanal por zona; copia de ajustes a otras zonas |
| Cambiar de opinión | Manual por duración, hasta el siguiente bloque o hasta volver al programa |
| Ventilar | Pausa por contacto de ventana, con retardos configurables |
| Aprovechar el entorno | Fuentes de meteo/exterior seleccionables y solar por orientación y elevación |
| Tener en cuenta la inercia | Observación por temporada, adelanto de horario y pausa predictiva acotados |
| Ausentarse | Vacaciones de toda la vivienda con fecha/hora de vuelta y excepciones por zona |
| Compartir una entrada de agua | Válvula general opcional, gestionada por un único módulo de maniobras |
| Entender qué ocurre | Motivo de regulación, estado Manual y disponibilidad de fuentes/modelo |

Los controles y datos pertenecen a la integración. **No exige crear input_number, scripts ni automatizaciones externos**, ni depende de Dual Smart Thermostat o Versatile Thermostat. Añadir una zona reutiliza el mismo motor.

## Compatibilidad y requisitos

La versión está probada automáticamente con **Home Assistant Core 2026.10.4 y 2026.11.0**. No se deduce compatibilidad con cualquier versión posterior: revisa la release y sus comprobaciones antes de actualizar.

| Para empezar | Requisito |
|---|---|
| Temperatura interior | Una entidad `sensor` con valor válido en °C |
| Actuación | Una o varias entidades `switch`, sin otro controlador activo sobre ellas |
| Funcionamiento | Calor, frío o ambos; consigna inicial |
| Opcional | General compartida, contacto `binary_sensor`, exterior, entidad `weather` y posición solar de HA |

Un termostato básico funciona sin meteo, exterior, ventanas ni horario. Las fuentes exteriores opcionales admiten conversión desde °C, °F y K; el sensor interior de esta beta debe exponer °C. Una zona puede agrupar varios circuitos que compartan objetivo de temperatura.

El control básico es local y no solicita cuentas ni credenciales. La integración meteorológica que elijas puede depender de un proveedor externo. No se añade telemetría propia.

## Instalación

### Home Assistant 2026.11 o posterior: Marketplace

1. Abre **Configuración → Marketplace → Añadir desde enlace**.
2. Introduce `https://github.com/Carbanog/radiant-climate`.
3. Selecciona **v0.2.3**. Añadir un repositorio personalizado puede requerir la conexión con GitHub que gestiona Marketplace; esta release no necesita mostrar versiones preliminares.
4. Instala. Marketplace abre directamente el asistente de configuración de una integración nueva, sin reinicio intermedio.

No se instala HACS por separado en 2026.11. Las actualizaciones pueden solicitar un reinicio aunque la primera instalación no lo necesite.

### Home Assistant 2026.10.4: HACS

1. Con HACS ya configurado, abre su menú → **Repositorios personalizados**.
2. Añade `https://github.com/Carbanog/radiant-climate`, categoría **Integración**.
3. Descarga **v0.2.3**; esta release no necesita mostrar versiones preliminares.
4. Reinicia HA y abre **Dispositivos y servicios → Añadir integración → Radiant Climate**.

El repositorio se añade mediante enlace; no se afirma su inclusión en el catálogo oficial. Para instalación mediante ZIP, comprobación de integridad y reversión, consulta la [guía de instalación](docs/installation.md). Utiliza primero un entorno de pruebas y conserva una copia recuperable.

## Primer arranque

### 1. Configura el sistema compartido

La primera pantalla se llama **«Configuración general»**. Configura el sistema compartido antes de añadir las zonas; no es una pantalla de descarga de archivos.

La **válvula general es opcional**: déjala vacía si no existe o si prefieres configurarla después. Esta entrada crea el interruptor **Climatización**, el selector **Temporada de suministro declarada** y el diagnóstico **Oportunidad solar compartida**. El control comienza apagado.

### 2. Añade el primer termostato

Añade otra entrada de Radiant Climate y selecciona:

- Sensor de temperatura interior.
- Relé o relés de la zona.
- Calor, frío o ambos.
- Consigna inicial.

El nombre se propone a partir del sensor y puede renombrarse desde HA. La zona se crea apagada. Repite este paso para añadir más habitaciones, sin duplicar automatizaciones.

### 3. Comprueba la regulación básica

Revisa sensores, asignaciones, temporada y tiempos de maniobra. En un ensayo, utiliza salidas simuladas. Después selecciona un modo en la zona y habilita **Climatización**.

El sensor **Motivo de regulación** explica si demanda, espera un mínimo, encuentra un bloqueo o tiene satisfecha la consigna. Un cambio de temperatura no vence un Apagado general o individual.

### 4. Ajusta perfiles y agenda

Edita las temperaturas Normal/Eco/Noche/Ausente en **Configuración del dispositivo**. Los valores iniciales son orientativos, no una recomendación de confort para todas las viviendas.

En las opciones de la zona, utiliza **Añadir o sustituir bloque horario**: elige días, hora y perfil. Cada bloque continúa hasta el siguiente, también entre días. Activa **Usar horario** cuando quieras seguir la agenda.

### 5. Activa solo los módulos que necesites

Empieza por el funcionamiento básico. Después configura las fuentes y activa módulos por separado. Solar dispone de **Observación**, que muestra oportunidades sin actuar. El aprendizaje comienza recopilando datos; no incluye un modelo precargado de tu vivienda.

Si prefieres un termostato de consigna fija, deja el horario y las optimizaciones desactivados.

## Uso diario y prioridad Manual

| Control | Comportamiento |
|---|---|
| Consigna fija | Mantiene el objetivo elegido, sin vencimiento por horario |
| Usar horario | Sigue el bloque vigente; no enciende una zona apagada |
| Cambiar temperatura con agenda o Ausente activos | Inicia una retención Manual, incluso si coincide con el valor de un perfil |
| Volver al horario | Termina Manual y retoma el programa vigente; durante Ausente, retoma Ausente |
| Apagado individual | Detiene esa zona; horarios y optimizaciones no la reactivan |
| Climatización apagada | Suspende todas las zonas y conserva sus intenciones |
| Reactivar Climatización | Reevalúa condiciones y respeta las zonas individualmente apagadas |

Puedes elegir la política predeterminada de Manual: **duración configurable**, **próximo bloque** o **hasta volver al programa**. Repetir una intervención renueva su duración. Cambiar la preferencia no altera una retención que ya estaba en curso.

Por ejemplo, si eliges cuatro horas y subes a las 21:30, el comienzo de Noche a las 22:00 no cancela esa retención. Los plazos siguen transcurriendo durante una parada; al terminar se consulta el programa vigente.

Manual prevalece sobre las optimizaciones. Un fallo de sensor, Apagado o una ventana habilitada puede suspender el aporte sin borrar la intención. La [guía de configuración](docs/configuration.md) detalla estas interacciones, el cambio de hora y las vacaciones.

## Configurar sin modificar código

| Quiero cambiar… | Dónde |
|---|---|
| Temperaturas de perfiles | Controles `number` propios en Configuración del dispositivo |
| Días, horas y perfiles | Opciones de zona → añadir/sustituir/eliminar bloque |
| Duración y política Manual | Controles propios de la zona |
| Fuentes compartidas | Opciones de la entrada general |
| Fuente particular, orientación y umbrales solares | Opciones de zona → Entorno, sol y anticipación |
| Activación de funciones | Interruptores de módulos y selector solar de cada zona |
| Ventanas, mínimos, histéresis y caducidad | Opciones de zona → Dispositivos y regulación |
| Ausencia con regreso | Opciones de zona → Vacaciones |
| Aplicar ajustes a varias zonas | Acción **Copiar ajustes entre termostatos** |

La copia no traslada sensores, relés, orientación ni modelos aprendidos. Destinos vacíos significa las demás zonas; se validan los requisitos antes de aplicar.

### Qué necesitan las optimizaciones

| Módulo | Condición para actuar | Si faltan datos |
|---|---|---|
| Meteo/exterior | Fuente seleccionada, habilitada y utilizable | Se omite esa aportación; continúa el control interior |
| Solar | Geometría por zona y tendencia interior; Optimizar exige incidencia/sombras confirmadas | Degrada al control base; Observación no cambia relés |
| Anticipación | Agenda, próximo perfil más exigente y modelo válido | Aplica la agenda sin adelanto |
| Pausa por inercia | Modelo válido, tendencia y proximidad al objetivo | Continúa la regulación normal |

Las optimizaciones conservan el objetivo de confort y ajustan el aporte dentro de límites. La regla solar inicial actúa únicamente en calefacción. El modelo separa temporadas y exige calidad mínima; no se promete aprendizaje válido tras un plazo fijo. Consulta [algoritmos y límites](docs/intelligence.md) y [observación y ajuste](docs/tuning.md).

## Si algo no funciona

Empieza por **Motivo de regulación** y por el estado comunicado de sensores y actuadores.

| Síntoma | Primera comprobación |
|---|---|
| No abre una zona | General y zona habilitadas, temporada compatible, sensor válido y mínimos de maniobra |
| Se detienen otras zonas tras un fallo | Una salida no aislable puede bloquear el suministro compartido |
| No anticipa | Horario activo, modelo listo y próximo perfil más exigente |
| No actúa Solar | Distingue Observación de Optimizar; revisa umbrales, incidencia y tendencia |
| Falta meteo o exterior | El control interior debe continuar; revisa fuente y diagnóstico del módulo |
| Manual termina antes de lo esperado | Comprueba política, plazo, cambio real de temporada y acciones explícitas |
| Aparece «7056482» al instalar | Es el commit de la primera beta; selecciona su etiqueta para fijar la versión |
| No hay miniatura en Marketplace | El icono local existe; la miniatura depende del índice externo del catálogo |

La [guía de problemas y soluciones](docs/troubleshooting.md) explica cada caso, las comprobaciones y qué información compartir si persiste. No hace falta editar archivos internos para el diagnóstico habitual.

## Actualizar y volver atrás

Conserva una copia recuperable y la versión anterior. Lee las notas de la nueva release, apaga **Climatización**, actualiza y sigue el aviso de reinicio de HA. Revisa entradas, modos y diagnósticos antes de reactivar.

Para recuperar otro controlador, apaga y deshabilita primero Radiant Climate y después restaura el anterior. Evita dos controladores activos sobre el mismo relé. Una desinstalación no equivale a restaurar la configuración: consulta [reversión](docs/installation.md#reversión). No edites `.storage` con HA activo ni borres los componentes anteriores antes de aceptar la migración.

## Validación y límites

La primera beta superó **90 pruebas del núcleo y 41 pruebas en cada versión de Core: 2026.10.4 y 2026.11.0**, además de HACS y hassfest. Los adaptadores utilizan Core real con sensores, relés, previsiones y modelos de prueba explícitos. Se prueban, entre otros, reinicios completos, Manual coincidente con perfiles, apagados, pérdidas de fuentes y conflictos de salidas. [Alcance de las pruebas](docs/testing.md).

El estado de un relé y el transcurso de un tiempo estimado **no confirman posición de válvula ni caudal**. Las esperas de apertura general/cierre de zona se configuran según los actuadores. No se controla producción ni bombas comunitarias ni se utilizan persianas. Esta beta no implementa protección anticondensación: se mantienen las protecciones físicas de la instalación.

Las pruebas de software no acreditan precisión, ahorro ni respuesta térmica de un edificio. La validación física y la calibración son parte de la puesta en servicio.

## Documentación

| Guía | Contenido |
|---|---|
| [Instalación y reversión](docs/installation.md) | Marketplace, HACS, ZIP, piloto y recuperación |
| [Configuración y uso](docs/configuration.md) | Parámetros, perfiles, horarios, Manual y vacaciones |
| [Problemas y soluciones](docs/troubleshooting.md) | Diagnóstico por síntoma y motivos visibles |
| [Módulos avanzados](docs/intelligence.md) | Fuentes, algoritmos, requisitos y degradación |
| [Observación y ajuste](docs/tuning.md) | Qué medir y plantilla de diagnóstico local |
| [Pruebas](docs/testing.md) | Casos cubiertos y límites de la validación |
| [Desarrollo](docs/development.md) | Entorno, comprobaciones y contribuciones |
| [Arquitectura](docs/architecture.md) · [Alcance](docs/roadmap.md) | Responsabilidades y condiciones de aceptación |

## Proyecto, soporte y licencia

Radiant Climate es un proyecto personal, publicado bajo [licencia MIT](LICENSE). Las referencias a otras soluciones no implican afiliación ni reutilización de sus algoritmos. La compatibilidad se mantiene mediante versiones y pruebas; no se garantiza mantenimiento nulo ante cambios de HA.

Para comunicar un defecto, abre una [incidencia](https://github.com/Carbanog/radiant-climate/issues) indicando versión de HA, versión de la integración, pasos y comportamiento observado. Revisa y anonimiza los diagnósticos: no publiques credenciales, copias de seguridad ni exportaciones domésticas completas.

Si te resulta útil, puedes [apoyar voluntariamente el proyecto](https://buymeacoffee.com/Carbanog). El apoyo no concede funciones ni ventajas.
