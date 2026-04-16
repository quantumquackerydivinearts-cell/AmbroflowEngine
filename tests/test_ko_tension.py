"""
Tests for the VITRIOL tension system and Ko's dialogue lines.

The tension system encodes the gap between Ko's immutable initial reading
and the player's chosen profile. That gap is generative — not an error state.
"""

import pytest

from ambroflow.ko.calibration import (
    DreamCalibrationSession,
    CalibrationTongue,
    _stat_tier,
    get_assignment_line,
)
from ambroflow.ko.vitriol import assign_vitriol, VITRIOLProfile, VITRIOL_STATS
from ambroflow.ko.tension import (
    KoReading,
    TensionVector,
    VITRIOLTension,
    derive_tension,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _run_calibration(resonance: float = 0.7, game_id: str = "7_KLGS") -> object:
    session = DreamCalibrationSession(game_id=game_id)
    for _ in range(9):  # 3 phases × 3 responses
        session.respond(resonance)
    return session.complete()


def _make_ko_reading(resonance: float = 0.7, coil: float = 6.0) -> KoReading:
    cal = _run_calibration(resonance=resonance)
    profile = assign_vitriol(cal, coil_position=coil)
    return KoReading(
        profile=profile,
        calibration=cal,
        game_id="7_KLGS",
        coil_position=coil,
    )


def _make_profile(**overrides) -> VITRIOLProfile:
    """Build a VITRIOLProfile. Unspecified stats default to 4."""
    defaults = {s: 4 for s in VITRIOL_STATS}
    defaults.update(overrides)
    # Adjust to hit budget=31 if needed (tests override individually)
    return VITRIOLProfile(**defaults)


# ── TensionVector ─────────────────────────────────────────────────────────────

def test_tension_vector_aligned_when_within_one():
    v = TensionVector(stat="vitality", ko_value=5, player_value=5)
    assert v.tension_type == "aligned"
    assert v.magnitude == 0

    v2 = TensionVector(stat="vitality", ko_value=5, player_value=6)
    assert v2.tension_type == "aligned"
    assert v2.magnitude == 1


def test_tension_vector_elevated_when_player_higher():
    v = TensionVector(stat="levity", ko_value=3, player_value=7)
    assert v.tension_type == "elevated"
    assert v.delta == 4
    assert v.magnitude == 4


def test_tension_vector_suppressed_when_player_lower():
    v = TensionVector(stat="introspection", ko_value=8, player_value=3)
    assert v.tension_type == "suppressed"
    assert v.delta == -5
    assert v.magnitude == 4  # capped at 4


def test_tension_vector_magnitude_capped_at_four():
    v = TensionVector(stat="reflectivity", ko_value=1, player_value=10)
    assert v.magnitude == 4


def test_tension_vector_is_aligned_method():
    v = TensionVector(stat="vitality", ko_value=5, player_value=5)
    assert v.is_aligned()

    v2 = TensionVector(stat="vitality", ko_value=5, player_value=9)
    assert not v2.is_aligned()


# ── VITRIOLTension ────────────────────────────────────────────────────────────

def _build_tension(ko_vals: dict[str, int], player_vals: dict[str, int]) -> VITRIOLTension:
    vectors = {
        stat: TensionVector(stat=stat, ko_value=ko_vals[stat], player_value=player_vals[stat])
        for stat in VITRIOL_STATS
    }
    return VITRIOLTension(vectors=vectors)


def test_total_magnitude_zero_when_fully_aligned():
    vals = {s: 5 for s in VITRIOL_STATS}
    t = _build_tension(vals, vals)
    assert t.total_magnitude() == 0


def test_total_magnitude_sums_all_stats():
    ko     = {s: 5 for s in VITRIOL_STATS}
    player = {s: 2 for s in VITRIOL_STATS}   # all suppressed by 3
    t = _build_tension(ko, player)
    assert t.total_magnitude() == 3 * 7   # 3 per stat × 7 stats


def test_is_high_tension_threshold():
    ko     = {s: 5 for s in VITRIOL_STATS}
    # Two stats suppressed by 4 each = magnitude 8 = threshold
    player = dict(ko)
    player["vitality"]     = 1
    player["introspection"] = 1
    t = _build_tension(ko, player)
    assert t.total_magnitude() >= 8
    assert t.is_high_tension()


def test_is_not_high_tension_below_threshold():
    ko     = {s: 5 for s in VITRIOL_STATS}
    player = dict(ko)
    player["levity"] = 4   # magnitude 1 — well under threshold
    t = _build_tension(ko, player)
    assert not t.is_high_tension()


def test_alignment_count_all_aligned():
    vals = {s: 5 for s in VITRIOL_STATS}
    t = _build_tension(vals, vals)
    assert t.alignment_count() == 7


def test_alignment_count_partial():
    ko     = {s: 5 for s in VITRIOL_STATS}
    player = dict(ko)
    player["vitality"]     = 8
    player["introspection"] = 1
    t = _build_tension(ko, player)
    assert t.alignment_count() == 5


# ── Alchemy resonance modifier ────────────────────────────────────────────────

def test_aligned_reflectivity_gives_neutral_modifier():
    ko     = {s: 5 for s in VITRIOL_STATS}
    t = _build_tension(ko, ko)
    assert t.alchemy_resonance_mod("reflectivity") == pytest.approx(1.0)


def test_suppressed_reflectivity_lowers_modifier():
    ko     = {s: 5 for s in VITRIOL_STATS}
    player = dict(ko)
    player["reflectivity"] = 1   # suppressed by 4 → magnitude 4
    t = _build_tension(ko, player)
    mod = t.alchemy_resonance_mod("reflectivity")
    assert mod < 1.0
    assert mod == pytest.approx(0.80)   # 1.0 - 4 × 0.05


def test_elevated_reflectivity_boosts_modifier_slightly():
    ko     = {s: 5 for s in VITRIOL_STATS}
    player = dict(ko)
    player["reflectivity"] = 9   # elevated by 4 → magnitude 4
    t = _build_tension(ko, player)
    mod = t.alchemy_resonance_mod("reflectivity")
    assert mod > 1.0
    assert mod == pytest.approx(1.12)   # 1.0 + 4 × 0.03


def test_suppressed_modifier_floored_at_0_6():
    # Even a magnitude-10 suppression can't go below 0.6
    v = TensionVector(stat="reflectivity", ko_value=10, player_value=1)
    t = VITRIOLTension(vectors={"reflectivity": v})
    mod = t.alchemy_resonance_mod("reflectivity")
    assert mod >= 0.6


def test_elevated_modifier_capped_at_1_12():
    v = TensionVector(stat="reflectivity", ko_value=1, player_value=10)
    t = VITRIOLTension(vectors={"reflectivity": v})
    mod = t.alchemy_resonance_mod("reflectivity")
    assert mod <= 1.12


def test_non_reflectivity_stat_always_neutral_in_alchemy():
    ko     = {s: 5 for s in VITRIOL_STATS}
    player = dict(ko)
    player["vitality"] = 1   # large suppression, but not reflectivity
    t = _build_tension(ko, player)
    for stat in ("vitality", "introspection", "tactility", "ingenuity", "ostentation", "levity"):
        assert t.alchemy_resonance_mod(stat) == pytest.approx(1.0), (
            f"{stat} should not affect alchemy resonance mod"
        )


# ── Sanity bias ───────────────────────────────────────────────────────────────

def test_sanity_bias_zero_when_aligned():
    vals = {s: 5 for s in VITRIOL_STATS}
    t = _build_tension(vals, vals)
    bias = t.sanity_bias()
    for dim, val in bias.items():
        assert val == pytest.approx(0.0), f"{dim} bias should be 0 when aligned"


def test_introspection_tension_biases_narrative_and_alchemical():
    ko     = {s: 5 for s in VITRIOL_STATS}
    player = dict(ko)
    player["introspection"] = 1   # magnitude 4
    t = _build_tension(ko, player)
    bias = t.sanity_bias()
    assert bias["narrative"]  < 0
    assert bias["alchemical"] < 0
    # Terrestrial should be only the ingenuity spread (0)
    assert bias["terrestrial"] == pytest.approx(0.0)


def test_vitality_tension_biases_terrestrial():
    ko     = {s: 5 for s in VITRIOL_STATS}
    player = dict(ko)
    player["vitality"] = 1   # magnitude 4
    t = _build_tension(ko, player)
    bias = t.sanity_bias()
    assert bias["terrestrial"] < 0


def test_levity_tension_biases_cosmic():
    ko     = {s: 5 for s in VITRIOL_STATS}
    player = dict(ko)
    player["levity"] = 1   # magnitude 4
    t = _build_tension(ko, player)
    bias = t.sanity_bias()
    assert bias["cosmic"] < 0


# ── derive_tension ────────────────────────────────────────────────────────────

def test_derive_tension_zero_when_profiles_match():
    ko_reading = _make_ko_reading(resonance=0.7)
    # Use Ko's own profile as the player's choice
    tension = derive_tension(ko_reading, ko_reading.profile)
    assert tension.total_magnitude() == 0
    assert tension.alignment_count() == 7


def test_derive_tension_produces_seven_vectors():
    ko_reading = _make_ko_reading()
    player     = assign_vitriol(_run_calibration(resonance=0.3))  # different densities
    tension    = derive_tension(ko_reading, player)
    assert len(tension.vectors) == 7
    assert set(tension.vectors.keys()) == set(VITRIOL_STATS)


def test_derive_tension_stat_names_match():
    ko_reading = _make_ko_reading()
    player     = ko_reading.profile
    tension    = derive_tension(ko_reading, player)
    for stat, vec in tension.vectors.items():
        assert vec.stat == stat


def test_derive_tension_ko_value_matches_ko_profile():
    ko_reading = _make_ko_reading(resonance=0.8)
    ko_dict    = ko_reading.profile.as_dict()
    player     = ko_reading.profile
    tension    = derive_tension(ko_reading, player)
    for stat, vec in tension.vectors.items():
        assert vec.ko_value == ko_dict[stat]


# ── Ko's dialogue lines ───────────────────────────────────────────────────────

def test_game_7_has_three_opening_lines():
    lines = DreamCalibrationSession.GAME_OPENING_LINES["7_KLGS"]
    assert len(lines) == 3


def test_opening_first_line_is_pure_presence():
    first = DreamCalibrationSession.GAME_OPENING_LINES["7_KLGS"][0]
    assert first.strip() == "You are here."


def test_opening_last_line_establishes_reading_contract():
    last = DreamCalibrationSession.GAME_OPENING_LINES["7_KLGS"][-1]
    # Must name the reading and what drives it (you, not the questions)
    assert "reading" in last.lower()
    assert "you" in last.lower()


def test_game_7_has_three_closing_lines():
    lines = DreamCalibrationSession.GAME_CLOSING_LINES["7_KLGS"]
    assert len(lines) == 3


def test_closing_final_line_is_single_word():
    last = DreamCalibrationSession.GAME_CLOSING_LINES["7_KLGS"][-1]
    assert last.strip() == "Wake."


def test_closing_middle_line_names_the_gap():
    mid = DreamCalibrationSession.GAME_CLOSING_LINES["7_KLGS"][1]
    # Must acknowledge the gap between Ko's read and what the player will choose
    assert "distance" in mid.lower() or "gap" in mid.lower() or "between" in mid.lower()


def test_assignment_lines_cover_all_seven_stats():
    lines = DreamCalibrationSession.GAME_ASSIGNMENT_LINES["7_KLGS"]
    for stat in VITRIOL_STATS:
        assert stat in lines, f"Missing assignment lines for stat: {stat}"


def test_assignment_lines_have_all_three_tiers():
    lines = DreamCalibrationSession.GAME_ASSIGNMENT_LINES["7_KLGS"]
    for stat in VITRIOL_STATS:
        for tier in ("low", "mid", "high"):
            assert tier in lines[stat], f"Missing {tier} tier for stat: {stat}"
            assert lines[stat][tier].strip(), f"Empty line for {stat}/{tier}"


def test_assignment_lines_are_declarative():
    """Ko's lines state what IS — they do not use 'you have' or 'I give'."""
    lines = DreamCalibrationSession.GAME_ASSIGNMENT_LINES["7_KLGS"]
    forbidden_phrases = ["you have", "i give", "i assign", "you receive", "you get"]
    for stat, tiers in lines.items():
        for tier, line in tiers.items():
            line_lower = line.lower()
            for phrase in forbidden_phrases:
                assert phrase not in line_lower, (
                    f"Assignment line {stat}/{tier} contains performative phrase '{phrase}': {line!r}"
                )


# ── _stat_tier and get_assignment_line helpers ────────────────────────────────

def test_stat_tier_boundaries():
    assert _stat_tier(1)  == "low"
    assert _stat_tier(4)  == "low"
    assert _stat_tier(5)  == "mid"
    assert _stat_tier(7)  == "mid"
    assert _stat_tier(8)  == "high"
    assert _stat_tier(10) == "high"


def test_get_assignment_line_returns_string():
    line = get_assignment_line("7_KLGS", "vitality", 3)
    assert isinstance(line, str)
    assert len(line) > 0


def test_get_assignment_line_low_vitality():
    line = get_assignment_line("7_KLGS", "vitality", 2)
    assert "body" in line.lower()


def test_get_assignment_line_high_reflectivity():
    line = get_assignment_line("7_KLGS", "reflectivity", 9)
    assert "transformation" in line.lower() or "material" in line.lower()


def test_get_assignment_line_unknown_game_fallback():
    line = get_assignment_line("99_UNKNOWN", "vitality", 5)
    assert isinstance(line, str)
    assert "Vitality" in line or "vitality" in line.lower()


def test_get_assignment_line_all_stats_all_tiers_return_strings():
    for stat in VITRIOL_STATS:
        for value in (2, 6, 9):
            line = get_assignment_line("7_KLGS", stat, value)
            assert isinstance(line, str) and len(line) > 0, (
                f"Empty line for stat={stat}, value={value}"
            )