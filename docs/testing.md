# Validación

## Capas

- `tests/test_control.py`: lógica pura con temperaturas y tiempos sintéticos. No importa HA ni toca dispositivos.
- `tests/test_homeassistant.py`: instancia real de Core y servicios nativos con sensores ficticios y switches de plantilla respaldados por booleanos de prueba. Los tiempos mínimos se aceleran explícitamente a cero solo en esta fixture.
- Ensayo físico: todavía no realizado. CI no valida tensión, corriente, apertura de válvula, caudal, disponibilidad de suministro ni respuesta térmica de un edificio.

CI utiliza Python 3.12 para el núcleo y Python 3.14 con Core 2026.10.4 para adaptación. Deben pasar los dos trabajos. El soporte de otra versión de HA no se deduce de que importe el código.

## Casos del núcleo

Calor/frío; histéresis; mínimos de maniobra; prioridad de Apagado y fallos; sensor inválido/caducado; conservación de consigna fija; tres políticas Manual; renovación al repetir consigna; ausencia de próximo cambio; cambio de temporada; almacenamiento y rechazo de estados inválidos.

## Casos del adaptador

Alta por formulario; creación apagada sin exterior ni meteo; habilitación general; Apagado individual persistente; pérdida de un sensor y continuidad de otra zona aislable; rechazo de salida duplicada; persistencia mediante Store de HA; refrigeración y compatibilidad con temporada declarada.

## Lo que no acreditan estas pruebas

No validan todas las prestaciones de la especificación futura. Las retenciones todavía no se ofrecen al usuario porque no existe agenda operativa. Falta probar el adaptador con fallos prolongados de comunicación, detención durante servicios pendientes, ventanas con retardos, conflictos externos, migraciones de almacenamiento y ensayo de dispositivos reales. El código debe permanecer en desarrollo hasta ampliar estas pruebas.

## Artefactos

El ZIP de CI identifica el commit en su nombre y en BUILD.json; solo empaqueta código, licencia y README. No es una release ni activa servicios. La creación de etiquetas o releases requiere una aprobación de instalación/publicación independiente.
