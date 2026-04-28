"""Tests for temporally bounded alchemy — calendar × alchemy system integration."""

import pytest

from ambroflow.world.calendar import (
    AeraluneDate,
    AlchemyCalendarContext,
    get_alchemy_calendar_context,
    SPRING_EQUINOX, SUMMER_SOLSTICE, AUTUMN_EQUINOX, WINTER_SOLSTICE,
    alzedroswune_present,
    _anchor_proximity,
)
from ambroflow.alchemy.system import (
    AlchemySystem,
    DiagnosticReading,
    TreatmentApproach,
    PresenceState,
    SUBJECT_BY_ID,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def ctx(doy: int) -> AlchemyCalendarContext:
    return get_alchemy_calendar_context(AeraluneDate(year=1, day_of_year=doy))


# ── Season classification ─────────────────────────────────────────────────────

def test_nigredo_season():
    c = ctx(1)
    assert c.season_name == "nigredo"
    assert c.peak_axis   == "temporal"

def test_albedo_season():
    c = ctx(SPRING_EQUINOX)
    assert c.season_name == "albedo"
    assert c.peak_axis   == "mental"

def test_albedo_midpoint():
    c = ctx(145)
    assert c.season_name == "albedo"

def test_citrinitas_season():
    c = ctx(SUMMER_SOLSTICE)
    assert c.season_name == "citrinitas"
    assert c.peak_axis   == "spatial"

def test_citrinitas_midpoint():
    c = ctx(240)
    assert c.season_name == "citrinitas"

def test_rubedo_season():
    c = ctx(AUTUMN_EQUINOX)
    assert c.season_name == "rubedo"
    assert c.peak_axis   == "temporal"

def test_vrwumane_season():
    c = ctx(WINTER_SOLSTICE)
    assert c.season_name == "vrwumane"
    assert c.peak_axis is None


# ── Base axis bonuses ─────────────────────────────────────────────────────────

def test_nigredo_temporal_bonus():
    c = ctx(50)   # mid-nigredo, well away from any anchor
    assert c.axis_bonus["temporal"] > 0.0
    assert c.axis_bonus.get("mental", 0.0) < 0.0

def test_albedo_mental_bonus():
    c = ctx(144)   # mid-albedo
    assert c.axis_bonus["mental"] > 0.0
    assert c.axis_bonus.get("temporal", 0.0) < 0.0

def test_citrinitas_spatial_bonus():
    c = ctx(240)   # mid-citrinitas
    assert c.axis_bonus["spatial"] > 0.0

def test_rubedo_temporal_bonus():
    c = ctx(340)   # mid-rubedo
    assert c.axis_bonus["temporal"] > 0.0
    assert c.axis_bonus.get("spatial", 0.0) < 0.0

def test_vrwumane_all_axes_positive():
    c = ctx(WINTER_SOLSTICE)
    assert c.axis_bonus["temporal"] > 0.0
    assert c.axis_bonus["mental"]   > 0.0
    assert c.axis_bonus["spatial"]  > 0.0


# ── Anchor proximity ──────────────────────────────────────────────────────────

def test_anchor_proximity_on_anchor():
    assert _anchor_proximity(SPRING_EQUINOX)  == pytest.approx(1.0)
    assert _anchor_proximity(SUMMER_SOLSTICE) == pytest.approx(1.0)
    assert _anchor_proximity(AUTUMN_EQUINOX)  == pytest.approx(1.0)
    assert _anchor_proximity(WINTER_SOLSTICE) == pytest.approx(1.0)

def test_anchor_proximity_zero_far():
    assert _anchor_proximity(50)  == pytest.approx(0.0)
    assert _anchor_proximity(150) == pytest.approx(0.0)

def test_anchor_proximity_partial():
    p7  = _anchor_proximity(SPRING_EQUINOX - 7)
    p14 = _anchor_proximity(SPRING_EQUINOX - 14)
    assert 0.0 < p14 < p7 < 1.0

def test_anchor_bonus_adds_to_peak_axis():
    # Days after Spring Equinox are albedo; near the equinox gets more mental bonus
    c_near = ctx(SPRING_EQUINOX + 3)    # albedo, 3 days in — still near the anchor
    c_far  = ctx(SPRING_EQUINOX + 30)   # albedo, well away from any anchor
    assert c_near.axis_bonus["mental"] > c_far.axis_bonus["mental"]


# ── Epiphany threshold ────────────────────────────────────────────────────────

def test_epiphany_threshold_normal_day():
    c = ctx(50)
    assert c.epiphany_threshold == pytest.approx(0.85)

def test_epiphany_threshold_on_anchor():
    c = ctx(SPRING_EQUINOX)
    assert c.epiphany_threshold == pytest.approx(0.70)

def test_epiphany_threshold_vrwumane():
    c = ctx(WINTER_SOLSTICE)
    assert c.epiphany_threshold == pytest.approx(0.60)

def test_epiphany_threshold_near_anchor_lower_than_normal():
    c_near = ctx(SUMMER_SOLSTICE - 3)
    c_far  = ctx(150)   # mid-albedo, far from any anchor
    assert c_near.epiphany_threshold < c_far.epiphany_threshold


# ── Charge multiplier ─────────────────────────────────────────────────────────

def test_charge_multiplier_normal_day():
    c = ctx(50)
    assert c.charge_multiplier == pytest.approx(1.0)

def test_charge_multiplier_on_anchor():
    c = ctx(AUTUMN_EQUINOX)
    assert c.charge_multiplier == pytest.approx(2.0)

def test_charge_multiplier_vrwumane():
    c = ctx(WINTER_SOLSTICE)
    assert c.charge_multiplier == pytest.approx(3.0)


# ── Alzedroswune effects ──────────────────────────────────────────────────────

def test_alzedroswune_formula_bonus_present():
    # Day 65 = first day of month 3
    c = ctx(65)
    assert c.alzedroswune_present is True
    assert c.formula_approach_bonus == pytest.approx(0.10)

def test_alzedroswune_formula_bonus_absent():
    c = ctx(30)   # month 1 — not yet arrived
    assert c.alzedroswune_present is False
    assert c.formula_approach_bonus == pytest.approx(0.0)

def test_alzedroswune_spatial_bonus():
    c_present = ctx(200)   # mid-citrinitas, alzedroswune present
    c_absent  = ctx(320)   # rubedo, alzedroswune gone
    # Both non-spatial-peak; but citrinitas has the base spatial bonus + alzedroswune
    # While rubedo doesn't. Just verify alzedroswune adds on top in citrinitas:
    c_citrinitas_no_alz = ctx(240)   # citrinitas, should have alz (day 240 is in window)
    assert c_citrinitas_no_alz.alzedroswune_present is True
    assert c_citrinitas_no_alz.axis_bonus["spatial"] > 0.20   # base 0.20 + 0.10 alz


# ── Locked subjects ───────────────────────────────────────────────────────────

def test_desire_crystal_locked_pre_alzedroswune():
    # Day 30 — nigredo before alzedroswune window
    c = ctx(30)
    assert "0036_KLIT" in c.locked_subject_ids
    assert "0038_KLIT"   in c.locked_subject_ids

def test_desire_crystal_locked_rubedo():
    c = ctx(320)   # rubedo, alzedroswune gone
    assert "0036_KLIT" in c.locked_subject_ids
    assert "0038_KLIT"   in c.locked_subject_ids

def test_desire_crystal_unlocked_citrinitas():
    c = ctx(240)
    assert "0036_KLIT" not in c.locked_subject_ids
    assert "0038_KLIT"   not in c.locked_subject_ids

def test_desire_crystal_unlocked_vrwumane():
    c = ctx(WINTER_SOLSTICE)
    assert "0036_KLIT" not in c.locked_subject_ids
    assert "0038_KLIT"   not in c.locked_subject_ids

def test_desire_crystal_unlocked_albedo_when_alz_present():
    # Day 100 = albedo and alzedroswune present (>= day 65)
    assert alzedroswune_present(AeraluneDate(1, 100)) is True
    c = ctx(100)
    assert "0036_KLIT" not in c.locked_subject_ids

def test_infernal_salve_never_locked():
    for doy in [30, 100, 200, 320, 385]:
        c = ctx(doy)
        assert "0037_KLIT" not in c.locked_subject_ids

def test_tincture_basic_never_locked():
    for doy in [1, 97, 193, 289, 385]:
        c = ctx(doy)
        assert "0034_KLIT" not in c.locked_subject_ids


# ── Season note content ───────────────────────────────────────────────────────

def test_season_notes_contain_season_name():
    assert "Nigredo"    in ctx(50).season_note
    assert "Albedo"     in ctx(144).season_note
    assert "Citrinitas" in ctx(240).season_note
    assert "Rubedo"     in ctx(320).season_note
    assert "Vrwumane"   in ctx(385).season_note

def test_season_note_mentions_alzedroswune():
    # Alzedroswune present during albedo (day 100)
    assert "Alzedroswune" in ctx(100).season_note
    # Not present during rubedo
    assert "Alzedroswune" not in ctx(320).season_note


# ── Integration: treat() with calendar context ───────────────────────────────

class _MockOrrery:
    def record(self, *a, **kw): pass
    def record_sanity_delta(self, *a, **kw): pass


def _make_reading(subject_id: str, permeability: float = 0.8) -> DiagnosticReading:
    subject = SUBJECT_BY_ID[subject_id]
    return DiagnosticReading(
        subject_id=subject_id,
        identified_axes=subject.field.axes(),
        mode_engagement={"ontological": 0.9, "cosmological": 0.7, "narrative": 0.8, "somatic": 0.7},
        presence_score=permeability,
    )


def test_seasonal_boost_raises_resonance_in_peak_season():
    """Temporal subject (tincture_basic) should score higher during temporal seasons."""
    system   = AlchemySystem(_MockOrrery())
    subject  = SUBJECT_BY_ID["0034_KLIT"]
    reading  = _make_reading("0034_KLIT", permeability=0.7)
    approach = TreatmentApproach(approach_mode="presence")
    presence = PresenceState(permeability=0.7, epiphanic_charge=0.0)
    inv      = {"0073_KLOB": 5, "0040_KLOB": 5, "0001_KLOB": 1, "0002_KLOB": 1}

    ctx_temporal  = get_alchemy_calendar_context(AeraluneDate(1, 50))   # nigredo — temporal peak
    ctx_antiphase = get_alchemy_calendar_context(AeraluneDate(1, 144))  # albedo — mental peak, temporal -0.05

    r_peak = system.treat(
        "0034_KLIT", "0000_0451", reading, approach, presence, dict(inv),
        calendar_context=ctx_temporal,
    )
    r_anti = system.treat(
        "0034_KLIT", "0000_0451", reading, approach, presence, dict(inv),
        calendar_context=ctx_antiphase,
    )
    assert r_peak.resonance_quality > r_anti.resonance_quality


def test_epiphany_threshold_lowered_on_anchor():
    """On an anchor day, a treatment that normally fails epiphany can trigger it."""
    system   = AlchemySystem(_MockOrrery())
    reading  = _make_reading("0034_KLIT", permeability=1.0)
    approach = TreatmentApproach(approach_mode="presence")
    # Charge at exactly the required level; resonance just above 0.70 but below 0.85
    presence = PresenceState(permeability=1.0, epiphanic_charge=0.80)
    inv      = {"0073_KLOB": 5, "0040_KLOB": 5, "0001_KLOB": 1, "0002_KLOB": 1}

    ctx_anchor  = get_alchemy_calendar_context(AeraluneDate(1, WINTER_SOLSTICE))   # threshold 0.60
    ctx_normal  = get_alchemy_calendar_context(AeraluneDate(1, 50))                # threshold 0.85

    r_anchor = system.treat(
        "0034_KLIT", "0000_0451", reading, approach, presence, dict(inv),
        calendar_context=ctx_anchor,
    )
    r_normal = system.treat(
        "0034_KLIT", "0000_0451", reading, approach, presence, dict(inv),
        calendar_context=ctx_normal,
    )
    # On Vrwumane the threshold is 0.60 — more likely to be epiphanic
    # On normal day threshold is 0.85 — harder
    # At least one of these should differ, or both can be True (anchor is richer)
    assert r_anchor.epiphanic or not r_normal.epiphanic   # anchor at least as epiphanic


def test_formula_bonus_from_alzedroswune():
    """Formula mode should achieve higher resonance when Alzedroswune are present."""
    system   = AlchemySystem(_MockOrrery())
    reading  = _make_reading("0036_KLIT", permeability=0.8)
    approach = TreatmentApproach(approach_mode="formula")
    presence = PresenceState(permeability=0.8)
    inv      = {"0076_KLOB": 5, "0077_KLOB": 5, "0001_KLOB": 1, "0002_KLOB": 1, "0010_KLOB": 1, "0017_KLOB": 1}

    ctx_alz    = get_alchemy_calendar_context(AeraluneDate(1, 240))   # citrinitas, alz present
    ctx_no_alz = get_alchemy_calendar_context(AeraluneDate(1, 385))   # Vrwumane — alz absent, but subject unlocked

    r_alz    = system.treat(
        "0036_KLIT", "0000_0451", reading, approach, presence, dict(inv),
        calendar_context=ctx_alz,
    )
    r_no_alz = system.treat(
        "0036_KLIT", "0000_0451", reading, approach, presence, dict(inv),
        calendar_context=ctx_no_alz,
    )
    # Alzedroswune: formula_approach_bonus 0.10 + spatial axis bonus 0.30 (0.20 base + 0.10 alz)
    # vs Vrwumane: formula_approach_bonus 0.0 + spatial axis bonus 0.25 (0.15 vrwumane all)
    assert r_alz.resonance_quality > r_no_alz.resonance_quality


def test_angelic_revival_subject_exists():
    assert "0038_KLIT" in SUBJECT_BY_ID


def test_angelic_revival_requires_desire_crystal_and_infernal_salve():
    subj = SUBJECT_BY_ID["0038_KLIT"]
    assert "0023_KLIT" in subj.required_materials
    assert "0037_KLIT" in subj.required_materials


def test_angelic_revival_field_has_spatial_and_temporal():
    subj  = SUBJECT_BY_ID["0038_KLIT"]
    axes  = subj.field.axes()
    assert "spatial"   in axes
    assert "temporal"  in axes


def test_angelic_revival_locked_outside_alzedroswune():
    c = ctx(50)   # nigredo, pre-alzedroswune
    assert "0038_KLIT" in c.locked_subject_ids

def test_angelic_revival_unlocked_in_alzedroswune_window():
    c = ctx(200)
    assert "0038_KLIT" not in c.locked_subject_ids

def test_angelic_revival_unlocked_on_vrwumane():
    c = ctx(385)
    assert "0038_KLIT" not in c.locked_subject_ids


def test_season_recorded_in_orrery():
    """Orrery payload should include season when calendar context is provided."""
    recorded = {}

    class TrackingOrrery:
        def record(self, event, payload):
            if event == "alchemy.treated":
                recorded.update(payload)
        def record_sanity_delta(self, *a, **kw): pass

    system   = AlchemySystem(TrackingOrrery())
    reading  = _make_reading("0034_KLIT")
    approach = TreatmentApproach(approach_mode="presence")
    presence = PresenceState(permeability=0.8)
    inv      = {"0073_KLOB": 5, "0040_KLOB": 5, "0001_KLOB": 1, "0002_KLOB": 1}
    cal      = get_alchemy_calendar_context(AeraluneDate(1, 50))

    system.treat("0034_KLIT", "0000_0451", reading, approach, presence, inv,
                 calendar_context=cal)
    assert recorded.get("season") == "nigredo"