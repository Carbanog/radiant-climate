"""Grouped agenda editing over the existing per-day storage format."""

from .program import Block, Program

DAY_GROUPS = {"week": range(7), "weekdays": range(5), "weekend": (5, 6)}


def weekdays(values):
    result = sorted({int(day) for value in values for day in DAY_GROUPS.get(value, (value,))})
    if not result or any(day not in range(7) for day in result):
        raise ValueError("invalid_configuration")
    return result


def groups(blocks):
    grouped = {}
    for block in sorted(blocks):
        grouped.setdefault((block.minute, block.profile), []).append(block.day)
    return [
        (
            f"{','.join(map(str, days))}|{minute}|{profile}",
            days,
            minute,
            profile,
        )
        for (minute, profile), days in sorted(grouped.items())
    ]


def selection(blocks, key, scope=()):
    # Accept the original single-day removal token for existing API callers.
    if "|" not in key:
        day, minute = map(int, key.split(":"))
        selected = [b for b in blocks if (b.day, b.minute) == (day, minute)]
    else:
        days, minute, profile = key.split("|")
        expected = [Block(int(d), int(minute), profile) for d in days.split(",")]
        if any(b not in blocks for b in expected):
            raise ValueError("schedule_changed")
        selected = expected
    if scope:
        selected = [b for b in selected if b.day in weekdays(scope)]
    if not selected:
        raise ValueError("schedule_changed")
    return tuple(selected)


def replace_blocks(program: Program, original, days=None, minute=None, profile=None):
    """Validate before mutation; preserve unselected exceptions and reject collisions."""
    if not original or any(b not in program.blocks for b in original):
        raise ValueError("schedule_changed")
    remaining = [b for b in program.blocks if b not in original]
    new = [] if days is None else [Block(d, minute, profile) for d in days]
    if len({(b.day, b.minute) for b in new}) != len(new):
        raise ValueError("invalid_configuration")
    if {(b.day, b.minute) for b in remaining} & {(b.day, b.minute) for b in new}:
        raise ValueError("schedule_conflict")
    program.blocks = sorted(remaining + new)
