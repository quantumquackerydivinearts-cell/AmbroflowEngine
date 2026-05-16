"""
klob/pipeline.py — KLOB manufacturing pipeline.

The pipeline is what Hypatia teaches in 0005_KLST — how physical objects,
materials, and alchemy skill combine to produce outputs. Three layers:

  1. ToolRequirements  — which categories of tool each operation needs
  2. RecipeStep        — one stage of a multi-step recipe
  3. ManufacturingRecipe — a named recipe with ordered steps, alchemy
                           rank requirement, and key output

Recipes defined here:
  infernal_salve       — Crystal Dust → Infernal Salve (gates ring descent)
  nexiott_poison       — Demonic Iron → Purified → Rusted → + Mercury → Poison
  colt_45              — Demonic Iron + Angelic Spears → Angelic Gun
  metal_transposition  — Any metal → next grade up (Giann's perk operation)

The pipeline integrates with Inventory (checks ingredient presence),
KlobRegistry (validates object IDs), and the key-lock system (grants
completion keys when recipes finish).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .registry import klob_registry, KlobObject


# ── Operation categories ──────────────────────────────────────────────────────
# Each operation names the category of tool required to perform it.

OPERATION_TOOL_CATEGORIES: dict[str, list[str]] = {
    "grinding":   ["grinding"],          # Mortar + Pestle both required
    "heating":    ["heat"],              # Furnace
    "melting":    ["heat", "vessel"],    # Furnace + Crucible
    "stirring":   ["stirring"],          # any Spoon
    "filtering":  ["filtering"],         # Diatom Earth as filter medium
    "smithing":   ["smithing", "heat"],  # Anvil/Hammer + Furnace for hot work
    "casting":    ["heat", "tool"],      # Furnace + a Mold
    "collecting": [],                    # no tool — manual collection
    "mixing":     ["vessel"],            # Bottle or Jar
}

# ── ToolRequirement ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ToolRequirement:
    """
    What physical tools must be present to perform an operation.

    operation:       name of the operation (see OPERATION_TOOL_CATEGORIES)
    required_ids:    specific KLOB IDs required (overrides category check)
    required_categories: tool categories that must be present (at least one each)
    """
    operation:            str
    required_ids:         tuple[str, ...] = ()
    required_categories:  tuple[str, ...] = ()

    def satisfied_by(self, held_ids: set[str]) -> bool:
        """
        Check whether the held set of KLOB IDs satisfies this requirement.
        specific IDs are checked directly; categories require at least one match.
        """
        reg = klob_registry()
        for klob_id in self.required_ids:
            if klob_id not in held_ids:
                return False
        for cat in self.required_categories:
            if not any(
                (obj := reg.get(hid)) and obj.category == cat
                for hid in held_ids
            ):
                return False
        return True


def tool_requirement(operation: str) -> ToolRequirement:
    """Build a ToolRequirement from the operation's canonical category list."""
    cats = OPERATION_TOOL_CATEGORIES.get(operation, [])
    return ToolRequirement(
        operation=operation,
        required_categories=tuple(cats),
    )


# ── RecipeStep ────────────────────────────────────────────────────────────────

@dataclass
class RecipeStep:
    """
    One stage of a manufacturing recipe.

    name:           human-readable name of this step
    operation:      operation type (keys OPERATION_TOOL_CATEGORIES)
    ingredient_ids: KLOB IDs consumed in this step
    tool_req:       tool requirement for this step
    output_id:      KLOB ID produced by this step (intermediate or final)
    output_name:    human-readable output name
    consumes:       if True, ingredients are removed from inventory
    """
    name:           str
    operation:      str
    ingredient_ids: list[str]
    tool_req:       ToolRequirement
    output_id:      str
    output_name:    str
    consumes:       bool = True

    def can_execute(self, inventory: "Inventory", held_tools: set[str]) -> tuple[bool, str]:
        """
        Check whether this step can execute.
        Returns (ok, reason). reason is empty string if ok.
        """
        for ing_id in self.ingredient_ids:
            if not inventory.has(ing_id):
                reg = klob_registry()
                name = (reg.get(ing_id) or type("", (), {"name": ing_id})()).name
                return False, f"Missing ingredient: {name} ({ing_id})"
        if not self.tool_req.satisfied_by(held_tools):
            return False, f"Missing tools for operation: {self.operation}"
        return True, ""


# ── ManufacturingRecipe ───────────────────────────────────────────────────────

@dataclass
class ManufacturingRecipe:
    """
    A named multi-step manufacturing recipe.

    id:              recipe identifier, e.g. "infernal_salve"
    name:            human-readable name
    steps:           ordered list of RecipeStep
    alchemy_rank:    minimum alchemy skill rank required (0 = no requirement)
    perk_required:   perk ID required, e.g. "alchemical_meditation" (None = no perk)
    grants_key:      yeigo key granted on completion (None = no key grant)
    description:     what the recipe produces and why it matters
    """
    id:              str
    name:            str
    steps:           list[RecipeStep]
    alchemy_rank:    int          = 0
    perk_required:   Optional[str] = None
    grants_key:      Optional[str] = None
    description:     str          = ""

    @property
    def final_output_id(self) -> str:
        return self.steps[-1].output_id if self.steps else ""

    @property
    def final_output_name(self) -> str:
        return self.steps[-1].output_name if self.steps else ""

    def eligible(self, alchemy_rank: int, held_perks: set[str]) -> tuple[bool, str]:
        """Check player eligibility before checking ingredients/tools."""
        if alchemy_rank < self.alchemy_rank:
            return False, f"Requires alchemy rank {self.alchemy_rank} (have {alchemy_rank})"
        if self.perk_required and self.perk_required not in held_perks:
            return False, f"Requires perk: {self.perk_required}"
        return True, ""


# ── Canonical recipes ─────────────────────────────────────────────────────────

INFERNAL_SALVE = ManufacturingRecipe(
    id          = "infernal_salve",
    name        = "Infernal Salve",
    alchemy_rank= 30,
    perk_required = "alchemical_meditation",
    grants_key  = "infernal_salve_made",
    description = (
        "The player's longing dissolved the dream crystal into dust in 0007. "
        "That dust, coagulated through alchemy, becomes the salve that enables "
        "descent into the rings. Solve et coagula in one object."
    ),
    steps = [
        RecipeStep(
            name          = "Grind crystal dust with sulphur",
            operation     = "grinding",
            ingredient_ids= ["9003_KLOB", "1007_KLOB"],   # Crystal Dust + Sulphur
            tool_req      = ToolRequirement(
                operation            = "grinding",
                required_ids         = ("8000_KLOB", "2000_KLOB"),  # Mortar + Pestle both
                required_categories  = (),
            ),
            output_id     = "9003_KLOB",   # intermediate — still Crystal Dust, now charged
            output_name   = "Charged Crystal Dust",
            consumes      = False,         # the dust is transformed, not consumed
        ),
        RecipeStep(
            name          = "Heat in crucible to bind",
            operation     = "melting",
            ingredient_ids= ["9003_KLOB"],  # Charged Crystal Dust
            tool_req      = ToolRequirement(
                operation            = "melting",
                required_ids         = ("0030_KLOB", "0007_KLOB", "0010_KLOB"),
                required_categories  = (),
            ),
            output_id     = "9008_KLOB",
            output_name   = "Infernal Salve",
            consumes      = True,
        ),
    ],
)


NEXIOTT_POISON = ManufacturingRecipe(
    id          = "nexiott_poison",
    name        = "Nexiott's Poison",
    alchemy_rank= 50,
    grants_key  = "nexiott_poison_complete",
    description = (
        "Demonic iron purified over sulphur, rusted by salt water, rust collected, "
        "mixed with mercury. The demonic iron having passed through the infernal "
        "register makes the poison legible to Kielum's protection."
    ),
    steps = [
        RecipeStep(
            name          = "Purify demonic iron over sulphur in furnace",
            operation     = "heating",
            ingredient_ids= ["9001_KLOB", "1007_KLOB"],   # Demonic Iron + Sulphur
            tool_req      = ToolRequirement(
                operation            = "heating",
                required_ids         = ("0030_KLOB",),     # Furnace
                required_categories  = (),
            ),
            output_id     = "9005_KLOB",
            output_name   = "Purified Demonic Iron",
            consumes      = True,
        ),
        RecipeStep(
            name          = "Rust with salt water",
            operation     = "collecting",
            ingredient_ids= ["9005_KLOB", "9004_KLOB"],   # Purified Iron + Salt Water
            tool_req      = ToolRequirement(operation="collecting"),
            output_id     = "9005_KLOB",   # same ID, rusted state
            output_name   = "Salt-Rusted Demonic Iron",
            consumes      = False,
        ),
        RecipeStep(
            name          = "Collect rust into vial",
            operation     = "collecting",
            ingredient_ids= ["9005_KLOB", "0005_KLOB"],   # Rusted Iron + Reagent Bottle
            tool_req      = ToolRequirement(operation="collecting"),
            output_id     = "9006_KLOB",
            output_name   = "Rusted Iron Vial",
            consumes      = True,
        ),
        RecipeStep(
            name          = "Mix rust with mercury",
            operation     = "mixing",
            ingredient_ids= ["9006_KLOB", "2005_KLOB"],   # Rust Vial + Mercury
            tool_req      = ToolRequirement(
                operation            = "mixing",
                required_categories  = ("vessel",),
            ),
            output_id     = "9009_KLOB",
            output_name   = "Nexiott's Poison",
            consumes      = True,
        ),
    ],
)


COLT_45 = ManufacturingRecipe(
    id          = "colt_45",
    name        = "Colt .45 — Hypatia's Angelic Gun",
    alchemy_rank= 65,
    grants_key  = "colt_45_crafted",
    description = (
        "Demonic iron melted with angelic spears from the Pride Ring ash fields. "
        "The angelic purification transforms the infernal base. "
        "Cast into gun form. Fires gold bullets — the only thing that can kill Sophia."
    ),
    steps = [
        RecipeStep(
            name          = "Melt demonic iron with angelic spears",
            operation     = "melting",
            ingredient_ids= ["9001_KLOB", "9002_KLOB"],   # Demonic Iron + Angelic Spear
            tool_req      = ToolRequirement(
                operation            = "melting",
                required_ids         = ("0030_KLOB", "0007_KLOB", "0010_KLOB"),
                required_categories  = (),
            ),
            output_id     = "9007_KLOB",
            output_name   = "Angelic-Purified Iron",
            consumes      = True,
        ),
        RecipeStep(
            name          = "Cast into gun form",
            operation     = "casting",
            ingredient_ids= ["9007_KLOB"],
            tool_req      = ToolRequirement(
                operation            = "casting",
                required_ids         = ("0030_KLOB", "0012_KLOB"),  # Furnace + Ingot Mold
                required_categories  = (),
            ),
            output_id     = "9010_KLOB",
            output_name   = "Colt .45",
            consumes      = True,
        ),
    ],
)


# Metal transposition: any metal → next grade up (Giann's perk operation)
# Grade ladder: Iron→Steel-grade, Copper→Bronze-grade, Silver→Silver-refined,
#               Gold→Gold-refined, Tin→Pewter-grade, Lead→Lead-refined
# Represented as a family of single-step recipes sharing the same structure.

_METAL_TRANSPOSITIONS: dict[str, tuple[str, str]] = {
    # input_id → (output_id, output_name)
    # Using existing metal IDs as input; outputs are newly refined versions
    # Since we don't have "Steel" as a separate KLOB yet, the output_id points
    # to the same ID with a note — in practice the inventory item gains a trait.
    "2002_KLOB": ("2002_KLOB", "Steel-Grade Iron"),   # Iron → Steel-grade
    "2004_KLOB": ("2004_KLOB", "Bronze-Grade Copper"), # Copper → Bronze-grade
    "2006_KLOB": ("2006_KLOB", "Refined Silver"),      # Silver → Refined Silver
    "2003_KLOB": ("2003_KLOB", "Refined Gold"),        # Gold → Refined Gold
    "2001_KLOB": ("2001_KLOB", "Pewter-Grade Tin"),    # Tin → Pewter-grade
    "2007_KLOB": ("2007_KLOB", "Refined Lead"),        # Lead → Refined Lead
    "2008_KLOB": ("2008_KLOB", "Refined Nickel"),      # Nickel → Refined Nickel
}


def metal_transposition_recipe(input_id: str) -> Optional[ManufacturingRecipe]:
    """
    Return the transposition recipe for a given metal input KLOB ID.
    Returns None if the metal is not transposable.
    Requires metal_transposition perk (Giann's boon from 0020_KLST).
    """
    if input_id not in _METAL_TRANSPOSITIONS:
        return None
    output_id, output_name = _METAL_TRANSPOSITIONS[input_id]
    reg = klob_registry()
    input_obj = reg.get(input_id)
    input_name = input_obj.name if input_obj else input_id
    return ManufacturingRecipe(
        id           = f"transposition_{input_id}",
        name         = f"Transposition: {input_name} → {output_name}",
        alchemy_rank = 0,
        perk_required= "metal_transposition",
        description  = (
            f"Giann's boon — transmute {input_name} upward one grade at the cost of density."
        ),
        steps = [
            RecipeStep(
                name          = f"Transmute {input_name}",
                operation     = "melting",
                ingredient_ids= [input_id],
                tool_req      = ToolRequirement(
                    operation            = "melting",
                    required_ids         = ("0030_KLOB", "0007_KLOB", "0010_KLOB"),
                    required_categories  = (),
                ),
                output_id     = output_id,
                output_name   = output_name,
                consumes      = True,
            ),
        ],
    )


# ── Canonical recipe registry ─────────────────────────────────────────────────

NAMED_RECIPES: dict[str, ManufacturingRecipe] = {
    r.id: r for r in (INFERNAL_SALVE, NEXIOTT_POISON, COLT_45)
}


def get_recipe(recipe_id: str) -> Optional[ManufacturingRecipe]:
    return NAMED_RECIPES.get(recipe_id)


def all_recipes() -> list[ManufacturingRecipe]:
    return list(NAMED_RECIPES.values())
