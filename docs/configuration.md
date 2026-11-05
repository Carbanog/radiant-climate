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

Los sensores deben exponer una temperatura compatible en °C. Esta primera versión no convierte sensores Fahrenheit: no los selecciones. La validación automática de unidades y de sensores derivados aún debe ampliarse antes de producción.

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
