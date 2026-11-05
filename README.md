# Radiant Climate

Integración local de Home Assistant para crear termostatos de calefacción y refrigeración a partir de sensores de temperatura y relés.

[![Verify development candidate](https://github.com/Carbanog/radiant-climate/actions/workflows/ci.yml/badge.svg)](https://github.com/Carbanog/radiant-climate/actions/workflows/ci.yml)

**Proyecto personal en desarrollo. No es una versión aprobada para producción ni un controlador certificado.** El repositorio público permite revisar el trabajo y reproducir pruebas; publicar código no acredita funcionamiento físico ni ahorro energético. No se incluyen datos de ninguna vivienda ni configuraciones de dispositivos reales.

## Objetivo

Añadir un termostato seleccionando sensor interior, relé o relés, modos disponibles y temperatura deseada. Después, habilitar únicamente las funciones avanzadas necesarias desde la interfaz. Sin numerosos ayudantes externos, sin depender de Dual Smart Thermostat ni Versatile Thermostat.

La primera base implementada es deliberadamente pequeña. La tabla siguiente distingue el código operativo, las pruebas y lo que todavía falta. No se ofrecen interruptores de módulos vacíos para aparentar que existen.

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
| Perfiles editables y programación propia | Normal/Eco/Noche por temporada, agenda semanal por zona y controles propios; CI valida el adaptador |
| Meteorología seleccionable, solar y compensación exterior | Pendientes; no hay controles sin efecto |
| Aprendizaje en observación, anticipación y parada predictiva | Pendientes |
| Copiar temperaturas, política Manual y agenda a otras zonas/todas | Implementado mediante acción nativa con selectores |
| Vacaciones | Pendientes |
| Precisión térmica, comportamiento físico e instalación real | No validados |

Consulta [arquitectura y prioridades](docs/architecture.md), [uso y configuración](docs/configuration.md), [validación](docs/testing.md) y [plan de desarrollo](docs/roadmap.md).

## Compatibilidad y alcance

- Objetivo inicial: **Home Assistant Core 2026.10.4**. Su entorno requiere Python **3.14.2 o posterior**. El núcleo aislado también se prueba con Python 3.12.
- Dispositivos expuestos como entidades `sensor` de temperatura, `switch` de actuador y opcionalmente `binary_sensor` de ventana.
- El control es local. No se piden credenciales, no se añade telemetría y no se llama a servicios externos desde esta base.
- La temporada de suministro se declara con un selector. No mide la temperatura del agua ni controla producción, bomba, caldera o enfriadora.
- No se usan persianas como dependencias ni como actuadores.
- No hay protección anticondensación implementada. Un suelo refrescante necesita sus protecciones físicas y de instalación adecuadas. El software no debe sustituirlas.

## Instalación de desarrollo

No se ha publicado una release. Los ZIP de CI son **artefactos temporales del commit**, no versiones aprobadas para instalar en una vivienda.

1. Utiliza una instancia de pruebas aislada y salidas simuladas o desconectadas de equipos reales. Conserva copia recuperable de su configuración.
2. Abre [Actions](https://github.com/Carbanog/radiant-climate/actions), selecciona una ejecución correcta y descarga el artefacto identificado por su SHA. Comprueba `BUILD.json` y el SHA-256 cuando se facilite.
3. Copia únicamente `custom_components/radiant_climate` dentro de `custom_components` de esa instancia. No copies pruebas, scripts de desarrollo ni documentos como configuración HA.
4. Reinicia HA y entra en **Ajustes → Dispositivos y servicios → Añadir integración → Radiant Climate**.
5. Crea primero la instalación, seleccionando la general solo si existe. El interruptor general empieza apagado.
6. Añade otra entrada de Radiant Climate para cada termostato: sensor, relés, modos disponibles y consigna inicial. Cada zona comienza apagada.
7. Revisa las opciones de regulación, la temporada declarada y las salidas antes de habilitar el interruptor general y encender una zona de prueba.

No se modifica `configuration.yaml` ni se crean automatizaciones para utilizar la base. Todavía no se ha validado la instalación a través de HACS; `hacs.json` y la estructura se preparan para ese canal. El repositorio público puede añadirse como repositorio personalizado cuando se verifique ese procedimiento. No se afirma inclusión en el catálogo HACS.

## Uso de la base actual

- **Apagado individual:** la zona deja de demandar. Horarios pendientes de implementar no podrán reactivarla.
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
python -m pytest tests/test_control.py tests/test_program.py -q
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
