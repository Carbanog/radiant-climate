"""Synthetic observations; no assumed valve feedback, flow or household data."""

import pytest
from core.hydraulic import HydraulicObserver


def observe(observer, now=0, **changes):
    data = dict(
        now=now,
        enabled=True,
        supply=30.0,
        returning=25.0,
        active=("a",),
        relays_ready=True,
        mode="heat",
        config=("fixture",),
        settle=300,
        duration=300,
        reference=35,
    )
    return observer.evaluate(**(data | changes))


def advance(observer, end, **changes):
    result = None
    for now in range(0, end + 1, 15):
        result = observe(observer, now, **changes)
    return result


def test_stabilisation_then_continuous_violation_and_immediate_recovery():
    observer = HydraulicObserver()
    assert advance(observer, 285) == "stabilizing"
    assert observe(observer, 300) == "reference_pending"
    for now in range(315, 600, 15):
        assert observe(observer, now) == "reference_pending"
    assert observe(observer, 600) == "possible_low_supply"
    assert observe(observer, 615, supply=35) == "observing"
    assert observe(observer, 630) == "reference_pending"


@pytest.mark.parametrize(
    "change,status",
    [
        ({"enabled": False}, "disabled"),
        ({"supply": None}, "sensor_unavailable"),
        ({"returning": float("nan")}, "sensor_unavailable"),
        ({"returning": float("inf")}, "sensor_unavailable"),
        ({"supply": -1}, "sensor_unavailable"),
        ({"returning": 91}, "sensor_unavailable"),
        ({"active": ()}, "idle"),
        ({"relays_ready": False}, "waiting_relays"),
    ],
)
def test_invalid_evidence_clears_all_timing(change, status):
    observer = HydraulicObserver()
    assert advance(observer, 600) == "possible_low_supply"
    assert observe(observer, 615, **change) == status
    assert observe(observer, 630) == "stabilizing"
    assert observer.concern_since is None


@pytest.mark.parametrize(
    "changes",
    [
        {"active": ("a", "b")},
        {"active": ("b",)},
        {"mode": "cool"},
        {"config": ("replacement",)},
        {"settle": 600},
        {"duration": 600},
        {"reference": 32},
    ],
)
def test_context_change_starts_fresh(changes):
    observer = HydraulicObserver()
    advance(observer, 600)
    assert observe(observer, 615, **changes) == "stabilizing"


def test_observer_gap_or_backwards_clock_never_inherits_elapsed_time():
    observer = HydraulicObserver()
    advance(observer, 600)
    assert observe(observer, 700) == "stabilizing"
    assert observe(observer, 400) == "stabilizing"
    assert observe(HydraulicObserver(), 10000) == "stabilizing"


def test_no_reference_only_observes_without_inventing_supply_requirement():
    assert advance(HydraulicObserver(), 900, reference=None) == "observing"


def test_cooling_has_its_own_reference_and_delta_sign():
    observer = HydraulicObserver()
    assert (
        advance(observer, 600, mode="cool", supply=23, returning=25, reference=20)
        == "possible_high_supply"
    )
    assert observe(observer, 615, mode="cool", supply=18, returning=22, reference=20) == "observing"


@pytest.mark.parametrize("mode,supply,returning", [("heat", 20, 25), ("cool", 25, 20)])
def test_reversed_delta_requires_sustained_evidence(mode, supply, returning):
    assert (
        advance(
            HydraulicObserver(), 600, mode=mode, supply=supply, returning=returning, reference=None
        )
        == "unexpected_delta"
    )


def test_warning_timer_does_not_accumulate_intermittent_deviations():
    observer = HydraulicObserver()
    advance(observer, 570)
    assert observe(observer, 585, supply=35) == "observing"
    assert observe(observer, 600) == "reference_pending"
    assert observe(observer, 615, returning=40) == "reference_pending"
    assert observer.concern_since == 615


def test_native_enum_is_translated_in_all_shipped_languages():
    import json
    from pathlib import Path

    from core.hydraulic import STATES

    component = Path(__file__).resolve().parents[1] / "custom_components/radiant_climate"
    for relative in ("strings.json", "translations/en.json", "translations/es.json"):
        document = json.loads((component / relative).read_text(encoding="utf-8"))
        assert set(document["entity"]["sensor"]["hydraulic"]["state"]) == set(STATES)
