"""Read and write the existing Home Assistant storage envelope with checked writes."""

import asyncio
from pathlib import Path

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.json import save_json
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util.json import load_json

from .const import DOMAIN, STORAGE_VERSION


class InstallationStorage:
    def __init__(self, hass):
        self.hass = hass
        self.key = f"{DOMAIN}.state"
        self.path = Path(hass.config.path(STORAGE_DIR, self.key))

    async def async_load(self):
        return await self.hass.async_add_executor_job(self._read)

    def _read(self):
        envelope = load_json(self.path, None)
        if envelope is None and not self.path.exists():
            return None
        if (
            not isinstance(envelope, dict)
            or envelope.get("key") != self.key
            or envelope.get("version") != STORAGE_VERSION
            or envelope.get("minor_version", 1) != 1
            or not isinstance(envelope.get("data"), dict)
        ):
            raise HomeAssistantError("Invalid or unsupported Radiant Climate storage envelope")
        return envelope["data"]

    async def async_save(self, data):
        write = self.hass.async_add_executor_job(self._write, data)
        try:
            await asyncio.shield(write)
        except asyncio.CancelledError:
            # The executor still owns the file. Let it finish before a
            # compensating write is allowed to replace the same snapshot.
            await write
            raise

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        save_json(
            str(self.path),
            {"key": self.key, "version": STORAGE_VERSION, "minor_version": 1, "data": data},
            private=True,
            atomic_writes=True,
        )
