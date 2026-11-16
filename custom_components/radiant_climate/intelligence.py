"""Optional zone policy, isolated from hardware writes and weather requests."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from math import isfinite

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
    circuit_seconds: dict[str, float] = field(default_factory=dict)
    _active_mode: Mode | None = None
    _observed_at: datetime | None = None
    _sparse_since: datetime | None = None

    def dump(self):
        return {
            "features": asdict(self.features),
            "model": self.model.dump(),
            "circuit_seconds": dict(self.circuit_seconds),
        }

    @classmethod
    def restore(cls, raw):
        result = cls(
            Features.restore(raw.get("features", {})), ThermalModel.restore(raw.get("model", {}))
        )
        totals = raw.get("circuit_seconds", {})
        if isinstance(totals, dict):
            result.circuit_seconds = {
                key: value
                for key, value in totals.items()
                if key in ("heat", "cool")
                and type(value) in (int, float)
                and isfinite(value)
                and value >= 0
            }
        return result

    def observe_circuit(self, now, mode):
        # Drop the gap on restart or when reconciliation was suspended.
        if self._active_mode is not None and self._observed_at is not None:
            elapsed = (now - self._observed_at).total_seconds()
            if 0 <= elapsed <= 60:
                key = self._active_mode.value
                self.circuit_seconds[key] = self.circuit_seconds.get(key, 0) + elapsed
            else:
                self._sparse_since = None
        if mode != self._active_mode:
            self._sparse_since = None
        self._active_mode, self._observed_at = mode, now

    def interrupt_sparse(self):
        self._sparse_since = None
        self.model.sparse_anchor = None

    def evaluate(self, z, manager, now, sensor, measured, on, opened, enabled, available):
        def regulation(target):
            return decide(
                z.settings,
                z.intent,
                now,
                measured=measured,
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
        training_allowed = f.learning and not learning_exposure and uniform_outputs and inlet_ready
        active = (
            on
            and uniform_outputs
            and (not manager.general or (inlet is not None and inlet.state == "on"))
        )
        self.observe_circuit(now, manager.supply_mode if active else None)
        if active and training_allowed and allowed and measured is not None and sensor is not None:
            self._sparse_since = self._sparse_since or now
            self.model.observe_sparse(
                mode, sensor.last_reported, measured, since=self._sparse_since
            )
        else:
            self.interrupt_sparse()
        if measured is not None and sensor is not None:
            self.model.observe(
                sensor.last_reported,
                measured,
                mode,
                on,
                eligible=allowed,
                learning=training_allowed,
                outside=outdoor,
                observed_at=now,
            )
        elif not allowed:
            self.model.reset_period(now)
        trend = self.model.trend(now)
        response = self.model.response(mode)
        display_mode = z.intent.last_mode if mode == Mode.OFF else mode
        progress = self.model.response(display_mode).summary()
        manual = z.intent.hold is not None and z.intent.hold.active(now)
        self.diagnostics = {
            "outside_available": outdoor is not None,
            "weather_status": environment.availability(weather, now) if f.weather else "disabled",
            "solar_candidate": bool(solar),
            "solar_basis": "weather_and_geometry" if condition else "geometry_only",
            "solar_mode": f.solar,
            "learning_solar_exclusion": bool(learning_exposure),
            "trend_c_per_hour": round(trend, 3) if trend is not None else None,
            "learning_collecting": bool(training_allowed and allowed and measured is not None),
            "learning_circuit_active": active,
            "model_mode": display_mode.value,
            "model_ready": progress["ready"],
            "model_hours": progress["hours"],
            "model_intervals": progress["intervals"],
            "model_rate_c_per_hour": progress["rate_c_per_hour"],
            "learning_max_gap_minutes": MAX_LEARNING_INTERVAL / 60,
            "model_episodes": progress["episodes"],
            "model_missing_requirements": progress["missing_requirements"],
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
