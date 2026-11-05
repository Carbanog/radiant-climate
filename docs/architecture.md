# Arquitectura

El objetivo es una configuración cotidiana sencilla y módulos opcionales. El núcleo no sabe qué entidad física existe ni accede a HA; la adaptación se ocupa de eventos, almacenamiento y servicios. No hay automatizaciones o ayudantes externos requeridos por la base.

| Módulo | Responsabilidad |
|---|---|
| `core/control.py` | Modos, consignas, retenciones, caducidad y decisión de demanda |
| `core/program.py` | Perfiles, bloques semanales y límites horarios con cambio de hora |
| `runtime.py` | Registro de zonas, estado persistente, serialización y único escritor de salidas |
| `config_flow.py` | Alta mínima, opciones y rechazo de asignaciones duplicadas |
| `climate.py` | Interfaz nativa de temperatura y modo |
| `switch.py` / `select.py` | Habilitación general y temporada declarada |
| `number.py` / `button.py` / `services.py` | Temperaturas editables, retención, retorno al horario y copia explícita entre zonas |
| `sensor.py` / `diagnostics.py` | Causa de actuación y diagnóstico reducido |

## Prioridades de la base

Apagado general o individual, incompatibilidad de temporada, actuador inválido, ventana y dato interior inválido/caducado fuerzan ausencia de demanda. No esperan el mínimo de tiempo activo. Después actúa la regulación básica.

Un fallo interior detiene su zona. Con general compartida, si una zona que debe estar cerrada no comunica apagado no se permite abrir el suministro común. Esto puede suspender otras zonas: independencia de control no significa aislamiento hidráulico demostrado.

## Autoridad sobre salidas

Dentro de esta integración las salidas tienen un solo escritor. La validación evita asignar un relé a dos zonas o usarlo como general y zona. Esto no bloquea los servicios de HA ni a un controlador externo: los anteriores deben detenerse antes de habilitar esta integración.

Las discrepancias no generan un bucle de reintentos ilimitado. Una orden pendiente no se repite; al superar su plazo de respuesta se requiere revisión. Apagar explícitamente la general permite un nuevo intento acotado de cierre. La detección detallada del autor de una orden externa y la reparación de conflictos son trabajo pendiente.

## Persistencia

Se guardan habilitación general, temporada, intención, programa, perfiles, políticas y activación de ventana por zona. Las salidas no se restauran ciegamente: se recalculan con los datos disponibles. Cada zona nueva se crea en Apagado y la primera instalación deshabilitada. Opciones de instalación provocan deshabilitación conservadora durante la recarga. Una orden que no puede guardarse no habilita actuadores y deshabilita la instalación actual.

La parada ordenada de HA intenta desenergizar salidas sin olvidar la intención guardada. Un corte eléctrico, un proceso terminado a la fuerza o un dispositivo incomunicado no puede recibir esa orden: se necesitan comportamientos físicos adecuados.

## Optimización opcional implementada

Programación y perfiles calculan el objetivo sin escribir en relés. Las tres políticas Manual se conectan a la agenda y sobreviven a reinicios completos. `environment.py` obtiene fuentes y previsión con tiempos y frecuencia acotados fuera del bloqueo de actuadores; `intelligence.py` aplica políticas de zona y `core/intelligence.py` calcula geometría, tendencias, calidad y adelanto. Los módulos se habilitan por separado, sin cambiar la intención ni deshabilitar protecciones.

El aprendizaje separa zona, temporada y estado de actuación y comienza observando. Anticipación y pausa por inercia exigen calidad mínima; solar requiere geometría y tendencia, y la activación exige confirmar incidencia. Las heurísticas mantienen la consigna de confort y tienen límites explícitos. No equivalen a un modelo físico completo, aprendizaje causal de ganancias solares ni ahorro demostrado. Véase [algoritmos y límites](intelligence.md).

Core puede cargar entradas concurrentemente al arrancar. La creación del gestor está protegida por un bloqueo de instalación y el registro de zonas comparte el bloqueo de maniobras. Ninguna apertura se permite antes de registrar las entradas habilitadas. Las discrepancias repetidas quedan enclavadas y persistidas hasta revisión y apagado general explícito.
