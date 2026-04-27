"""
Tests for the Negaya encounter system, all 7 meditation perk effects,
and the MeditationSession driver:
  - negaya_triggered / negaya_permanent / negaya_duration threshold logic
  - NegayaEncounterScreen PIL rendering
  - TileTracer.kill_count()
  - MeditationSession gate logic and full run
  - Calibration boosts: depth (Lotus/Rose), infernal (Sakura), transcendental (all)
  - Sanity deltas: all 7 perks including alchemical cross-skill synergy
"""

import pytest

from ambroflow.ko.calibration import DreamCalibrationSession, CalibrationTongue
from ambroflow.ko.negaya import (
    NegayaEncounterScreen,
    NEGAYA_KILL_THRESHOLD,
    NEGAYA_PERMANENT_THRESHOLD,
    negaya_triggered,
    negaya_permanent,
    negaya_duration,
)
from ambroflow.ko.flags import FlagState
from ambroflow.ko.breath import BreathOfKo
from ambroflow.ko.meditation import (
    MeditationSession,
    MeditationOutcome,
    compute_session_sanity_delta,
)
from ambroflow.world.tile_trace import TileTracer, ZO


# ── Threshold logic ───────────────────────────────────────────────────────────

def test_not_triggered_below_threshold():
    assert not negaya_triggered(20, negaya_appeased=False)


def test_triggered_at_threshold():
    assert negaya_triggered(21, negaya_appeased=False)


def test_not_triggered_when_appeased():
    assert not negaya_triggered(100, negaya_appeased=True)


def test_not_permanent_below_threshold():
    assert not negaya_permanent(71)


def test_permanent_at_threshold():
    assert negaya_permanent(72)


def test_permanent_well_above():
    assert negaya_permanent(200)


def test_duration_zero_below_trigger():
    assert negaya_duration(0) == 0
    assert negaya_duration(20) == 0


def test_duration_equals_kill_count_in_range():
    assert negaya_duration(21) == 21
    assert negaya_duration(50) == 50
    assert negaya_duration(71) == 71


def test_duration_none_at_permanent():
    assert negaya_duration(72) is None
    assert negaya_duration(500) is None


# ── TileTracer.kill_count ─────────────────────────────────────────────────────

def test_kill_count_zero_initially():
    tracer = TileTracer()
    assert tracer.kill_count() == 0


def test_kill_count_increments_with_zo():
    tracer = TileTracer()
    tracer.deposit("zone", 0, 0, ZO)
    assert tracer.kill_count() == 1


def test_kill_count_accumulates_across_tiles():
    tracer = TileTracer()
    tracer.deposit("zone", 0, 0, ZO)
    tracer.deposit("zone", 1, 0, ZO)
    tracer.deposit("zone", 0, 1, ZO)
    assert tracer.kill_count() == 3


def test_kill_count_not_affected_by_other_bytes():
    from ambroflow.world.tile_trace import FY, PU
    tracer = TileTracer()
    tracer.deposit("zone", 0, 0, FY)
    tracer.deposit("zone", 0, 0, PU)
    assert tracer.kill_count() == 0


def test_kill_count_multiple_zo_on_same_tile():
    tracer = TileTracer()
    tracer.deposit("zone", 0, 0, ZO)
    tracer.deposit("zone", 0, 0, ZO)
    assert tracer.kill_count() == 2


# ── NegayaEncounterScreen ─────────────────────────────────────────────────────

def test_render_frame_returns_png():
    pytest.importorskip("PIL")
    screen = NegayaEncounterScreen()
    frame = screen.render_frame(kill_count=25, sob_num=5, width=320, height=200)
    assert frame is not None
    assert frame[:4] == b"\x89PNG"


def test_render_permanent_frame_returns_png():
    pytest.importorskip("PIL")
    screen = NegayaEncounterScreen()
    frame = screen.render_permanent_frame(width=320, height=200)
    assert frame is not None
    assert frame[:4] == b"\x89PNG"


def test_render_frames_differ_by_sob():
    pytest.importorskip("PIL")
    screen = NegayaEncounterScreen()
    f1 = screen.render_frame(40, 1,  320, 200)
    f2 = screen.render_frame(40, 20, 320, 200)
    # Different sob counts produce different frames (progress indicator differs)
    assert f1 != f2


# ── MeditationSession.check_gate ─────────────────────────────────────────────

def _flags(**active: bool) -> FlagState:
    state = FlagState()
    for flag_id, on in active.items():
        if on:
            state.raise_flag(flag_id, 1.0)
    return state


def test_gate_completed_below_threshold():
    session = MeditationSession(BreathOfKo())
    outcome = session.check_gate(kill_count=10, flag_state=_flags())
    assert outcome == MeditationOutcome.COMPLETED


def test_gate_broken_in_finite_range():
    session = MeditationSession(BreathOfKo())
    outcome = session.check_gate(kill_count=21, flag_state=_flags())
    assert outcome == MeditationOutcome.BROKEN


def test_gate_broken_upper_edge():
    session = MeditationSession(BreathOfKo())
    outcome = session.check_gate(kill_count=71, flag_state=_flags())
    assert outcome == MeditationOutcome.BROKEN


def test_gate_blocked_at_permanent():
    session = MeditationSession(BreathOfKo())
    outcome = session.check_gate(kill_count=72, flag_state=_flags())
    assert outcome == MeditationOutcome.BLOCKED


def test_gate_blocked_well_above():
    session = MeditationSession(BreathOfKo())
    outcome = session.check_gate(kill_count=300, flag_state=_flags())
    assert outcome == MeditationOutcome.BLOCKED


def test_gate_completed_when_appeased_at_high_kills():
    session = MeditationSession(BreathOfKo())
    outcome = session.check_gate(kill_count=200, flag_state=_flags(negaya_appeased=True))
    assert outcome == MeditationOutcome.COMPLETED


# ── MeditationSession.run ─────────────────────────────────────────────────────

def test_run_completed_updates_breath():
    breath = BreathOfKo()
    session = MeditationSession(breath)
    outcome, frames = session.run(kill_count=0, flag_state=_flags(), resonance=0.7)
    assert outcome == MeditationOutcome.COMPLETED
    assert frames == []
    assert len(breath.dream_calibrations) == 1


def test_run_broken_does_not_update_breath():
    pytest.importorskip("PIL")
    breath = BreathOfKo()
    session = MeditationSession(breath)
    outcome, frames = session.run(kill_count=25, flag_state=_flags())
    assert outcome == MeditationOutcome.BROKEN
    assert len(breath.dream_calibrations) == 0


def test_run_broken_produces_sob_frames():
    pytest.importorskip("PIL")
    breath = BreathOfKo()
    session = MeditationSession(breath)
    outcome, frames = session.run(kill_count=25, flag_state=_flags(), width=320, height=200)
    assert outcome == MeditationOutcome.BROKEN
    assert len(frames) == 25   # one per sob (= kill_count for 21–71)
    assert all(f[:4] == b"\x89PNG" for f in frames)


def test_run_blocked_produces_one_permanent_frame():
    pytest.importorskip("PIL")
    breath = BreathOfKo()
    session = MeditationSession(breath)
    outcome, frames = session.run(kill_count=72, flag_state=_flags(), width=320, height=200)
    assert outcome == MeditationOutcome.BLOCKED
    assert len(frames) == 1
    assert frames[0][:4] == b"\x89PNG"


def test_run_blocked_does_not_update_breath():
    pytest.importorskip("PIL")
    breath = BreathOfKo()
    session = MeditationSession(breath)
    outcome, frames = session.run(kill_count=72, flag_state=_flags())
    assert outcome == MeditationOutcome.BLOCKED
    assert len(breath.dream_calibrations) == 0


def test_run_appeased_at_high_kills_completes():
    breath = BreathOfKo()
    session = MeditationSession(breath)
    outcome, frames = session.run(
        kill_count=200, flag_state=_flags(negaya_appeased=True), resonance=0.8
    )
    assert outcome == MeditationOutcome.COMPLETED
    assert len(breath.dream_calibrations) == 1


# ── Calibration perk effects ──────────────────────────────────────────────────

def _calibrate(active_perks: frozenset[str], resonance: float = 0.5):
    """Run a full calibration session with the given perks."""
    session = DreamCalibrationSession(game_id="7_KLGS", active_perks=active_perks)
    for phase in (CalibrationTongue.SAKURA, CalibrationTongue.ROSE, CalibrationTongue.LOTUS):
        for _ in range(3):
            session.respond(resonance)
    return session.complete()


def test_depth_meditation_boosts_lotus_and_rose():
    base  = _calibrate(frozenset())
    boosted = _calibrate(frozenset({"depth_meditation"}))
    assert boosted.lotus_density > base.lotus_density
    assert boosted.rose_density  > base.rose_density


def test_depth_meditation_does_not_boost_sakura():
    base    = _calibrate(frozenset())
    boosted = _calibrate(frozenset({"depth_meditation"}))
    assert boosted.sakura_density == base.sakura_density


def test_infernal_meditation_boosts_sakura():
    base    = _calibrate(frozenset())
    boosted = _calibrate(frozenset({"infernal_meditation"}))
    assert boosted.sakura_density > base.sakura_density


def test_infernal_meditation_does_not_boost_lotus_or_rose():
    base    = _calibrate(frozenset())
    boosted = _calibrate(frozenset({"infernal_meditation"}))
    assert boosted.lotus_density == base.lotus_density
    assert boosted.rose_density  == base.rose_density


def test_transcendental_meditation_boosts_all_phases():
    base    = _calibrate(frozenset())
    boosted = _calibrate(frozenset({"transcendental_meditation"}))
    assert boosted.sakura_density > base.sakura_density
    assert boosted.rose_density   > base.rose_density
    assert boosted.lotus_density  > base.lotus_density


def test_depth_and_infernal_stack():
    # Both together: Lotus/Rose boosted by depth, Sakura boosted by infernal
    base      = _calibrate(frozenset())
    both      = _calibrate(frozenset({"depth_meditation", "infernal_meditation"}))
    depth_only = _calibrate(frozenset({"depth_meditation"}))
    infernal_only = _calibrate(frozenset({"infernal_meditation"}))
    assert both.lotus_density   == depth_only.lotus_density
    assert both.sakura_density  == infernal_only.sakura_density


def test_transcendental_stacks_with_specialist_perks():
    # Transcendental +0.05 stacks on top of depth +0.08 for Lotus/Rose
    depth_only  = _calibrate(frozenset({"depth_meditation"}))
    both        = _calibrate(frozenset({"depth_meditation", "transcendental_meditation"}))
    assert both.lotus_density  > depth_only.lotus_density
    assert both.sakura_density > depth_only.sakura_density   # transcendental adds to Sakura too


def test_calibration_perks_recorded_in_result():
    perks = frozenset({"depth_meditation", "infernal_meditation"})
    cal   = _calibrate(perks)
    assert cal.active_perks == perks


def test_no_perks_records_empty_frozenset():
    cal = _calibrate(frozenset())
    assert cal.active_perks == frozenset()


def test_non_calibration_perks_do_not_affect_density():
    # breathwork, alchemical, hypnotic, zen — sanity only, no calibration boost
    for perk in ("breathwork_meditation", "alchemical_meditation",
                 "hypnotic_meditation", "zen_meditation"):
        base    = _calibrate(frozenset())
        with_perk = _calibrate(frozenset({perk}))
        assert with_perk.sakura_density == base.sakura_density, perk
        assert with_perk.rose_density   == base.rose_density,   perk
        assert with_perk.lotus_density  == base.lotus_density,  perk


# ── Sanity delta computation ──────────────────────────────────────────────────

def test_no_perks_no_delta():
    delta = compute_session_sanity_delta(frozenset(), {})
    assert delta == {}


def test_breathwork_delta():
    delta = compute_session_sanity_delta(frozenset({"breathwork_meditation"}), {})
    assert abs(delta["terrestrial"] - 0.04) < 1e-9
    assert abs(delta["alchemical"]  - 0.03) < 1e-9


def test_alchemical_base_delta_no_alchemy_skill():
    delta = compute_session_sanity_delta(frozenset({"alchemical_meditation"}), {})
    assert abs(delta["alchemical"] - 0.06) < 1e-9   # rank 0 → no synergy


def test_alchemical_synergy_at_max_rank():
    delta = compute_session_sanity_delta(frozenset({"alchemical_meditation"}), {"alchemy": 50})
    assert abs(delta["alchemical"] - 0.12) < 1e-9   # 0.06 × (1 + 50/50) = 0.12


def test_alchemical_synergy_at_half_rank():
    delta = compute_session_sanity_delta(frozenset({"alchemical_meditation"}), {"alchemy": 25})
    assert abs(delta["alchemical"] - 0.09) < 1e-9   # 0.06 × (1 + 25/50) = 0.09


def test_hypnotic_delta():
    delta = compute_session_sanity_delta(frozenset({"hypnotic_meditation"}), {})
    assert abs(delta["narrative"] - 0.04) < 1e-9
    assert abs(delta["cosmic"]    - 0.02) < 1e-9


def test_depth_delta_all_dims():
    delta = compute_session_sanity_delta(frozenset({"depth_meditation"}), {})
    for dim in ("alchemical", "narrative", "terrestrial", "cosmic"):
        assert abs(delta[dim] - 0.03) < 1e-9, dim


def test_infernal_delta():
    delta = compute_session_sanity_delta(frozenset({"infernal_meditation"}), {})
    assert abs(delta["cosmic"] - 0.08) < 1e-9


def test_transcendental_delta():
    delta = compute_session_sanity_delta(frozenset({"transcendental_meditation"}), {})
    assert abs(delta["cosmic"] - 0.05) < 1e-9


def test_zen_delta():
    delta = compute_session_sanity_delta(frozenset({"zen_meditation"}), {})
    assert abs(delta["narrative"] - 0.05) < 1e-9


def test_all_7_perks_accumulate():
    all_perks = frozenset({
        "breathwork_meditation", "alchemical_meditation", "hypnotic_meditation",
        "depth_meditation", "infernal_meditation", "transcendental_meditation",
        "zen_meditation",
    })
    delta = compute_session_sanity_delta(all_perks, {"alchemy": 50})
    # cosmic: hypnotic 0.02 + depth 0.03 + infernal 0.08 + transcendental 0.05 = 0.18
    assert abs(delta["cosmic"] - 0.18) < 1e-9
    # narrative: hypnotic 0.04 + depth 0.03 + zen 0.05 = 0.12
    assert abs(delta["narrative"] - 0.12) < 1e-9
    # alchemical: breathwork 0.03 + alchemical 0.12 (synergy, rank 50) + depth 0.03 = 0.18
    assert abs(delta["alchemical"] - 0.18) < 1e-9
    # terrestrial: breathwork 0.04 + depth 0.03 = 0.07
    assert abs(delta["terrestrial"] - 0.07) < 1e-9


def test_run_completed_passes_perks_to_calibration():
    breath = BreathOfKo()
    session = MeditationSession(breath)
    perks = frozenset({"depth_meditation", "infernal_meditation"})
    session.run(kill_count=0, flag_state=_flags(), active_perks=perks, resonance=0.5)
    cal = breath.dream_calibrations[0]
    assert cal.active_perks == perks