# Alcance de la primera beta

La implementación de software incluye termostatos propios calor/frío, intención persistente, apagado general/individual, perfiles, agenda, las tres políticas Manual, ventanas con retardos, módulos ambientales independientes, solar por zona, observación térmica, adelanto acotado, pausa por inercia, vacaciones y copia de ajustes.

La primera beta se entrega para una instalación voluntaria e identificable. No se conecta automáticamente a dispositivos ni cambia una instalación existente. Las funciones avanzadas comienzan desactivadas y requieren configurar sus fuentes; predicción exige calidad mínima y solar activo exige confirmar incidencia.

## Antes de aceptar una vivienda

1. Instalar la beta en un único laboratorio limpio y probar sus formularios y salidas simuladas.
2. Confirmar modelos, tiempos, comunicaciones, comportamiento al volver la alimentación y dimensionado eléctrico.
3. Copia y reversión recuperables; detener los otros escritores antes de conectar salidas reales.
4. Configurar horarios y consignas, validar calor y frío según suministro disponible y conservar las protecciones físicas de la instalación.
5. Recopilar datos reales en observación y calibrar por zona/temporada; comparar confort antes de activar predicciones.
6. Aprobar expresamente una versión doméstica y retirar componentes antiguos solo tras revisar dependencias.

## Mejoras futuras que no se simulan

Un modelo físico completo de losa, atribución causal de ganancias solares, geometría detallada de obstáculos y confirmación real de posición/caudal requieren más modelos o instrumentación. No se afirma que existan en esta beta. Las heurísticas actuales tienen límites publicados y pueden desactivarse individualmente.

No se controlan producción ni bombas comunitarias, ni se utilizan persianas. La facilidad de mantenimiento se basa en módulos pequeños, configuración nativa y regresiones automatizadas; no significa mantenimiento nulo ante futuras versiones de HA.
