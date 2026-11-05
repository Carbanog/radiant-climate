# Módulos opcionales y límites

La consigna de confort pertenece al usuario o al programa. Las optimizaciones no la rebajan para aparentar ahorro. La tarjeta muestra la consigna vigente; `control_target` identifica por separado un objetivo anticipado. Manual, Apagado, sensores críticos, ventanas habilitadas y compatibilidad de suministro tienen prioridad. Todo módulo empieza desactivado.

## Fuentes y fallos

En Configurar la instalación se pueden elegir exterior y entidad `weather` compartidos; cada zona puede sustituirlos en Entorno, sol y anticipación. Vacío hereda la fuente común. Los interruptores de previsión y exterior son independientes. No hacen falta ayudantes ni credenciales en esta integración.

La previsión se obtiene mediante la acción oficial `weather.get_forecasts`, tipo horario, como máximo una vez cada quince minutos por fuente y con un plazo de cinco segundos. La petición se realiza fuera del bloqueo de actuadores. Proveedores sin previsión horaria, errores, respuesta vacía, datos caducados o fuente indisponible no se sustituyen por valores inventados. La caché caduca a los treinta minutos. Se utilizan puntos futuros cercanos al bloque que se anticipa.

El exterior puede corregir conservadoramente el adelanto según las condiciones con las que se observó el modelo; la previsión puede aportar la temperatura esperada a la hora de llegada. Sin esos datos se utiliza el modelo interior, y sin modelo se utiliza la agenda normal. No es una curva de agua: no se gobiernan temperaturas de impulsión ni producción.

Fuentes: [acciones meteorológicas de HA](https://www.home-assistant.io/integrations/weather/), [contrato de entidades meteorológicas](https://developers.home-assistant.io/docs/core/entity/weather/). El adaptador se prueba con Core 2026.10.4.

## Solar

Una entidad binaria de instalación muestra la oportunidad compartida a partir de la posición solar y las condiciones actuales cuando se habilita la meteorología. Sin meteo utiliza solo la posición solar e indica esa base; no demuestra sol directo.

Cada zona tiene azimut de ventanas, elevación mínima observada y amplitud angular. La elevación se refiere al horizonte local, pero la incidencia depende también del azimut y los obstáculos. No se usan persianas. Una zona sin ganancias directas puede mantener Solar desactivado.

El selector permite Desactivado, Observación y Optimizar. Observación muestra candidatos sin modificar salidas. Optimizar exige confirmar previamente los umbrales de incidencia y sombra. La regla inicial solo pausa calefacción cerca del objetivo (hasta 0,3 °C por debajo), con tendencia interior ascendente que proyecta alcanzar la consigna. Si falla la meteo, sigue exigiendo geometría y tendencia interior. Manual impide esa pausa. No se invierte esta regla para refrigeración, no se atribuye al sol toda subida y no se promete conocer sombras no medidas.

No hay una predicción causal de ganancias solares de varias horas. La combinación inicial es deliberadamente acotada: posición solar, contexto meteorológico y calentamiento observado, con degradación al termostato base.

## Observación y anticipación

Aprender respuesta térmica recopila periodos válidos por zona, temporada y estado comunicado de actuación. Excluye paradas, ventanas, fallos y periodos de incidencia solar candidata; no cose muestras a través de reinicios. Solo procesa nuevos informes, limita memoria y rechaza saltos incompatibles. Las estadísticas se guardan periódicamente y al parar ordenadamente.

Se requieren al menos doce intervalos, seis horas y tres episodios, respuesta entre 0,05 y 3 °C/h y dispersión acotada para declarar un modelo utilizable. Son umbrales de calidad del algoritmo inicial, no garantía de aprendizaje en un número de días. La resolución, cadencia y condiciones de la instalación pueden impedir alcanzar esa calidad. Se muestran horas, episodios, tendencia, rechazos y disponibilidad. Restablecer aprendizaje elimina las estadísticas propias de esa zona y obliga a volver a observar.

Anticipar horario calcula el tiempo para alcanzar un perfil próximo más exigente con el ritmo observado y un límite de adelanto configurable. No actúa sin agenda o modelo válido, durante Manual o Ausente, ni vence Apagado. No aprende preferencias de las modificaciones manuales. El adelanto y el objetivo de regulación se muestran separados del bloque actual.

Aprovechar inercia usa modelo válido y tendencia observada para pausar cerca del objetivo cuando se proyecta aporte residual. Tiene horizonte configurable y el mismo margen conservador; respeta los mínimos y funciona por separado en calor/frío. No mide energía acumulada en la losa. Sin tendencia/modelo, vuelve a regulación normal. Estas heurísticas necesitan piloto y evaluación de confort; no son un modelo físico certificado ni ahorro demostrado.

## Ausente y vacaciones

El perfil Ausente tiene temperaturas propias para calor/frío. El interruptor de zona permite ausencia indefinida y Configurar → Vacaciones permite regreso con fecha/hora local. El regreso recupera el programa o ajuste fijo previo; nunca enciende una zona individualmente apagada. Una intervención posterior tiene prioridad Manual y al vencer vuelve a Ausente si sigue vigente. En una ausencia indefinida, Manual hasta próximo bloque se transforma explícitamente en hasta retomar, sin fecha ficticia.

La acción de copia permite aplicar módulos o vacaciones a otras zonas. No copia modelos aprendidos, sensores, orientación ni relés. Activar solar en otra zona exige que sus umbrales también estén confirmados.

## Actuadores y seguridad

Los tiempos de apertura general y cierre de zona son estimados y configurables; cero significa desconocido. El software espera los estados comunicados y los tiempos configurados, y cierra durante una transición real de temporada. No se muestra confirmación física. Un relé indisponible o discrepante puede bloquear el suministro compartido si no se puede aislar su zona.

Las discrepancias repetidas no provocan competencia ilimitada: inhiben control y requieren revisión y apagado general explícito para rearmar. No se identifica un autor externo sin evidencia. Solo un controlador debe estar autorizado operativamente a escribir en cada salida. Ninguna funcionalidad opcional sustituye protecciones eléctricas, anticondensación, final de carrera ni medición de caudal.
