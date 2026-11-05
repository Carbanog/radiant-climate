"""Temperature control and user intent, independent of actuator I/O.

All timestamps are aware datetimes. A decision never proves valve position.
The initial controller uses hysteresis with minimum cycle times. Predictive
control is deliberately not claimed by this development baseline.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum


class Mode(StrEnum):
    OFF = "off"
    HEAT = "heat"
    COOL = "cool"


class HoldPolicy(StrEnum):
    DURATION = "duration"
    NEXT_CHANGE = "next_change"
    UNTIL_RESUME = "until_resume"


def aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An aware timestamp is required")


def temperature(value: object, minimum: float = 5, maximum: float = 40) -> float:
    if isinstance(value, bool):
        raise ValueError("A numeric temperature is required")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("A numeric temperature is required") from exc
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError("Temperature outside the supported range")
    return result


@dataclass(frozen=True, slots=True)
class Settings:
    modes: tuple[Mode, ...] = (Mode.HEAT, Mode.COOL)
    hysteresis: float = 0.2
    minimum_on: float = 180
    minimum_off: float = 180
    stale_after: float = 3600
    hold_minutes: float = 240
    hold_policy: HoldPolicy = HoldPolicy.DURATION

    def __post_init__(self) -> None:
        if not self.modes or any(m not in (Mode.HEAT, Mode.COOL) for m in self.modes):
            raise ValueError("At least one supported operating mode is required")
        if len(set(self.modes)) != len(self.modes):
            raise ValueError("Operating modes must be unique")
        if not math.isfinite(self.hysteresis) or not 0.05 <= self.hysteresis <= 2:
            raise ValueError("Invalid hysteresis")
        for value in (self.minimum_on, self.minimum_off, self.stale_after):
            if not math.isfinite(value) or value < 0:
                raise ValueError("Invalid control interval")
        if self.stale_after <= 0 or not 1 <= self.hold_minutes <= 1440:
            raise ValueError("Invalid expiry interval")


@dataclass(slots=True)
class Hold:
    target: float
    policy: HoldPolicy
    until: datetime | None

    def active(self, now: datetime) -> bool:
        return self.until is None or now < self.until


@dataclass(slots=True)
class Intent:
    mode: Mode = Mode.OFF
    last_mode: Mode = Mode.HEAT
    targets: dict[Mode, float] = field(default_factory=lambda: {Mode.HEAT: 21.0, Mode.COOL: 25.0})
    hold: Hold | None = None

    def set_mode(self, mode: Mode, settings: Settings) -> None:
        if mode != Mode.OFF and mode not in settings.modes:
            raise ValueError("Unsupported operating mode")
        if mode != self.last_mode and mode != Mode.OFF:
            self.hold = None
        if mode != Mode.OFF:
            self.last_mode = mode
        self.mode = mode

    def set_target(
        self,
        value: float,
        now: datetime,
        settings: Settings,
        *,
        scheduled: bool = False,
        next_change: datetime | None = None,
        policy: HoldPolicy | None = None,
    ) -> None:
        aware(now)
        target = temperature(value)
        # Adjusting a temperature while off must not implicitly turn the zone on.
        mode = self.mode if self.mode != Mode.OFF else self.last_mode
        if mode not in settings.modes:
            mode = settings.modes[0]
        if not scheduled:
            self.targets[mode] = target
            self.last_mode = mode
            self.hold = None
            return
        selected = HoldPolicy(policy or settings.hold_policy)
        if selected == HoldPolicy.NEXT_CHANGE:
            if next_change is None:
                raise ValueError("No upcoming schedule boundary")
            aware(next_change)
            if next_change <= now:
                raise ValueError("Schedule boundary must be in the future")
            until = next_change
        else:
            until = (
                now + timedelta(minutes=settings.hold_minutes)
                if selected == HoldPolicy.DURATION
                else None
            )
        self.targets[mode] = target
        self.last_mode = mode
        self.hold = Hold(target, selected, until)

    def target(self, now: datetime, *, scheduled_target: float | None = None) -> float:
        aware(now)
        if self.hold and not self.hold.active(now):
            self.hold = None
        if self.hold:
            return self.hold.target
        if scheduled_target is not None:
            return temperature(scheduled_target)
        mode = self.mode if self.mode != Mode.OFF else self.last_mode
        return self.targets[mode]

    def resume(self) -> None:
        self.hold = None

    def dump(self) -> dict:
        return {
            "mode": self.mode.value,
            "last_mode": self.last_mode.value,
            "targets": {k.value: v for k, v in self.targets.items()},
            "hold": {
                "target": self.hold.target,
                "policy": self.hold.policy.value,
                "until": self.hold.until.isoformat() if self.hold.until else None,
            }
            if self.hold
            else None,
        }

    @classmethod
    def restore(cls, data: dict) -> "Intent":
        mode = Mode(data["mode"])
        last_mode = Mode(data.get("last_mode", "heat"))
        if last_mode == Mode.OFF:
            raise ValueError("Invalid last operating mode")
        targets = {Mode(k): temperature(v) for k, v in data["targets"].items()}
        if set(targets) != {Mode.HEAT, Mode.COOL}:
            raise ValueError("Incomplete stored temperature targets")
        raw = data.get("hold")
        hold = None
        if raw:
            policy = HoldPolicy(raw["policy"])
            until = datetime.fromisoformat(raw["until"]) if raw["until"] else None
            if until:
                aware(until)
            if (policy == HoldPolicy.UNTIL_RESUME) != (until is None):
                raise ValueError("Inconsistent stored hold")
            hold = Hold(temperature(raw["target"]), policy, until)
        return cls(mode=mode, last_mode=last_mode, targets=targets, hold=hold)


@dataclass(frozen=True, slots=True)
class Decision:
    demand: bool
    reason: str
    target: float


def decide(
    settings: Settings,
    intent: Intent,
    now: datetime,
    *,
    measured: object,
    measured_at: datetime | None,
    actual_on: bool,
    switched_at: datetime,
    enabled: bool,
    supply_mode: Mode,
    window_open: bool | None = False,
    actuator_available: bool = True,
    scheduled_target: float | None = None,
) -> Decision:
    """Safety, user-off and invalid input bypass minimum run times immediately."""
    aware(now)
    aware(switched_at)
    target = intent.target(now, scheduled_target=scheduled_target)
    if not enabled:
        return Decision(False, "global_off", target)
    if intent.mode == Mode.OFF:
        return Decision(False, "zone_off", target)
    if intent.mode not in settings.modes:
        return Decision(False, "unsupported_mode", target)
    if intent.mode != supply_mode:
        return Decision(False, "supply_mode_mismatch", target)
    if not actuator_available:
        return Decision(False, "actuator_unavailable", target)
    if window_open is not False:
        return Decision(False, "window_open" if window_open else "window_unavailable", target)
    try:
        current = temperature(measured, -30, 65)
    except ValueError:
        return Decision(False, "temperature_invalid", target)
    if measured_at is None:
        return Decision(False, "temperature_missing", target)
    aware(measured_at)
    age = (now - measured_at).total_seconds()
    if age < -60 or age > settings.stale_after:
        return Decision(False, "temperature_stale", target)
    delta = target - current if intent.mode == Mode.HEAT else current - target
    wanted = delta > -settings.hysteresis if actual_on else delta >= settings.hysteresis
    elapsed = (now - switched_at).total_seconds()
    if elapsed < 0:
        return Decision(False, "clock_changed", target)
    if wanted != actual_on:
        minimum = settings.minimum_on if actual_on else settings.minimum_off
        if elapsed < minimum:
            return Decision(actual_on, "minimum_cycle", target)
    return Decision(wanted, "demand" if wanted else "satisfied", target)
