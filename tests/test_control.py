"""Behavioural regressions; all times and temperatures are synthetic fixtures."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from core.control import Hold, HoldPolicy, Intent, Mode, Settings, decide, temperature


@pytest.mark.parametrize("profile", [None, "home", "eco", "sleep"])
def test_held_profile_roundtrip_is_additive(profile):
    intent = Intent(hold=Hold(22, HoldPolicy.UNTIL_RESUME, None, profile))
    assert Intent.restore(intent.dump()).hold.profile == profile
    old = intent.dump()
    del old["hold"]["profile"]
    assert Intent.restore(old).hold.profile is None


def test_invalid_held_profile_is_rejected():
    raw = Intent(hold=Hold(22, HoldPolicy.UNTIL_RESUME, None)).dump()
    raw["hold"]["profile"] = "unsupported"
    with pytest.raises(ValueError, match="profile"):
        Intent.restore(raw)


NOW = datetime(2026, 1, 1, 12, tzinfo=UTC)


def evaluate(*, mode=Mode.HEAT, measured=19, actual_on=False, settings=None, intent=None, **kwargs):
    settings = settings or Settings()
    intent = intent or Intent(mode=mode)
    inputs = {
        "measured_at": NOW,
        "switched_at": NOW - timedelta(hours=1),
        "enabled": True,
        "supply_mode": mode,
    }
    inputs.update(kwargs)
    return decide(settings, intent, NOW, measured=measured, actual_on=actual_on, **inputs)


@pytest.mark.parametrize(
    "value", [None, "unknown", "unavailable", "nan", float("inf"), True, -100, 100]
)
def test_invalid_temperature_stops(value):
    assert not evaluate(measured=value, actual_on=True).demand


@pytest.mark.parametrize(
    "mode,measured,wanted",
    [(Mode.HEAT, 19, True), (Mode.HEAT, 23, False), (Mode.COOL, 27, True), (Mode.COOL, 23, False)],
)
def test_heat_and_cool_are_symmetric_in_baseline(mode, measured, wanted):
    assert evaluate(mode=mode, measured=measured).demand is wanted


def test_hysteresis_retains_state_inside_band():
    assert evaluate(measured=21, actual_on=True).demand
    assert not evaluate(measured=21, actual_on=False).demand


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"enabled": False}, "global_off"),
        ({"window_open": True}, "window_open"),
        ({"window_open": None}, "window_unavailable"),
        ({"actuator_available": False}, "actuator_unavailable"),
        ({"measured_at": NOW - timedelta(hours=2)}, "temperature_stale"),
        ({"supply_mode": Mode.COOL}, "supply_mode_mismatch"),
    ],
)
def test_protections_bypass_minimum_on(override, reason):
    result = evaluate(actual_on=True, switched_at=NOW, **override)
    assert result.reason == reason
    assert not result.demand


def test_off_is_not_overridden_by_short_cycle():
    result = evaluate(intent=Intent(), actual_on=True, switched_at=NOW)
    assert not result.demand
    assert result.reason == "zone_off"


def test_minimum_on_and_off():
    assert evaluate(measured=23, actual_on=True, switched_at=NOW).demand
    assert not evaluate(measured=19, actual_on=False, switched_at=NOW).demand


def test_invalid_zone_does_not_change_another_intent():
    good, failed = Intent(mode=Mode.HEAT), Intent(mode=Mode.HEAT)
    assert not evaluate(intent=failed, measured=None).demand
    assert evaluate(intent=good).demand
    assert good.mode == Mode.HEAT


def test_fixed_has_no_expiry_and_temperature_while_off_does_not_start():
    intent = Intent()
    intent.set_target(22, NOW, Settings())
    assert intent.mode == Mode.OFF
    assert intent.hold is None
    assert intent.target(NOW + timedelta(days=100)) == 22


@pytest.mark.parametrize("policy", list(HoldPolicy))
def test_manual_hold_survives_roundtrip_and_uses_current_schedule_after_expiry(policy):
    intent = Intent(mode=Mode.HEAT)
    settings = Settings(hold_minutes=120, hold_policy=policy)
    intent.set_target(22, NOW, settings, scheduled=True, next_change=NOW + timedelta(hours=1))
    restored = Intent.restore(json.loads(json.dumps(intent.dump())))
    assert restored.target(NOW + timedelta(minutes=30), scheduled_target=19) == 22
    late = NOW + timedelta(hours=3)
    assert restored.target(late, scheduled_target=18) == (
        22 if policy == HoldPolicy.UNTIL_RESUME else 18
    )


def test_repeated_equal_target_renews_timer():
    intent = Intent(mode=Mode.HEAT)
    intent.set_target(21, NOW, Settings(), scheduled=True)
    old = intent.hold.until
    intent.set_target(21, NOW + timedelta(minutes=5), Settings(), scheduled=True)
    assert intent.hold.until == old + timedelta(minutes=5)


def test_no_next_schedule_boundary_is_rejected_atomically():
    intent = Intent(mode=Mode.HEAT)
    before = intent.dump()
    with pytest.raises(ValueError):
        intent.set_target(24, NOW, Settings(), scheduled=True, policy=HoldPolicy.NEXT_CHANGE)
    assert intent.dump() == before


def test_resume_and_mode_change_end_holds_but_off_does_not_erase_them():
    intent = Intent(mode=Mode.HEAT)
    intent.set_target(22, NOW, Settings(), scheduled=True)
    intent.set_mode(Mode.OFF, Settings())
    intent.set_mode(Mode.HEAT, Settings())
    assert intent.hold is not None
    intent.set_mode(Mode.COOL, Settings())
    assert intent.hold is None
    intent.set_target(24, NOW, Settings(), scheduled=True)
    intent.resume()
    assert intent.hold is None


def test_cooling_target_is_kept_while_off():
    intent = Intent(mode=Mode.COOL, last_mode=Mode.COOL)
    intent.set_target(24, NOW, Settings())
    intent.set_mode(Mode.OFF, Settings())
    assert Intent.restore(intent.dump()).target(NOW) == 24


@pytest.mark.parametrize(
    "settings",
    [{"hysteresis": 0}, {"minimum_on": -1}, {"stale_after": 0}, {"hold_minutes": 0}, {"modes": ()}],
)
def test_invalid_settings_are_rejected(settings):
    with pytest.raises(ValueError):
        Settings(**settings)


def test_corrupt_state_and_naive_time_are_rejected():
    with pytest.raises(ValueError):
        temperature(float("nan"))
    with pytest.raises(ValueError):
        Intent.restore({"mode": "heat", "targets": {"heat": 21}})
    with pytest.raises(ValueError):
        Intent().target(datetime(2026, 1, 1))
