# Configuración y uso

Esta guía describe únicamente la base de desarrollo implementada. Consulta siempre el estado de CI del commit que estás utilizando. No hay una versión aprobada para producción.

## Instalación

La primera entrada de la integración representa el control general. La válvula de entrada es opcional: déjala sin seleccionar si los actuadores no comparten una válvula controlada por HA. No selecciones una bomba o producción como si fuera una válvula.

Se crean dos controles propios: **Climatización** y **Temporada de suministro declarada**. La temporada es una decisión/configuración, no una medición de agua disponible.

## Añadir una zona

Al añadir otra entrada eliges:

1. Sensor interior con temperatura en grados Celsius.
2. Uno o varios interruptores correspondientes a sus actuadores.
3. Calor, frío o ambos.
4. Consigna inicial.

La zona aparece apagada. El nombre inicial se obtiene del sensor y puede editarse desde HA. Una zona puede agrupar varios circuitos, pero deben compartir un objetivo de temperatura. No se exige un termostato independiente para cada circuito físico.

Los sensores deben exponer temperatura en °C. Un valor sin unidad o con otra unidad se rechaza y detiene la zona. Esta versión no convierte sensores Fahrenheit. La cadencia y fiabilidad de sensores derivados requieren comprobación antes de producción.

## Perfiles y programación semanal

Cada zona crea sus propios controles de temperatura Normal, Eco y Noche para cada modo disponible. Son entidades `number` mantenidas por la integración, sin `input_number` externos ni valores duplicados. Los valores iniciales son orientativos y editables desde el dispositivo o un panel nativo. Noche no obliga a reducir la temperatura de todos los dormitorios: ajústala según el uso y la inercia.

En **Configurar → Añadir o sustituir bloque horario**, selecciona días, hora y perfil. Un bloque continúa hasta el siguiente, incluso entre días; repetir día y hora lo sustituye. El botón de eliminar muestra los bloques existentes. El horario pertenece a cada termostato y utiliza la zona horaria de HA. En el salto de primavera, una hora inexistente se ejecuta al primer minuto válido; la hora repetida de otoño se ejecuta una vez, en su primera aparición.

El interruptor **Usar horario** habilita la programación, sin encender un termostato apagado. Requiere al menos un bloque. Apagarlo conserva la consigna efectiva actual como fija, sin vencimiento. **Volver al horario** elimina Manual y habilita el horario; tampoco vence Apagado individual/general.

**Comportamiento de Manual** permite elegir duración (240 minutos inicialmente, editable), próximo bloque o hasta volver expresamente al horario. Cambiar esta preferencia solo afecta a futuras intervenciones. Cambiar temperatura o seleccionar un perfil desde cualquier servicio `climate` crea Manual cuando hay horario activo, incluso si coincide con el perfil. Una intervención repetida renueva su duración. Cambiar temperaturas de los perfiles no cancela Manual. Sin horario, seleccionar un perfil sigue su valor editable; girar la consigna pasa a fija.

El termostato muestra `control_state`, `manual_policy`, `manual_until` y `next_schedule_change`. Los atributos explican la intención; el sensor Motivo explica los bloqueos y la demanda. Un modo individual Apagado prevalece sobre cualquier perfil. El cambio explícito de temporada elimina la retención del modo anterior y consulta el perfil de la temporada nueva. No se afirma que cuatro horas sean el tiempo de respuesta de un suelo.

## Opciones

En las opciones de la zona puedes cambiar entradas, seleccionar un contacto de ventana y ajustar histéresis, tiempos mínimos y caducidad. Un contacto configurado abierto pausa; uno no disponible también pausa. Sin contacto configurado no hay dependencia de ventana.

Los retardos de apertura/cierre de ventana, el perfil de emisor y la configuración por módulos previstos no están todavía implementados. La interfaz de esta base no debe confundirse con el producto final.

Para eliminar un contacto o una general, limpia su campo en las opciones. La eliminación debe quedar guardada como valor vacío, no recuperar una referencia anterior por mezclar opciones y datos originales.

## Apagado y reactivación

La orden de Apagado individual permanece. El interruptor general suspende todas las zonas, conserva sus intenciones y ordena apagar zonas y general. Una consigna editada durante esa parada se guarda sin abrir salidas.

Al habilitar de nuevo, solo demandan las zonas que estaban encendidas, tienen datos válidos y son compatibles con la temporada declarada. Cambiar la temporada actualiza el modo de zonas activas compatibles y conserva las apagadas.

No utilices directamente los relés como mandos cotidianos. Si otro controlador está escribiendo en ellos, detén el ensayo y resuelve la asignación. El estado comunicado no es posición de válvula.

## Pendiente de documentar como función operativa

Las siguientes opciones pertenecen al diseño, no a este menú: agenda propia, perfiles editables, retención Manual desde el panel, meteo, solar, influencia exterior, anticipación, vacaciones y aprendizaje. No hay que crear ayudantes para simularlas mientras se desarrollan.
