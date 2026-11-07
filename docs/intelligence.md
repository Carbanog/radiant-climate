# Módulos opcionales y límites

La consigna de confort pertenece al usuario o al programa. Las optimizaciones no la rebajan para aparentar ahorro. La tarjeta muestra la consigna vigente; `control_target` identifica por separado un objetivo anticipado. Manual, Apagado, sensores críticos, ventanas habilitadas y compatibilidad de suministro tienen prioridad. Todo módulo empieza desactivado.

## Fuentes y fallos

En Configurar la instalación se pueden elegir exterior y entidad `weather` compartidos; cada zona puede sustituirlos en Entorno, sol y anticipación. Vacío hereda la fuente común. Los interruptores de previsión y exterior son independientes. No hacen falta ayudantes ni credenciales en esta integración.

La previsión se obtiene mediante la acción oficial `weather.get_forecasts`, tipo horario, como máximo una vez cada quince minutos por fuente y con un plazo de cinco segundos. La petición se realiza fuera del bloqueo de actuadores. Proveedores sin previsión horaria, errores, respuesta vacía, datos caducados o fuente indisponible no se sustituyen por valores inventados. La caché caduca a los treinta minutos. Se utilizan puntos futuros cercanos al bloque que se anticipa.

El exterior puede corregir conservadoramente el adelanto según las condiciones con las que se observó el modelo; la previsión puede aportar la temperatura esperada a la hora de llegada. Sin esos datos se utiliza el modelo interior, y sin modelo se utiliza la agenda normal. No es una curva de agua: no se gobiernan temperaturas de impulsión ni producción.

Fuentes: [acciones meteorológicas de HA](https://www.home-assistant.io/integrations/weather/), [contrato de entidades meteorológicas](https://developers.home-assistant.io/docs/core/entity/weather/). El adaptador se prueba con Core 2026.10.4.

## Solar

Una entidad binaria de instalación muestra la oportunidad compartida a partir de la posición solar y las condiciones actuales cuando se habilita la meteorología. Sin meteo utiliza solo la posición solar e indica esa base; no demuestra sol directo.

Cada zona tiene azimut de ventanas, elevación mínima observada y amplitud angular. La elevación se refiere al horizonte astronómico calculado para la ubicación, sin incluir edificios ni terrazas; pero la incidencia depende también del azimut y los obstáculos. No se usan persianas. Una zona sin ganancias directas puede mantener Solar desactivado.

El selector permite Desactivado, Observación y Optimizar. Observación muestra candidatos sin modificar salidas. Optimizar exige confirmar previamente los umbrales de incidencia y sombra. La regla inicial solo pausa calefacción cerca del objetivo (hasta 0,3 °C por debajo), con tendencia interior ascendente que proyecta alcanzar la consigna. Si falla la meteo, sigue exigiendo geometría y tendencia interior. Manual impide esa pausa. No se invierte esta regla para refrigeración, no se atribuye al sol toda subida y no se promete conocer sombras no medidas.

Desde v0.2.6 existe además un **adelanto antes de entrar el sol**, opcional por zona y
con 0 minutos inicialmente. Proyecta la posición astronómica en la ubicación de HA con
Astral, compartiendo una trayectoria de tres horas y resolución de dos minutos. Solo
utiliza esa proyección si la fuente actual coincide dentro de 3° en elevación y azimut.
La primera entrada en los límites configurados estima el comienzo; no mide sombras reales.
No es un aprendizaje de la geometría ni una predicción causal de ganancias solares.

Antes de la incidencia se exige previsión horaria vigente y explícitamente favorable
(cobertura de nubes válida de hasta 50 % o condición sunny), una tendencia interior
calculable entre −0,1 y 3 °C/h, temperatura como máximo 0,2 °C bajo consigna y una
proyección conservadora hasta la llegada que no baje más de 0,3 °C bajo ella. Solo actúa
en calor, con Solar Optimizar, exposición confirmada y fuera de Manual. Respeta mínimos
de maniobra, ventanas, Off, fallos y suministro. No cambia la consigna. En Observación
muestra `solar_arrival` y `solar_lead_candidate`, sin modificar relés. No actúa sin
previsión ni con una fuente solar ausente/inconsistente. Se reevalúa normalmente; no
mantiene un corte fijo si empeoran las condiciones. Una previsión favorable puede fallar:
calibra el adelanto con observación real antes de confiar en él para evitar sobrecalentamiento.

## Observación y anticipación

Aprender respuesta térmica recopila periodos válidos por zona, temporada y estado comunicado de actuación. Excluye paradas, ventanas, fallos y periodos de incidencia solar candidata; no cose muestras a través de reinicios. Solo procesa nuevos informes, limita memoria y rechaza saltos incompatibles. Las estadísticas se guardan periódicamente y al parar ordenadamente.

### Lecturas irregulares — desarrollo posterior a v0.2.7

Esta mejora está en `main`, todavía no en una release nueva. v0.2.7 mantiene el
límite anterior de veinte minutos entre informes para el aprendizaje.

La respuesta térmica lenta admite ventanas de 30 a 90 minutos construidas solo
con informes reales. Cada separación entre informes debe ser como máximo el menor
de 90 minutos y la caducidad interior configurada. El límite de 90 minutos es una
cota conservadora de este algoritmo, no una cadencia recomendada para sensores ni
un parámetro aprendido. No se rellena el hueco con copias del último valor. Más de
90 minutos, una discontinuidad conocida o una velocidad incompatible descartan la
continuidad; una temperatura nueva permite iniciar otro periodo.

Se interrumpe el entrenamiento al cambiar los relés de zona/general y ante ventanas
habilitadas o datos interiores inválidos, incluso si varios eventos llegan antes
de la siguiente reconciliación. Una lectura anterior a la interrupción no sirve
como inicio de otro periodo. Los estados parciales de una zona multicanal y una
general indisponible o aún en apertura estimada no entrenan respuesta activa.
Esto comprueba estados comunicados y eventos observados por HA, nunca posiciones,
caudal ni sucesos físicos que los dispositivos no hayan comunicado.

La tendencia reciente mantiene su requisito de al menos tres puntos, un tramo de
quince minutos y separaciones no mayores de veinte minutos. Lecturas cada 45 minutos
pueden permitir aprender y anticipar horarios, pero no justifican por sí solas una
pausa solar o por inercia inmediata. Sin tendencia reciente, esas pausas no actúan.

La caducidad de seguridad y el modelo siguen separados: la mejora no aumenta el
margen interior ni utiliza batería, disponibilidad o `last_seen` para renovar una
temperatura. Se usa el `last_reported` registrado por HA, que tampoco garantiza
por sí solo una medición física nueva si la integración de origen republica datos.

El almacenamiento de estadísticas mantiene su formato; los modelos existentes no
se borran y los límites de periodo no se conservan a través de reinicios. Los nuevos
atributos de diagnóstico son `model_intervals`, `model_rate_c_per_hour` y
`learning_max_gap_minutes`; se suman a horas, episodios, rechazos y disponibilidad.

Se requieren al menos doce intervalos, seis horas y tres episodios, respuesta entre 0,05 y 3 °C/h y dispersión acotada para declarar un modelo utilizable. Son umbrales de calidad del algoritmo inicial, no garantía de aprendizaje en un número de días. La resolución, cadencia y condiciones de la instalación pueden impedir alcanzar esa calidad. Se muestran horas, episodios, tendencia, rechazos y disponibilidad. Restablecer aprendizaje elimina las estadísticas propias de esa zona y obliga a volver a observar.

Anticipar horario calcula el tiempo para alcanzar un perfil próximo más exigente con el ritmo observado y un límite de adelanto configurable. No actúa sin agenda o modelo válido, durante Manual o Ausente, ni vence Apagado. No aprende preferencias de las modificaciones manuales. El adelanto y el objetivo de regulación se muestran separados del bloque actual.

Aprovechar inercia usa modelo válido y tendencia observada para pausar cerca del objetivo cuando se proyecta aporte residual. Tiene horizonte configurable y el mismo margen conservador; respeta los mínimos y funciona por separado en calor/frío. No mide energía acumulada en la losa. Sin tendencia/modelo, vuelve a regulación normal. Estas heurísticas necesitan piloto y evaluación de confort; no son un modelo físico certificado ni ahorro demostrado.

## Ausente y vacaciones

El perfil Ausente tiene temperaturas propias para calor/frío. El interruptor de zona permite ausencia indefinida y Configurar → Vacaciones permite regreso con fecha/hora local. El regreso recupera el programa o ajuste fijo previo; nunca enciende una zona individualmente apagada. Una intervención posterior tiene prioridad Manual y al vencer vuelve a Ausente si sigue vigente. En una ausencia indefinida, Manual hasta próximo bloque se transforma explícitamente en hasta retomar, sin fecha ficticia.

La acción de copia permite aplicar módulos o vacaciones a otras zonas. No copia modelos aprendidos, sensores, orientación ni relés. Activar solar en otra zona exige que sus umbrales también estén confirmados.

## Actuadores y seguridad

Los tiempos de apertura general y cierre de zona son estimados y configurables; cero significa desconocido. El software espera los estados comunicados y los tiempos configurados, y cierra durante una transición real de temporada. No se muestra confirmación física. Un relé indisponible o discrepante puede bloquear el suministro compartido si no se puede aislar su zona.

Las discrepancias repetidas no provocan competencia ilimitada: inhiben control y desde v0.2.2 requieren revisión y reconocimiento explícito con Climatización apagada para rearmar. El apagado cotidiano no borra averías. No se identifica un autor externo sin evidencia. Solo un controlador debe estar autorizado operativamente a escribir en cada salida. Ninguna funcionalidad opcional sustituye protecciones eléctricas, anticondensación, final de carrera ni medición de caudal.
