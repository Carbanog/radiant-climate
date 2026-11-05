# Cambios y actualización

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
