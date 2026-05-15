"""
Tests for the SamosMyr ↔ Ambroflow bridge.
Covers parsing, Ga/Va operator extraction, [reversible] detection,
and cross-scene validation.
"""

import pytest
from ambroflow.quests.samosmyr_bridge import (
    parse_scene, SamosMyrScript, ClosureOp,
)


# ── Basic parsing ─────────────────────────────────────────────────────────────

def test_parses_ident_and_coherence():
    s = parse_scene("LoShun: Shakshi { }")
    assert s.ident == "LoShun"
    assert s.coherence == "Shakshi"


def test_parses_interior():
    s = parse_scene("LoShun: Shakshi(TaLaShaN) { }")
    assert s.interior == ["TaLaShaN"]


def test_parses_empty_body():
    s = parse_scene("LoShun: Shakshi { }")
    assert s.entity_specs == []
    assert s.closure_ops == []
    assert s.temporal is None


def test_parses_entity_words():
    s = parse_scene("LoShun: Shakshi { [Ao Ye] }")
    assert len(s.entity_specs) == 1
    assert "Ao" in s.entity_specs[0].words
    assert "Ye" in s.entity_specs[0].words


def test_parses_multiple_entity_specs():
    s = parse_scene("LoShun: Shakshi { [Ao Ye] [Ui Kiel] }")
    assert len(s.entity_specs) == 2


# ── [reversible] ──────────────────────────────────────────────────────────────

def test_reversible_absent_by_default():
    s = parse_scene("LoShun: Shakshi { [Ao] }")
    assert s.reversible is False


def test_reversible_detected():
    s = parse_scene("LoShun: Shakshi [reversible] { [Ao] }")
    assert s.reversible is True


def test_reversible_case_insensitive():
    s = parse_scene("LoShun: Shakshi [Reversible] { }")
    assert s.reversible is True


def test_reversible_without_body():
    s = parse_scene("LoShun: Shakshi [reversible]")
    assert s.reversible is True


# ── Ga / Va operators ─────────────────────────────────────────────────────────

def test_ga_operator_parsed():
    s = parse_scene("Soa: FrontierOpen { [Ga(LoShun) Ao] }")
    assert len(s.closure_ops) == 1
    assert s.closure_ops[0].op == "Ga"
    assert s.closure_ops[0].target == "LoShun"


def test_va_operator_parsed():
    s = parse_scene("YeShu: FrontierOpen { [Va(LoShun) Ao] }")
    assert len(s.closure_ops) == 1
    assert s.closure_ops[0].op == "Va"
    assert s.closure_ops[0].target == "LoShun"


def test_ga_does_not_set_hasParen_entity_spec_still_created():
    # A [Ga(X) Word] block: the Word should still form an entity spec
    s = parse_scene("Soa: FrontierOpen { [Ga(LoShun) Ao Ye] }")
    assert len(s.entity_specs) == 1
    assert "Ao" in s.entity_specs[0].words


def test_ga_only_block_no_entity_spec():
    # A [Ga(X)] block with no other words produces no entity spec
    s = parse_scene("Soa: FrontierOpen { [Ga(LoShun)] }")
    assert len(s.entity_specs) == 0
    assert len(s.closure_ops) == 1


def test_multiple_closure_ops():
    s = parse_scene("Soa: FrontierOpen { [Ga(A) Ga(B)] }")
    targets = {op.target for op in s.closure_ops}
    assert targets == {"A", "B"}


def test_mixed_ga_and_va_different_targets():
    s = parse_scene("Soa: FrontierOpen { [Ga(A) Va(B)] }")
    assert s.ga_targets == ["A"]
    assert s.va_targets == ["B"]


def test_closure_op_not_mistaken_for_temporal():
    s = parse_scene("Soa: FrontierOpen { [Ga(LoShun)] [TaShyMa(AonkielYeShu)] }")
    assert s.temporal is not None
    assert s.temporal["operator"] == "TaShyMa"
    assert len(s.closure_ops) == 1
    assert s.closure_ops[0].op == "Ga"


# ── Temporal closure ─────────────────────────────────────────────────────────

def test_tashyma_parsed():
    s = parse_scene("LoShun: Shakshi { [TaShyMa(AonkielYeShu)] }")
    assert s.temporal is not None
    assert s.temporal["operator"] == "TaShyMa"


def test_tashyma_does_not_produce_entity_spec():
    s = parse_scene("LoShun: Shakshi { [TaShyMa(AonkielYeShu)] }")
    assert len(s.entity_specs) == 0


# ── ga_targets / va_targets properties ───────────────────────────────────────

def test_ga_targets_property():
    s = parse_scene("Soa: FrontierOpen { [Ga(X) Ga(Y)] }")
    assert set(s.ga_targets) == {"X", "Y"}


def test_va_targets_property():
    s = parse_scene("YeShu: FrontierOpen { [Va(Z)] }")
    assert s.va_targets == ["Z"]


# ── Validation errors ─────────────────────────────────────────────────────────

def test_self_reference_raises():
    with pytest.raises(ValueError, match="self-reference"):
        parse_scene("LoShun: Shakshi { [Ga(LoShun)] }")


def test_contradictory_ga_va_same_target_raises():
    with pytest.raises(ValueError, match="contradictory"):
        parse_scene("Soa: FrontierOpen { [Ga(X) Va(X)] }")


# ── SamosMyrScript — cross-scene validation ───────────────────────────────────

def test_script_from_text_parses_multiple_scenes():
    src = """
LoShun: Shakshi [reversible] { [Ao Ye] }

Soa: FrontierOpen { [Ga(LoShun) Ao] }
"""
    script = SamosMyrScript.from_text(src)
    assert len(script.scenes) == 2


def test_script_validate_passes_valid_ga():
    src = """
LoShun: Shakshi { [Ao] }

Soa: FrontierOpen { [Ga(LoShun) Ye] }
"""
    script = SamosMyrScript.from_text(src)
    errors = script.validate()
    assert errors == []


def test_script_validate_fails_ga_missing_target():
    src = """
Soa: FrontierOpen { [Ga(NonExistent) Ao] }
"""
    script = SamosMyrScript.from_text(src)
    errors = script.validate()
    assert any("not found" in e for e in errors)


def test_script_validate_fails_va_non_reversible():
    src = """
LoShun: Shakshi { [Ao] }

YeShu: FrontierOpen { [Va(LoShun) Ye] }
"""
    script = SamosMyrScript.from_text(src)
    errors = script.validate()
    assert any("not declared [reversible]" in e for e in errors)


def test_script_validate_passes_va_reversible():
    src = """
LoShun: Shakshi [reversible] { [Ao] }

YeShu: FrontierOpen { [Va(LoShun) Ye] }
"""
    script = SamosMyrScript.from_text(src)
    errors = script.validate()
    assert errors == []


def test_script_scene_lookup():
    src = """
LoShun: Shakshi [reversible] { [Ao] }

Soa: FrontierOpen { [Ga(LoShun)] }
"""
    script = SamosMyrScript.from_text(src)
    assert script.scene("LoShun") is not None
    assert script.scene("LoShun").reversible is True
    assert script.scene("Missing") is None


def test_script_full_amelia_case():
    src = """
AmeliaAlive: Shakshi [reversible] { [SaelithChain AmourBond] }

AmeliaDead: FrontierOpen { [Ga(AmeliaAlive) PlayerKilledAmelia] }

AmeliaRestored: FrontierOpen { [Va(AmeliaAlive) NecromancyPerformed] }
"""
    script = SamosMyrScript.from_text(src)
    errors = script.validate()
    assert errors == []

    alive  = script.scene("AmeliaAlive")
    dead   = script.scene("AmeliaDead")
    reborn = script.scene("AmeliaRestored")

    assert alive.reversible is True
    assert dead.ga_targets == ["AmeliaAlive"]
    assert reborn.va_targets == ["AmeliaAlive"]
