"""Optional zone policy, isolated from hardware writes and weather requests."""

from dataclasses import asdict, dataclass, field
from datetime import timedelta

from .core.control import Decision, Mode, decide
from .core.intelligence import (
    MAX_LEARNING_INTERVAL,
    Features,
    ThermalModel,
    before_sun_pause,
    lead_minutes,
    should_pause,
    solar_geometry,
    solar_weather,
)
from .solar import confirmed


@dataclass
class Intelligence:
    features: Features = field(default_factory=Features)
    model: ThermalModel = field(default_factory=ThermalModel)
    diagnostics: dict = field(default_factory=dict)

    def dump(self):
        return {"features": asdict(self.features), "model": self.model.dump()}

    @classmethod
    def restore(cls, raw):
        return cls(
            Features.restore(raw.get("features", {})), ThermalModel.restore(raw.get("model", {}))
        )

    def evaluate(self, z, manager, now, sensor, measured, on, opened, enabled, available):
        def regulation(target):
            return decide(
                z.settings,
                z.intent,
                now,
                measured=measured,
                measured_at=sensor.last_reported if sensor else None,
                actual_on=on,
                switched_at=z.switched_at,
                enabled=enabled,
                supply_mode=manager.supply_mode,
                window_open=opened,
                actuator_available=available,
                scheduled_target=target,
            )

        timezone = manager.hass.config.time_zone
        target = z.program.scheduled_target(z.intent, now, timezone)
        base = regulation(target)
        allowed = base.reason in ("demand", "satisfied", "minimum_cycle")
        f = self.features
        mode = z.intent.mode
        config = z.config
        environment = manager.environment
        exposure_confirmed = confirmed(config, environment.solar_config)
        weather = manager.source(z, "weather")
        outdoor = environment.outdoor(manager.source(z, "outdoor"), now) if f.outside else None
        if outdoor is None and f.weather:
            outdoor = environment.weather_temperature(weather, now)
        azimuth, elevation = environment.sun
        exposure = solar_geometry(
            azimuth,
            elevation,
            config.get("orientation", 180),
            config.get("solar_elevation", 15),
            config.get("solar_width", 75),
        )
        geometry = f.solar != "off" and exposure
        # Turning off an optimisation must not make known solar exposure into
        # training evidence for the emitter. Unconfirmed default geometry is
        # insufficient to exclude samples when no solar module is configured.
        learning_exposure = exposure and (f.solar != "off" or exposure_confirmed)
        condition, clouds = environment.weather(weather, now) if f.weather else (None, None)
        weather_solar = solar_weather(condition, clouds)
        solar = geometry and weather_solar is not False
        # Relay states are observations, not proof of water flow. Do not train
        # an active response during partial activation or an unavailable inlet.
        outputs = [manager.hass.states.get(e) for e in config["actuators"]]
        uniform_outputs = all(s is not None and s.state == ("on" if on else "off") for s in outputs)
        inlet = manager.hass.states.get(manager.general) if manager.general else None
        inlet_ready = not manager.general or (
            inlet is not None
            and manager.general not in manager.actuator_faults
            and inlet.state in ("on", "off")
            and (
                not on
                or (
                    inlet.state == "on"
                    and (now - inlet.last_changed).total_seconds()
                    >= manager.entries.get(manager.hub, {}).get("general_travel", 0)
                )
            )
        )
        if measured is not None and sensor is not None:
            self.model.observe(
                sensor.last_reported,
                measured,
                mode,
                on,
                eligible=allowed,
                learning=f.learning and not learning_exposure and uniform_outputs and inlet_ready,
                outside=outdoor,
                observed_at=now,
                maximum_gap=z.settings.stale_after,
            )
        elif not allowed:
            self.model.reset_period(now)
        trend = self.model.trend(now)
        response = self.model.response(mode)
        manual = z.intent.hold is not None and z.intent.hold.active(now)
        self.diagnostics = {
            "outside_available": outdoor is not None,
            "weather_status": environment.availability(weather, now) if f.weather else "disabled",
            "solar_candidate": bool(solar),
            "solar_basis": "weather_and_geometry" if condition else "geometry_only",
            "solar_mode": f.solar,
            "learning_solar_exclusion": bool(learning_exposure),
            "trend_c_per_hour": round(trend, 3) if trend is not None else None,
            "model_ready": response.ready,
            "model_hours": round(response.hours, 2),
            "model_intervals": response.count,
            "model_rate_c_per_hour": round(response.rate, 3) if response.hours else None,
            "learning_max_gap_minutes": min(MAX_LEARNING_INTERVAL, z.settings.stale_after) / 60,
            "model_episodes": response.episodes,
            "model_rejected": self.model.rejected,
            "advance_minutes": None,
            "solar_arrival": None,
            "solar_lead_candidate": False,
        }
        if not allowed or measured is None or manual:
            return base
        # Optional policies introduce their own demand transition. The base
        # regulator may still demand heat, so its reason alone cannot enforce
        # the minimum ON time for a pause introduced here.
        can_pause = not on or (now - z.switched_at).total_seconds() >= z.settings.minimum_on
        solar_pre_pause = False
        # Observation reports candidates but cannot alter the regulator. A
        # forecast is mandatory before exposure; current clear sky is not one.
        if mode == Mode.HEAT and not exposure and f.solar != "off" and f.weather:
            arrival = environment.projection.arrival(now, (azimuth, elevation), config)
            forecast = environment.future(weather, arrival, now) if arrival else None
            predicted_sun = (
                solar_weather(forecast.get("condition"), forecast.get("cloud_coverage"))
                if forecast
                else None
            )
            candidate = bool(
                arrival
                and before_sun_pause(
                    mode,
                    measured,
                    base.target,
                    trend,
                    (arrival - now).total_seconds() / 60,
                    predicted_sun,
                )
            )
            self.diagnostics["solar_arrival"] = arrival.isoformat() if arrival else None
            self.diagnostics["solar_lead_candidate"] = candidate
            if (
                candidate
                and f.solar == "active"
                and exposure_confirmed
                and base.reason != "minimum_cycle"
                and can_pause
            ):
                solar_pre_pause = True
        next_time = (
            z.program.next_change(now, timezone)
            if z.program.enabled and not z.program.away
            else None
        )
        if f.anticipation and next_time:
            profile = z.program.active(next_time + timedelta(seconds=1), timezone)
            future_target = z.program.profiles[mode.value][profile]
            future_weather = environment.future(weather, next_time, now) if f.weather else None
            exterior = future_weather.get("temperature") if future_weather else outdoor
            if exterior is None:
                exterior = outdoor
            lead = lead_minutes(
                response, mode, measured, future_target, config.get("max_advance", 120), exterior
            )
            self.diagnostics["advance_minutes"] = round(lead, 1) if lead is not None else None
            direction = 1 if mode == Mode.HEAT else -1
            if (
                lead is not None
                and (next_time - now).total_seconds() <= lead * 60
                and (future_target - base.target) * direction > 0
            ):
                advanced = regulation(future_target)
                return Decision(
                    advanced.demand,
                    "anticipation"
                    if advanced.demand and advanced.reason == "demand"
                    else advanced.reason,
                    advanced.target,
                )
        # A due, higher-comfort schedule advance takes priority over solar gain
        # that has not arrived yet. Do not suppress an actual comfort request.
        if solar_pre_pause:
            return Decision(False, "solar_anticipation", base.target)
        pause = should_pause(
            mode,
            measured,
            base.target,
            trend,
            config.get("residual_minutes", 15),
            solar=solar and f.solar == "active" and exposure_confirmed,
            predictive=f.predictive,
            ready=response.ready,
            manual=manual,
        )
        if pause and can_pause and base.reason != "minimum_cycle":
            return Decision(False, pause, base.target)
        return base
