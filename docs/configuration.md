# Configuración y uso

Candidata de desarrollo: consulta CI y el commit instalado. Instalar en laboratorio no aprueba una migración doméstica. Todas las operaciones habituales se realizan desde Home Assistant, sin editar configuration.yaml ni crear ayudantes externos.

## Alta mínima

Crea primero la instalación; selecciona la válvula de entrada solo si existe. No selecciones producción o bomba como si fueran una válvula. Aparecen Climatización, Vacaciones de la vivienda, Temporada de suministro declarada y Oportunidad solar compartida. La temporada se declara; no se mide disponibilidad de agua.

Añade una entrada por zona con cuatro campos: sensor interior, uno o varios relés, calor/frío/ambos y consigna inicial. Empieza apagada. El nombre se propone a partir del sensor y puede renombrarse desde HA. Varios circuitos pueden compartir una zona y consigna; una futura zona independiente se añade con el mismo asistente.

El sensor interior debe informar grados Celsius. Una unidad ausente o incompatible bloquea esa zona. Las fuentes exteriores opcionales admiten Celsius, Fahrenheit o Kelvin convertidos. Revisa la cadencia de cada dispositivo antes de fijar su caducidad; last_reported no demuestra por sí solo comunicación física.

## Mandos cotidianos

- Tarjeta termostato: modo y temperatura. Cambiar temperatura estando apagado no lo enciende; una llamada que solicita expresamente modo y temperatura respeta ambos.
- Climatización: parada general persistente, sin perder intenciones. Al reactivar no enciende zonas individualmente apagadas.
- Temporada: solo cuando cambie el suministro declarado. Un cambio real cierra antes de permitir el otro modo y termina la retención anterior. Repetir la misma temporada no cancela Manual.
- Usar horario por zona: activarlo aplica el programa sin vencer Apagado. Desactivarlo conserva la consigna efectiva como fija. Si hay vacaciones activas, ese control modifica el programa subyacente, sin cancelar la ausencia ni una retención posterior.
- Volver al horario: termina Manual y recupera el programa vigente. Durante Ausente recupera Ausente; no enciende una zona apagada. Sin agenda configurada no inventa horarios.
- Ausente: activa el perfil prolongado. Elegir away en los presets también activa ausencia indefinida. Terminar Ausente no anula una retención manual posterior.
- Vacaciones de la vivienda: encender aplica Ausente a todas las zonas cargadas; apagar termina esas ausencias. No enciende zonas apagadas ni activa Climatización. Cada zona utiliza su propia temperatura Ausente para la temporada.

Los ajustes avanzados y temperaturas aparecen agrupados en Configuración del dispositivo; no es necesario mostrarlos todos en el panel principal. Se pueden añadir individualmente a un panel nativo.

## Perfiles y Manual

Normal, Eco, Noche y Ausente tienen temperaturas independientes para calor y frío, almacenadas una sola vez. Sus controles number los crea la integración; no son input_number externos. Los valores iniciales son orientativos. Ajusta Noche por estancia e inercia; no se obliga a aplicar la misma reducción a todas.

En Comportamiento de Manual elige duración, próximo bloque o hasta volver expresamente al programa. La duración inicial es 240 minutos, editable entre 1 y 1440; no representa un tiempo térmico aprendido. Cambiar la preferencia no modifica una retención ya iniciada.

Con programación o vacaciones activas, cualquier orden climate de temperatura inicia Manual, incluida una consigna igual al perfil. Repetirla renueva la duración. La integración no utiliza context.user_id ni deducciones por preset_mode: la entidad propia recibe la orden y la lógica interna no se llama a sí misma a través de servicios climate.

Durante Manual no actúan anticipación, solar ni pausa predictiva. Editar un perfil no cancela la retención. Al terminar, se consulta el programa vigente, sin recuperar un perfil antiguo. En Fijo la consigna no caduca; los módulos que se activen pueden regular aporte dentro de sus límites sin cambiar ese objetivo.

## Agenda semanal

Configurar → Añadir o sustituir bloque horario permite seleccionar días, hora y perfil. Cada bloque continúa hasta el siguiente, también entre días. Repetir día/hora sustituye el bloque. Eliminar bloque muestra los existentes. Utiliza la zona horaria de HA.

Para eliminar el último bloque debes desactivar antes **Usar horario**. Esto conserva la consigna vigente como fija; después puedes vaciar la agenda y seguir haciendo cambios manuales. La interfaz impide dejar una agenda habilitada sin transiciones.

En primavera una hora inexistente se desplaza al primer minuto válido; en otoño una hora repetida se ejecuta una sola vez, en la primera aparición. Manual hasta próximo bloque termina en la frontera aunque ambos perfiles tengan igual temperatura. Editar agenda recalcula esa frontera; si desaparecen todas, la retención pasa a sin vencimiento explícito. Activar horario desde cero exige un bloque.

### Ejemplo paso a paso

Para Normal de día y Noche al dormir en una habitación:

1. Ajusta las temperaturas **Calor · Normal** y **Calor · Noche** de ese termostato; para refrigeración existen valores separados de Frío.
2. En Configurar → Añadir o sustituir bloque horario, selecciona los días deseados, **07:00** y **Normal**. Guarda.
3. Añade otro bloque para esos días: **23:00**, **Noche**. Guarda y activa **Usar horario** en esa zona.

Normal rige desde las 07:00 hasta las 23:00; Noche desde las 23:00 hasta las 07:00 del siguiente día programado. No necesitas bloques separados de inicio y fin. Son ejemplos, no horas ni temperaturas prescritas para un suelo radiante.

Puedes usar Normal/Eco en salón, otras horas en despacho y Noche solo en habitación. Para compartir un programa ya preparado utiliza **Copiar ajustes de Radiant Climate**, seleccionando únicamente Programación; después puedes modificar cada zona por separado.

Si a las 22:30 subes manualmente la temperatura durante cuatro horas, la retención sigue hasta las 02:30 aunque a las 23:00 comience Noche. Después vuelve al perfil que corresponda entonces. Apagar **Usar horario** deja una consigna fija; no apaga el termostato.

## Vacaciones de toda la vivienda

Utiliza **Vacaciones de la vivienda** para una ausencia indefinida y para terminarla al volver antes. Para fecha de vuelta: **Configuración general → Configurar → Vacaciones y regreso**, activa la ausencia y selecciona **fecha y hora de regreso**. Se aplica a todas las zonas cargadas usando sus perfiles Ausente; no exige ayudantes, scripts ni automatizaciones.

Al llegar esa fecha/hora, cada zona recupera su horario o consigna fija. Una retención Manual posterior aún vigente conserva prioridad. Las zonas apagadas siguen apagadas. La fecha indica cuándo se reanuda la regulación habitual: no promete que la vivienda ya haya alcanzado la consigna a esa hora.

Activar explícitamente Vacaciones sustituye retenciones manuales anteriores; una intervención manual posterior prevalece. También puedes ajustar o terminar la ausencia de una habitación desde su propio control. El interruptor de vivienda permanece encendido mientras alguna zona esté en Ausente, para poder terminar todas de una vez. Sus atributos indican cuántas están ausentes, si es parcial y si tienen regresos diferentes.

La acción global utiliza los mismos estados de cada zona, persistentes al reiniciar; no mantiene una segunda agenda de vacaciones en competencia. Una zona nueva empieza apagada: si la añades durante una ausencia, aplícale Vacaciones antes de habilitarla.

## Fuentes y módulos

La instalación admite exterior y entidad weather compartidos en Configurar. Entorno, sol y anticipación permite sustituirlos por zona; dejar vacíos hereda. No hace falta editar identificadores en código ni crear otra fuente de temperaturas.

| Control por zona | Resultado al activarlo | Sin datos/desactivado |
|---|---|---|
| Usar previsión meteorológica | Contexto solar y temperatura prevista para anticipación | Continúa la regulación interior |
| Usar temperatura exterior | Contexto de pérdidas para modelo/adelanto cuando sea utilizable | Modelo interior o agenda normal |
| Aprender respuesta térmica | Estadísticas separadas por temporada, sin actuar por aprender | Conserva el modelo y deja de entrenarlo |
| Anticipar horario | Adelanto acotado del próximo perfil más exigente | Sin agenda/modelo válido, no anticipa |
| Aprovechar inercia térmica | Pausa acotada cerca del objetivo y con modelo/tendencia válidos | Regulación normal |
| Aporte solar | Desactivado, Observación u Optimizar por zona | Observación no altera relés; datos perdidos degradan el módulo |
| Pausar por ventana | Suspende según contacto y retardos | Sin dependencia del contacto |

Solar Optimizar requiere confirmar orientación, elevación y sombras observadas. No confundir oportunidad compartida, geometría y sol directo. No se usan persianas. La regla solar inicial no se aplica a refrigeración. Consulta [algoritmos y límites](intelligence.md).

## Regulación y válvulas

En Dispositivos y regulación se ajustan histéresis, mínimos, caducidad, contacto, retardos y tiempo estimado de cierre. En instalación se configuran por separado los tiempos estimados de apertura y cierre general; no se presupone que sean iguales. Cero indica desconocido, nunca maniobra instantánea demostrada.

### Sustituir un relé o dividir una zona

1. Apaga **Climatización** y comprueba el cierre comunicado. La instalación física y su aislamiento deben realizarse con los medios y conocimientos adecuados, sin manipular cableado bajo tensión.
2. Una vez que HA exponga las salidas nuevas como entidades `switch` independientes, abre **Configurar → Dispositivos y regulación** del termostato existente y cambia su relé. Se conservan su identidad, perfiles y agenda.
3. Las salidas antiguas siguen pendientes de aislamiento hasta comunicar apagado y transcurrir su tiempo de cierre estimado. Mientras haya alguna pendiente, no se permiten nuevas aperturas en la instalación. El motivo y los atributos de Climatización muestran qué queda pendiente; el bloqueo persiste al reiniciar.
4. Si has retirado físicamente el módulo y la entidad antigua ya no puede comunicar, utiliza **Confirmar retirada física de un relé antiguo** (`radiant_climate.acknowledge_retired_actuator`), con Climatización apagada, introduciendo el identificador antiguo y confirmando la desconexión comprobada. La acción no admite una salida todavía asignada. No se debe usar para ocultar un fallo sin resolver.
5. Revisa los tiempos del dispositivo nuevo y vuelve a habilitar tras comprobar las asignaciones. Si han cambiado los circuitos o el sensor, utiliza **Restablecer aprendizaje térmico** para no seguir utilizando la respuesta anterior.

Para separar un circuito antes agrupado, conserva el termostato original asignado a su nueva salida y añade otro para el circuito separado, con su propio sensor, consigna y horario. Cada uno puede usar calor/frío, aprendizaje e inercia, con solar desactivado. Un contacto de puerta puede seleccionarse igual que uno de ventana para pausar esa zona. El control no depende del número de canales que tenga cada módulo, sino de que HA exponga sus salidas independientes y no estén asignadas a más de un controlador.

Un fallo de actuador mantiene bloqueadas las aperturas. El cierre admite hasta dos intentos de recuperación separados al menos 30 segundos, con presupuesto persistente; no se reintenta indefinidamente. Apagado general explícito autoriza un nuevo ciclo acotado de cierre. Una orden ya enviada puede terminar antes de que se procese la siguiente; nuevas aperturas se inhiben mientras haya cambios pendientes. Cada llamada de maniobra está acotada a cinco segundos, sin acreditar tiempos físicos.

| Ajuste | Inicial | Rango del asistente |
|---|---:|---:|
| Histéresis | 0,2 °C | 0,05–2 °C |
| Mínimos activo/inactivo | 180 s | 0–3600 s |
| Caducidad interior | 3600 s | 60–86400 s |
| Retardos ventana | 0 s | 0–600 s |
| Maniobra estimada de válvula | 0 s (desconocida) | 0–900 s |
| Adelanto máximo | 120 min | 0–360 min |
| Proyección residual | 15 min | 5–60 min |

Son puntos de partida, no parámetros calibrados para una vivienda. Un fallo o Apagado no espera el mínimo activo. Un contacto desconocido pausa inmediatamente si la función está habilitada. Una zona no aislable puede impedir suministro compartido.

Limpiar un contacto o una fuente elimina su referencia; una fuente vacía vuelve a heredar si existe una compartida. Cambiar dispositivos recarga la zona y cierra sus salidas durante la operación. Editar la instalación deshabilita conservadoramente la general y requiere reactivación explícita tras revisar.

## Vacaciones y aplicar a todas

Configurar → Vacaciones permite ausencia indefinida o regreso con fecha y hora locales. Activar vacaciones sustituye una retención previa; las intervenciones posteriores tienen prioridad Manual. No activa zonas apagadas. Al regreso recupera el programa o ajuste fijo subyacente.

La acción Radiant Climate: Copiar ajustes entre termostatos elige origen, destinos y grupos: temperaturas, política/duración, agenda, módulos y vacaciones. Destinos vacíos significa las demás zonas. No copia sensores, orientación, relés ni modelos aprendidos. Los requisitos se validan antes de copiar. Copiar una agenda deshabilitada deja consigna fija, conservando el objetivo efectivo.

## Diagnóstico

Motivo de regulación explica Apagado, fallo, ventana, mínimos, maniobra estimada, anticipación o pausa. El climate expone intención solicitada, control_state, manual_policy, manual_until, next_schedule_change, control_target, disponibilidad de fuentes y calidad del modelo. El objetivo anticipado se distingue de la consigna del bloque actual.

El diagnóstico exportable omite nombres, entidades fuente, identificadores y agenda. Restablecer aprendizaje elimina solo el modelo de esa zona. Si un relé presenta discrepancias repetidas, revisa escritores, comunicaciones y comportamiento al encender; apagar la general permite un nuevo intento acotado. No uses los relés como mandos cotidianos ni atribuyas el cambio a una persona sin evidencia.
