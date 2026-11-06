# Instalación, piloto y reversión

La release v0.2.5 incluye las correcciones y pruebas descritas en las notas de versión. Su publicación no configura los actuadores domésticos. Conserva una copia recuperable y el commit exacto. Detén y deshabilita los controladores anteriores **antes de asignar sus relés** a Radiant Climate, incluida la válvula general.

**Apagado es una orden de cierre, no un modo pasivo de observación.** Una vez
asignada una salida, Radiant Climate puede solicitar apagarla aunque Climatización
esté desactivada. Instalar los archivos sin asignar salidas no transfiere su control;
configurarlas sí. No prepares en paralelo dos controladores sobre relés reales.

## Marketplace/HACS y alta por interfaz

1. En el HA donde vayas a instalar, crea una copia completa y comprueba que aparece con contenido de Home Assistant y opción de restauración. No envíes esa copia a un repositorio público.
2. En HA 2026.11 o posterior, abre Configuración → Marketplace → Añadir desde enlace e introduce `https://github.com/Carbanog/radiant-climate`. En 2026.10 y anteriores, utiliza HACS → Repositorios personalizados, categoría Integración. No reinstales HACS en 2026.11: Marketplace lo sustituye.
3. Busca Radiant Climate y selecciona `v0.2.5`, sin necesidad de mostrar versiones preliminares. Registra versión y commit. Main es una rama mutable: no uses su estado futuro como sustituto de una versión identificada.
4. En Marketplace 2026.11 una instalación nueva abre directamente el asistente de configuración, sin reinicio intermedio. Las actualizaciones todavía pueden requerir reiniciar según el aviso de HA. Con HACS antiguo, reinicia ese HA y utiliza Dispositivos y servicios → Añadir integración. No actualices Core como parte de este procedimiento.
5. La primera pantalla, «Configuración general», configura el sistema compartido. En beta.1 se llamaba «Instalación». La válvula general es opcional; puede dejarse vacía y configurarse después. Para el ensayo selecciona únicamente una salida simulada.
6. Añade otra entrada por termostato. Elige sensor interior, relés, modos y consigna; conserva Climatización y las zonas apagadas hasta revisar las asignaciones.
7. Revisa perfiles, temperatura real, disponibilidad de salidas y suministro declarado. Después habilita una zona de prueba y la general.

No necesitas Studio Code Server, YAML interno ni automatizaciones para usar la integración. Los ejemplos YAML de paneles o acciones pueden pegarse en los editores de interfaz si se desean. No copies fixtures de CI a producción.

Si se usa el ZIP temporal de CI, comprueba el SHA-256 y BUILD.json y copia solo la carpeta de la integración. El ZIP es un artefacto del commit, no una release aprobada. Marketplace/HACS evita copiar archivos manualmente.

## Pruebas del piloto

### Icono y miniatura

El componente incluye `custom_components/radiant_climate/brand/icon.png`. El icono local y la miniatura previa de Marketplace tienen rutas de distribución diferentes. Marketplace usa el servicio de imágenes de Home Assistant, cuyo índice se obtiene del catálogo; un repositorio personalizado todavía no indexado puede carecer de miniatura aunque su PNG exista. Reinstalar la integración no incorpora el repositorio a ese índice. No se modifica automáticamente el catálogo público por añadir un repositorio personalizado.

Fuentes: [flujo Marketplace 2026.11](https://www.home-assistant.io/Changelogs), [servicio oficial de miniaturas](https://github.com/home-assistant/brands#marketplace-icons).

Primero prueba sin horario ni módulos: calor, frío, consigna fija, Apagado individual y general. Usa un margen de temperatura suficiente para no confundir histéresis con fallo de regulación. Verifica los motivos visibles y las salidas comunicadas.

Configura dos bloques y modifica la temperatura, incluida una consigna igual al perfil. Comprueba las tres políticas Manual, una retención que atraviese Noche, Volver al horario, edición de perfil durante Manual y desactivar programación conservando la consigna.

Activa módulos uno a uno: ventanas; fuentes auxiliares y su pérdida; solar en Observación; aprendizaje en observación. Sin datos válidos no deben aparecer predicciones activas. Las pruebas con modelos sintéticos acreditan lógica de software y nunca son una calibración que se copie a la vivienda.

Ensaya reinicio con Manual, fecha vencida y Apagado. Con suministro compartido comprueba demandas simultáneas, pérdida de una zona aislable, salida desconocida y general indisponible. No interpretes una orden o una espera temporal como confirmación de apertura, cierre o caudal.

## Migración doméstica posterior

Antes de aprobarla deben estar confirmados los modelos, tiempos, comportamiento al recuperar alimentación y dimensionado eléctrico. Mantén las protecciones físicas de refrigeración de la instalación. No manipules cableado bajo tensión ni deduzcas estado hidráulico de un relé.

Haz copia de VM/configuración, exporta valores y horarios y conserva los paneles anteriores. Detén automatizaciones que escriban en las salidas y apaga/deshabilita los termostatos anteriores, sin borrarlos. Crea las zonas nuevas apagadas, copia consignas y programa y revisa todos los parámetros antes de habilitar.

Si empiezas probando una sola zona con una general compartida, mantén el resto
apagado y los controladores antiguos deshabilitados sobre esas salidas y la
general. No mantengas otras zonas en DST/VT con otra automatización escribiendo
en la misma general. Tras comprobar esa primera zona, configura y valida las
restantes durante la misma migración controlada.

Migra referencias de paneles al climate y controles propios. Haz una prueba controlada y revisa trazas y motivos. No borres ayudantes o scripts antiguos hasta comprobar consumidores y aceptar el comportamiento. El inventario doméstico debe mantenerse fuera de este repositorio.

## Reversión

Apaga Climatización en Radiant Climate y verifica los estados comunicados. Deshabilita sus entradas antes de habilitar el controlador anterior. Nunca dejes ambos activos sobre los mismos relés. Reactiva las automatizaciones y paneles conservados y declara la temporada correcta.

Si una actualización impide arrancar, utiliza el modo seguro o la restauración de la copia anterior. Para volver a un commit, restaura juntos código, configuración y almacenamiento respaldados; no cambies archivos de .storage a mano con HA activo. Retirar el paquete mediante HACS y reiniciar es una desinstalación, no recupera por sí sola la configuración anterior.

No vuelvas a v0.2.0 mientras existan actuadores retirados pendientes: esa versión no supervisa ese registro. Resuelve el aislamiento antes de una reversión. No elimines toda la integración para eludirlo; aunque la supervisión se conserva mientras HA sigue ejecutándose, no se puede prometer control tras eliminar todas las entradas y reiniciar HA.

Las entregas se publican después de validar sus pruebas; no se crean releases para cada ensayo. Conserva la versión elegida y su copia para recuperación sin depender de main. Los ajustes cotidianos se realizan desde HA; las correcciones de código se distribuyen como nuevas releases.
