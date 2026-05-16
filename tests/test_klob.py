"""
Tests for the KLOB registry and manufacturing pipeline.
"""

import pytest
from unittest.mock import MagicMock

from ambroflow.klob.registry import (
    KlobObject, KlobRegistry, klob_registry, ALL_OBJECTS, CATEGORIES,
)
from ambroflow.klob.pipeline import (
    ToolRequirement, RecipeStep, ManufacturingRecipe,
    INFERNAL_SALVE, NEXIOTT_POISON, COLT_45,
    BUILD_RECEIVER, BUILD_TRANSMITTER, BUILD_RADIO,
    metal_transposition_recipe, get_recipe, all_recipes,
    OPERATION_TOOL_CATEGORIES,
)
from ambroflow.inventory.manager import Inventory


# ── KlobRegistry ─────────────────────────────────────────────────────────────

def test_registry_has_all_objects():
    reg = klob_registry()
    assert len(reg) == len(ALL_OBJECTS)


def test_registry_get_by_id():
    reg = klob_registry()
    obj = reg.get("8000_KLOB")
    assert obj is not None
    assert obj.name == "Mortar"
    assert obj.category == "grinding"


def test_registry_get_by_name():
    reg = klob_registry()
    obj = reg.get_by_name("pestle")
    assert obj is not None
    assert obj.id == "2000_KLOB"


def test_registry_get_by_name_case_insensitive():
    reg = klob_registry()
    assert reg.get_by_name("FURNACE") is not None
    assert reg.get_by_name("furnace") is not None


def test_registry_by_category():
    reg = klob_registry()
    metals = reg.by_category("metal")
    assert len(metals) == 8
    ids = {m.id for m in metals}
    assert "2002_KLOB" in ids   # Iron
    assert "2005_KLOB" in ids   # Mercury


def test_registry_contains():
    reg = klob_registry()
    assert "9008_KLOB" in reg   # Infernal Salve
    assert "9999_KLOB" not in reg


def test_all_categories_valid():
    for obj in ALL_OBJECTS:
        assert obj.category in CATEGORIES, \
            f"{obj.id} {obj.name!r} has unknown category {obj.category!r}"


def test_all_ids_unique():
    ids = [obj.id for obj in ALL_OBJECTS]
    assert len(ids) == len(set(ids)), "Duplicate KLOB IDs found"


def test_quest_materials_present():
    reg = klob_registry()
    assert reg.get("9001_KLOB").name == "Demonic Iron"
    assert reg.get("9002_KLOB").name == "Angelic Spear"
    assert reg.get("9003_KLOB").name == "Crystal Dust"
    assert reg.get("9008_KLOB").name == "Infernal Salve"
    assert reg.get("9009_KLOB").name == "Nexiott Poison"
    assert reg.get("9010_KLOB").name == "Colt .45"


# ── ToolRequirement ───────────────────────────────────────────────────────────

def test_tool_req_empty_always_satisfied():
    req = ToolRequirement(operation="collecting")
    assert req.satisfied_by(set()) is True


def test_tool_req_specific_id_satisfied():
    req = ToolRequirement(operation="grinding", required_ids=("8000_KLOB",))
    assert req.satisfied_by({"8000_KLOB"}) is True
    assert req.satisfied_by({"2000_KLOB"}) is False


def test_tool_req_specific_ids_both_required():
    req = ToolRequirement(
        operation="grinding",
        required_ids=("8000_KLOB", "2000_KLOB"),
    )
    assert req.satisfied_by({"8000_KLOB", "2000_KLOB"}) is True
    assert req.satisfied_by({"8000_KLOB"}) is False


def test_tool_req_category_satisfied():
    req = ToolRequirement(
        operation="melting",
        required_categories=("heat", "vessel"),
    )
    # Furnace (heat) + Crucible (vessel)
    assert req.satisfied_by({"0030_KLOB", "0007_KLOB"}) is True
    # Missing vessel
    assert req.satisfied_by({"0030_KLOB"}) is False


# ── RecipeStep ────────────────────────────────────────────────────────────────

def _inventory(*ids: str) -> Inventory:
    return Inventory(initial={i: 1 for i in ids})


def test_recipe_step_can_execute_ok():
    step = NEXIOTT_POISON.steps[0]  # purify demonic iron
    inv = _inventory("9001_KLOB", "1007_KLOB")   # Demonic Iron + Sulphur
    ok, reason = step.can_execute(inv, {"0030_KLOB"})  # has Furnace
    assert ok is True
    assert reason == ""


def test_recipe_step_missing_ingredient():
    step = NEXIOTT_POISON.steps[0]
    inv = _inventory("1007_KLOB")   # Sulphur but no Demonic Iron
    ok, reason = step.can_execute(inv, {"0030_KLOB"})
    assert ok is False
    assert "Demonic Iron" in reason or "9001_KLOB" in reason


def test_recipe_step_missing_tool():
    step = NEXIOTT_POISON.steps[0]
    inv = _inventory("9001_KLOB", "1007_KLOB")
    ok, reason = step.can_execute(inv, set())   # no tools
    assert ok is False
    assert "tool" in reason.lower() or "operation" in reason.lower()


# ── ManufacturingRecipe ───────────────────────────────────────────────────────

def test_infernal_salve_recipe():
    assert INFERNAL_SALVE.id == "infernal_salve"
    assert INFERNAL_SALVE.alchemy_rank == 30
    assert INFERNAL_SALVE.perk_required == "alchemical_meditation"
    assert INFERNAL_SALVE.grants_key == "infernal_salve_made"
    assert INFERNAL_SALVE.final_output_id == "9008_KLOB"
    assert len(INFERNAL_SALVE.steps) == 2


def test_nexiott_poison_recipe():
    assert NEXIOTT_POISON.id == "nexiott_poison"
    assert NEXIOTT_POISON.alchemy_rank == 50
    assert NEXIOTT_POISON.grants_key == "nexiott_poison_complete"
    assert NEXIOTT_POISON.final_output_id == "9009_KLOB"
    assert len(NEXIOTT_POISON.steps) == 4


def test_colt_45_recipe():
    assert COLT_45.id == "colt_45"
    assert COLT_45.alchemy_rank == 65
    assert COLT_45.grants_key == "colt_45_crafted"
    assert COLT_45.final_output_id == "9010_KLOB"
    assert len(COLT_45.steps) == 2


def test_recipe_eligible_rank_ok():
    ok, reason = INFERNAL_SALVE.eligible(alchemy_rank=35, held_perks={"alchemical_meditation"})
    assert ok is True


def test_recipe_eligible_rank_too_low():
    ok, reason = INFERNAL_SALVE.eligible(alchemy_rank=20, held_perks={"alchemical_meditation"})
    assert ok is False
    assert "rank" in reason.lower()


def test_recipe_eligible_missing_perk():
    ok, reason = INFERNAL_SALVE.eligible(alchemy_rank=35, held_perks=set())
    assert ok is False
    assert "perk" in reason.lower()


# ── Metal transposition ───────────────────────────────────────────────────────

def test_metal_transposition_iron():
    recipe = metal_transposition_recipe("2002_KLOB")
    assert recipe is not None
    assert recipe.perk_required == "metal_transposition"
    assert "Iron" in recipe.name
    assert len(recipe.steps) == 1
    assert recipe.steps[0].ingredient_ids == ["2002_KLOB"]


def test_metal_transposition_invalid():
    assert metal_transposition_recipe("0001_KLOB") is None   # Rag not transposable
    assert metal_transposition_recipe("9001_KLOB") is None   # Demonic Iron not transposable


def test_metal_transposition_all_metals():
    transposable = ["2001_KLOB","2002_KLOB","2003_KLOB","2004_KLOB",
                    "2005_KLOB","2006_KLOB","2007_KLOB","2008_KLOB"]
    # Only the ones in _METAL_TRANSPOSITIONS should return a recipe
    for klob_id in ["2002_KLOB","2003_KLOB","2004_KLOB","2006_KLOB","2007_KLOB","2008_KLOB"]:
        assert metal_transposition_recipe(klob_id) is not None


# ── Recipe registry ───────────────────────────────────────────────────────────

def test_get_recipe():
    assert get_recipe("infernal_salve") is INFERNAL_SALVE
    assert get_recipe("nexiott_poison") is NEXIOTT_POISON
    assert get_recipe("colt_45") is COLT_45
    assert get_recipe("nonexistent") is None


def test_all_recipes():
    recipes = all_recipes()
    ids = {r.id for r in recipes}
    # Original quest recipes
    assert "infernal_salve" in ids
    assert "nexiott_poison" in ids
    assert "colt_45" in ids
    # Smithing family
    assert "forge_dagger" in ids
    assert "forge_sword" in ids
    assert "forge_gold_bullet" in ids
    # Alchemy / distillation
    assert "make_gunpowder" in ids
    assert "brew_health_potion" in ids
    assert "distill_aqua_vitae" in ids
    assert "brew_absinthe" in ids
    # Electronics family
    assert "build_receiver" in ids
    assert "build_transmitter" in ids
    assert "build_radio" in ids
    # All 24 named recipes registered
    assert len(recipes) == 24


# ── Electronics ──────────────────────────────────────────────────────────────

def test_receiver_recipe():
    assert BUILD_RECEIVER.hack_rank == 35
    assert BUILD_RECEIVER.grants_key == "receiver_built"
    assert BUILD_RECEIVER.final_output_id == "0081_KLIT"
    assert len(BUILD_RECEIVER.steps) == 1
    # Quartz (3005_KLOB) and Copper (2004_KLOB) required
    assert "3005_KLOB" in BUILD_RECEIVER.steps[0].ingredient_ids
    assert "2004_KLOB" in BUILD_RECEIVER.steps[0].ingredient_ids


def test_transmitter_recipe():
    assert BUILD_TRANSMITTER.hack_rank == 55
    assert BUILD_TRANSMITTER.grants_key == "transmitter_built"
    assert BUILD_TRANSMITTER.final_output_id == "0082_KLIT"
    # Iron (2002_KLOB) added for coil core
    assert "2002_KLOB" in BUILD_TRANSMITTER.steps[0].ingredient_ids


def test_radio_recipe():
    assert BUILD_RADIO.hack_rank == 80
    assert BUILD_RADIO.grants_key == "radio_built"
    assert BUILD_RADIO.final_output_id == "0083_KLIT"
    # Radio assembles Receiver + Transmitter
    assert "0081_KLIT" in BUILD_RADIO.steps[0].ingredient_ids
    assert "0082_KLIT" in BUILD_RADIO.steps[0].ingredient_ids


def test_electronics_hack_gate():
    # Receiver requires Hack 35
    ok, reason = BUILD_RECEIVER.eligible(alchemy_rank=0, held_perks=set(), hack_rank=20)
    assert ok is False
    assert "hack" in reason.lower()

    ok, _ = BUILD_RECEIVER.eligible(alchemy_rank=0, held_perks=set(), hack_rank=35)
    assert ok is True


def test_radio_ladder_progression():
    # Radio requires Hack 80 — a player with only 55 cannot build it
    ok, reason = BUILD_RADIO.eligible(alchemy_rank=0, held_perks=set(), hack_rank=55)
    assert ok is False
    ok, _ = BUILD_RADIO.eligible(alchemy_rank=0, held_perks=set(), hack_rank=80)
    assert ok is True


# ── Operation categories ──────────────────────────────────────────────────────

def test_operation_tool_categories_defined():
    for op in ["grinding", "heating", "melting", "stirring", "filtering",
               "smithing", "casting", "collecting", "mixing"]:
        assert op in OPERATION_TOOL_CATEGORIES
