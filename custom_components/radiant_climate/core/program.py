"""Weekly comfort plans and editable profiles, without Home Assistant state."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .control import HoldPolicy, Intent, Mode, Settings, aware, temperature

PROFILES = ("home", "eco", "sleep")


@dataclass(frozen=True, order=True)
class Block:
    day: int
    minute: int
    profile: str

    def __post_init__(self):
        if not 0 <= self.day <= 6 or not 0 <= self.minute < 1440 or self.profile not in PROFILES:
            raise ValueError("Invalid weekly block")


@dataclass
class Program:
    enabled: bool = False
    selected: str | None = None
    policy: HoldPolicy = HoldPolicy.DURATION
    minutes: float = 240
    profiles: dict = field(
        default_factory=lambda: {
            "heat": {"home": 21.0, "eco": 19.0, "sleep": 20.0},
            "cool": {"home": 25.0, "eco": 27.0, "sleep": 26.0},
        }
    )
    blocks: list[Block] = field(default_factory=list)

    def set_blocks(self, days: list[int], minute: int, profile: str) -> None:
        new = [Block(d, minute, profile) for d in days]
        if not new or len(set(days)) != len(days):
            raise ValueError("Choose distinct weekdays")
        keys = {(b.day, b.minute) for b in new}
        self.blocks = sorted([b for b in self.blocks if (b.day, b.minute) not in keys] + new)

    def occurrences(self, now: datetime, timezone: str) -> list[tuple[datetime, Block]]:
        aware(now)
        zone = ZoneInfo(timezone)
        today = now.astimezone(zone).date()
        events = []
        for offset in range(-7, 9):
            day = today + timedelta(days=offset)
            for block in self.blocks:
                if block.day != day.weekday():
                    continue
                local = datetime.combine(day, time(block.minute // 60, block.minute % 60))
                # A missing spring clock time runs at the first valid minute.
                # An autumn repeated time runs once, at its first occurrence.
                for shift in range(181):
                    candidate = (local + timedelta(minutes=shift)).replace(tzinfo=zone, fold=0)
                    utc = candidate.astimezone(UTC)
                    if utc.astimezone(zone).replace(tzinfo=None) == candidate.replace(tzinfo=None):
                        events.append((utc, block))
                        break
        return sorted(events)

    def active(self, now: datetime, timezone: str) -> str:
        previous = [b for when, b in self.occurrences(now, timezone) if when <= now]
        return previous[-1].profile if previous else "home"

    def next_change(self, now: datetime, timezone: str) -> datetime | None:
        return next((when for when, _ in self.occurrences(now, timezone) if when > now), None)

    def scheduled_target(self, intent: Intent, now: datetime, timezone: str) -> float | None:
        mode = intent.mode if intent.mode != Mode.OFF else intent.last_mode
        profile = self.active(now, timezone) if self.enabled else self.selected
        return self.profiles[mode.value][profile] if profile else None

    def target(self, intent: Intent, now: datetime, timezone: str) -> float:
        return intent.target(now, scheduled_target=self.scheduled_target(intent, now, timezone))

    def set_manual(
        self, intent: Intent, settings: Settings, value: float, now: datetime, timezone: str
    ):
        if self.enabled and self.policy == HoldPolicy.NEXT_CHANGE and not self.blocks:
            raise ValueError("A schedule block is required for next-change holds")
        from dataclasses import replace

        intent.set_target(
            value,
            now,
            replace(settings, hold_policy=self.policy, hold_minutes=self.minutes),
            scheduled=self.enabled,
            next_change=self.next_change(now, timezone),
        )
        self.selected = None

    def dump(self) -> dict:
        return {
            "enabled": self.enabled,
            "selected": self.selected,
            "policy": self.policy.value,
            "minutes": self.minutes,
            "profiles": self.profiles,
            "blocks": [
                {"day": b.day, "minute": b.minute, "profile": b.profile} for b in self.blocks
            ],
        }

    @classmethod
    def restore(cls, raw: dict) -> "Program":
        if not isinstance(raw["enabled"], bool) or raw["selected"] not in (*PROFILES, None):
            raise ValueError("Invalid stored program")
        minutes = float(raw["minutes"])
        if not 1 <= minutes <= 1440:
            raise ValueError("Invalid hold duration")
        profiles = {
            mode: {p: temperature(raw["profiles"][mode][p]) for p in PROFILES}
            for mode in ["heat", "cool"]
        }
        blocks = [Block(**b) for b in raw["blocks"]]
        if len({(b.day, b.minute) for b in blocks}) != len(blocks):
            raise ValueError("Duplicate weekly block")
        return cls(
            raw["enabled"],
            raw["selected"],
            HoldPolicy(raw["policy"]),
            minutes,
            profiles,
            sorted(blocks),
        )
