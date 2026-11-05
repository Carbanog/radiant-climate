"""Integration identifiers and supported platforms."""

from homeassistant.const import Platform

DOMAIN = "radiant_climate"
PLATFORMS = [
    Platform.CLIMATE,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
]
STORAGE_VERSION = 1
VERSION = "0.2.2"
