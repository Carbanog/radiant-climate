# Diagnóstico hidráulico opcional

Este módulo observa las temperaturas generales de impulsión y retorno. No cambia
consignas, perfiles, horarios, aprendizaje, prioridades ni órdenes a válvulas.
Los termostatos funcionan sin él y continúan regulando si sus sondas fallan.
No necesita ayudantes, automatizaciones externas ni dependencias adicionales.

## Configuración

En **Ajustes → Dispositivos y servicios → Radiant Climate**, abre **Configurar**
en la instalación general y selecciona **Diagnóstico hidráulico**.

1. Selecciona dos sensores existentes y distintos: impulsión y retorno generales.
   Se admiten °C, °F y K; se muestran valores convertidos a °C. El intervalo
   admisible de agua es 0–90 °C. Comprueba ubicación, montaje y unidades.
2. Activa el diagnóstico. No activa la climatización ni ninguna zona.
3. Ajusta la antigüedad máxima al ritmo real de informes de las sondas: por defecto
   900 segundos, configurable entre 60 y 3600. Una lectura caducada no sirve como
   evidencia. `last_reported` indica recepción de datos, no garantiza que el
   dispositivo haya realizado una medición nueva.
4. Conserva inicialmente 30 minutos de estabilización y otros 30 minutos de
   desviación continua. Son ventanas de observación, no tiempos de calentamiento
   de la vivienda ni parámetros del control. Se respeta también el mayor tiempo
   estimado configurado de maniobra; ello no confirma apertura física.
5. Deja vacías las referencias de impulsión salvo que dispongas de valores
   adecuados de vuestro proyecto o mantenedor. La mínima de calor y máxima de
   frío son independientes, opcionales y se introducen en °C.

Las referencias son **límites fijos de observación** para las condiciones en que
son válidos. No hay una curva climática universal ni se calcula aquí una tabla
de impulsión según temperatura exterior. Si la comunidad trabaja con una curva
variable, deja la referencia vacía hasta disponer de una comparación válida.
Este módulo no usa ni depende de meteo o temperatura exterior; puedes contrastar
sus históricos con el sensor exterior existente.

Para activarlo o desactivarlo desde el panel, añade el interruptor nativo
**Usar diagnóstico hidráulico**. También puedes desmarcar **Activar diagnóstico**
en Opciones. Se conservan sus fuentes y parámetros. Vaciar un selector o una referencia elimina esa asignación o umbral,
sin valores ocultos duplicados. Los datos y temperaturas originales siguen en
sus sensores habituales.

## Entidad y estados

Al configurar el módulo se añaden **un sensor de diagnóstico y un interruptor**
a la instalación. Si no lo configuras, no se crean estas entidades. Los atributos
del sensor contienen impulsión,
retorno, ΔT firmado = impulsión − retorno, temporada declarada, referencia y
número de zonas con demanda. Los sensores originales permiten consultar los
históricos numéricos sin duplicarlos. El diagnóstico enumera estas situaciones:

| Estado | Interpretación |
|---|---|
| Desactivado | No se evalúan avisos. |
| Lecturas ausentes, caducadas o inválidas | No hay evidencia suficiente; se descarta el tiempo acumulado. |
| Sin demanda activa | No se interpreta agua posiblemente estancada como falta de suministro. |
| Esperando estados comunicados de relés | Falta algún On comunicado o hay averías/retiradas pendientes. No confirma posiciones ni caudal. |
| Esperando estabilización | Han empezado o cambiado las condiciones observadas. |
| Observación | No se detecta una desviación sostenida de las comprobaciones configuradas; no certifica suficiencia. |
| Desviación en observación | Todavía no ha transcurrido el tiempo continuo requerido. |
| Impulsión inferior/superior a referencia | Se mantiene demanda con los relés comunicados On y un umbral configurado incumplido durante el periodo requerido. |
| Diferencia inesperada | Tras estabilizar, ΔT < −1 °C en calor o > +1 °C en frío se mantiene durante el periodo requerido. Revisar sondas, montaje, temporada y suministro; no implica por sí solo avería. |

El margen de 1 °C evita interpretar pequeñas diferencias invertidas como un
aviso; no constituye una especificación de rendimiento ni una tolerancia
certificada de las sondas. Una recuperación elimina el aviso y una nueva
desviación debe acumular de nuevo el tiempo completo. No se envían notificaciones
automáticas ni se reconocen averías del control desde este módulo.

## Reinicios y cambios

La configuración persiste con las opciones de Home Assistant. El tiempo de
observación no persiste: después de reiniciar se exige evidencia nueva. Cambiar
fuentes, umbrales, temporada, salidas o conjunto de zonas demandantes reinicia
la observación; perder lecturas o estados comunicados también. Un hueco de
ejecución superior a un minuto invalida el tiempo continuo acumulado.

Guardar únicamente opciones hidráulicas no recarga termostatos, retira relés,
invalida planes de apertura ni ejecuta una regulación. El observador recibe
notificaciones fuera de la transacción de control y libera sus escuchas al
descargar la entidad. Los eventos de agua no se añaden al conjunto de entradas
de regulación.

## Qué permite concluir

Un retorno global es la mezcla de los circuitos: el número de zonas, los caudales
y la carga térmica influyen en él. Sin medir caudal no se calculan W, kWh,
eficiencia ni reparto por habitación. ΔT pequeño o grande no demuestra por sí
solo buen o mal funcionamiento. Los contactos externos requieren montaje
comparable y buen acoplamiento/aislamiento para obtener diferencias útiles.

El sensor puede aportar evidencia para investigar un termostato que no alcanza
su objetivo: consulta simultáneamente su **Motivo de regulación**, consigna,
temperatura interior y el histórico de agua. No atribuye automáticamente el
problema al termostato o a la comunidad. No sustituye protecciones de temperatura
del suelo, anticondensación, medición de caudal ni inspección física.

Referencia técnica: [Caleffi: mediciones de rendimiento de circuitos](https://www.caleffi.com/en-us/blog/3-site-measurements-circuit-performance),
que distingue temperatura diferencial, caudal y estabilización. Los intervalos y
umbrales de este módulo son decisiones conservadoras de observación del proyecto,
no límites reglamentarios ni valores universales prescritos por ese documento.
