"""
klob/registry.py — KLOB object registry.

KLOB (Ko's Lab Objects) are the physical tools and materials used in
alchemy and manufacturing. They are placed in zones via the Kobra zone
loader, held in the player's Inventory, and consumed or required by
ManufacturingRecipes.

ID groupings:
  0001-0029   Lab equipment (tools, vessels)
  0020-0024   Spoons (stirring)
  0030        Furnace (heat)
  0040        Water Flask (material)
  0073-0077   Botanical / consumable ingredients
  1001-1099   Processing materials and chemicals
  2001-2099   Metals
  3001-3099   Minerals
  4001-4099   Gems and special stones
  5001-5099   Writing materials
  8000, 2000  Grinding tools (Mortar, Pestle)
  9001-9099   Quest / realm-specific materials and outputs
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ── KlobObject ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class KlobObject:
    id:            str                # e.g. "0007_KLOB"
    name:          str                # e.g. "Crucible"
    category:      str                # see CATEGORIES below
    default_trait: Optional[int] = None
    note:          Optional[str] = None


CATEGORIES = frozenset({
    "grinding",        # Mortar, Pestle
    "tool",            # Rag, Stand, Bellows, Crucible Tongs, etc.
    "vessel",          # Retort, Volume Flask, Crucible, Bottle, Jar
    "stirring",        # Wooden/Copper/Iron/Steel/Granite Spoon
    "heat",            # Furnace
    "smithing",        # Anvil, Hammer, Lathe, Chisel, Molds
    "filtering",       # Diatom Earth
    "chemical",        # Sulphur, Saltpeter, Charcoal, Cyanide, etc.
    "material",        # Sand, Water, Wood, etc.
    "metal",           # Tin, Iron, Gold, Copper, Mercury, Silver, Lead, Nickel
    "mineral",         # Granite, Obsidian, Chalk, Quartz, Flint, Shark Tooth
    "gem",             # Amethyst, Ruby, Sapphire, Emerald, Diamond, Jade, etc.
    "writing",         # Pulp, Paper, Ink, Pen
    "quest_material",  # Demonic Iron, Angelic Spear, Crystal Dust, Salt Water, intermediates
    "quest_output",    # Infernal Salve, Nexiott Poison, Colt .45
})


# ── Canonical registry ────────────────────────────────────────────────────────

ALL_OBJECTS: tuple[KlobObject, ...] = (
    # ── Grinding tools ────────────────────────────────────────────────────────
    KlobObject("8000_KLOB", "Mortar",               "grinding",  default_trait=0),
    KlobObject("2000_KLOB", "Pestle",               "grinding",  default_trait=1),

    # ── Lab equipment ─────────────────────────────────────────────────────────
    KlobObject("0001_KLOB", "Rag",                  "tool"),
    KlobObject("0002_KLOB", "Stand",                "tool"),
    KlobObject("0003_KLOB", "Retort",               "vessel"),
    KlobObject("0004_KLOB", "Volume Flask",         "vessel"),
    KlobObject("0005_KLOB", "Reagent Bottle",       "vessel"),
    KlobObject("0006_KLOB", "Bellows",              "tool"),
    KlobObject("0007_KLOB", "Crucible",             "vessel"),
    KlobObject("0008_KLOB", "Bottle",               "vessel"),
    KlobObject("0009_KLOB", "Jar",                  "vessel"),
    KlobObject("0010_KLOB", "Crucible Tongs",       "tool"),
    KlobObject("0011_KLOB", "Ring Mold",            "tool"),
    KlobObject("0012_KLOB", "Ingot Mold",           "tool"),
    KlobObject("0013_KLOB", "Anvil",                "smithing"),
    KlobObject("0014_KLOB", "Hammer",               "smithing"),
    KlobObject("0015_KLOB", "Lathe Chuck",          "smithing"),
    KlobObject("0016_KLOB", "Lathe",                "smithing"),
    KlobObject("0017_KLOB", "Chisel",               "smithing"),
    KlobObject("0018_KLOB", "Ring Blank",           "smithing"),
    KlobObject("0019_KLOB", "Pen",                  "writing"),

    # ── Spoons ────────────────────────────────────────────────────────────────
    KlobObject("0020_KLOB", "Wooden Spoon",         "stirring"),
    KlobObject("0021_KLOB", "Copper Spoon",         "stirring"),
    KlobObject("0022_KLOB", "Iron Spoon",           "stirring"),
    KlobObject("0023_KLOB", "Steel Spoon",          "stirring"),
    KlobObject("0024_KLOB", "Granite Spoon",        "stirring"),

    # ── Heat equipment ────────────────────────────────────────────────────────
    KlobObject("0030_KLOB", "Furnace",              "heat"),

    # ── Botanical / consumable ingredients ────────────────────────────────────
    KlobObject("0040_KLOB", "Water Flask",          "material",
               note="Purified water in a sealed flask — base solvent for tinctures"),
    KlobObject("0073_KLOB", "Herb (Common)",        "material",
               note="Common dried herb — mild temporal field, base reduction ingredient"),
    KlobObject("0074_KLOB", "Herb (Restorative)",   "material",
               note="Dried herb with mental-axis affinity — noise reduction, restorative"),
    KlobObject("0075_KLOB", "Binding Wax",          "material",
               note="Rendered wax — cohesive agent, fixes field resonance in salves"),
    KlobObject("0076_KLOB", "Raw Desire Stone",     "material",
               note="Unrefined Asmodean crystal — spatial field, high intensity unfocused"),
    KlobObject("0077_KLOB", "Asmodean Essence",     "material",
               note="Refined desire-field liquid — concentrated spatial-axis reagent"),

    # ── Processing materials ──────────────────────────────────────────────────
    KlobObject("1001_KLOB", "Sand",                 "material"),
    KlobObject("1002_KLOB", "Refined Sand",         "material"),
    KlobObject("1003_KLOB", "Diatom Earth",         "filtering"),
    KlobObject("1004_KLOB", "Glycerine",            "chemical"),
    KlobObject("1005_KLOB", "Petroleum Jelly",      "chemical"),
    KlobObject("1006_KLOB", "Saltpeter",            "chemical"),
    KlobObject("1007_KLOB", "Sulphur",              "chemical"),
    KlobObject("1008_KLOB", "Charcoal",             "chemical"),
    KlobObject("1009_KLOB", "Ashes",                "chemical"),
    KlobObject("1010_KLOB", "Caustic Lye",          "chemical"),
    KlobObject("1011_KLOB", "Potassium",            "chemical"),
    KlobObject("1012_KLOB", "Phosphorus",           "chemical"),
    KlobObject("1013_KLOB", "Arsenic",              "chemical"),
    KlobObject("1014_KLOB", "Cyanide",              "chemical"),
    KlobObject("1015_KLOB", "Water",                "material"),
    KlobObject("1016_KLOB", "Wood",                 "material"),
    KlobObject("1017_KLOB", "Flint",                "mineral"),
    KlobObject("1018_KLOB", "Shark Tooth",          "mineral"),

    # ── Metals ────────────────────────────────────────────────────────────────
    KlobObject("2001_KLOB", "Tin",                  "metal"),
    KlobObject("2002_KLOB", "Iron",                 "metal"),
    KlobObject("2003_KLOB", "Gold",                 "metal"),
    KlobObject("2004_KLOB", "Copper",               "metal"),
    KlobObject("2005_KLOB", "Mercury",              "metal"),
    KlobObject("2006_KLOB", "Silver",               "metal"),
    KlobObject("2007_KLOB", "Lead",                 "metal"),
    KlobObject("2008_KLOB", "Nickel",               "metal"),

    # ── Minerals ──────────────────────────────────────────────────────────────
    KlobObject("3001_KLOB", "Granite",              "mineral"),
    KlobObject("3002_KLOB", "Obsidian",             "mineral"),
    KlobObject("3003_KLOB", "Chalk",                "mineral"),
    KlobObject("3004_KLOB", "Gypsum",               "mineral"),
    KlobObject("3005_KLOB", "Quartz",               "mineral"),
    KlobObject("3006_KLOB", "Pumice",               "mineral"),

    # ── Gems and special stones ───────────────────────────────────────────────
    KlobObject("4001_KLOB", "Amethyst",             "gem"),
    KlobObject("4002_KLOB", "Ruby",                 "gem"),
    KlobObject("4003_KLOB", "Sapphire",             "gem"),
    KlobObject("4004_KLOB", "Emerald",              "gem"),
    KlobObject("4005_KLOB", "Diamond",              "gem"),
    KlobObject("4006_KLOB", "Jade",                 "gem"),
    KlobObject("4007_KLOB", "Moldavite",            "gem"),
    KlobObject("4008_KLOB", "Desert Glass",         "gem"),
    KlobObject("4009_KLOB", "Pearl",                "gem"),
    KlobObject("4010_KLOB", "Black Pearl",          "gem"),

    # ── Writing materials ─────────────────────────────────────────────────────
    KlobObject("5001_KLOB", "Pulp",                 "writing"),
    KlobObject("5002_KLOB", "Paper",                "writing"),
    KlobObject("5003_KLOB", "Ink",                  "writing"),

    # ── Quest / realm-specific materials ─────────────────────────────────────
    KlobObject("9001_KLOB", "Demonic Iron",         "quest_material",
               note="Iron from Sulphera — carries the infernal register"),
    KlobObject("9002_KLOB", "Angelic Spear",        "quest_material",
               note="From Pride Ring ash fields — continuous extermination campaign"),
    KlobObject("9003_KLOB", "Crystal Dust",         "quest_material",
               note="Dissolved Asmodean Crystal from 0007 — reagent for Infernal Salve"),
    KlobObject("9004_KLOB", "Salt Water",           "quest_material",
               note="Ocean water — used to rust purified demonic iron in 0041"),
    KlobObject("9005_KLOB", "Purified Demonic Iron","quest_material",
               note="Intermediate: demonic iron purified over sulphur in furnace"),
    KlobObject("9006_KLOB", "Rusted Iron Vial",     "quest_material",
               note="Intermediate: rust from salt-corroded demonic iron, collected in vial"),
    KlobObject("9007_KLOB", "Angelic-Purified Iron","quest_material",
               note="Intermediate: demonic iron melted with angelic spears"),
    KlobObject("9008_KLOB", "Infernal Salve",       "quest_output",
               note="Enables descent into Sulphera rings. Made from Crystal Dust."),
    KlobObject("9009_KLOB", "Nexiott Poison",       "quest_output",
               note="Rusted iron vial mixed with mercury. Penetrates Kielum's protection."),
    KlobObject("9010_KLOB", "Colt .45",             "quest_output",
               note="Hypatia's Angelic Gun. Fires gold bullets. Only thing that can kill Sophia."),
)


# ── KlobRegistry ─────────────────────────────────────────────────────────────

class KlobRegistry:
    """Indexed lookup for all KLOB objects by ID and name."""

    def __init__(self) -> None:
        self._by_id:   dict[str, KlobObject] = {}
        self._by_name: dict[str, KlobObject] = {}
        for obj in ALL_OBJECTS:
            self._by_id[obj.id] = obj
            self._by_name[obj.name.lower()] = obj

    def get(self, klob_id: str) -> Optional[KlobObject]:
        return self._by_id.get(klob_id)

    def get_by_name(self, name: str) -> Optional[KlobObject]:
        return self._by_name.get(name.lower())

    def by_category(self, category: str) -> list[KlobObject]:
        return [o for o in ALL_OBJECTS if o.category == category]

    def __contains__(self, klob_id: str) -> bool:
        return klob_id in self._by_id

    def __len__(self) -> int:
        return len(self._by_id)


# ── Global singleton ──────────────────────────────────────────────────────────

_REGISTRY: Optional[KlobRegistry] = None


def klob_registry() -> KlobRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = KlobRegistry()
    return _REGISTRY
