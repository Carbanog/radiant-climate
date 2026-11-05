"""Calendar and user intentions, including DST transitions."""

from datetime import UTC, datetime, timedelta

import pytest
from core.control import HoldPolicy, Intent, Mode, Settings
from core.program import Block, Program

NOW = datetime(2026, 11, 2, 17, tzinfo=UTC)
TZ = "Europe/Paris"


def plan():
    p = Program(enabled=True)
    p.set_blocks(list(range(7)), 7 * 60, "home")
    p.set_blocks(list(range(7)), 22 * 60, "sleep")
    return p


def test_weekly_cycle_and_roundtrip():
    p = Program.restore(plan().dump())
    assert p.active(NOW, TZ) == "home"
    assert p.next_change(NOW, TZ) == NOW.replace(hour=21)
    assert p.active(NOW.replace(hour=23), TZ) == "sleep"


@pytest.mark.parametrize("policy", list(HoldPolicy))
def test_manual_survives_schedule_when_policy_requires(policy):
    p = plan()
    p.policy = policy
    p.minutes = 480
    i = Intent(mode=Mode.HEAT)
    p.set_manual(i, Settings(), 22, NOW, TZ)
    assert p.target(i, NOW + timedelta(hours=5), TZ) == (
        20 if policy == HoldPolicy.NEXT_CHANGE else 22
    )
    p = Program.restore(p.dump())
    i = Intent.restore(i.dump())
    assert p.target(i, NOW + timedelta(hours=9), TZ) == (
        22 if policy == HoldPolicy.UNTIL_RESUME else 20
    )


def test_disabling_schedule_keeps_current_temperature_indefinitely():
    p, i = plan(), Intent(mode=Mode.HEAT)
    current = p.target(i, NOW, TZ)
    p.enabled = False
    p.set_manual(i, Settings(), current, NOW, TZ)
    assert p.target(i, NOW + timedelta(days=4), TZ) == current


def test_same_preset_value_is_still_manual_and_repeated_change_renews_hold():
    p, i = plan(), Intent(mode=Mode.HEAT)
    p.set_manual(i, Settings(), 21, NOW, TZ)
    deadline = i.hold.until
    p.set_manual(i, Settings(), 21, NOW + timedelta(hours=1), TZ)
    assert i.hold.until == deadline + timedelta(hours=1)


def test_clock_forward_missing_local_time_moves_to_first_valid_minute():
    p = Program(blocks=[Block(6, 150, "home")])
    now = datetime(2026, 3, 29, 0, tzinfo=UTC)
    assert p.next_change(now, TZ) == now.replace(hour=1)


def test_clock_backward_repeated_local_time_runs_once():
    p = Program(blocks=[Block(6, 150, "home")])
    now = datetime(2026, 10, 25, 0, tzinfo=UTC)
    first = p.next_change(now, TZ)
    assert first == now.replace(minute=30)
    assert p.next_change(first, TZ) > first + timedelta(days=6)


def test_cooling_profile_is_independent_and_off_does_not_enable():
    p, i = plan(), Intent(last_mode=Mode.COOL)
    assert p.target(i, NOW, TZ) == 25
    p.set_manual(i, Settings(), 24, NOW, TZ)
    assert i.mode == Mode.OFF
    assert p.target(i, NOW, TZ) == 24


def test_block_replace_and_reject_bad_storage():
    p = plan()
    p.set_blocks([0], 420, "eco")
    assert len(p.blocks) == 14
    raw = p.dump()
    raw["minutes"] = 0
    with pytest.raises(ValueError):
        Program.restore(raw)


def test_editing_schedule_recalculates_next_block_and_no_blocks_keeps_manual():
    p, i = plan(), Intent(mode=Mode.HEAT)
    p.policy = HoldPolicy.NEXT_CHANGE
    p.set_manual(i, Settings(), 22, NOW, TZ)
    p.set_blocks([0], 20 * 60, "eco")
    p.reconcile_edit(i, NOW, TZ)
    assert i.hold.until == NOW.replace(hour=19)
    p.blocks.clear()
    p.reconcile_edit(i, NOW, TZ)
    assert i.hold.until is None
    assert i.hold.policy == HoldPolicy.UNTIL_RESUME
    assert p.target(i, NOW + timedelta(days=15), TZ) == 22


@pytest.mark.parametrize("day,minute", [(1.1, 400), (True, 400), (0, 400.5)])
def test_corrupt_calendar_rejected(day, minute):
    with pytest.raises(ValueError):
        Block(day, minute, "home")
