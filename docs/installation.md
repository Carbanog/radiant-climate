# Instalación, piloto y reversión

La candidata está destinada primero a pruebas aisladas. Aprobar código no aprueba su conexión a actuadores domésticos. Conserva una copia recuperable y el commit exacto, y detén cualquier controlador anterior sobre las mismas salidas antes de habilitar la nueva instalación.

## HACS y alta por interfaz

1. En el HA de pruebas, crea una copia completa y comprueba que aparece con contenido de Home Assistant y opción de restauración. No envíes esa copia a un repositorio público.
2. En HACS, abre el menú → Repositorios personalizados. Introduce `https://github.com/Carbanog/radiant-climate` y categoría Integración.
3. Busca Radiant Climate, descarga la rama principal y registra el commit instalado. No se necesita una release para un repositorio personalizado, pero main es una rama de desarrollo mutable: no uses actualizaciones automáticas en una vivienda.
4. Reinicia únicamente ese HA de pruebas. No actualices Core como parte de esta instalación.
5. En Dispositivos y servicios → Añadir integración crea Radiant Climate. La primera entrada es la instalación. Selecciona la válvula general solo si existe y, para el ensayo, únicamente una salida simulada.
6. Añade otra entrada por termostato. Elige sensor interior, relés, modos y consigna; conserva Climatización y las zonas apagadas hasta revisar las asignaciones.
7. Revisa perfiles, temperatura real, disponibilidad de salidas y suministro declarado. Después habilita una zona de prueba y la general.

No necesitas Studio Code Server, YAML interno ni automatizaciones para usar la integración. Los ejemplos YAML de paneles o acciones pueden pegarse en los editores de interfaz si se desean. No copies fixtures de CI a producción.

Si se usa el ZIP temporal de CI, comprueba el SHA-256 y BUILD.json y copia solo la carpeta de la integración. El ZIP es un artefacto del commit, no una release aprobada. La alternativa HACS evita copiar archivos manualmente.

## Pruebas del piloto

Primero prueba sin horario ni módulos: calor, frío, consigna fija, Apagado individual y general. Usa un margen de temperatura suficiente para no confundir histéresis con fallo de regulación. Verifica los motivos visibles y las salidas comunicadas.

Configura dos bloques y modifica la temperatura, incluida una consigna igual al perfil. Comprueba las tres políticas Manual, una retención que atraviese Noche, Volver al horario, edición de perfil durante Manual y desactivar programación conservando la consigna.

Activa módulos uno a uno: ventanas; fuentes auxiliares y su pérdida; solar en Observación; aprendizaje en observación. Sin datos válidos no deben aparecer predicciones activas. Las pruebas con modelos sintéticos acreditan lógica de software y nunca son una calibración que se copie a la vivienda.

Ensaya reinicio con Manual, fecha vencida y Apagado. Con suministro compartido comprueba demandas simultáneas, pérdida de una zona aislable, salida desconocida y general indisponible. No interpretes una orden o una espera temporal como confirmación de apertura, cierre o caudal.

## Migración doméstica posterior

Antes de aprobarla deben estar confirmados los modelos, tiempos, comportamiento al recuperar alimentación y dimensionado eléctrico. Mantén las protecciones físicas de refrigeración de la instalación. No manipules cableado bajo tensión ni deduzcas estado hidráulico de un relé.

Haz copia de VM/configuración, exporta valores y horarios y conserva los paneles anteriores. Detén automatizaciones que escriban en las salidas y apaga/deshabilita los termostatos anteriores, sin borrarlos. Crea las zonas nuevas apagadas, copia consignas y programa y revisa todos los parámetros antes de habilitar.

Migra referencias de paneles al climate y controles propios. Haz una prueba controlada y revisa trazas y motivos. No borres ayudantes o scripts antiguos hasta comprobar consumidores y aceptar el comportamiento. El inventario doméstico debe mantenerse fuera de este repositorio.

## Reversión

Apaga Climatización en Radiant Climate y verifica los estados comunicados. Deshabilita sus entradas antes de habilitar el controlador anterior. Nunca dejes ambos activos sobre los mismos relés. Reactiva las automatizaciones y paneles conservados y declara la temporada correcta.

Si una actualización impide arrancar, utiliza el modo seguro o la restauración de la copia anterior. Para volver a un commit, restaura juntos código, configuración y almacenamiento respaldados; no cambies archivos de .storage a mano con HA activo. Retirar el paquete mediante HACS y reiniciar es una desinstalación, no recupera por sí sola la configuración anterior.

No se han publicado etiquetas/releases solo para ensayar. Una versión doméstica deberá quedar identificada y aprobada para poder recuperarla sin depender del estado futuro de main.
