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
            NOW + timedelta(minutes=75 + n * 5),
            20 + n / 60,
            Mode.HEAT,
            True,
            eligible=True,
            learning=False,
        )
    assert not m.statistics
    assert m.trend(NOW + timedelta(minutes=145)) is not None


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


def test_temporary_away_manual_does_not_overwrite_underlying_fixed_profile():
    p, i = (
        Program(selected="home", away=True, away_until=NOW + timedelta(days=2)),
        Intent(mode=Mode.HEAT),
    )
    p.profiles["heat"]["home"] = 21.5
    p.set_manual(i, Settings(), 22, NOW, "UTC")
    assert p.target(i, NOW, "UTC") == 22
    assert p.target(i, NOW + timedelta(days=3), "UTC") == 21.5
    assert i.targets[Mode.HEAT] == 21


def test_corrupt_required_profile_is_not_silently_replaced():
    raw = Program().dump()
    raw["profiles"]["heat"].pop("home")
    with pytest.raises(KeyError):
        Program.restore(raw)


def test_corrupt_model_variance_cannot_enable_predictions():
    with pytest.raises(ValueError):
        ThermalModel.restore(
            {
                "statistics": {
                    "heat_on": {
                        "count": 12,
                        "hours": 6,
                        "delta": 3,
                        "rate_square": -1,
                        "episodes": 3,
                    }
                }
            }
        )


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


def test_training_exclusion_resets_anchor_even_without_a_new_temperature_report():
    from datetime import UTC, datetime

    from core.control import Mode
    from core.intelligence import ThermalModel

    model = ThermalModel()
    now = datetime(2026, 1, 1, tzinfo=UTC)
    model.observe(now, 20, Mode.HEAT, True, eligible=True, learning=True)
    assert model.anchor is not None
    previous_points = list(model.points)
    model.observe(now, 20, Mode.HEAT, True, eligible=True, learning=False)
    assert model.anchor is None
    assert model.cohort is None
    assert model.points == previous_points


@pytest.mark.parametrize(
    "mode,current,trend,minutes,sunny,expected",
    [
        (Mode.HEAT, 21, 0, 60, True, True),
        (Mode.HEAT, 20.9, -0.05, 90, True, True),
        (Mode.HEAT, 20.5, 0.1, 60, True, False),
        (Mode.HEAT, 20.85, -0.1, 180, True, False),
        (Mode.HEAT, 21, None, 60, True, False),
        (Mode.HEAT, 21, 0, 60, None, False),
        (Mode.HEAT, 21, 0, 60, False, False),
        (Mode.HEAT, 21, 0, 0, True, False),
        (Mode.HEAT, 21, -0.5, 60, True, False),
        (Mode.COOL, 21, 0, 60, True, False),
        (Mode.OFF, 21, 0, 60, True, False),
        (Mode.HEAT, float("nan"), 0, 60, True, False),
    ],
)
def test_pre_sun_pause_respects_comfort_and_requires_forecast(
    mode, current, trend, minutes, sunny, expected
):
    from core.intelligence import before_sun_pause

    assert before_sun_pause(mode, current, 21, trend, minutes, sunny) == expected


@pytest.mark.parametrize("minutes", [30, 45, 60, 90])
@pytest.mark.parametrize("mode,direction", [(Mode.HEAT, 1), (Mode.COOL, -1)])
def test_sparse_reports_train_response_without_inventing_recent_trend(minutes, mode, direction):
    model = ThermalModel()
    for episode in range(3):
        model.reset_period()
        for elapsed in range(0, 361, minutes):
            when = NOW + timedelta(days=episode, minutes=elapsed)
            model.observe(
                when, 21 + direction * elapsed / 120, mode, True, eligible=True, learning=True
            )
    response = model.response(mode)
    assert response.ready
    assert response.rate == pytest.approx(0.5)
    assert response.episodes == 3
    assert response.count == 3 * (360 // minutes)
    assert model.trend(when) is None


@pytest.mark.parametrize("minutes", [91, 120, 300])
def test_long_unknown_intervals_are_not_training_evidence(minutes):
    model = ThermalModel()
    model.observe(NOW, 20, Mode.HEAT, True, eligible=True, learning=True)
    model.observe(
        NOW + timedelta(minutes=minutes), 20.3, Mode.HEAT, True, eligible=True, learning=True
    )
    assert not model.statistics
    assert model.rejected == 1
    assert not model.response(Mode.HEAT).ready


@pytest.mark.parametrize("interruption", ["relay", "event", "excluded", "blocked"])
def test_cached_reading_cannot_bridge_intervening_control_changes(interruption):
    model = ThermalModel()
    for minute in (0, 15):
        model.observe(
            NOW + timedelta(minutes=minute),
            20 + minute / 120,
            Mode.HEAT,
            True,
            eligible=True,
            learning=True,
        )
    cached = NOW + timedelta(minutes=15)
    changed = NOW + timedelta(minutes=20)
    if interruption == "event":
        model.interrupt_training(changed)
    else:
        model.observe(
            cached,
            20.125,
            Mode.HEAT,
            interruption != "relay",
            eligible=interruption != "blocked",
            learning=interruption != "excluded",
            observed_at=changed,
        )
    model.observe(
        cached,
        20.125,
        Mode.HEAT,
        True,
        eligible=True,
        learning=True,
        observed_at=NOW + timedelta(minutes=25),
    )
    assert model.anchor is None
    model.observe(
        NOW + timedelta(minutes=45), 20.375, Mode.HEAT, True, eligible=True, learning=True
    )
    assert not model.statistics
    model.observe(NOW + timedelta(minutes=90), 20.75, Mode.HEAT, True, eligible=True, learning=True)
    response = model.response(Mode.HEAT)
    assert response.count == 1
    assert response.hours == pytest.approx(0.75)
    assert response.rate == pytest.approx(0.5)


def test_repeated_cached_reports_do_not_fill_sparse_intervals():
    model = ThermalModel()
    model.observe(NOW, 20, Mode.HEAT, True, eligible=True, learning=True)
    for minute in range(1, 45):
        model.observe(
            NOW,
            20,
            Mode.HEAT,
            True,
            eligible=True,
            learning=True,
            observed_at=NOW + timedelta(minutes=minute),
        )
    assert len(model.points) == 1
    assert not model.statistics
    model.observe(
        NOW + timedelta(minutes=45), 20.375, Mode.HEAT, True, eligible=True, learning=True
    )
    assert model.response(Mode.HEAT).count == 1
    assert model.trend(NOW + timedelta(minutes=45)) is None


def test_restart_cannot_join_the_last_sparse_training_anchor():
    model = ThermalModel()
    for minute in (0, 45):
        model.observe(
            NOW + timedelta(minutes=minute),
            20 + minute / 120,
            Mode.HEAT,
            True,
            eligible=True,
            learning=True,
        )
    restored = ThermalModel.restore(model.dump())
    restored.observe(
        NOW + timedelta(minutes=90), 20.75, Mode.HEAT, True, eligible=True, learning=True
    )
    assert restored.response(Mode.HEAT).hours == pytest.approx(0.75)
    assert restored.response(Mode.HEAT).count == 1
    assert restored.trend(NOW + timedelta(minutes=90)) is None


def test_learning_gap_limit_does_not_limit_continuously_observed_window():
    model = ThermalModel()
    for minute in range(0, 31, 5):
        model.observe(
            NOW + timedelta(minutes=minute),
            20 + minute / 120,
            Mode.HEAT,
            True,
            eligible=True,
            learning=True,
            maximum_gap=600,
        )
    assert model.response(Mode.HEAT).count == 1
    assert model.response(Mode.HEAT).hours == pytest.approx(0.5)


def test_learning_does_not_bridge_gap_beyond_configured_temperature_expiry():
    model = ThermalModel()
    model.observe(NOW, 20, Mode.HEAT, True, eligible=True, learning=True, maximum_gap=3600)
    model.observe(
        NOW + timedelta(minutes=75),
        20.625,
        Mode.HEAT,
        True,
        eligible=True,
        learning=True,
        maximum_gap=3600,
    )
    assert not model.statistics
    assert model.rejected == 1
