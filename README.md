# Radiant Climate

Integración local de Home Assistant para crear termostatos de calefacción y refrigeración a partir de sensores de temperatura y relés.

[![Verify development candidate](https://github.com/Carbanog/radiant-climate/actions/workflows/ci.yml/badge.svg)](https://github.com/Carbanog/radiant-climate/actions/workflows/ci.yml)

**Proyecto personal en desarrollo. No es una versión aprobada para producción ni un controlador certificado.** El repositorio público permite revisar el trabajo y reproducir pruebas; publicar código no acredita funcionamiento físico ni ahorro energético. No se incluyen datos de ninguna vivienda ni configuraciones de dispositivos reales.

## Objetivo

Añadir un termostato seleccionando sensor interior, relé o relés, modos disponibles y temperatura deseada. Después, habilitar únicamente las funciones avanzadas necesarias desde la interfaz. Sin numerosos ayudantes externos, sin depender de Dual Smart Thermostat ni Versatile Thermostat.

La candidata incluye regulación, programación y módulos opcionales. La tabla distingue las funciones de software de la calibración y validación físicas. Los módulos avanzados empiezan desactivados y no incluyen modelos preentrenados.

## Estado de las funciones

| Función | Estado de esta candidata |
|---|---|
| Alta de instalación y zonas mediante formularios nativos | Implementada y probada en Core 2026.10.4 |
| Termostato fijo con calor, frío y apagado | Implementado con histéresis y tiempos mínimos |
| Interruptor general con intención individual conservada | Implementado |
| Fuente exterior o meteorología obligatorias | No: el control básico no depende de ellas |
| Válvula de entrada compartida opcional | Coordinación por estado comunicado del relé; no confirma apertura física |
| Sensor interior inválido/caducado y ventana configurada | Detienen la zona; aislamiento no confirmado puede bloquear el suministro compartido |
| Consignas por calor/frío y restauración de intención | Implementadas; pruebas de almacenamiento en Core en CI |
| Relé asignado dos veces o como general y zona | Rechazado al configurar |
| Diagnóstico del motivo de actuación y opciones en español/inglés | Implementados |
| Tres políticas Manual | Conectadas a programación y controles nativos; CI valida el adaptador |
| Perfiles editables y programación propia | Normal/Eco/Noche/Ausente por temporada y agenda semanal por zona |
| Meteorología seleccionable, exterior y solar por zona | Implementados en la candidata; validación ampliada en CI |
| Observación, anticipación y pausa por inercia | Implementados con calidad mínima y límites; necesitan datos reales y piloto |
| Aplicar ajustes a otras zonas/todas | Temperaturas, política Manual, agenda, activación de módulos y vacaciones |
| Ausente/vacaciones | Perfil por temporada, ausencia indefinida o regreso programado |
| Precisión térmica, comportamiento físico e instalación real | No validados |

Consulta [arquitectura y prioridades](docs/architecture.md), [uso y configuración](docs/configuration.md), [validación](docs/testing.md) y [plan de desarrollo](docs/roadmap.md).

Los [módulos avanzados y sus límites](docs/intelligence.md) distinguen la implementación del ajuste físico. No hay un modelo preentrenado de una vivienda ni promesa de ahorro o precisión comercial.

## Compatibilidad y alcance

- Matriz de compatibilidad: **Home Assistant Core 2026.10.4 y 2026.11.0**, Python 3.14. El núcleo aislado también se prueba con Python 3.12. Consulta el resultado del commit que vayas a utilizar.
- Dispositivos expuestos como entidades `sensor` de temperatura, `switch` de actuador y opcionalmente `binary_sensor` de ventana.
- El control básico es local y no pide credenciales ni añade telemetría. La previsión utiliza la integración meteorológica elegida en HA, que puede depender de un proveedor externo.
- La temporada de suministro se declara con un selector. No mide la temperatura del agua ni controla producción, bomba, caldera o enfriadora.
- No se usan persianas como dependencias ni como actuadores.
- No hay protección anticondensación implementada. Un suelo refrescante necesita sus protecciones físicas y de instalación adecuadas. El software no debe sustituirlas.

## Instalación de desarrollo

La primera entrega es **v0.2.0-beta.1**, para ensayo voluntario y calibración. Utiliza [Releases](https://github.com/Carbanog/radiant-climate/releases) para elegir una versión identificable. Los ZIP de CI son artefactos temporales y no acreditan aprobación doméstica.

1. Utiliza una instancia de pruebas aislada y salidas simuladas o desconectadas de equipos reales. Conserva copia recuperable de su configuración.
2. Abre [Actions](https://github.com/Carbanog/radiant-climate/actions), selecciona una ejecución correcta y descarga el artefacto identificado por su SHA. Comprueba `BUILD.json` y el SHA-256 cuando se facilite.
3. Copia únicamente `custom_components/radiant_climate` dentro de `custom_components` de esa instancia. No copies pruebas, scripts de desarrollo ni documentos como configuración HA.
4. Reinicia HA y entra en **Ajustes → Dispositivos y servicios → Añadir integración → Radiant Climate**.
5. Crea primero la instalación, seleccionando la general solo si existe. El interruptor general empieza apagado.
6. Añade otra entrada de Radiant Climate para cada termostato: sensor, relés, modos disponibles y consigna inicial. Cada zona comienza apagada.
7. Revisa las opciones de regulación, la temporada declarada y las salidas antes de habilitar el interruptor general y encender una zona de prueba.

No se modifica `configuration.yaml` ni se crean automatizaciones externas. HACS y hassfest comprueban estructura y metadatos. Añade el repositorio a HACS como Integración y selecciona expresamente la beta identificada; activa la visualización de versiones beta si hace falta. Conserva copia y versión para revertir. No se afirma inclusión en el catálogo ni aprobación para una vivienda. [Instalación y reversión](docs/installation.md).

## Uso de la base actual

- **Apagado individual:** la zona deja de demandar. Horarios, vacaciones y optimizaciones no la reactivan.
- **Climatización general apagada:** cierra las salidas por orden software y conserva qué zonas estaban encendidas. Cambiar una consigna no vence el bloqueo.
- **Reactivar la general:** reconcilia estados y sensores; una zona individualmente apagada sigue apagada.
- **Calor/frío:** la consigna se guarda por modo. Un modo incompatible con la temporada de suministro declarada no produce demanda.
- **Motivo de regulación:** el sensor de diagnóstico explica bloqueo general, apagado, falta de datos, ventana, tiempo mínimo, demanda o consigna satisfecha.

El estado `on` de un relé no prueba apertura, circulación o disponibilidad de energía. El coordinador espera el estado comunicado de la general antes de permitir aperturas de zona, pero aún no incorpora un modelo de tiempos físicos de válvulas. No se debe inferir consumo térmico de la potencia eléctrica de un actuador.

## Ajustes iniciales

| Ajuste | Valor inicial | Alcance |
|---|---:|---|
| Histéresis | 0,2 °C | Punto de partida, no calibración de una instalación |
| Tiempo mínimo activo | 180 s | La seguridad y Apagado pueden interrumpirlo |
| Tiempo mínimo inactivo | 180 s | Evita ciclos rápidos; revisar actuadores reales |
| Caducidad interior | 3600 s | Basada en `last_reported` de HA; no certifica comunicación física del sensor |

Un sensor que solo cambia de valor ocasionalmente o un sensor derivado puede necesitar una política de caducidad diferente. Las propiedades del dispositivo y su cadencia se revisan antes de producción. Los tiempos acelerados de las pruebas no son valores domésticos.

## Desarrollo y pruebas

```sh
python -m venv .venv
# Activa el entorno según tu sistema operativo.
python -m pip install pytest==8.4.2 pytest-asyncio==1.2.0 ruff==0.14.4 tzdata==2025.2
python -m pytest tests/test_control.py tests/test_program.py tests/test_intelligence.py -q
ruff check .
ruff format --check .
python scripts/check_public_content.py
```

La suite `tests/test_homeassistant.py` utiliza Core real con sensores y relés **simulados**. En un entorno Linux compatible:

```sh
python -m pip install homeassistant==2026.10.4 pytest==8.4.2 pytest-asyncio==1.2.0
python -m pytest tests/test_homeassistant.py -q
```

CI ejecuta ambas suites separadas. Una suite omitida por falta de HA local no cuenta como una prueba de compatibilidad. No se contacta con dispositivos domésticos en CI.

## Actualización y reversión

Conserva el commit/ZIP anterior y una copia recuperable de HA. Desactiva el interruptor general y comprueba las órdenes de apagado antes de reemplazar archivos. Reinicia y revisa compatibilidad, estados y diagnósticos antes de reactivar.

Para volver a un controlador anterior, detén y deshabilita primero las entradas de Radiant Climate y después rehabilita el anterior. Nunca mantengas dos controladores sobre las mismas salidas. No borres la configuración previa hasta aceptar el cambio.

La integración usa almacenamiento de HA versionado; no edites `.storage` en caliente. Aún no existe una política de migración entre releases porque no hay una primera release publicada.

## Privacidad y contribuciones

Los ejemplos son genéricos y las pruebas identifican sus fixtures. No subas exportaciones de HA, copias de seguridad, direcciones privadas, nombres de personas, ubicaciones, contraseñas o tokens. El comprobador automático ayuda, pero no sustituye la revisión del diff. Los diagnósticos omiten nombres, entidades fuente e identificadores; revisa también las temperaturas y estados antes de compartirlos.

El código de esta base es original. Las referencias comerciales de diseño no implican copiar sus algoritmos ni incorporar código de otras integraciones. Licencia [MIT](LICENSE).

Si te resulta útil, puedes [apoyar voluntariamente el proyecto](https://buymeacoffee.com/Carbanog). El apoyo no concede funciones ni ventajas.
