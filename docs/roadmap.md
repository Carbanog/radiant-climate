# Plan de desarrollo

El proyecto es personal, público y con alcance explícito. Tener una función en este plan no significa que esté implementada. Cada fase debe cerrar comportamiento, implementación, pruebas, diagnóstico y documentación antes de declarar su disponibilidad.

1. **Base local:** termostato fijo, apagado general/individual, fallos y persistencia. Es el trabajo inicial de esta candidata.
2. **Programación y perfiles:** agenda por zona, temperaturas editables y tres políticas Manual conectadas a la interfaz. Sin ayudantes externos obligatorios y con restauración/cambio horario probados.
3. **Módulos opcionales:** exterior y meteorología seleccionables, solar por orientación y ventanas. Falta de datos degrada solo el módulo; cada control del panel debe tener efecto real y explicación.
4. **Observación térmica:** calidad de datos, tendencias y modelos separados por calor/frío. No atribuir todo cambio a los actuadores.
5. **Anticipación y parada predictiva:** activación por zona tras validación del modelo, límites de confort y degradación al control base.
6. **Uso avanzado:** ausencia/vacaciones, aplicar ajustes a todas y mejoras de accesibilidad y diagnóstico.
7. **Piloto y aceptación:** copia/restauración, comprobaciones físicas, pruebas en un único laboratorio limpio y posterior aprobación de una versión identificable antes de cualquier instalación doméstica.

No se controla producción comunitaria, bombas ni persianas. El proyecto no puede garantizar posición de válvulas sin sensores ni sustituir protecciones físicas de refrigeración. Se prioriza previsibilidad y mantenimiento frente a añadir opciones sin validar.
