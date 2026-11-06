"""Optional HA environmental sources; bounded forecast I/O outside actuator locks."""

import asyncio
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.weather import WeatherEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .core.control import temperature
from .core.intelligence import solar_weather


def fresh(state, now, maximum=3600):
    return (
        state is not None
        and state.state not in ("unknown", "unavailable")
        and -60 <= (now - state.last_reported).total_seconds() <= maximum
    )


def celsius(value, unit):
    if isinstance(value, bool):
        return None
    if unit not in ("°C", "°F", "K"):
        return None
    try:
        return temperature(TemperatureConverter.convert(float(value), unit, "°C"), -60, 70)
    except (ValueError, TypeError):
        return None


@dataclass
class Forecast:
    fetched: datetime
    points: list


class Environment:
    def __init__(self, hass):
        self.hass = hass
        self.forecasts: dict[str, Forecast] = {}
        self.status: dict[str, str] = {}
        self.attempted: dict[str, datetime] = {}

    def weather_temperature(self, entity, now):
        state = self.hass.states.get(entity) if entity else None
        return (
            celsius(state.attributes.get("temperature"), state.attributes.get("temperature_unit"))
            if fresh(state, now)
            else None
        )

    def availability(self, entity, now):
        state = self.hass.states.get(entity) if entity else None
        return self.status.get(entity, "not_requested") if fresh(state, now) else "unavailable"

    def outdoor(self, entity, now):
        state = self.hass.states.get(entity) if entity else None
        return (
            celsius(state.state, state.attributes.get("unit_of_measurement"))
            if fresh(state, now)
            else None
        )

    def weather(self, entity, now):
        state = self.hass.states.get(entity) if entity else None
        if not fresh(state, now):
            return None, None
        try:
            clouds = float(state.attributes["cloud_coverage"])
        except (ValueError, TypeError, KeyError):
            clouds = None
        return state.state, clouds

    def future(self, entity, when, now):
        cached = self.forecasts.get(entity)
        state = self.hass.states.get(entity) if entity else None
        if (
            not fresh(state, now)
            or cached is None
            or not 0 <= (now - cached.fetched).total_seconds() <= 1800
        ):
            return None
        candidates = [
            (abs((t - when).total_seconds()), point) for t, point in cached.points if t >= now
        ]
        if not candidates:
            return None
        distance, point = min(candidates, key=lambda item: item[0])
        return point if distance <= 3600 else None

    @property
    def sun(self):
        state = self.hass.states.get("sun.sun")
        if not fresh(state, dt_util.utcnow(), 900):
            return None, None
        try:
            az, el = float(state.attributes["azimuth"]), float(state.attributes["elevation"])
            if not 0 <= az <= 360 or not -90 <= el <= 90:
                return None, None
            return az, el
        except (ValueError, TypeError, KeyError):
            return None, None

    def opportunity(self, weather_entity, now):
        _, elevation = self.sun
        if elevation is None:
            return None
        condition, clouds = self.weather(weather_entity, now)
        return elevation > 0 and solar_weather(condition, clouds) is not False

    async def refresh(self, entities):
        now = dt_util.utcnow()
        for entity in set(filter(None, entities)):
            if entity in self.attempted and (now - self.attempted[entity]).total_seconds() < 900:
                continue
            self.attempted[entity] = now
            state = self.hass.states.get(entity)
            if not fresh(state, now):
                self.forecasts.pop(entity, None)
                self.status[entity] = "unavailable"
                continue
            # Unsupported providers must not prevent base thermostat regulation.
            if not (
                state.attributes.get("supported_features", 0) & WeatherEntityFeature.FORECAST_HOURLY
            ) or not self.hass.services.has_service("weather", "get_forecasts"):
                self.forecasts.pop(entity, None)
                self.status[entity] = "hourly_not_supported"
                continue
            try:
                async with asyncio.timeout(5):
                    response = await self.hass.services.async_call(
                        "weather",
                        "get_forecasts",
                        {"entity_id": entity, "type": "hourly"},
                        blocking=True,
                        return_response=True,
                    )
                rows = response[entity]["forecast"]
                if not isinstance(rows, list):
                    raise ValueError("Invalid forecast response")
                points = []
                for row in rows[:72]:
                    if not isinstance(row, dict):
                        continue
                    when = dt_util.parse_datetime(row.get("datetime", ""))
                    if when is None or when.tzinfo is None:
                        continue
                    item = dict(row)
                    item["temperature"] = celsius(
                        row.get("temperature"), state.attributes.get("temperature_unit")
                    )
                    points.append((dt_util.as_utc(when), item))
                self.forecasts[entity] = Forecast(now, points)
                self.status[entity] = "available" if points else "forecast_empty"
            except (HomeAssistantError, TimeoutError, ValueError, KeyError, TypeError):
                self.forecasts.pop(entity, None)
                self.status[entity] = "forecast_unavailable"
