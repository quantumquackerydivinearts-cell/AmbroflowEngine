"""Tests for the laboratory process simulator."""

import pytest
from ambroflow.alchemy.laboratory import (
    LaboratorySession,
    SubstanceState,
    OperationDef,
    OperationResult,
    OPERATIONS,
    OP_BY_ID,
    SUBSTANCE_DEFAULTS,
    _T,
    _E,
    _BOTCH_THRESHOLD,
    _AXIS_ID_THRESHOLD,
    _PRESENCE_THRESHOLD,
    _INTUITION_THRESHOLD,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

MORTAR_PESTLE = frozenset({_E.MORTAR, _E.PESTLE})
FULL_LAB = frozenset({
    _E.MORTAR, _E.PESTLE, _E.RAG, _E.RETORT, _E.VOLUME_FLASK,
    _E.REAGENT_BOTTLE, _E.SAND, _E.REFINED_SAND, _E.FURNACE,
    _E.BELLOWS, _E.CRUCIBLE, _E.JAR, _E.DIATOM_EARTH,
    _E.RING_MOLD, _E.INGOT_MOLD,
})

HERB_SUBSTANCE   = SubstanceState.default_for("0073_KLOB")   # Herb (Common): Alive, Usable, Movable, Flammable
IRON_SUBSTANCE   = SubstanceState.default_for("2002_KLOB")   # Iron: Usable, Movable, Inert
SULPHUR_SUBST    = SubstanceState.default_for("1007_KLOB")   # Sulphur: Usable, Movable, Flammable, Poisonous

FULL_VITRIOL   = {"V": 1.0, "I": 1.0, "T": 1.0, "R": 1.0, "O": 1.0, "L": 1.0}
ZERO_VITRIOL   = {"V": 0.0, "I": 0.0, "T": 0.0, "R": 0.0, "O": 0.0, "L": 0.0}
EXPERT_RANK    = 100
NOVICE_RANK    = 15
ZERO_RANK      = 0


def _session(
    subject_id="0034_KLIT",
    equipment=FULL_LAB,
    substance=None,
    actor_id="test_actor",
):
    if substance is None:
        substance = HERB_SUBSTANCE
    return LaboratorySession(subject_id, equipment, substance, actor_id)


# ── Operation registry ────────────────────────────────────────────────────────

def test_all_operations_have_required_fields():
    for op in OPERATIONS:
        assert op.op_id
        assert op.name
        assert op.vitriol_letter in ("V", "I", "T", "R", "O", "L")
        assert op.field_axis in ("mental", "temporal", "spatial")
        assert op.engagement_mode in ("ontological", "cosmological", "narrative", "somatic")
        assert 0.0 <= op.engagement_weight <= 1.0
        assert 0.0 <= op.base_difficulty <= 1.0


def test_op_by_id_covers_all_operations():
    for op in OPERATIONS:
        assert op.op_id in OP_BY_ID
        assert OP_BY_ID[op.op_id] is op


def test_no_duplicate_op_ids():
    ids = [op.op_id for op in OPERATIONS]
    assert len(ids) == len(set(ids))


def test_distillation_variants_present():
    assert "distillation_sand" in OP_BY_ID
    assert "distillation_refined" in OP_BY_ID
    # Refined sand variant should be lower difficulty
    assert OP_BY_ID["distillation_refined"].base_difficulty < OP_BY_ID["distillation_sand"].base_difficulty


def test_both_casting_variants_present():
    assert "ring_casting" in OP_BY_ID
    assert "ingot_casting" in OP_BY_ID


def test_equipment_ids_end_with_klob():
    for op in OPERATIONS:
        for eid in op.required_equipment:
            assert eid.endswith("_KLOB"), f"{op.op_id}: equipment {eid!r} must end with _KLOB"


# ── SubstanceState ────────────────────────────────────────────────────────────

def test_default_for_known_substance():
    herb = SubstanceState.default_for("0073_KLOB")
    assert herb.has_trait(_T.ALIVE)
    assert herb.has_trait(_T.FLAMMABLE)
    assert herb.has_trait(_T.USABLE)


def test_default_for_unknown_substance_is_generic_usable():
    unknown = SubstanceState.default_for("9999_KLOB")
    assert unknown.has_trait(_T.USABLE)
    assert unknown.has_trait(_T.MOVABLE)


def test_with_traits_add_and_remove():
    herb = SubstanceState.default_for("0073_KLOB")
    calcined = herb.with_traits(
        add=frozenset({_T.DEAD, _T.POWDERED}),
        remove=frozenset({_T.ALIVE, _T.FLAMMABLE}),
    )
    assert calcined.has_trait(_T.DEAD)
    assert calcined.has_trait(_T.POWDERED)
    assert not calcined.has_trait(_T.ALIVE)
    assert not calcined.has_trait(_T.FLAMMABLE)


def test_with_traits_purity_delta():
    s = SubstanceState.default_for("0073_KLOB")
    assert s.purity == 0.5
    s2 = s.with_traits(purity_delta=0.20)
    assert abs(s2.purity - 0.70) < 1e-9
    s3 = s2.with_traits(purity_delta=0.50)
    assert s3.purity == 1.0  # clamped


def test_with_traits_purity_clamped_at_zero():
    s = SubstanceState.default_for("0073_KLOB")
    s2 = s.with_traits(purity_delta=-1.0)
    assert s2.purity == 0.0


def test_has_all_and_has_none():
    s = SubstanceState.default_for("0073_KLOB")
    assert s.has_all(frozenset({_T.ALIVE, _T.USABLE}))
    assert not s.has_all(frozenset({_T.MOLTEN}))
    assert s.has_none(frozenset({_T.MOLTEN, _T.DEAD}))
    assert not s.has_none(frozenset({_T.ALIVE}))


def test_trait_names_returns_strings():
    herb = SubstanceState.default_for("0073_KLOB")
    names = herb.trait_names()
    assert isinstance(names, list)
    assert "Alive" in names
    assert "Flammable" in names


def test_substance_defaults_all_have_usable():
    for obj_id, traits in SUBSTANCE_DEFAULTS.items():
        assert _T.USABLE in traits, f"{obj_id} should start with USABLE"


# ── Skill check ───────────────────────────────────────────────────────────────

def test_expert_rank_easy_op_high_quality():
    quality = LaboratorySession._skill_check(EXPERT_RANK, 1.0, 0.15)
    assert quality >= 0.85


def test_zero_rank_easy_op_low_quality():
    quality = LaboratorySession._skill_check(ZERO_RANK, 0.0, 0.15)
    assert quality < _BOTCH_THRESHOLD


def test_expert_rank_hard_op_still_succeeds():
    quality = LaboratorySession._skill_check(EXPERT_RANK, 1.0, 0.55)
    assert quality >= _AXIS_ID_THRESHOLD


def test_novice_rank_hard_op_botches():
    quality = LaboratorySession._skill_check(NOVICE_RANK, 0.0, 0.55)
    assert quality < _AXIS_ID_THRESHOLD


def test_vitriol_score_lifts_quality():
    q_low  = LaboratorySession._skill_check(50, 0.0, 0.30)
    q_high = LaboratorySession._skill_check(50, 1.0, 0.30)
    assert q_high > q_low


def test_quality_always_in_range():
    for rank in (0, 20, 50, 80, 100):
        for vit in (0.0, 0.5, 1.0):
            for diff in (0.15, 0.30, 0.40, 0.55):
                q = LaboratorySession._skill_check(rank, vit, diff)
                assert 0.0 <= q <= 1.0, f"rank={rank} vit={vit} diff={diff} → q={q}"


# ── Available operations ──────────────────────────────────────────────────────

def test_grinding_available_for_herb_with_mortar_pestle():
    sess = _session(equipment=MORTAR_PESTLE, substance=HERB_SUBSTANCE)
    available = [op.op_id for op in sess.available_operations()]
    assert "grinding" in available


def test_grinding_not_available_without_pestle():
    sess = _session(equipment=frozenset({_E.MORTAR}), substance=HERB_SUBSTANCE)
    available = [op.op_id for op in sess.available_operations()]
    assert "grinding" not in available


def test_calcination_available_for_herb_with_furnace_crucible():
    sess = _session(
        equipment=frozenset({_E.FURNACE, _E.CRUCIBLE}),
        substance=HERB_SUBSTANCE,
    )
    available = [op.op_id for op in sess.available_operations()]
    assert "calcination" in available


def test_smelting_available_for_inert_metal():
    sess = _session(
        equipment=frozenset({_E.FURNACE, _E.CRUCIBLE, _E.BELLOWS}),
        substance=IRON_SUBSTANCE,
    )
    available = [op.op_id for op in sess.available_operations()]
    assert "smelting" in available


def test_smelting_not_available_for_herb():
    sess = _session(
        equipment=frozenset({_E.FURNACE, _E.CRUCIBLE, _E.BELLOWS}),
        substance=HERB_SUBSTANCE,   # ALIVE and FLAMMABLE — forbidden for smelting
    )
    available = [op.op_id for op in sess.available_operations()]
    assert "smelting" not in available


def test_dissolution_not_available_before_grinding():
    sess = _session(equipment=FULL_LAB, substance=HERB_SUBSTANCE)
    available = [op.op_id for op in sess.available_operations()]
    assert "dissolution" not in available   # Herb is not Powdered yet


def test_dissolution_available_after_grinding():
    sess = _session(equipment=FULL_LAB, substance=HERB_SUBSTANCE)
    sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    available = [op.op_id for op in sess.available_operations()]
    assert "dissolution" in available


def test_distillation_not_available_before_dissolution():
    sess = _session(equipment=FULL_LAB, substance=HERB_SUBSTANCE)
    sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    available = [op.op_id for op in sess.available_operations()]
    # Not Full yet — dissolution not done
    assert "distillation_sand" not in available


def test_unusable_substance_blocks_all_operations():
    dead_substance = SubstanceState(
        object_id="0073_KLOB",
        traits=frozenset({_T.UNUSABLE, _T.DEAD}),
    )
    sess = _session(equipment=FULL_LAB, substance=dead_substance)
    assert sess.available_operations() == []


def test_coagulation_available_only_when_molten():
    molten = SubstanceState(
        object_id="2002_KLOB",
        traits=frozenset({_T.USABLE, _T.MOVABLE, _T.MOLTEN}),
    )
    sess = _session(equipment=FULL_LAB, substance=molten)
    available = [op.op_id for op in sess.available_operations()]
    assert "ring_casting" in available
    assert "ingot_casting" in available


# ── Perform — success cases ───────────────────────────────────────────────────

def test_grinding_adds_powdered_trait():
    sess = _session(equipment=MORTAR_PESTLE, substance=HERB_SUBSTANCE)
    result = sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    assert result.success
    assert result.new_substance.has_trait(_T.POWDERED)
    assert sess.substance.has_trait(_T.POWDERED)


def test_calcination_removes_alive_adds_dead():
    sess = _session(
        equipment=frozenset({_E.FURNACE, _E.CRUCIBLE}),
        substance=HERB_SUBSTANCE,
    )
    result = sess.perform("calcination", EXPERT_RANK, FULL_VITRIOL)
    assert result.success
    assert result.new_substance.has_trait(_T.DEAD)
    assert result.new_substance.has_trait(_T.POWDERED)
    assert not result.new_substance.has_trait(_T.ALIVE)
    assert not result.new_substance.has_trait(_T.FLAMMABLE)


def test_smelting_adds_molten_removes_inert():
    sess = _session(
        equipment=frozenset({_E.FURNACE, _E.CRUCIBLE, _E.BELLOWS}),
        substance=IRON_SUBSTANCE,
    )
    result = sess.perform("smelting", EXPERT_RANK, FULL_VITRIOL)
    assert result.success
    assert result.new_substance.has_trait(_T.MOLTEN)
    assert not result.new_substance.has_trait(_T.INERT)


def test_dissolution_adds_full_removes_powdered():
    powdered = HERB_SUBSTANCE.with_traits(
        add=frozenset({_T.POWDERED}),
        remove=frozenset({_T.ALIVE, _T.FLAMMABLE}),
    )
    sess = _session(equipment=frozenset({_E.VOLUME_FLASK}), substance=powdered)
    result = sess.perform("dissolution", EXPERT_RANK, FULL_VITRIOL)
    assert result.success
    assert result.new_substance.has_trait(_T.FULL)
    assert not result.new_substance.has_trait(_T.POWDERED)


def test_filtration_increases_purity():
    full_subst = SubstanceState(
        object_id="0073_KLOB",
        traits=frozenset({_T.USABLE, _T.MOVABLE, _T.FULL}),
        purity=0.5,
    )
    sess = _session(
        equipment=frozenset({_E.DIATOM_EARTH, _E.RAG}),
        substance=full_subst,
    )
    result = sess.perform("filtration", EXPERT_RANK, FULL_VITRIOL)
    assert result.success
    assert result.new_substance.purity > full_subst.purity


def test_distillation_increases_purity_more_than_filtration():
    full_subst = SubstanceState(
        object_id="0073_KLOB",
        traits=frozenset({_T.USABLE, _T.MOVABLE, _T.FULL}),
        purity=0.5,
    )
    eq_sand = frozenset({_E.RETORT, _E.FURNACE, _E.SAND})
    eq_filt = frozenset({_E.DIATOM_EARTH, _E.RAG})

    sess_d = _session(equipment=eq_sand,  substance=full_subst)
    sess_f = _session(equipment=eq_filt,  substance=full_subst)

    dist = sess_d.perform("distillation_sand",  EXPERT_RANK, FULL_VITRIOL)
    filt = sess_f.perform("filtration",          EXPERT_RANK, FULL_VITRIOL)

    assert dist.new_substance.purity > filt.new_substance.purity


def test_ring_casting_removes_molten_adds_inert():
    molten = SubstanceState(
        object_id="2003_KLOB",
        traits=frozenset({_T.USABLE, _T.MOVABLE, _T.MOLTEN}),
    )
    sess = _session(equipment=frozenset({_E.RING_MOLD}), substance=molten)
    result = sess.perform("ring_casting", EXPERT_RANK, FULL_VITRIOL)
    assert result.success
    assert not result.new_substance.has_trait(_T.MOLTEN)
    assert result.new_substance.has_trait(_T.INERT)


# ── Perform — failure cases ───────────────────────────────────────────────────

def test_perform_unknown_op_returns_failure():
    sess = _session()
    result = sess.perform("nonexistent_op", EXPERT_RANK, FULL_VITRIOL)
    assert not result.success
    assert "unknown_operation" in result.reason


def test_perform_missing_equipment_returns_failure():
    sess = _session(equipment=frozenset({_E.MORTAR}))   # Pestle missing
    result = sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    assert not result.success
    assert "missing_equipment" in result.reason
    assert _E.PESTLE in result.reason


def test_perform_missing_required_trait_returns_failure():
    # Substance is not Powdered — dissolution requires Powdered
    sess = _session(equipment=frozenset({_E.VOLUME_FLASK}), substance=HERB_SUBSTANCE)
    result = sess.perform("dissolution", EXPERT_RANK, FULL_VITRIOL)
    assert not result.success
    assert "missing_traits" in result.reason


def test_perform_forbidden_trait_returns_failure():
    # Substance has INERT (required by smelting) but ALSO ALIVE (which smelting forbids).
    # Forbidden-trait check must fire despite required traits being met.
    mixed = SubstanceState(
        object_id="2002_KLOB",
        traits=frozenset({_T.USABLE, _T.MOVABLE, _T.INERT, _T.ALIVE}),
    )
    sess = _session(
        equipment=frozenset({_E.FURNACE, _E.CRUCIBLE, _E.BELLOWS}),
        substance=mixed,
    )
    result = sess.perform("smelting", EXPERT_RANK, FULL_VITRIOL)
    assert not result.success
    assert "blocked_by_traits" in result.reason


def test_failed_perform_does_not_change_substance():
    sess = _session(equipment=frozenset({_E.MORTAR}))   # Pestle missing
    before = sess.substance
    sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    assert sess.substance is before


def test_failed_perform_not_added_to_history():
    sess = _session(equipment=frozenset({_E.MORTAR}))
    sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    assert len(sess.history) == 0


# ── Catastrophic botch ────────────────────────────────────────────────────────

def test_catastrophic_botch_adds_unusable():
    # Distillation at zero rank + zero vitriol botches catastrophically
    full_subst = SubstanceState(
        object_id="0073_KLOB",
        traits=frozenset({_T.USABLE, _T.MOVABLE, _T.FULL}),
        purity=0.5,
    )
    sess = _session(
        equipment=frozenset({_E.RETORT, _E.FURNACE, _E.SAND}),
        substance=full_subst,
    )
    result = sess.perform("distillation_sand", ZERO_RANK, ZERO_VITRIOL)
    assert result.catastrophic
    assert result.new_substance.has_trait(_T.UNUSABLE)


def test_catastrophic_botch_blocks_further_operations():
    full_subst = SubstanceState(
        object_id="0073_KLOB",
        traits=frozenset({_T.USABLE, _T.MOVABLE, _T.FULL}),
        purity=0.5,
    )
    sess = _session(
        equipment=FULL_LAB,
        substance=full_subst,
    )
    sess.perform("distillation_sand", ZERO_RANK, ZERO_VITRIOL)  # catastrophic
    assert sess.available_operations() == []


# ── Engagement accumulation ───────────────────────────────────────────────────

def test_grinding_contributes_to_somatic_mode():
    sess = _session(equipment=MORTAR_PESTLE, substance=HERB_SUBSTANCE)
    sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    reading, _ = sess.conclude()
    assert reading.mode_engagement.get("somatic", 0.0) > 0.0


def test_dissolution_contributes_to_ontological_mode():
    powdered = HERB_SUBSTANCE.with_traits(
        add=frozenset({_T.POWDERED}),
        remove=frozenset({_T.ALIVE, _T.FLAMMABLE}),
    )
    sess = _session(equipment=frozenset({_E.VOLUME_FLASK}), substance=powdered)
    sess.perform("dissolution", EXPERT_RANK, FULL_VITRIOL)
    reading, _ = sess.conclude()
    assert reading.mode_engagement.get("ontological", 0.0) > 0.0


def test_fermentation_contributes_to_cosmological_mode():
    sess = _session(equipment=frozenset({_E.JAR}), substance=HERB_SUBSTANCE)
    sess.perform("fermentation", EXPERT_RANK, FULL_VITRIOL)
    reading, _ = sess.conclude()
    assert reading.mode_engagement.get("cosmological", 0.0) > 0.0


def test_conjunction_contributes_to_narrative_mode():
    sess = _session(equipment=frozenset({_E.VOLUME_FLASK}), substance=HERB_SUBSTANCE)
    sess.perform("conjunction", EXPERT_RANK, FULL_VITRIOL)
    reading, _ = sess.conclude()
    assert reading.mode_engagement.get("narrative", 0.0) > 0.0


def test_mode_engagement_capped_at_one():
    sess = _session(equipment=MORTAR_PESTLE, substance=HERB_SUBSTANCE)
    # Perform grinding many times (should cap at 1.0)
    for _ in range(20):
        # Restore Powdered=False so grinding is available each time
        sess._substance = HERB_SUBSTANCE
        sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    reading, _ = sess.conclude()
    assert reading.mode_engagement.get("somatic", 0.0) <= 1.0


def test_high_skill_gives_higher_engagement_than_low_skill():
    powdered_herb = HERB_SUBSTANCE.with_traits(
        add=frozenset({_T.POWDERED}),
        remove=frozenset({_T.ALIVE, _T.FLAMMABLE}),
    )
    eq = frozenset({_E.VOLUME_FLASK})

    sess_expert = LaboratorySession("0034_KLIT", eq, powdered_herb, "expert")
    sess_novice = LaboratorySession("0034_KLIT", eq, powdered_herb, "novice")

    sess_expert.perform("dissolution", EXPERT_RANK, FULL_VITRIOL)
    sess_novice.perform("dissolution", NOVICE_RANK, ZERO_VITRIOL)

    r_expert, _ = sess_expert.conclude()
    r_novice, _ = sess_novice.conclude()

    assert (r_expert.mode_engagement.get("ontological", 0.0) >
            r_novice.mode_engagement.get("ontological", 0.0))


# ── Axis identification ───────────────────────────────────────────────────────

def test_grinding_identifies_temporal_axis():
    sess = _session(equipment=MORTAR_PESTLE, substance=HERB_SUBSTANCE)
    result = sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    assert result.axis_identified == "temporal"
    reading, _ = sess.conclude()
    assert "temporal" in reading.identified_axes


def test_dissolution_identifies_mental_axis():
    powdered = HERB_SUBSTANCE.with_traits(
        add=frozenset({_T.POWDERED}),
        remove=frozenset({_T.ALIVE, _T.FLAMMABLE}),
    )
    sess = _session(equipment=frozenset({_E.VOLUME_FLASK}), substance=powdered)
    result = sess.perform("dissolution", EXPERT_RANK, FULL_VITRIOL)
    assert result.axis_identified == "mental"


def test_conjunction_identifies_spatial_axis():
    sess = _session(equipment=frozenset({_E.VOLUME_FLASK}), substance=HERB_SUBSTANCE)
    result = sess.perform("conjunction", EXPERT_RANK, FULL_VITRIOL)
    assert result.axis_identified == "spatial"


def test_low_quality_does_not_identify_axis():
    # Novice + zero VITRIOL → quality will be below _AXIS_ID_THRESHOLD for grinding
    sess = _session(equipment=MORTAR_PESTLE, substance=HERB_SUBSTANCE)
    result = sess.perform("grinding", ZERO_RANK, ZERO_VITRIOL)
    assert result.axis_identified is None


def test_multiple_axes_identified_across_operations():
    powdered = HERB_SUBSTANCE.with_traits(
        add=frozenset({_T.POWDERED}),
        remove=frozenset({_T.ALIVE, _T.FLAMMABLE}),
    )
    eq = frozenset({_E.MORTAR, _E.PESTLE, _E.VOLUME_FLASK, _E.JAR})
    # Start with live herb for fermentation, then grind a separate one
    sess = LaboratorySession("0034_KLIT", eq, HERB_SUBSTANCE, "test")
    sess.perform("fermentation", EXPERT_RANK, FULL_VITRIOL)  # temporal
    sess.perform("conjunction", EXPERT_RANK, FULL_VITRIOL)   # spatial

    reading, _ = sess.conclude()
    assert "temporal" in reading.identified_axes
    assert "spatial" in reading.identified_axes


# ── conclude() → approach mode ────────────────────────────────────────────────

def test_expert_session_yields_presence_approach():
    sess = _session(equipment=MORTAR_PESTLE, substance=HERB_SUBSTANCE)
    sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    _, approach = sess.conclude()
    assert approach.approach_mode == "presence"


def test_novice_session_yields_formula_approach():
    sess = _session(equipment=MORTAR_PESTLE, substance=HERB_SUBSTANCE)
    sess.perform("grinding", ZERO_RANK, ZERO_VITRIOL)
    _, approach = sess.conclude()
    assert approach.approach_mode == "formula"


def test_empty_session_yields_formula_approach():
    sess = _session()
    _, approach = sess.conclude()
    assert approach.approach_mode == "formula"


def test_mid_rank_session_yields_intuition_approach():
    # Grinding at medium competence should yield intuition
    sess = _session(equipment=MORTAR_PESTLE, substance=HERB_SUBSTANCE)
    quality = LaboratorySession._skill_check(40, 0.3, 0.15)
    sess.perform("grinding", 40, {"T": 0.3})
    _, approach = sess.conclude()
    if _INTUITION_THRESHOLD <= quality < _PRESENCE_THRESHOLD:
        assert approach.approach_mode == "intuition"
    elif quality >= _PRESENCE_THRESHOLD:
        assert approach.approach_mode == "presence"
    else:
        assert approach.approach_mode == "formula"


# ── conclude() → DiagnosticReading ───────────────────────────────────────────

def test_conclude_reading_has_correct_subject_id():
    sess = _session(subject_id="0037_KLIT")
    reading, _ = sess.conclude()
    assert reading.subject_id == "0037_KLIT"


def test_conclude_reading_identified_axes_is_frozenset():
    sess = _session()
    reading, _ = sess.conclude()
    assert isinstance(reading.identified_axes, frozenset)


def test_conclude_presence_score_reflects_purity():
    # Higher purity substance → higher presence_score even with same skill
    low_purity = SubstanceState(
        object_id="0073_KLOB",
        traits=frozenset({_T.USABLE, _T.MOVABLE}),
        purity=0.1,
    )
    high_purity = SubstanceState(
        object_id="0073_KLOB",
        traits=frozenset({_T.USABLE, _T.MOVABLE}),
        purity=0.9,
    )
    # Empty sessions (no ops) — only purity differs
    sess_low  = LaboratorySession("0034_KLIT", FULL_LAB, low_purity,  "a")
    sess_high = LaboratorySession("0034_KLIT", FULL_LAB, high_purity, "b")

    r_low,  _ = sess_low.conclude()
    r_high, _ = sess_high.conclude()
    assert r_high.presence_score > r_low.presence_score


# ── Full sequence: herb → tincture path ──────────────────────────────────────

def test_full_herb_grinding_dissolution_sequence():
    """Herb → grind → dissolve: trait chain works end-to-end."""
    sess = _session(
        equipment=frozenset({_E.MORTAR, _E.PESTLE, _E.VOLUME_FLASK}),
        substance=HERB_SUBSTANCE,
    )
    # 1. Grind
    r1 = sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    assert r1.success
    assert sess.substance.has_trait(_T.POWDERED)

    # 2. Dissolve
    r2 = sess.perform("dissolution", EXPERT_RANK, FULL_VITRIOL)
    assert r2.success
    assert sess.substance.has_trait(_T.FULL)
    assert not sess.substance.has_trait(_T.POWDERED)

    # Session has engaged both somatic and ontological modes
    reading, approach = sess.conclude()
    assert reading.mode_engagement.get("somatic",     0.0) > 0.0
    assert reading.mode_engagement.get("ontological", 0.0) > 0.0
    assert approach.approach_mode == "presence"


def test_full_metal_smelt_cast_sequence():
    """Iron → smelt → ring cast: produces solid ring."""
    sess = _session(
        equipment=frozenset({_E.FURNACE, _E.CRUCIBLE, _E.BELLOWS, _E.RING_MOLD}),
        substance=IRON_SUBSTANCE,
    )
    r1 = sess.perform("smelting",     EXPERT_RANK, FULL_VITRIOL)
    assert r1.success
    assert sess.substance.has_trait(_T.MOLTEN)

    r2 = sess.perform("ring_casting", EXPERT_RANK, FULL_VITRIOL)
    assert r2.success
    assert not sess.substance.has_trait(_T.MOLTEN)
    assert sess.substance.has_trait(_T.INERT)


# ── Snapshot ──────────────────────────────────────────────────────────────────

def test_snapshot_returns_dict():
    sess = _session()
    sess.perform("grinding", EXPERT_RANK, FULL_VITRIOL)
    snap = sess.snapshot()
    assert isinstance(snap, dict)
    assert "subject_id" in snap
    assert "ops_performed" in snap
    assert snap["ops_performed"] == 1


def test_history_grows_with_successful_operations():
    sess = _session(equipment=FULL_LAB, substance=HERB_SUBSTANCE)
    assert len(sess.history) == 0
    sess.perform("grinding",     EXPERT_RANK, FULL_VITRIOL)
    sess.perform("dissolution",  EXPERT_RANK, FULL_VITRIOL)
    assert len(sess.history) == 2


# ── Integration: LaboratorySession → AlchemySystem ───────────────────────────

def test_lab_conclude_feeds_alchemy_system():
    """Full pipeline: lab session → DiagnosticReading → AlchemySystem.treat()."""
    from ambroflow.alchemy.system import AlchemySystem, PresenceState, SUBJECT_BY_ID

    class _MockOrrery:
        def __init__(self):
            self.events = []
        def record(self, kind, payload):
            self.events.append((kind, payload))
        def record_sanity_delta(self, **kwargs):
            self.events.append(("sanity_delta", kwargs))

    alchemy = AlchemySystem(orrery=_MockOrrery())

    # Build a lab session for Basic Tincture (0034_KLIT)
    # subject requires Herb (0073_KLOB) + Water (0040_KLOB), apparatus Mortar+Pestle
    subject = SUBJECT_BY_ID["0034_KLIT"]
    inventory = {
        "0073_KLOB": 2, "0040_KLOB": 1,
        "8000_KLOB": 1, "2000_KLOB": 1,  # Mortar + Pestle (apparatus)
    }

    # grinding (somatic 0.15) + dissolution (ontological 0.40) + filtration (ontological→1.0)
    # + conjunction (narrative 0.20) → mode_score ≈ 0.64 → resonance ≈ 0.64 > 0.50
    # so base_outputs fires and {"0034_KLIT": 1} is produced.
    sess = LaboratorySession(
        subject_id="0034_KLIT",
        available_equipment=frozenset({
            "8000_KLOB", "2000_KLOB",   # Mortar + Pestle
            "0004_KLOB",                # Volume Flask
            "1003_KLOB", "0001_KLOB",   # Diatom Earth + Rag
        }),
        starting_substance=SubstanceState.default_for("0073_KLOB"),
        actor_id="player",
    )
    sess.perform("grinding",    EXPERT_RANK, FULL_VITRIOL)   # somatic
    sess.perform("dissolution", EXPERT_RANK, FULL_VITRIOL)   # ontological — substance FULL
    sess.perform("filtration",  EXPERT_RANK, FULL_VITRIOL)   # ontological (caps at 1.0)
    sess.perform("conjunction", EXPERT_RANK, FULL_VITRIOL)   # narrative

    reading, approach = sess.conclude()

    presence = PresenceState(permeability=1.0)
    result = alchemy.treat(
        subject_id="0034_KLIT",
        actor_id="player",
        reading=reading,
        approach=approach,
        presence=presence,
        inventory=inventory,
    )

    # Grinding identified temporal axis; dissolution identified mental
    assert "temporal" in reading.identified_axes
    assert "mental"   in reading.identified_axes
    # Both operations at expert rank → presence approach
    assert approach.approach_mode == "presence"
    # Somatic + ontological engagement gives resonance > 0.25 → success
    assert result.success
    assert inventory.get("0034_KLIT", 0) >= 1
