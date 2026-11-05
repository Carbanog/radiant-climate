# Arquitectura

El objetivo es una configuración cotidiana sencilla y módulos opcionales. El núcleo no sabe qué entidad física existe ni accede a HA; la adaptación se ocupa de eventos, almacenamiento y servicios. No hay automatizaciones o ayudantes externos requeridos por la base.

| Módulo | Responsabilidad |
|---|---|
| `core/control.py` | Modos, consignas, retenciones, caducidad y decisión de demanda |
| `runtime.py` | Registro de zonas, estado persistente, serialización y único escritor de salidas |
| `config_flow.py` | Alta mínima, opciones y rechazo de asignaciones duplicadas |
| `climate.py` | Interfaz nativa de temperatura y modo |
| `switch.py` / `select.py` | Habilitación general y temporada declarada |
| `sensor.py` / `diagnostics.py` | Causa de actuación y diagnóstico reducido |

## Prioridades de la base

Apagado general o individual, incompatibilidad de temporada, actuador inválido, ventana y dato interior inválido/caducado fuerzan ausencia de demanda. No esperan el mínimo de tiempo activo. Después actúa la regulación básica.

Un fallo interior detiene su zona. Con general compartida, si una zona que debe estar cerrada no comunica apagado no se permite abrir el suministro común. Esto puede suspender otras zonas: independencia de control no significa aislamiento hidráulico demostrado.

## Autoridad sobre salidas

Dentro de esta integración las salidas tienen un solo escritor. La validación evita asignar un relé a dos zonas o usarlo como general y zona. Esto no bloquea los servicios de HA ni a un controlador externo: los anteriores deben detenerse antes de habilitar esta integración.

Las discrepancias no generan un bucle de reintentos ilimitado. Una orden pendiente no se repite; al superar su plazo de respuesta se requiere revisión. Apagar explícitamente la general permite un nuevo intento acotado de cierre. La detección detallada del autor de una orden externa y la reparación de conflictos son trabajo pendiente.

## Persistencia

Se guardan habilitación general, temporada declarada e intención por zona. Las salidas no se restauran ciegamente: se recalculan con los datos disponibles. Cada zona nueva se crea en Apagado y la primera instalación deshabilitada. Opciones de instalación provocan deshabilitación conservadora durante la recarga.

La parada ordenada de HA intenta desenergizar salidas sin olvidar la intención guardada. Un corte eléctrico, un proceso terminado a la fuerza o un dispositivo incomunicado no puede recibir esa orden: se necesitan comportamientos físicos adecuados.

## Evolución prevista, todavía no operativa

Programación y perfiles calcularán el objetivo sin escribir en relés. Las tres políticas Manual del núcleo se conectarán al módulo de agenda. Solar, exterior, previsión y aprendizaje serán módulos opcionales con condiciones de disponibilidad explícitas. Una predicción no cambiará la intención del usuario ni deshabilitará una protección.

El aprendizaje tendrá estado separado por zona y temporada y comenzará en observación. La primera estrategia de confort mantendrá la consigna de la persona y optimizará el aporte; no anunciará ahorro simplemente por reducirla. No hay algoritmo predictivo implementado en esta base.
