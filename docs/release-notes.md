# Cambios y actualización

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
