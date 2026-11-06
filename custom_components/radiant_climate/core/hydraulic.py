"""Read-only hydraulic observations, with no access to thermostat commands."""

from dataclasses import dataclass
from math import isfinite

STATES = [
    "disabled",
    "sensor_unavailable",
    "idle",
    "waiting_relays",
    "stabilizing",
    "observing",
    "reference_pending",
    "possible_low_supply",
    "possible_high_supply",
    "unexpected_delta",
]


@dataclass
class HydraulicObserver:
    """Elapsed time is process-local: restart or invalid evidence starts afresh."""

    signature: tuple | None = None
    since: float | None = None
    concern: str | None = None
    concern_since: float | None = None
    last: float | None = None

    def evaluate(
        self,
        *,
        now: float,
        enabled: bool,
        supply: float | None,
        returning: float | None,
        active: tuple,
        relays_ready: bool,
        mode: str,
        config: tuple,
        settle: float,
        duration: float,
        reference: float | None,
    ) -> str:
        # Monotonic time avoids clock adjustments extending/shortening a warning.
        signature = (active, mode, config, settle, duration, reference)
        reset = signature != self.signature or (self.last is not None and now - self.last > 60)
        reset |= self.last is not None and now < self.last
        self.last = now
        self.signature = signature
        if reset:
            self.since = self.concern_since = self.concern = None
        valid = all(v is not None and isfinite(v) and 0 <= v <= 90 for v in (supply, returning))
        preliminary = (
            "disabled"
            if not enabled
            else "sensor_unavailable"
            if not valid
            else "idle"
            if not active
            else "waiting_relays"
            if not relays_ready
            else None
        )
        if preliminary:
            self.since = self.concern_since = self.concern = None
            return preliminary
        if self.since is None:
            self.since = now
        if now - self.since < settle:
            return "stabilizing"
        delta = supply - returning
        concern = (
            "unexpected_delta"
            if (mode == "heat" and delta < -1) or (mode == "cool" and delta > 1)
            else "possible_low_supply"
            if mode == "heat" and reference is not None and supply < reference
            else "possible_high_supply"
            if mode == "cool" and reference is not None and supply > reference
            else None
        )
        if concern != self.concern:
            self.concern, self.concern_since = concern, now if concern else None
        if concern is None:
            return "observing"
        return concern if now - self.concern_since >= duration else "reference_pending"
