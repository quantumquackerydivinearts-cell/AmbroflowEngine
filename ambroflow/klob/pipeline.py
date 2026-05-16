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
                ing_obj = reg.get(ing_id)
                name: str = ing_obj.name if ing_obj is not None else ing_id
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
    hack_rank:       minimum hack skill rank required (0 = no requirement)
    perk_required:   perk ID required, e.g. "alchemical_meditation" (None = no perk)
    grants_key:      yeigo key granted on completion (None = no key grant)
    description:     what the recipe produces and why it matters
    """
    id:              str
    name:            str
    steps:           list[RecipeStep]
    alchemy_rank:    int           = 0
    hack_rank:       int           = 0
    perk_required:   Optional[str] = None
    grants_key:      Optional[str] = None
    description:     str           = ""

    @property
    def final_output_id(self) -> str:
        return self.steps[-1].output_id if self.steps else ""

    @property
    def final_output_name(self) -> str:
        return self.steps[-1].output_name if self.steps else ""

    def eligible(
        self,
        alchemy_rank: int,
        held_perks: set[str],
        hack_rank: int = 0,
    ) -> tuple[bool, str]:
        """Check player eligibility before checking ingredients/tools."""
        if alchemy_rank < self.alchemy_rank:
            return False, f"Requires alchemy rank {self.alchemy_rank} (have {alchemy_rank})"
        if hack_rank < self.hack_rank:
            return False, f"Requires hack rank {self.hack_rank} (have {hack_rank})"
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


# ── Smelting family ───────────────────────────────────────────────────────────
# Each metal KLOB → typed ingot KLIT via Furnace + Crucible + Crucible Tongs.
# KLIT output IDs: Iron=0040, Copper=0041, Gold=0042, Silver=0043,
#                  Lead=0044, Tin=0045, Nickel=0046

_SMELT_TABLE: dict[str, tuple[str, str, int]] = {
    # klob_id → (klit_id, ingot_name, min_alchemy_rank)
    "2002_KLOB": ("0040_KLIT", "Iron Ingot",   10),
    "2004_KLOB": ("0041_KLIT", "Copper Ingot",  10),
    "2003_KLOB": ("0042_KLIT", "Gold Ingot",    25),
    "2006_KLOB": ("0043_KLIT", "Silver Ingot",  20),
    "2007_KLOB": ("0044_KLIT", "Lead Ingot",    10),
    "2001_KLOB": ("0045_KLIT", "Tin Ingot",     10),
    "2008_KLOB": ("0046_KLIT", "Nickel Ingot",  15),
}

_SMELT_TOOLS = ToolRequirement(
    operation           = "melting",
    required_ids        = ("0030_KLOB", "0007_KLOB", "0010_KLOB"),  # Furnace+Crucible+Tongs
    required_categories = (),
)


def smelt_recipe(klob_id: str) -> Optional[ManufacturingRecipe]:
    """Return the smelting recipe for a raw metal KLOB → typed Ingot KLIT."""
    if klob_id not in _SMELT_TABLE:
        return None
    klit_id, ingot_name, rank = _SMELT_TABLE[klob_id]
    reg = klob_registry()
    obj = reg.get(klob_id)
    metal_name: str = obj.name if obj is not None else klob_id
    return ManufacturingRecipe(
        id           = f"smelt_{klob_id}",
        name         = f"Smelt {metal_name}",
        alchemy_rank = rank,
        description  = f"Heat {metal_name} in crucible to produce a {ingot_name}.",
        steps = [
            RecipeStep(
                name           = f"Smelt {metal_name} in crucible",
                operation      = "melting",
                ingredient_ids = [klob_id],
                tool_req       = _SMELT_TOOLS,
                output_id      = klit_id,
                output_name    = ingot_name,
                consumes       = True,
            ),
        ],
    )


# ── Smithing family ────────────────────────────────────────────────────────────

_FORGE_TOOLS = ToolRequirement(
    operation           = "smithing",
    required_ids        = ("0013_KLOB", "0014_KLOB"),  # Anvil + Hammer
    required_categories = (),
)

FORGE_DAGGER = ManufacturingRecipe(
    id           = "forge_dagger",
    name         = "Forge Iron Dagger",
    alchemy_rank = 0,
    description  = "Hammer an iron ingot into a dagger blade on the anvil.",
    steps = [
        RecipeStep(
            name           = "Hammer ingot into blade",
            operation      = "smithing",
            ingredient_ids = ["0040_KLIT"],   # Iron Ingot
            tool_req       = _FORGE_TOOLS,
            output_id      = "0014_KLIT",
            output_name    = "Dagger",
            consumes       = True,
        ),
    ],
)

FORGE_SWORD = ManufacturingRecipe(
    id           = "forge_sword",
    name         = "Forge Iron Sword",
    alchemy_rank = 15,
    description  = "Two iron ingots worked into a sword blank, then shaped.",
    steps = [
        RecipeStep(
            name           = "Forge sword blank from two ingots",
            operation      = "smithing",
            ingredient_ids = ["0040_KLIT", "0040_KLIT"],   # 2× Iron Ingot
            tool_req       = ToolRequirement(
                operation           = "smithing",
                required_ids        = ("0013_KLOB", "0014_KLOB", "0017_KLOB"),  # Anvil+Hammer+Chisel
                required_categories = (),
            ),
            output_id      = "0015_KLIT",
            output_name    = "Sword",
            consumes       = True,
        ),
    ],
)

FORGE_IRON_ARROW = ManufacturingRecipe(
    id           = "forge_iron_arrow",
    name         = "Forge Iron Arrows",
    alchemy_rank = 0,
    description  = "Iron ingot worked into arrowheads, set on wood shafts.",
    steps = [
        RecipeStep(
            name           = "Shape arrowhead and set on shaft",
            operation      = "smithing",
            ingredient_ids = ["0040_KLIT", "1016_KLOB"],  # Iron Ingot + Wood
            tool_req       = _FORGE_TOOLS,
            output_id      = "0061_KLIT",
            output_name    = "Iron Arrow",
            consumes       = True,
        ),
    ],
)

KNAP_FLINT_ARROW = ManufacturingRecipe(
    id           = "knap_flint_arrow",
    name         = "Knap Flint Arrows",
    alchemy_rank = 0,
    description  = "Flint knapped into arrowheads, no heat required.",
    steps = [
        RecipeStep(
            name           = "Knap flint tip and set on shaft",
            operation      = "smithing",
            ingredient_ids = ["1017_KLOB", "1016_KLOB"],  # Flint + Wood
            tool_req       = ToolRequirement(
                operation           = "smithing",
                required_ids        = ("0014_KLOB",),  # Hammer only — no anvil for knapping
                required_categories = (),
            ),
            output_id      = "0062_KLIT",
            output_name    = "Flint Arrow",
            consumes       = True,
        ),
    ],
)

FORGE_GOLD_COIN = ManufacturingRecipe(
    id           = "forge_gold_coin",
    name         = "Mint Gold Coin",
    alchemy_rank = 20,
    description  = "Gold ingot stamped into coins using ingot mold and hammer.",
    steps = [
        RecipeStep(
            name           = "Stamp gold into coins",
            operation      = "casting",
            ingredient_ids = ["0042_KLIT"],   # Gold Ingot
            tool_req       = ToolRequirement(
                operation           = "casting",
                required_ids        = ("0012_KLOB", "0014_KLOB"),  # Ingot Mold + Hammer
                required_categories = (),
            ),
            output_id      = "0050_KLIT",
            output_name    = "Gold Coin",
            consumes       = True,
        ),
    ],
)

FORGE_SILVER_COIN = ManufacturingRecipe(
    id           = "forge_silver_coin",
    name         = "Mint Silver Coin",
    alchemy_rank = 15,
    description  = "Silver ingot stamped into coins.",
    steps = [
        RecipeStep(
            name           = "Stamp silver into coins",
            operation      = "casting",
            ingredient_ids = ["0043_KLIT"],   # Silver Ingot
            tool_req       = ToolRequirement(
                operation           = "casting",
                required_ids        = ("0012_KLOB", "0014_KLOB"),
                required_categories = (),
            ),
            output_id      = "0051_KLIT",
            output_name    = "Silver Coin",
            consumes       = True,
        ),
    ],
)

FORGE_COPPER_COIN = ManufacturingRecipe(
    id           = "forge_copper_coin",
    name         = "Mint Copper Coin",
    alchemy_rank = 10,
    description  = "Copper ingot stamped into coins.",
    steps = [
        RecipeStep(
            name           = "Stamp copper into coins",
            operation      = "casting",
            ingredient_ids = ["0041_KLIT"],   # Copper Ingot
            tool_req       = ToolRequirement(
                operation           = "casting",
                required_ids        = ("0012_KLOB", "0014_KLOB"),
                required_categories = (),
            ),
            output_id      = "0052_KLIT",
            output_name    = "Copper Coin",
            consumes       = True,
        ),
    ],
)

FORGE_RING = ManufacturingRecipe(
    id           = "forge_ring",
    name         = "Turn a Ring",
    alchemy_rank = 20,
    description  = "Gold or silver ingot turned on lathe into a ring.",
    steps = [
        RecipeStep(
            name           = "Turn ring on lathe from ingot",
            operation      = "smithing",
            ingredient_ids = ["0042_KLIT", "0018_KLOB"],  # Gold Ingot + Ring Blank
            tool_req       = ToolRequirement(
                operation           = "smithing",
                required_ids        = ("0015_KLOB", "0016_KLOB"),  # Lathe Chuck + Lathe
                required_categories = (),
            ),
            output_id      = "0011_KLIT",
            output_name    = "Ring",
            consumes       = True,
        ),
    ],
)

FORGE_NECKLACE = ManufacturingRecipe(
    id           = "forge_necklace",
    name         = "Hammer a Necklace",
    alchemy_rank = 20,
    description  = "Gold ingot worked into a pendant necklace.",
    steps = [
        RecipeStep(
            name           = "Work ingot into pendant and chain",
            operation      = "smithing",
            ingredient_ids = ["0042_KLIT"],   # Gold Ingot
            tool_req       = ToolRequirement(
                operation           = "smithing",
                required_ids        = ("0013_KLOB", "0014_KLOB", "0017_KLOB"),
                required_categories = (),
            ),
            output_id      = "0010_KLIT",
            output_name    = "Necklace",
            consumes       = True,
        ),
    ],
)

FORGE_GOLD_BULLET = ManufacturingRecipe(
    id           = "forge_gold_bullet",
    name         = "Cast Gold Bullet",
    alchemy_rank = 40,
    grants_key   = "gold_bullet_crafted",
    description  = "Gold ingot precision-cast into a bullet for the Colt .45. Only thing that can kill Sophia.",
    steps = [
        RecipeStep(
            name           = "Cast and turn gold bullet",
            operation      = "casting",
            ingredient_ids = ["0042_KLIT"],   # Gold Ingot
            tool_req       = ToolRequirement(
                operation           = "casting",
                required_ids        = ("0030_KLOB", "0012_KLOB", "0016_KLOB"),  # Furnace+Ingot Mold+Lathe
                required_categories = (),
            ),
            output_id      = "0060_KLIT",
            output_name    = "Gold Bullet",
            consumes       = True,
        ),
    ],
)


# ── Alchemy / chemistry family ────────────────────────────────────────────────

MAKE_GUNPOWDER = ManufacturingRecipe(
    id           = "make_gunpowder",
    name         = "Grind Gunpowder",
    alchemy_rank = 20,
    description  = "Traditional formula: Saltpeter + Sulphur + Charcoal ground together. 75/10/15 ratio.",
    steps = [
        RecipeStep(
            name           = "Grind saltpeter, sulphur, charcoal",
            operation      = "grinding",
            ingredient_ids = ["1006_KLOB", "1007_KLOB", "1008_KLOB"],  # Saltpeter+Sulphur+Charcoal
            tool_req       = ToolRequirement(
                operation           = "grinding",
                required_ids        = ("8000_KLOB", "2000_KLOB"),
                required_categories = (),
            ),
            output_id      = "0070_KLIT",
            output_name    = "Gunpowder",
            consumes       = True,
        ),
    ],
)

BREW_HEALTH_POTION = ManufacturingRecipe(
    id           = "brew_health_potion",
    name         = "Brew Health Potion",
    alchemy_rank = 15,
    perk_required= "alchemical_meditation",
    description  = "Lotus Flower steeped in water and heated — the ground of being made medicinal.",
    steps = [
        RecipeStep(
            name           = "Steep lotus flower in water and heat",
            operation      = "heating",
            ingredient_ids = ["0007_KLIT", "1015_KLOB", "0005_KLOB"],  # Lotus Flower+Water+Reagent Bottle
            tool_req       = ToolRequirement(
                operation           = "heating",
                required_ids        = ("0030_KLOB",),
                required_categories = (),
            ),
            output_id      = "0035_KLIT",
            output_name    = "Health Potion",
            consumes       = True,
        ),
    ],
)

MAKE_CAUSTIC_LYE = ManufacturingRecipe(
    id           = "make_caustic_lye",
    name         = "Make Caustic Lye",
    alchemy_rank = 10,
    description  = "Wood ash leached with water and reduced by heat — traditional soap-maker's lye.",
    steps = [
        RecipeStep(
            name           = "Leach ashes with water in jar and heat",
            operation      = "heating",
            ingredient_ids = ["1009_KLOB", "1015_KLOB", "0009_KLOB"],  # Ashes+Water+Jar
            tool_req       = ToolRequirement(
                operation           = "heating",
                required_ids        = ("0030_KLOB",),
                required_categories = (),
            ),
            output_id      = "1010_KLOB",   # Caustic Lye KLOB (closes its own production loop)
            output_name    = "Caustic Lye",
            consumes       = True,
        ),
    ],
)

MAKE_INK = ManufacturingRecipe(
    id           = "make_ink",
    name         = "Make Ink",
    alchemy_rank = 5,
    description  = "Carbon ink from ashes and water — traditional lampblack method.",
    steps = [
        RecipeStep(
            name           = "Mix ashes with water in jar",
            operation      = "mixing",
            ingredient_ids = ["1009_KLOB", "1015_KLOB", "0009_KLOB"],  # Ashes+Water+Jar
            tool_req       = ToolRequirement(
                operation           = "mixing",
                required_categories = ("vessel",),
            ),
            output_id      = "5003_KLOB",   # Ink KLOB
            output_name    = "Ink",
            consumes       = True,
        ),
    ],
)

MAKE_REFINED_SAND = ManufacturingRecipe(
    id           = "make_refined_sand",
    name         = "Refine Sand",
    alchemy_rank = 5,
    description  = "Sand ground and sifted through diatom earth to remove impurities.",
    steps = [
        RecipeStep(
            name           = "Grind sand and filter",
            operation      = "grinding",
            ingredient_ids = ["1001_KLOB", "1003_KLOB"],  # Sand + Diatom Earth
            tool_req       = ToolRequirement(
                operation           = "grinding",
                required_ids        = ("8000_KLOB", "2000_KLOB"),
                required_categories = (),
            ),
            output_id      = "1002_KLOB",   # Refined Sand KLOB
            output_name    = "Refined Sand",
            consumes       = True,
        ),
    ],
)

MAKE_PAPER = ManufacturingRecipe(
    id           = "make_paper",
    name         = "Make Paper",
    alchemy_rank = 10,
    description  = "Pulp treated with caustic lye, filtered through diatom earth, pressed flat.",
    steps = [
        RecipeStep(
            name           = "Treat pulp with lye",
            operation      = "mixing",
            ingredient_ids = ["5001_KLOB", "1010_KLOB"],  # Pulp + Caustic Lye
            tool_req       = ToolRequirement(
                operation           = "mixing",
                required_categories = ("vessel",),
            ),
            output_id      = "5001_KLOB",
            output_name    = "Treated Pulp",
            consumes       = False,
        ),
        RecipeStep(
            name           = "Filter and press into sheets",
            operation      = "filtering",
            ingredient_ids = ["5001_KLOB", "1003_KLOB"],  # Treated Pulp + Diatom Earth
            tool_req       = ToolRequirement(
                operation           = "filtering",
                required_categories = ("filtering",),
            ),
            output_id      = "5002_KLOB",   # Paper KLOB
            output_name    = "Paper",
            consumes       = True,
        ),
    ],
)


# ── Distillation family ───────────────────────────────────────────────────────

DISTILL_AQUA_VITAE = ManufacturingRecipe(
    id           = "distill_aqua_vitae",
    name         = "Distill Aqua Vitae",
    alchemy_rank = 25,
    perk_required= "alchemical_meditation",
    description  = "White wine distilled through retort and furnace into high-proof spirit. Basis for Absinthe.",
    steps = [
        RecipeStep(
            name           = "Distill white wine through retort",
            operation      = "heating",
            ingredient_ids = ["0027_KLIT", "0003_KLOB"],  # White Wine + Retort
            tool_req       = ToolRequirement(
                operation           = "heating",
                required_ids        = ("0030_KLOB", "0003_KLOB"),  # Furnace + Retort
                required_categories = (),
            ),
            output_id      = "0028_KLIT",
            output_name    = "Aqua Vitae",
            consumes       = True,
        ),
    ],
)

BREW_ABSINTHE = ManufacturingRecipe(
    id           = "brew_absinthe",
    name         = "Brew Absinthe",
    alchemy_rank = 30,
    description  = (
        "Traditional method: macerate wormwood, anise, and fennel in aqua vitae, "
        "then distill. The green fairy."
    ),
    steps = [
        RecipeStep(
            name           = "Macerate herbs in aqua vitae",
            operation      = "mixing",
            ingredient_ids = ["0028_KLIT", "0024_KLIT", "0025_KLIT", "0026_KLIT"],
            # Aqua Vitae + Wormwood + Anise + Fennel
            tool_req       = ToolRequirement(
                operation           = "mixing",
                required_ids        = ("0008_KLOB",),  # Bottle
                required_categories = (),
            ),
            output_id      = "0028_KLIT",
            output_name    = "Herb-Macerated Spirit",
            consumes       = False,
        ),
        RecipeStep(
            name           = "Distill macerated spirit",
            operation      = "heating",
            ingredient_ids = ["0028_KLIT", "0003_KLOB"],  # Macerated Spirit + Retort
            tool_req       = ToolRequirement(
                operation           = "heating",
                required_ids        = ("0030_KLOB", "0003_KLOB"),
                required_categories = (),
            ),
            output_id      = "0023_KLIT",
            output_name    = "Absinthe",
            consumes       = True,
        ),
    ],
)


# ── Electronics family (Hack-gated) ──────────────────────────────────────────
# Traditional crystal radio uses Quartz as the resonator, Copper for the coil.
# Transmitter adds Iron for the coil core.
# Full Radio assembles both units.

_ELECTRONICS_TOOLS = ToolRequirement(
    operation           = "smithing",
    required_ids        = ("0016_KLOB", "0015_KLOB"),  # Lathe + Lathe Chuck (precision winding)
    required_categories = (),
)

BUILD_RECEIVER = ManufacturingRecipe(
    id          = "build_receiver",
    name        = "Build Receiver",
    hack_rank   = 35,
    grants_key  = "receiver_built",
    description = (
        "Crystal radio receiver — Copper coil wound on a Quartz crystal resonator, "
        "set in a Wood housing. Passive: receives signal without transmitting."
    ),
    steps = [
        RecipeStep(
            name           = "Wind copper coil around quartz crystal in wood housing",
            operation      = "smithing",
            ingredient_ids = ["2004_KLOB", "3005_KLOB", "1016_KLOB"],
            # Copper + Quartz + Wood
            tool_req       = _ELECTRONICS_TOOLS,
            output_id      = "0081_KLIT",
            output_name    = "Receiver",
            consumes       = True,
        ),
    ],
)

BUILD_TRANSMITTER = ManufacturingRecipe(
    id          = "build_transmitter",
    name        = "Build Transmitter",
    hack_rank   = 55,
    grants_key  = "transmitter_built",
    description = (
        "Signal transmitter — Copper winding on Iron core, Quartz crystal for frequency "
        "stability, Wood housing. Active: sends signal into the Lapidus airwave infrastructure."
    ),
    steps = [
        RecipeStep(
            name           = "Wind copper on iron core with quartz stabiliser",
            operation      = "smithing",
            ingredient_ids = ["2004_KLOB", "2002_KLOB", "3005_KLOB", "1016_KLOB"],
            # Copper + Iron + Quartz + Wood
            tool_req       = _ELECTRONICS_TOOLS,
            output_id      = "0082_KLIT",
            output_name    = "Transmitter",
            consumes       = True,
        ),
    ],
)

BUILD_RADIO = ManufacturingRecipe(
    id          = "build_radio",
    name        = "Build Radio",
    hack_rank   = 80,
    grants_key  = "radio_built",
    description = (
        "Full radio unit — Receiver and Transmitter assembled with additional Copper wiring. "
        "The physical counterpart to St. Alaro's broadcast deal. "
        "Connects to the Lapidus airwave infrastructure without the BoK mark."
    ),
    steps = [
        RecipeStep(
            name           = "Assemble receiver and transmitter with copper wiring",
            operation      = "smithing",
            ingredient_ids = ["0081_KLIT", "0082_KLIT", "2004_KLOB"],
            # Receiver + Transmitter + Copper (additional wiring)
            tool_req       = _ELECTRONICS_TOOLS,
            output_id      = "0083_KLIT",
            output_name    = "Radio",
            consumes       = True,
        ),
    ],
)


# ── Canonical recipe registry ─────────────────────────────────────────────────

_ALL_NAMED = (
    INFERNAL_SALVE, NEXIOTT_POISON, COLT_45,
    FORGE_DAGGER, FORGE_SWORD, FORGE_IRON_ARROW, KNAP_FLINT_ARROW,
    FORGE_GOLD_COIN, FORGE_SILVER_COIN, FORGE_COPPER_COIN,
    FORGE_RING, FORGE_NECKLACE, FORGE_GOLD_BULLET,
    MAKE_GUNPOWDER, BREW_HEALTH_POTION, MAKE_CAUSTIC_LYE,
    MAKE_INK, MAKE_REFINED_SAND, MAKE_PAPER,
    DISTILL_AQUA_VITAE, BREW_ABSINTHE,
    BUILD_RECEIVER, BUILD_TRANSMITTER, BUILD_RADIO,
)

NAMED_RECIPES: dict[str, ManufacturingRecipe] = {
    r.id: r for r in _ALL_NAMED
}


def get_recipe(recipe_id: str) -> Optional[ManufacturingRecipe]:
    return NAMED_RECIPES.get(recipe_id)


def all_recipes() -> list[ManufacturingRecipe]:
    return list(NAMED_RECIPES.values())
