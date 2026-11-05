"""Synthetic trajectories are fixtures, never a pre-trained household model."""

from datetime import UTC, datetime, timedelta

import pytest
from core.control import HoldPolicy, Intent, Mode, Settings
from core.intelligence import (
    Features,
    Statistics,
    ThermalModel,
    lead_minutes,
    should_pause,
    solar_geometry,
    solar_weather,
    window_pause,
)
from core.program import Program

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "az,el,orientation,height,expected",
    [
        (130, 20, 135, 15, True),
        (130, 10, 135, 15, False),
        (320, 20, 135, 15, False),
        (359, 20, 1, 15, True),
        (130, -1, 135, 0, False),
        (None, 20, 135, 10, False),
        (float("nan"), 20, 135, 10, False),
    ],
)
def test_solar_geometry_checks_both_angles(az, el, orientation, height, expected):
    assert solar_geometry(az, el, orientation, height) is expected


@pytest.mark.parametrize(
    "condition,clouds,expected",
    [
        (None, None, None),
        ("sunny", None, True),
        ("cloudy", None, False),
        ("partlycloudy", None, None),
        ("sunny", 80, False),
        (None, 20, True),
        (None, 200, None),
    ],
)
def test_missing_weather_does_not_invent_forecast(condition, clouds, expected):
    assert solar_weather(condition, clouds) is expected


@pytest.mark.parametrize("mode,direction", [(Mode.HEAT, 1), (Mode.COOL, -1)])
def test_learning_needs_multiple_real_periods_and_is_season_specific(mode, direction):
    model = ThermalModel()
    for episode in range(3):
        model.reset_period()
        for sample in range(25):
            model.observe(
                NOW + timedelta(days=episode, minutes=sample * 5),
                21 + sample / 60 * direction,
                mode,
                True,
                eligible=True,
                learning=True,
            )
    assert model.response(mode).ready
    other = Mode.COOL if mode == Mode.HEAT else Mode.HEAT
    assert not model.response(other).ready
    restored = ThermalModel.restore(model.dump())
    assert restored.response(mode).ready
    assert not restored.points  # Do not stitch an observation across a restart.


def test_windows_invalid_periods_and_learning_off_do_not_train():
    m = ThermalModel()
    for n in range(15):
        m.observe(
            NOW + timedelta(minutes=n * 5),
            20 + n / 60,
            Mode.HEAT,
            True,
            eligible=False,
            learning=True,
        )
    assert not m.statistics
    for n in range(15):
        m.observe(
            NOW + timedelta(minutes=n * 5),
            20 + n / 60,
            Mode.HEAT,
            True,
            eligible=True,
            learning=False,
        )
    assert not m.statistics
    assert m.trend(NOW + timedelta(minutes=70)) is not None


def test_stale_constant_reports_do_not_create_fake_samples():
    m = ThermalModel()
    for _ in range(100):
        m.observe(NOW, 21, Mode.HEAT, True, eligible=True, learning=True)
    assert len(m.points) == 1
    assert not m.statistics
    assert m.trend(NOW + timedelta(hours=1)) is None


@pytest.mark.parametrize(
    "mode,current,target,trend,solar,predictive,ready,manual,expected",
    [
        (Mode.HEAT, 20.9, 21, 0.8, True, False, False, False, "solar_pause"),
        (Mode.HEAT, 20, 21, 0.8, True, True, True, False, None),
        (Mode.HEAT, 20.9, 21, 0.8, True, True, True, True, None),
        (Mode.COOL, 25.1, 25, -0.8, True, False, False, False, None),
        (Mode.COOL, 25.1, 25, -0.8, False, True, True, False, "predictive_pause"),
        (Mode.COOL, 25.1, 25, -0.8, False, True, False, False, None),
        (Mode.HEAT, 20.9, 21, None, True, True, True, False, None),
    ],
)
def test_pauses_respect_manual_comfort_and_cooling(
    mode, current, target, trend, solar, predictive, ready, manual, expected
):
    assert (
        should_pause(
            mode,
            current,
            target,
            trend,
            15,
            solar=solar,
            predictive=predictive,
            ready=ready,
            manual=manual,
        )
        == expected
    )


def test_anticipation_bounds_and_optional_external_loss_correction():
    rate = Statistics(
        count=12,
        hours=6,
        delta=3,
        rate_square=1.5,
        episodes=3,
        outdoor_sum=60,
        indoor_sum=126,
        outdoor_hours=6,
    )
    assert rate.ready
    assert lead_minutes(rate, Mode.HEAT, 20, 21, 180) == 120
    assert lead_minutes(rate, Mode.HEAT, 20, 21, 180, outside=0) == 180
    assert lead_minutes(Statistics(), Mode.HEAT, 20, 21, 180) is None


@pytest.mark.parametrize(
    "state,elapsed,opening,closing,expected",
    [
        ("on", 5, 10, 0, False),
        ("on", 15, 10, 0, True),
        ("off", 5, 0, 10, True),
        ("off", 15, 0, 10, False),
        ("unavailable", 20, 0, 0, None),
    ],
)
def test_window_delays_and_unknown_fail_closed(state, elapsed, opening, closing, expected):
    assert window_pause(state, NOW, NOW + timedelta(seconds=elapsed), opening, closing) is expected


def test_away_manual_priority_expiry_off_and_roundtrip():
    p, i = (
        Program(enabled=True, away=True, away_until=NOW + timedelta(days=2)),
        Intent(mode=Mode.HEAT),
    )
    p.set_blocks([0, 1, 2, 3, 4, 5, 6], 0, "home")
    assert p.target(i, NOW, "UTC") == 17
    p.set_manual(i, Settings(), 22, NOW, "UTC")
    p = Program.restore(p.dump())
    i = Intent.restore(i.dump())
    assert p.target(i, NOW + timedelta(hours=1), "UTC") == 22
    assert p.target(i, NOW + timedelta(hours=5), "UTC") == 17
    assert p.target(i, NOW + timedelta(days=3), "UTC") == 21
    i.set_mode(Mode.OFF, Settings())
    p.away = True
    assert i.mode == Mode.OFF


def test_indefinite_away_next_change_hold_has_no_fictional_deadline():
    p, i = Program(away=True, policy=HoldPolicy.NEXT_CHANGE), Intent(mode=Mode.HEAT)
    p.set_manual(i, Settings(), 22, NOW, "UTC")
    assert i.hold.until is None
    assert i.hold.policy == HoldPolicy.UNTIL_RESUME


def test_program_old_storage_migrates_away_profile_additively():
    old = Program().dump()
    for values in old["profiles"].values():
        values.pop("away")
    old.pop("away")
    old.pop("away_until")
    restored = Program.restore(old)
    assert restored.profiles["heat"]["away"] == 17
    assert not restored.away


@pytest.mark.parametrize("raw", [{"weather": "true"}, {"solar": "unknown"}, {"learning": 1}])
def test_invalid_module_storage_rejected(raw):
    with pytest.raises(ValueError):
        Features.restore(raw)
