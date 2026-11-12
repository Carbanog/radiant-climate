"""Bounded, optional optimisations. Never writes hardware or changes user intent.

Observed response is descriptive, not a causal heat-loss measurement. A useful
model requires repeated stable periods; synthetic fixtures cannot train a home.
"""

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime

from .control import Mode, aware

MAX_LEARNING_INTERVAL = 90 * 60
MAX_TREND_GAP = 20 * 60


@dataclass
class Features:
    weather: bool = False
    outside: bool = False
    learning: bool = False
    anticipation: bool = False
    predictive: bool = False
    solar: str = "off"

    @classmethod
    def restore(cls, raw: dict) -> "Features":
        result = cls(**raw)
        if any(
            type(getattr(result, k)) is not bool
            for k in ("weather", "outside", "learning", "anticipation", "predictive")
        ) or result.solar not in ("off", "observe", "active"):
            raise ValueError("Invalid optional module state")
        return result


@dataclass
class Statistics:
    count: int = 0
    hours: float = 0
    delta: float = 0
    rate_square: float = 0
    episodes: int = 0
    outdoor_sum: float = 0
    indoor_sum: float = 0
    outdoor_hours: float = 0

    @property
    def rate(self):
        return self.delta / self.hours if self.hours else 0.0

    @property
    def ready(self):
        return not self.missing_requirements

    @property
    def missing_requirements(self):
        variance = max(0, self.rate_square / self.hours - self.rate**2) if self.hours else 0
        return tuple(
            key
            for key, passed in (
                ("intervals", self.count >= 12),
                ("hours", self.hours >= 6),
                ("episodes", self.episodes >= 3),
                ("rate", 0.05 <= self.rate <= 3),
                ("dispersion", math.sqrt(variance) <= abs(self.rate) * 0.75),
            )
            if not passed
        )

    def summary(self):
        missing = self.missing_requirements
        return {
            "ready": not missing,
            "intervals": self.count,
            "hours": round(self.hours, 2),
            "episodes": self.episodes,
            "rate_c_per_hour": round(self.rate, 3) if self.hours else None,
            "missing_requirements": list(missing),
        }

    def add(self, hours, delta, new_episode, outside, indoor):
        self.count += 1
        self.hours += hours
        self.delta += delta
        self.rate_square += (delta / hours) ** 2 * hours
        self.episodes += bool(new_episode)
        if outside is not None:
            self.outdoor_sum += outside * hours
            self.indoor_sum += indoor * hours
            self.outdoor_hours += hours


@dataclass
class ThermalModel:
    statistics: dict[str, Statistics] = field(default_factory=dict)
    points: list[tuple[datetime, float]] = field(default_factory=list)
    anchor: tuple | None = None
    cohort: str | None = None
    episode_pending: bool = True
    rejected: int = 0
    training_not_before: datetime | None = None
    trend_not_before: datetime | None = None

    def interrupt_training(self, when: datetime):
        """Do not attribute a cached reading to a newly observed control state."""
        aware(when)
        self.anchor = None
        self.cohort = None
        self.episode_pending = True
        if self.training_not_before is None or when > self.training_not_before:
            self.training_not_before = when

    def reset_period(self, when: datetime | None = None):
        self.anchor = None
        self.points.clear()
        self.cohort = None
        self.episode_pending = True
        if when is not None:
            self.interrupt_training(when)
            if self.trend_not_before is None or when > self.trend_not_before:
                self.trend_not_before = when

    def observe(
        self,
        when: datetime,
        value: float,
        mode: Mode,
        active: bool,
        *,
        eligible: bool,
        learning: bool,
        outside: float | None = None,
        observed_at: datetime | None = None,
        maximum_gap: float = MAX_LEARNING_INTERVAL,
    ):
        aware(when)
        observed_at = observed_at or when
        aware(observed_at)
        if not eligible or mode == Mode.OFF:
            self.reset_period(observed_at)
            return
        key = f"{mode.value}_{'on' if active else 'off'}"
        if not learning or self.cohort != key:
            # Context changes matter even without a fresh temperature report.
            self.interrupt_training(observed_at)
            self.cohort = key if learning else None
        if self.trend_not_before is not None and when < self.trend_not_before:
            return
        if self.points and when <= self.points[-1][0]:
            return
        if self.points:
            hours = (when - self.points[-1][0]).total_seconds() / 3600
            if abs(value - self.points[-1][1]) / hours > 3:
                self.reset_period(observed_at)
                self.rejected += 1
                return
            if hours * 3600 > min(maximum_gap, MAX_LEARNING_INTERVAL):
                self.interrupt_training(observed_at)
                self.rejected += 1
            if hours * 3600 > MAX_TREND_GAP:
                # Sparse reports can train slow response, but cannot establish
                # the recent trend required for immediate optional pauses.
                self.points.clear()
        self.points.append((when, value))
        self.points = [(t, v) for t, v in self.points[-96:] if (when - t).total_seconds() <= 3600]
        if not learning or (
            self.training_not_before is not None and when < self.training_not_before
        ):
            return
        if self.cohort != key:
            self.anchor = None
            self.cohort = key
            self.episode_pending = True
        if self.anchor is None:
            self.anchor = (when, value)
            return
        hours = (when - self.anchor[0]).total_seconds() / 3600
        if hours < 0.5:
            return
        direction = 1 if mode == Mode.HEAT else -1
        delta = (value - self.anchor[1]) * direction
        if hours * 3600 <= MAX_LEARNING_INTERVAL and abs(delta / hours) <= 3:
            self.statistics.setdefault(key, Statistics()).add(
                hours, delta, self.episode_pending, outside, value
            )
            self.episode_pending = False
        else:
            self.rejected += 1
        self.anchor = (when, value)

    def trend(self, now: datetime) -> float | None:
        if len(self.points) < 3 or (now - self.points[-1][0]).total_seconds() > MAX_TREND_GAP:
            return None
        span = (self.points[-1][0] - self.points[0][0]).total_seconds()
        if span < 900:
            return None
        xs = [(t - self.points[0][0]).total_seconds() / 3600 for t, _ in self.points]
        ys = [v for _, v in self.points]
        mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
        denominator = sum((x - mean_x) ** 2 for x in xs)
        return (
            sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / denominator
            if denominator
            else None
        )

    def response(self, mode: Mode) -> Statistics:
        return self.statistics.get(f"{mode.value}_on", Statistics())

    def dump(self):
        # No raw temperatures/timestamps/household schedule in exported diagnostics.
        return {
            "statistics": {k: asdict(v) for k, v in self.statistics.items()},
            "rejected": self.rejected,
        }

    @classmethod
    def restore(cls, raw):
        result = cls(rejected=int(raw.get("rejected", 0)))
        for key, values in raw.get("statistics", {}).items():
            if key not in {"heat_on", "heat_off", "cool_on", "cool_off"}:
                raise ValueError("Invalid response cohort")
            value = Statistics(**values)
            if (
                any(
                    not isinstance(v, (float, int)) or not math.isfinite(v) for v in values.values()
                )
                or value.hours < 0
                or value.count < 0
                or value.episodes < 0
                or type(value.count) is not int
                or type(value.episodes) is not int
                or value.episodes > value.count
                or value.rate_square < 0
                or not 0 <= value.outdoor_hours <= value.hours
            ):
                raise ValueError("Invalid response statistics")
            result.statistics[key] = value
        return result


def solar_geometry(azimuth, elevation, orientation, minimum_elevation, width=75):
    if any(
        v is None or not math.isfinite(v)
        for v in (azimuth, elevation, orientation, minimum_elevation, width)
    ):
        return False
    difference = abs((azimuth - orientation + 180) % 360 - 180)
    return 0 < elevation <= 90 and elevation >= minimum_elevation and difference <= width


def solar_weather(condition: str | None, clouds: float | None) -> bool | None:
    if type(clouds) in (int, float) and math.isfinite(clouds) and 0 <= clouds <= 100:
        return clouds <= 50
    if condition == "sunny":
        return True
    if condition in (
        "cloudy",
        "rainy",
        "pouring",
        "fog",
        "snowy",
        "hail",
        "lightning",
        "snowy-rainy",
        "lightning-rainy",
    ):
        return False
    return None


def before_sun_pause(mode, current, target, trend, minutes, forecast_sunny):
    """Bounded preventive heat pause, never a reason to accept an unmet comfort need."""
    if mode != Mode.HEAT or forecast_sunny is not True or trend is None:
        return False
    if not all(math.isfinite(v) for v in (current, target, trend, minutes)):
        return False
    return (
        0 < minutes <= 180
        and -0.1 <= trend <= 3
        and target - current <= 0.2
        and current + min(trend, 0) * minutes / 60 >= target - 0.3
    )


def lead_minutes(
    model: Statistics,
    mode: Mode,
    current: float,
    target: float,
    maximum: float,
    outside: float | None = None,
):
    if not model.ready:
        return None
    error = (target - current) * (1 if mode == Mode.HEAT else -1)
    if error <= 0:
        return 0.0
    factor = 1.0
    if outside is not None and model.outdoor_hours >= 3:
        direction = 1 if mode == Mode.HEAT else -1
        previous_loss = (model.indoor_sum - model.outdoor_sum) / model.outdoor_hours * direction
        current_loss = (current - outside) * direction
        if previous_loss > 2:
            factor = min(2, max(0.5, current_loss / previous_loss))
    return min(maximum, error / model.rate * 60 * factor)


def should_pause(
    mode: Mode,
    current: float,
    target: float,
    trend: float | None,
    horizon: float,
    *,
    solar: bool,
    predictive: bool,
    ready: bool,
    manual: bool,
):
    if manual or mode == Mode.OFF or trend is None:
        return None
    direction = 1 if mode == Mode.HEAT else -1
    remaining = (target - current) * direction
    toward = trend * direction
    if remaining > 0.3 or not 0.05 <= toward <= 3 or toward * horizon / 60 < remaining + 0.05:
        return None
    if solar and mode == Mode.HEAT:
        return "solar_pause"
    if predictive and ready:
        return "predictive_pause"
    return None


def window_pause(
    state: str | None, since: datetime | None, now: datetime, opening: float, closing: float
):
    if state not in ("on", "off") or since is None:
        return None
    elapsed = (now - since).total_seconds()
    if elapsed < 0:
        return None
    return elapsed >= opening if state == "on" else elapsed < closing
