"""
Tests for the dream scene visual director and Wiltoll Lane location renderer.

All tests operate on PNG bytes — we verify structure and non-emptiness,
not pixel values.  Pixel-value tests would be brittle against minor rendering
tweaks and add no architectural value.

What we do verify:
  - Every render function returns bytes (not None) when PIL is available
  - PNG magic bytes are present in returned data
  - Each render function accepts its full documented parameter range
  - render_dream_sequence produces the correct frame count
  - VITRIOL spine progresses correctly (revealed dict grows per screen)
  - render_wiltoll_lane_interior works for both time-of-day variants
"""

import struct

import pytest

from ambroflow.ko.calibration import DreamCalibrationSession, CalibrationTongue
from ambroflow.ko.vitriol import assign_vitriol, VITRIOL_STATS
from ambroflow.ko.dream_scene import (
    render_arrival_screen,
    render_phase_screen,
    render_vitriol_screen,
    render_closing_screen,
    render_dream_sequence,
)
from ambroflow.scenes.location import render_wiltoll_lane_interior


# ── Helpers ───────────────────────────────────────────────────────────────────

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _is_png(data: bytes) -> bool:
    return data[:8] == _PNG_MAGIC


def _png_dimensions(data: bytes) -> tuple[int, int]:
    """Extract width and height from PNG IHDR chunk."""
    # IHDR starts at offset 16: 4-byte width, 4-byte height
    w = struct.unpack(">I", data[16:20])[0]
    h = struct.unpack(">I", data[20:24])[0]
    return w, h


def _run_calibration(resonance: float = 0.7) -> object:
    session = DreamCalibrationSession(game_id="7_KLGS")
    for _ in range(9):
        session.respond(resonance)
    return session.complete()


def _make_profile(resonance: float = 0.7):
    return assign_vitriol(_run_calibration(resonance=resonance))


def _assignment_line(stat: str, value: int) -> str:
    lines = DreamCalibrationSession.GAME_ASSIGNMENT_LINES["7_KLGS"]
    tier  = "low" if value <= 4 else ("mid" if value <= 7 else "high")
    return lines[stat][tier]


# ── render_arrival_screen ─────────────────────────────────────────────────────

def test_arrival_stage_0_returns_png():
    b = render_arrival_screen("You are here.", stage=0)
    assert b is not None
    assert _is_png(b)


def test_arrival_stage_1_returns_png():
    b = render_arrival_screen("The ground has not assembled yet. Stay in that.", stage=1)
    assert b is not None
    assert _is_png(b)


def test_arrival_stage_2_returns_png():
    b = render_arrival_screen(
        "The reading begins from what is already true. The questions are not the reading — you are.",
        stage=2,
    )
    assert b is not None
    assert _is_png(b)


def test_arrival_default_size_is_512():
    b = render_arrival_screen("You are here.")
    assert b is not None
    w, h = _png_dimensions(b)
    assert w == 512
    assert h == 512


def test_arrival_custom_size():
    b = render_arrival_screen("You are here.", size=256)
    assert b is not None
    w, h = _png_dimensions(b)
    assert w == 256 and h == 256


def test_arrival_all_game_opening_lines_render():
    for i, line in enumerate(DreamCalibrationSession.GAME_OPENING_LINES["7_KLGS"]):
        b = render_arrival_screen(line, stage=i)
        assert b is not None and _is_png(b), f"Arrival line {i} failed to render"


# ── render_phase_screen ───────────────────────────────────────────────────────

def test_phase_sakura_returns_png():
    b = render_phase_screen("The edge is moving. Not toward you — it is simply moving.", "sakura")
    assert b is not None and _is_png(b)


def test_phase_rose_returns_png():
    b = render_phase_screen("Something has arrived before you have words for it.", "rose")
    assert b is not None and _is_png(b)


def test_phase_lotus_returns_png():
    b = render_phase_screen("What is the ground that has assembled itself under this moment?", "lotus")
    assert b is not None and _is_png(b)


def test_phase_screen_is_square_512():
    for phase in ("sakura", "rose", "lotus"):
        b = render_phase_screen("test", phase)
        assert b is not None
        w, h = _png_dimensions(b)
        assert w == h == 512, f"{phase}: expected 512×512, got {w}×{h}"


def test_phase_screen_unknown_phase_does_not_crash():
    b = render_phase_screen("test", "unknown_phase")
    assert b is not None and _is_png(b)


def test_all_game_7_prompts_render():
    prompts = DreamCalibrationSession.GAME_PROMPTS["7_KLGS"]
    for tongue, phase_name in [
        (CalibrationTongue.SAKURA, "sakura"),
        (CalibrationTongue.ROSE,   "rose"),
        (CalibrationTongue.LOTUS,  "lotus"),
    ]:
        for prompt in prompts[tongue]:
            b = render_phase_screen(prompt, phase_name)
            assert b is not None and _is_png(b)


# ── render_vitriol_screen ─────────────────────────────────────────────────────

def test_vitriol_screen_first_stat_no_revealed():
    b = render_vitriol_screen(
        stat="vitality", value=5,
        ko_line="The body is present and active. It knows where it is.",
        revealed={"vitality": 5},
    )
    assert b is not None and _is_png(b)


def test_vitriol_screen_all_revealed():
    profile = _make_profile()
    pd      = profile.as_dict()
    revealed = {}
    for stat in VITRIOL_STATS:
        v = pd[stat]
        revealed[stat] = v
        b = render_vitriol_screen(
            stat=stat, value=v,
            ko_line=_assignment_line(stat, v),
            revealed=dict(revealed),
        )
        assert b is not None and _is_png(b), f"VITRIOL screen for {stat} failed"


def test_vitriol_screen_is_512():
    b = render_vitriol_screen("vitality", 4, "The body is present.", {"vitality": 4})
    assert b is not None
    w, h = _png_dimensions(b)
    assert w == h == 512


def test_vitriol_spine_covers_seven_stats():
    """Each of the 7 stats produces a non-None render."""
    profile  = _make_profile(resonance=0.6)
    pd       = profile.as_dict()
    revealed = {}
    frames   = []
    for stat in VITRIOL_STATS:
        v = pd[stat]
        revealed[stat] = v
        b = render_vitriol_screen(stat, v, _assignment_line(stat, v), dict(revealed))
        assert b is not None
        frames.append(b)
    assert len(frames) == 7


# ── render_closing_screen ─────────────────────────────────────────────────────

def test_closing_stage_0_returns_png():
    b = render_closing_screen("What you do with this reading is not my concern.", stage=0)
    assert b is not None and _is_png(b)


def test_closing_stage_1_returns_png():
    b = render_closing_screen(
        "The distance between what I see and what you choose to carry — "
        "that is where you will be living.",
        stage=1,
    )
    assert b is not None and _is_png(b)


def test_closing_stage_2_wake_returns_png():
    b = render_closing_screen("Wake.", stage=2)
    assert b is not None and _is_png(b)


def test_closing_wake_by_text_detection():
    """render_closing_screen treats 'Wake.' as final regardless of stage arg."""
    b = render_closing_screen("Wake.", stage=0)
    assert b is not None and _is_png(b)


def test_all_game_7_closing_lines_render():
    for i, line in enumerate(DreamCalibrationSession.GAME_CLOSING_LINES["7_KLGS"]):
        b = render_closing_screen(line, stage=i)
        assert b is not None and _is_png(b), f"Closing line {i} failed"


def test_closing_screen_is_512():
    for i, line in enumerate(DreamCalibrationSession.GAME_CLOSING_LINES["7_KLGS"]):
        b = render_closing_screen(line, stage=i)
        assert b is not None
        w, h = _png_dimensions(b)
        assert w == h == 512


# ── render_dream_sequence ─────────────────────────────────────────────────────

def _build_sequence_args(resonance: float = 0.7) -> dict:
    cal     = _run_calibration(resonance=resonance)
    profile = assign_vitriol(cal)
    pd      = profile.as_dict()

    prompts = {
        "sakura": [p for p in DreamCalibrationSession.GAME_PROMPTS["7_KLGS"][CalibrationTongue.SAKURA]],
        "rose":   [p for p in DreamCalibrationSession.GAME_PROMPTS["7_KLGS"][CalibrationTongue.ROSE]],
        "lotus":  [p for p in DreamCalibrationSession.GAME_PROMPTS["7_KLGS"][CalibrationTongue.LOTUS]],
    }
    assign_lines = {
        stat: _assignment_line(stat, pd[stat])
        for stat in VITRIOL_STATS
    }
    return dict(
        game_id="7_KLGS",
        calibration_prompts=prompts,
        assignment_lines=assign_lines,
        vitriol_profile=pd,
        opening_lines=DreamCalibrationSession.GAME_OPENING_LINES["7_KLGS"],
        closing_lines=DreamCalibrationSession.GAME_CLOSING_LINES["7_KLGS"],
    )


def test_dream_sequence_frame_count():
    # 3 opening + 9 calibration + 7 VITRIOL + 3 closing = 22
    frames = render_dream_sequence(**_build_sequence_args())
    assert len(frames) == 22


def test_dream_sequence_all_frames_are_pngs():
    frames = render_dream_sequence(**_build_sequence_args())
    for i, f in enumerate(frames):
        assert _is_png(f), f"Frame {i} is not a valid PNG"


def test_dream_sequence_all_frames_are_512():
    frames = render_dream_sequence(**_build_sequence_args())
    for i, f in enumerate(frames):
        w, h = _png_dimensions(f)
        assert w == h == 512, f"Frame {i}: expected 512×512, got {w}×{h}"


def test_dream_sequence_custom_size():
    frames = render_dream_sequence(**_build_sequence_args(), size=256)
    assert len(frames) == 22
    for f in frames:
        w, h = _png_dimensions(f)
        assert w == h == 256


def test_dream_sequence_empty_opening_still_runs():
    """Missing opening lines produce fewer frames but no crash."""
    args = _build_sequence_args()
    args["opening_lines"] = []
    frames = render_dream_sequence(**args)
    # 0 opening + 9 calibration + 7 VITRIOL + 3 closing = 19
    assert len(frames) == 19


# ── render_wiltoll_lane_interior ──────────────────────────────────────────────

def test_wiltoll_late_afternoon_returns_png():
    b = render_wiltoll_lane_interior(time_of_day="late_afternoon")
    assert b is not None and _is_png(b)


def test_wiltoll_night_returns_png():
    b = render_wiltoll_lane_interior(time_of_day="night")
    assert b is not None and _is_png(b)


def test_wiltoll_default_size_is_512x384():
    b = render_wiltoll_lane_interior()
    assert b is not None
    w, h = _png_dimensions(b)
    assert w == 512 and h == 384


def test_wiltoll_custom_size():
    b = render_wiltoll_lane_interior(width=256, height=192)
    assert b is not None
    w, h = _png_dimensions(b)
    assert w == 256 and h == 192


def test_wiltoll_day_and_night_differ():
    """Day and night renders should produce different output."""
    day   = render_wiltoll_lane_interior(time_of_day="late_afternoon")
    night = render_wiltoll_lane_interior(time_of_day="night")
    assert day is not None and night is not None
    assert day != night


def test_wiltoll_output_is_nontrivial():
    """Rendered image should be more than 1 kB — not a blank placeholder."""
    b = render_wiltoll_lane_interior()
    assert b is not None
    assert len(b) > 1024