# Desarrollo y contribuciones

El núcleo no depende de HA; los adaptadores se prueban contra versiones concretas de Core. Los dispositivos y modelos sintéticos se mantienen en tests, sin acceso a equipos domésticos. Consulta [arquitectura](architecture.md) y [alcance de validación](testing.md).

## Entorno local

Python 3.12 o posterior para el núcleo:

```sh
python -m venv .venv
# Activa .venv según tu sistema operativo.
python -m pip install pytest==8.4.2 pytest-asyncio==1.2.0 ruff==0.14.4 tzdata==2025.2
python -m pytest tests/test_control.py tests/test_program.py tests/test_intelligence.py -q
ruff check .
ruff format --check .
python scripts/check_public_content.py
```

`tzdata` proporciona la base de zonas horarias para las pruebas de cambio de hora en sistemas que no la incluyen. No sustituye la zona horaria configurada en HA.

## Adaptación a Home Assistant

En Linux y con un Python compatible con Core (3.14 para las versiones de la matriz):

```sh
python -m pip install homeassistant==2026.10.4 pytest==8.4.2 pytest-asyncio==1.2.0
python -m pytest tests/test_homeassistant.py -q
```

Repite en un entorno separado con `homeassistant==2026.11.0` para comprobar la otra versión. CI define la matriz en [ci.yml](../.github/workflows/ci.yml) y ejecuta HACS/hassfest en [metadata.yml](../.github/workflows/metadata.yml). Una suite omitida por falta de HA no cuenta como validación.

## Traducciones y artefactos

`scripts/generate_translations.py` mantiene el vocabulario de formularios y entidades en español/inglés. Si se modifica, genera los JSON y revisa el diff antes de confirmar. No traduzcas identificadores de servicios, atributos o almacenamiento como si fueran etiquetas.

`scripts/package.py` exige una copia de trabajo limpia y confirmada. Genera un ZIP con commit, versión, documentación y checksum. Ejecutarlo no publica ni despliega nada. No crees tags/releases para cada prueba; una entrega debe identificar el código validado y conservar su recuperación.

## Cambios y privacidad

Mantén responsabilidades y cambios pequeños. Si modificas comportamiento, añade regresiones y actualiza la guía correspondiente. Una función opcional necesita degradación, diagnóstico y control real; no añadas interruptores sin efecto ni predicciones ficticias.

No publiques configuraciones domésticas, credenciales, direcciones privadas, copias de seguridad ni modelos que identifiquen una instalación. La comprobación automática de privacidad complementa la revisión manual, no la sustituye. Consulta la [licencia MIT](../LICENSE) antes de redistribuir y conserva sus avisos.
