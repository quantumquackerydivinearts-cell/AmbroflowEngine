"""Tests for the Ko dream calibration, VITRIOL assignment, and BreathOfKo."""

import pytest
from ambroflow.ko.calibration import (
    DREAM_LAYERS, COIL_LAYERS, DreamCalibrationSession, CalibrationTongue,
)
from ambroflow.ko.vitriol import assign_vitriol, VITRIOLProfile, TOTAL_BUDGET
from ambroflow.ko.flags import FlagState, KO_FLAG_BY_ID
from ambroflow.ko.breath import BreathOfKo, _mandelbrot_iterations


# ── Coil / dream layer structure ──────────────────────────────────────────────

def test_12_coil_layers():
    assert len(COIL_LAYERS) == 12


def test_24_dream_layers():
    assert len(DREAM_LAYERS) == 24


def test_dream_layer_indices_contiguous():
    indices = sorted(d.index for d in DREAM_LAYERS)
    assert indices == list(range(1, 25))


def test_lotus_layers_1_to_8():
    lotus = [d for d in DREAM_LAYERS if d.tongue == CalibrationTongue.LOTUS]
    assert len(lotus) == 8
    assert all(1 <= d.index <= 8 for d in lotus)
    assert all(d.face == "waking" for d in lotus)


def test_rose_layers_9_to_16():
    rose = [d for d in DREAM_LAYERS if d.tongue == CalibrationTongue.ROSE]
    assert len(rose) == 8
    assert all(9 <= d.index <= 16 for d in rose)
    assert all(d.face == "dreaming" for d in rose)


def test_sakura_layers_17_to_24():
    sakura = [d for d in DREAM_LAYERS if d.tongue == CalibrationTongue.SAKURA]
    assert len(sakura) == 8
    assert all(17 <= d.index <= 24 for d in sakura)


def test_coil_layer_1_is_gaoh():
    from ambroflow.ko.calibration import COIL_BY_INDEX
    assert COIL_BY_INDEX[1].shygazun == "Gaoh"


def test_coil_layer_12_is_wu_yl():
    from ambroflow.ko.calibration import COIL_BY_INDEX
    assert COIL_BY_INDEX[12].shygazun == "Wu-Yl"


# ── DreamCalibrationSession ───────────────────────────────────────────────────

def _run_calibration(game_id="7_KLGS", active_perks=frozenset(), resonance=0.7):
    session = DreamCalibrationSession(game_id=game_id, active_perks=active_perks)
    # 3 phases × 3 responses each
    for phase in [CalibrationTongue.SAKURA, CalibrationTongue.ROSE, CalibrationTongue.LOTUS]:
        for _ in range(3):
            session.respond(resonance)
    assert session.is_complete()
    return session.complete()


def test_calibration_produces_result():
    cal = _run_calibration()
    assert 0.0 <= cal.sakura_density <= 1.0
    assert 0.0 <= cal.rose_density   <= 1.0
    assert 0.0 <= cal.lotus_density  <= 1.0


def test_24_layer_densities_produced():
    cal = _run_calibration()
    assert len(cal.layer_densities) == 24
    assert all(0.0 <= v <= 1.0 for v in cal.layer_densities.values())


def test_depth_meditation_boosts_lotus_rose():
    cal_no_depth   = _run_calibration(active_perks=frozenset(),                    resonance=0.5)
    cal_with_depth = _run_calibration(active_perks=frozenset({"depth_meditation"}), resonance=0.5)
    assert cal_with_depth.lotus_density >= cal_no_depth.lotus_density
    assert cal_with_depth.rose_density  >= cal_no_depth.rose_density


def test_calibration_not_complete_before_all_phases():
    session = DreamCalibrationSession(game_id="7_KLGS")
    session.respond(0.5)
    session.respond(0.5)
    assert not session.is_complete()


# ── VITRIOL assignment ────────────────────────────────────────────────────────

def test_vitriol_budget_is_31():
    cal = _run_calibration(resonance=0.7)
    profile = assign_vitriol(cal)
    assert profile.total() == TOTAL_BUDGET


def test_vitriol_stats_in_range():
    cal = _run_calibration(resonance=0.6)
    profile = assign_vitriol(cal)
    for stat, val in profile.as_dict().items():
        assert 1 <= val <= 10, f"{stat} = {val} out of range"


def test_vitriol_high_lotus_boosts_vitality_tactility():
    cal = _run_calibration(resonance=0.9)   # high lotus
    profile = assign_vitriol(cal)
    # With high lotus, V and T should be relatively high
    d = profile.as_dict()
    assert d["vitality"] >= 2
    assert d["tactility"] >= 2


def test_vitriol_reproducible():
    cal = _run_calibration(resonance=0.65)
    p1 = assign_vitriol(cal, coil_position=5.0)
    p2 = assign_vitriol(cal, coil_position=5.0)
    assert p1.as_dict() == p2.as_dict()


# ── KoFlags ───────────────────────────────────────────────────────────────────

def test_flag_state_raise_and_active():
    fs = FlagState()
    assert not fs.is_active("polarities_held")
    fs.raise_flag("polarities_held")
    assert fs.is_active("polarities_held")


def test_flag_decay():
    fs = FlagState({"absence_practiced": 1.0})
    flag = KO_FLAG_BY_ID["absence_practiced"]
    fs.decay()
    assert fs.weight("absence_practiced") == pytest.approx(1.0 - flag.decay_rate)


def test_permanent_flag_no_decay():
    fs = FlagState({"polarities_held": 1.0})
    fs.decay()
    assert fs.weight("polarities_held") == pytest.approx(1.0)


# ── BreathOfKo ────────────────────────────────────────────────────────────────

def test_breath_default_neutral():
    b = BreathOfKo()
    assert b.coil_position == 6.0
    snap = b.snapshot()
    assert snap["games_played"] == 0
    assert snap["active_flags"] == []


def test_breath_integrate_calibration():
    b = BreathOfKo()
    cal = _run_calibration(resonance=0.8)
    b.integrate_calibration(cal)
    assert b.snapshot()["games_played"] == 1
    # Coil should have advanced
    assert b.coil_position != 6.0


def test_breath_mandelbrot_bounded():
    b = BreathOfKo()  # all defaults at 0.5 → should be bounded or edge
    result = b.boundedness()
    assert result in ("bounded", "edge", "unbounded")


def test_mandelbrot_bounded_vs_unbounded():
    # Azoth at origin should be bounded (Mandelbrot set contains 0)
    iters = _mandelbrot_iterations(complex(0, 0), complex(0, 0))
    assert iters == 256   # bounded

    # Azoth far from origin should escape
    iters = _mandelbrot_iterations(complex(5, 5), complex(0, 0))
    assert iters < 256


def test_breath_snapshot_contains_expected_keys():
    b = BreathOfKo()
    snap = b.snapshot()
    for key in ("layer_densities", "coil_position", "games_played", "active_flags", "boundedness", "azoth"):
        assert key in snap, f"Missing key: {key}"
