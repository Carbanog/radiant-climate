# Panel nativo por secciones

La ficha genérica del dispositivo la organiza Home Assistant. Para un uso diario claro,
añade una tarjeta Termostato por zona y tarjetas Entidades separadas por tarea.
No necesitas instalar tarjetas externas ni crear ayudantes. En cada tarjeta Entidades,
selecciona las entidades reales desde el editor visual; los identificadores dependen del
nombre y área de tu instalación, no copies identificadores de otra vivienda.

| Tarjeta | Controles existentes que incluir |
|---|---|
| Vivienda | Climatización, Temporada de suministro declarada, Vacaciones de la vivienda |
| Termostato de la zona | Entidad climate; el modo Apagado se mantiene hasta encender |
| Horario y Manual | Usar horario, Comportamiento de Manual, Duración de Manual, Reanudar programa |
| Perfiles de calor | Calor · Normal, Eco, Noche, Ausente |
| Perfiles de frío | Frío · Normal, Eco, Noche, Ausente |
| Funciones opcionales | Aprender respuesta térmica, Aprovechar inercia, Anticipar horario, Aporte solar, Usar previsión, Usar temperatura exterior |
| Ventanas | Pausar por ventana |
| Diagnóstico | Motivo de regulación y Revisión de relés pendiente; agua si está configurada |

Usa un panel con vistas de Salón/Habitación/Despacho o una vista por zona para no mostrar
los ocho perfiles de cada estancia a la vez. Los ajustes de dispositivos, agenda,
fuentes y ángulos se cambian desde Configurar en la entrada correspondiente.
En móvil, las tarjetas nativas se disponen verticalmente; en escritorio puedes usar
una vista Secciones y agruparlas por tarea. No cambia el control térmico ni sus datos.

Para copiar preferencias entre zonas utiliza la acción Copiar ajustes y selecciona
solo las partes que quieras compartir. La copia de módulos no copia orientación,
sensores, relés o modelos térmicos. Comprueba siempre los perfiles de destino.
