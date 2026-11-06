"""Shared angular sources and bounded astronomical projection; no actuator I/O."""

import math
from datetime import timedelta

from homeassistant.helpers.sun import get_astral_observer

from .core.intelligence import solar_geometry

SOURCE_KEYS = ("solar_source", "sun_entity", "sun_elevation", "sun_azimuth")


def source_signature(config):
    return [config.get("solar_source", "standard"), *source_entities(config)]


def confirmed(config, source):
    return bool(config.get("solar_confirmed", False)) and config.get(
        "solar_source_signature", ["standard", "sun.sun"]
    ) == source_signature(source)


def source_entities(config):
    match config.get("solar_source", "standard"):
        case "standard":
            return ("sun.sun",)
        case "entity":
            return (config.get("sun_entity"),)
        case "sensors":
            return (config.get("sun_elevation"), config.get("sun_azimuth"))
    return ()


def angles(hass, config, now):
    entities = source_entities(config)
    states = [hass.states.get(e) if e else None for e in entities]
    if not states or any(
        s is None
        or s.state in ("unknown", "unavailable")
        or not -60 <= (now - s.last_reported).total_seconds() <= 1800
        for s in states
    ):
        return None, None
    try:
        if config.get("solar_source") == "sensors":
            el, az = states
            if any(s.attributes.get("unit_of_measurement") not in ("°", "deg") for s in states):
                return None, None
            if abs((el.last_reported - az.last_reported).total_seconds()) > 300:
                return None, None
            azimuth, elevation = float(az.state), float(el.state)
        else:
            azimuth = float(states[0].attributes["azimuth"])
            elevation = float(states[0].attributes["elevation"])
        if (
            math.isfinite(azimuth)
            and math.isfinite(elevation)
            and 0 <= azimuth <= 360
            and -90 <= elevation <= 90
        ):
            return azimuth, elevation
    except (ValueError, TypeError, KeyError):
        pass
    return None, None


class SolarProjection:
    def __init__(self, hass):
        self.hass = hass
        self._key = None
        self._points = ()

    def positions(self, now, current):
        """One shared three-hour path per minute, consistent with HA's location."""
        if current[0] is None:
            return ()
        from astral.sun import azimuth, elevation

        observer = get_astral_observer(self.hass)
        key = (
            now.replace(second=0, microsecond=0),
            observer.latitude,
            observer.longitude,
            observer.elevation,
        )
        if key != self._key:
            self._points = tuple(
                (when, azimuth(observer, when), elevation(observer, when))
                for minute in range(0, 181, 2)
                for when in (now.replace(second=0, microsecond=0) + timedelta(minutes=minute),)
            )
            self._key = key
        # Alternative sources must describe the same sky before HA coordinates
        # may predict their future. Missing/inconsistent sources fail optional.
        _, az, el = self._points[0]
        if abs((current[0] - az + 180) % 360 - 180) > 3 or abs(current[1] - el) > 3:
            return ()
        return self._points

    def arrival(self, now, current, config):
        lead = config.get("solar_lead", 0)
        if not lead:
            return None
        return next(
            (
                when
                for when, az, el in self.positions(now, current)
                if now < when <= now + timedelta(minutes=lead)
                and solar_geometry(
                    az,
                    el,
                    config.get("orientation", 180),
                    config.get("solar_elevation", 15),
                    config.get("solar_width", 75),
                )
            ),
            None,
        )
