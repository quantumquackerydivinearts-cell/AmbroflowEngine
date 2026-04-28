"""Tests for the presence-based alchemy system."""

import pytest
from ambroflow.alchemy.system import (
    AlchemySystem,
    DiagnosticReading,
    FieldProperty,
    InformationField,
    ItemProvenance,
    PresenceState,
    RecipeBook,
    TreatmentApproach,
    SUBJECT_BY_ID,
    _EPIPHANY_THRESHOLD,
    _EPIPHANIC_CHARGE_REQ,
    _FIELD_TRANSFORM_THRESH,
    _MATERIALS_ABSENT_CAP,
    _RECIPE_DISCOVERY_THRESH,
    _SOURCE_INTENSITY_MOD,
    _REALM_AXIS_AFFINITY,
    _aggregate_provenance_mod,
    consume_provenance,
)


class _MockOrrery:
    def __init__(self):
        self.events = []

    def record(self, kind, payload):
        self.events.append((kind, payload))

    def record_sanity_delta(self, **kwargs):
        self.events.append(("sanity_delta", kwargs))


def _make_system():
    return AlchemySystem(orrery=_MockOrrery())


def _full_reading(subject_id, axes):
    """A reading with full mode engagement and presence."""
    return DiagnosticReading(
        subject_id=subject_id,
        identified_axes=frozenset(axes),
        mode_engagement={
            "ontological":  1.0,
            "cosmological": 1.0,
            "narrative":    1.0,
            "somatic":      1.0,
        },
        presence_score=1.0,
        false_axes=frozenset(),
    )


def _partial_reading(subject_id, axes):
    """A reading with moderate engagement — intuition level."""
    return DiagnosticReading(
        subject_id=subject_id,
        identified_axes=frozenset(axes),
        mode_engagement={
            "ontological":  0.5,
            "cosmological": 0.5,
            "narrative":    0.4,
            "somatic":      0.3,
        },
        presence_score=0.5,
    )


def _formula_reading(subject_id):
    """A reading with no axis identification and minimal engagement."""
    return DiagnosticReading(
        subject_id=subject_id,
        identified_axes=frozenset(),
        mode_engagement={"narrative": 0.2},
        presence_score=0.2,
    )


# ── Subject registry ──────────────────────────────────────────────────────────

def test_known_subjects_exist():
    for sid in ("0034_KLIT", "0035_KLIT", "0036_KLIT", "0037_KLIT"):
        assert sid in SUBJECT_BY_ID


def test_each_subject_has_field_properties():
    for subject in SUBJECT_BY_ID.values():
        assert len(subject.field.properties) > 0


def test_field_properties_have_three_authored_modes():
    """FieldProperty has shygazun, narrative, somatic — NOT dragon_tongue."""
    for subject in SUBJECT_BY_ID.values():
        for prop in subject.field.properties:
            assert prop.shygazun
            assert prop.narrative
            assert prop.somatic
            # dragon_tongue must NOT be an attribute — it's a kernel register, not authored
            assert not hasattr(prop, "dragon_tongue"), (
                "dragon_tongue must not be an authored FieldProperty field; "
                "it is derived from the shygazun word via the kernel register"
            )


def test_field_engagement_modes_are_correct():
    """The four engagement modes are ontological/cosmological/narrative/somatic."""
    reading = _full_reading("0034_KLIT", {"temporal"})
    for mode in ("ontological", "cosmological", "narrative", "somatic"):
        assert mode in reading.mode_engagement
    # Old dragon_tongue mode must not appear
    assert "dragon_tongue" not in reading.mode_engagement


# ── Resonance calculation ─────────────────────────────────────────────────────

def test_full_presence_full_diagnosis_high_resonance():
    a = _make_system()
    subject  = SUBJECT_BY_ID["0034_KLIT"]
    reading  = _full_reading("0034_KLIT", subject.field.axes())
    approach = TreatmentApproach(approach_mode="presence")
    presence = PresenceState(permeability=1.0)
    inv      = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}

    resonance, _ = a.calculate_resonance(subject, reading, approach, presence, inv)
    assert resonance >= 0.85


def test_formula_approach_reduces_resonance():
    a       = _make_system()
    subject = SUBJECT_BY_ID["0034_KLIT"]
    reading  = _full_reading("0034_KLIT", subject.field.axes())
    presence = PresenceState(permeability=1.0)
    inv      = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}

    r_presence, _ = a.calculate_resonance(subject, reading, TreatmentApproach("presence"), presence, inv)
    r_formula,  _ = a.calculate_resonance(subject, reading, TreatmentApproach("formula"),  presence, inv)

    assert r_formula < r_presence


def test_false_axis_identification_penalises_resonance():
    a       = _make_system()
    subject = SUBJECT_BY_ID["0034_KLIT"]
    presence = PresenceState(permeability=1.0)
    inv      = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}

    clean_reading = _full_reading("0034_KLIT", subject.field.axes())
    noisy_reading = DiagnosticReading(
        subject_id="0034_KLIT",
        identified_axes=subject.field.axes(),
        false_axes=frozenset({"spatial", "mental"}),
        mode_engagement={
            "ontological": 1.0, "cosmological": 1.0, "narrative": 1.0, "somatic": 1.0
        },
        presence_score=1.0,
    )

    r_clean, _ = a.calculate_resonance(subject, clean_reading, TreatmentApproach("presence"), presence, inv)
    r_noisy, _ = a.calculate_resonance(subject, noisy_reading, TreatmentApproach("presence"), presence, inv)

    assert r_noisy < r_clean


def test_missing_materials_caps_resonance():
    a       = _make_system()
    subject = SUBJECT_BY_ID["0034_KLIT"]
    reading = _full_reading("0034_KLIT", subject.field.axes())
    presence = PresenceState(permeability=1.0)

    resonance, _ = a.calculate_resonance(
        subject, reading, TreatmentApproach("presence"), presence,
        inventory={},
    )
    assert resonance <= _MATERIALS_ABSENT_CAP


def test_low_permeability_reduces_resonance():
    a       = _make_system()
    subject = SUBJECT_BY_ID["0034_KLIT"]
    reading = _full_reading("0034_KLIT", subject.field.axes())
    inv     = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}

    r_high, _ = a.calculate_resonance(subject, reading, TreatmentApproach("presence"),
                                      PresenceState(permeability=1.0), inv)
    r_low,  _ = a.calculate_resonance(subject, reading, TreatmentApproach("presence"),
                                      PresenceState(permeability=0.0), inv)
    assert r_low < r_high


# ── Treatment outcomes ────────────────────────────────────────────────────────

def test_resonant_treatment_produces_output():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    result = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
    )
    assert result.success
    assert inv.get("0034_KLIT", 0) >= 1


def test_resonant_treatment_consumes_materials():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
    )
    assert inv.get("0073_KLOB", 0) == 0
    assert inv.get("0040_KLOB", 0) == 0


def test_epiphanic_result_requires_charge_and_resonance():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}

    # High resonance but no charge → not epiphanic
    result = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0, epiphanic_charge=0.0),
        inventory=inv,
    )
    assert not result.epiphanic

    # High resonance AND sufficient charge → epiphanic
    inv2 = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    result2 = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0, epiphanic_charge=_EPIPHANIC_CHARGE_REQ),
        inventory=inv2,
    )
    assert result2.epiphanic
    assert inv2.get("0034_KLIT", 0) == 2   # enhanced output


def test_epiphanic_result_has_contagion_radius():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    result = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0, epiphanic_charge=_EPIPHANIC_CHARGE_REQ, mania_level=1.0),
        inventory=inv,
    )
    assert result.epiphanic
    assert result.contagion_radius > 0.0


def test_non_epiphanic_result_has_no_contagion():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    result = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0, epiphanic_charge=0.0),
        inventory=inv,
    )
    assert result.contagion_radius == 0.0


def test_formula_approach_with_correct_materials_still_low_resonance():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    result = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_formula_reading("0034_KLIT"),
        approach=TreatmentApproach("formula"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
    )
    assert result.resonance_quality < 0.50


def test_field_transformed_above_threshold():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    result = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0, epiphanic_charge=0.0),
        inventory=inv,
    )
    assert result.field_transformed == (result.resonance_quality >= _FIELD_TRANSFORM_THRESH)


# ── Sanity delta ──────────────────────────────────────────────────────────────

def test_ontological_engagement_gives_alchemical_sanity():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    reading = DiagnosticReading(
        subject_id="0034_KLIT",
        identified_axes=frozenset({"temporal"}),
        mode_engagement={"ontological": 1.0, "cosmological": 0.0, "narrative": 0.0, "somatic": 0.0},
        presence_score=0.8,
    )
    result = a.treat("0034_KLIT", "test", reading, TreatmentApproach("presence"),
                     PresenceState(permeability=1.0), inv)
    assert result.sanity_delta.get("alchemical", 0.0) > 0.0


def test_cosmological_engagement_gives_cosmic_sanity():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    reading = DiagnosticReading(
        subject_id="0034_KLIT",
        identified_axes=frozenset({"temporal"}),
        mode_engagement={"ontological": 0.0, "cosmological": 1.0, "narrative": 0.0, "somatic": 0.0},
        presence_score=0.8,
    )
    result = a.treat("0034_KLIT", "test", reading, TreatmentApproach("presence"),
                     PresenceState(permeability=1.0), inv)
    assert result.sanity_delta.get("cosmic", 0.0) > 0.0


def test_epiphanic_sanity_delta_larger_than_base():
    a = _make_system()

    base_reading = _full_reading("0034_KLIT", {"temporal"})
    inv1 = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    base_result = a.treat("0034_KLIT", "test", base_reading, TreatmentApproach("presence"),
                          PresenceState(permeability=1.0, epiphanic_charge=0.0), inv1)

    inv2 = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    epic_result = a.treat("0034_KLIT", "test", base_reading, TreatmentApproach("presence"),
                          PresenceState(permeability=1.0, epiphanic_charge=_EPIPHANIC_CHARGE_REQ), inv2)

    base_total = sum(base_result.sanity_delta.values())
    epic_total = sum(epic_result.sanity_delta.values())
    assert epic_total > base_total


# ── Mode insights ─────────────────────────────────────────────────────────────

def test_mode_insights_reported_for_high_engagement():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    reading = DiagnosticReading(
        subject_id="0034_KLIT",
        identified_axes=frozenset({"temporal"}),
        mode_engagement={
            "ontological":  0.9,
            "cosmological": 0.8,
            "narrative":    0.3,
            "somatic":      0.2,
        },
        presence_score=0.8,
    )
    result = a.treat("0034_KLIT", "test", reading, TreatmentApproach("presence"),
                     PresenceState(permeability=1.0), inv)
    assert "ontological"  in result.mode_insights
    assert "cosmological" in result.mode_insights
    assert "narrative"    not in result.mode_insights


# ── Orrery recording ──────────────────────────────────────────────────────────

def test_treatment_recorded_to_orrery():
    orrery = _MockOrrery()
    a      = AlchemySystem(orrery=orrery)
    inv    = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    a.treat("0034_KLIT", "test", _full_reading("0034_KLIT", {"temporal"}),
            TreatmentApproach("presence"), PresenceState(permeability=1.0), inv)

    kinds = [e[0] for e in orrery.events]
    assert "alchemy.treated" in kinds


# ── Unknown subject ───────────────────────────────────────────────────────────

def test_unknown_subject_fails_gracefully():
    a      = _make_system()
    result = a.treat("nonexistent", "test", _formula_reading("nonexistent"),
                     TreatmentApproach("formula"), PresenceState(), {})
    assert not result.success
    assert "Unknown subject" in result.reason


# ── Available subjects ────────────────────────────────────────────────────────

def test_available_subjects_with_materials():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    available = a.available_subjects(inv)
    ids = [s.id for s in available]
    assert "0034_KLIT" in ids


def test_unavailable_subject_without_materials():
    a   = _make_system()
    available = a.available_subjects({})
    ids = [s.id for s in available]
    assert "0034_KLIT" not in ids


# ── Presence delta ────────────────────────────────────────────────────────────

def test_epiphanic_presence_delta_resets_charge():
    delta = AlchemySystem.derive_presence_delta(resonance=0.95, epiphanic=True)
    assert delta.epiphanic_charge_delta == -1.0


def test_good_result_builds_epiphanic_charge():
    delta = AlchemySystem.derive_presence_delta(resonance=0.70, epiphanic=False)
    assert delta.epiphanic_charge_delta > 0.0


# ── Provenance ────────────────────────────────────────────────────────────────

def test_realm_aligned_provenance_boosts_modifier():
    """Sulphera-sourced materials give a bonus for temporal-axis fields."""
    subject = SUBJECT_BY_ID["0034_KLIT"]   # temporal axis
    assert "temporal" in subject.field.axes()
    assert _REALM_AXIS_AFFINITY["sulphera"] == "temporal"

    store_aligned = {
        "0073_KLOB": [ItemProvenance(realm_id="sulphera", source_type="foraged", quantity=2)],
        "0040_KLOB": [ItemProvenance(realm_id="sulphera", source_type="foraged", quantity=1)],
    }
    store_neutral = {
        "0073_KLOB": [ItemProvenance(realm_id="lapidus",  source_type="purchased", quantity=2)],
        "0040_KLOB": [ItemProvenance(realm_id="lapidus",  source_type="purchased", quantity=1)],
    }

    mod_aligned = _aggregate_provenance_mod(
        subject.field.axes(), subject.required_materials, store_aligned
    )
    mod_neutral = _aggregate_provenance_mod(
        subject.field.axes(), subject.required_materials, store_neutral
    )

    assert mod_aligned > mod_neutral


def test_foraged_beats_purchased():
    subject = SUBJECT_BY_ID["0034_KLIT"]
    store_foraged = {
        "0073_KLOB": [ItemProvenance(realm_id="lapidus", source_type="foraged",   quantity=2)],
        "0040_KLOB": [ItemProvenance(realm_id="lapidus", source_type="foraged",   quantity=1)],
    }
    store_purchased = {
        "0073_KLOB": [ItemProvenance(realm_id="lapidus", source_type="purchased", quantity=2)],
        "0040_KLOB": [ItemProvenance(realm_id="lapidus", source_type="purchased", quantity=1)],
    }
    mod_foraged   = _aggregate_provenance_mod(subject.field.axes(), subject.required_materials, store_foraged)
    mod_purchased = _aggregate_provenance_mod(subject.field.axes(), subject.required_materials, store_purchased)
    assert mod_foraged > mod_purchased


def test_provenance_modifier_applied_to_resonance():
    """High-provenance materials produce higher resonance than no-provenance."""
    a       = _make_system()
    subject = SUBJECT_BY_ID["0034_KLIT"]
    # Use partial engagement so resonance has headroom below 1.0 for provenance to boost.
    reading = _partial_reading("0034_KLIT", subject.field.axes())
    presence = PresenceState(permeability=0.7)
    inv_base = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    inv_prov = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}

    # Aligned (sulphera → temporal), foraged — should give modifier > 1.0
    store_high = {
        "0073_KLOB": [ItemProvenance(realm_id="sulphera", source_type="foraged",   quantity=2)],
        "0040_KLOB": [ItemProvenance(realm_id="sulphera", source_type="inherited", quantity=1)],
    }

    r_no_prov,  _   = a.calculate_resonance(subject, reading, TreatmentApproach("presence"),
                                             presence, inv_base, provenance_store=None)
    r_high_prov, mod = a.calculate_resonance(subject, reading, TreatmentApproach("presence"),
                                              presence, inv_prov, provenance_store=store_high)

    # The modifier itself must be > 1.0 (alignment + foraged)
    assert mod > 1.0
    # And the resonance must be strictly higher (partial reading leaves room to boost)
    assert r_no_prov < 1.0, "test precondition: partial reading must not already saturate"
    assert r_high_prov > r_no_prov


def test_provenance_consumed_on_treat():
    """Materials consumed from provenance store when treatment succeeds."""
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    store = {
        "0073_KLOB": [ItemProvenance(realm_id="lapidus", source_type="foraged", quantity=2)],
        "0040_KLOB": [ItemProvenance(realm_id="lapidus", source_type="foraged", quantity=1)],
    }

    a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
        provenance_store=store,
    )

    # Both materials should be consumed from provenance store
    assert "0073_KLOB" not in store
    assert "0040_KLOB"  not in store


def test_partial_provenance_consume():
    """Consuming 1 of 3 leaves 2 remaining in the store."""
    store = {
        "0073_KLOB": [ItemProvenance(realm_id="lapidus", source_type="foraged", quantity=3)],
    }
    consume_provenance("0073_KLOB", 1, store)
    assert store["0073_KLOB"][0].quantity == 2


def test_provenance_missing_still_works():
    """treat() works without provenance_store — backward compatible."""
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    result = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
    )
    assert result.success
    assert result.provenance_modifier == 1.0


# ── Discovered recipes ────────────────────────────────────────────────────────

def test_recipe_discovered_at_sufficient_resonance():
    a    = _make_system()
    book = RecipeBook()
    inv  = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}

    result = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
        recipe_book=book,
    )

    # Full presence should exceed _RECIPE_DISCOVERY_THRESH
    assert result.resonance_quality >= _RECIPE_DISCOVERY_THRESH
    assert result.recipe_discovered
    assert book.is_known("0034_KLIT")


def test_recipe_not_discovered_at_low_resonance():
    a    = _make_system()
    book = RecipeBook()
    inv  = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}

    result = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_formula_reading("0034_KLIT"),
        approach=TreatmentApproach("formula"),
        presence=PresenceState(permeability=0.0),
        inventory=inv,
        recipe_book=book,
    )

    assert result.resonance_quality < _RECIPE_DISCOVERY_THRESH
    assert not result.recipe_discovered
    assert not book.is_known("0034_KLIT")


def test_recipe_not_re_discovered():
    """Second discovery at same subject returns recipe_discovered=False."""
    a    = _make_system()
    book = RecipeBook()

    for _ in range(2):
        inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
        result = a.treat(
            subject_id="0034_KLIT",
            actor_id="test",
            reading=_full_reading("0034_KLIT", {"temporal"}),
            approach=TreatmentApproach("presence"),
            presence=PresenceState(permeability=1.0),
            inventory=inv,
            recipe_book=book,
        )

    # Second call: already known, so recipe_discovered is False
    assert not result.recipe_discovered
    assert book.is_known("0034_KLIT")


def test_recipe_book_contains_correct_materials():
    a    = _make_system()
    book = RecipeBook()
    inv  = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}

    a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
        recipe_book=book,
    )

    recipe = book.get("0034_KLIT")
    assert recipe is not None
    assert recipe.required_materials == {"0073_KLOB": 2, "0040_KLOB": 1}
    assert "0034_KLIT" in recipe.output_items


def test_recipe_orrery_event_on_first_discovery():
    orrery = _MockOrrery()
    a      = AlchemySystem(orrery=orrery)
    book   = RecipeBook()
    inv    = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}

    a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
        recipe_book=book,
    )

    kinds = [e[0] for e in orrery.events]
    assert "alchemy.recipe_discovered" in kinds


def test_no_recipe_book_no_discovery_event():
    orrery = _MockOrrery()
    a      = AlchemySystem(orrery=orrery)
    inv    = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}

    a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
        # no recipe_book
    )

    kinds = [e[0] for e in orrery.events]
    assert "alchemy.recipe_discovered" not in kinds


# ── Apparatus (required_objects) ─────────────────────────────────────────────

def test_missing_apparatus_hard_blocks_treatment():
    a   = _make_system()
    # All materials present but no Mortar or Pestle
    inv = {"0073_KLOB": 2, "0040_KLOB": 1}
    result = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
    )
    assert not result.success
    assert "missing_apparatus" in result.reason


def test_apparatus_not_consumed_on_treatment():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
    )
    # Materials consumed; apparatus remains
    assert inv.get("0001_KLOB", 0) == 1
    assert inv.get("0002_KLOB", 0) == 1


def test_available_subjects_excludes_missing_apparatus():
    a   = _make_system()
    # All materials for Basic Tincture present but no apparatus
    inv = {"0073_KLOB": 2, "0040_KLOB": 1}
    ids = [s.id for s in a.available_subjects(inv)]
    assert "0034_KLIT" not in ids


def test_available_subjects_includes_when_apparatus_present():
    a   = _make_system()
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1, "0002_KLOB": 1}
    ids = [s.id for s in a.available_subjects(inv)]
    assert "0034_KLIT" in ids


def test_partial_apparatus_still_blocks():
    a   = _make_system()
    # Mortar present but Pestle missing
    inv = {"0073_KLOB": 2, "0040_KLOB": 1, "0001_KLOB": 1}
    result = a.treat(
        subject_id="0034_KLIT",
        actor_id="test",
        reading=_full_reading("0034_KLIT", {"temporal"}),
        approach=TreatmentApproach("presence"),
        presence=PresenceState(permeability=1.0),
        inventory=inv,
    )
    assert not result.success
    assert "0002_KLOB" in result.reason


def test_subject_required_objects_are_klob_ids():
    for subj in SUBJECT_BY_ID.values():
        for oid in subj.required_objects:
            assert oid.endswith("_KLOB"), f"{subj.id}: apparatus ID {oid!r} must be _KLOB"