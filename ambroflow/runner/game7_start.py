"""
game7_start.py — Canonical starting state for Game 7 (7_KLGS).

All skill ranks begin at 1.  The player's home is well-stocked before the
first letter arrives, allowing free alchemy and meditation exploration
before the plot makes any demands.

Apparatus present in the home (furnace built in, mortar/pestle on the Study
workbench) are included in the starting inventory so the alchemy system can
find them via the inventory dict — placement is visual; inventory is functional.
"""

from __future__ import annotations


# ── Starting inventory (KLOB IDs → quantity) ─────────────────────────────────
#
# Apparatus: permanently installed in the home.  Mortar/pestle on Study bench,
# furnace in Kitchen wall, crucible and vessels in the kitchen cabinet.
# These are never consumed — the alchemy system checks them as required_objects.
#
# Materials: a generous pre-letter stock covering all five starting subjects.

def game7_starting_inventory() -> dict[str, int]:
    return {
        # ── Home apparatus (environmental — always present) ───────────────────
        "8000_KLOB": 1,   # Mortar          (Study workbench)
        "2000_KLOB": 1,   # Pestle          (Study workbench)
        "0030_KLOB": 1,   # Furnace         (Kitchen wall, built-in)
        "0007_KLOB": 2,   # Crucible        (Kitchen cabinet)
        "0009_KLOB": 3,   # Jar             (Kitchen cabinet)
        "0005_KLOB": 4,   # Reagent Bottle  (Study shelf)
        "0003_KLOB": 1,   # Retort          (Study bench)
        "0004_KLOB": 1,   # Volume Flask    (Study bench)
        "0020_KLOB": 2,   # Wooden Spoon    (Kitchen)
        "0021_KLOB": 1,   # Copper Spoon    (Kitchen)
        "0001_KLOB": 3,   # Rag             (Kitchen)
        "0002_KLOB": 2,   # Stand           (Study)
        "0006_KLOB": 1,   # Bellows         (Kitchen)

        # ── Botanicals and consumable ingredients ─────────────────────────────
        "0073_KLOB": 8,   # Herb (Common)       — base for Basic Tincture
        "0074_KLOB": 6,   # Herb (Restorative)  — base for Restorative Tincture
        "0075_KLOB": 4,   # Binding Wax         — Infernal Salve cohesive
        "0076_KLOB": 2,   # Raw Desire Stone    — Desire Crystal ingredient
        "0077_KLOB": 2,   # Asmodean Essence    — Desire Crystal ingredient
        "0040_KLOB": 6,   # Water Flask         — universal solvent

        # ── Processing chemicals ──────────────────────────────────────────────
        "1007_KLOB": 5,   # Sulphur             — Infernal Salve ingredient
        "1008_KLOB": 4,   # Charcoal            — heat/reduction
        "1006_KLOB": 3,   # Saltpeter           — oxidation reactions
        "1003_KLOB": 3,   # Diatom Earth        — filtering
        "1004_KLOB": 2,   # Glycerine           — carrier/binding agent
        "1015_KLOB": 4,   # Water               — general solvent

        # ── Minerals ─────────────────────────────────────────────────────────
        "3005_KLOB": 3,   # Quartz              — crystal work, receiver recipe
        "3003_KLOB": 4,   # Chalk               — neutralising agent
        "3001_KLOB": 2,   # Granite             — grinding substrate
        "3006_KLOB": 2,   # Pumice              — abrasive/filtering

        # ── Currency ─────────────────────────────────────────────────────────
        "0050_KLIT": 40,  # Copper Coins        — enough to buy from the shop freely
        "0051_KLIT": 5,   # Silver Coins
    }


# ── Starting skill ranks ──────────────────────────────────────────────────────
#
# All skills begin at rank 1 — the player is an apprentice who has been
# trained in the fundamentals, not a beginner starting from zero.
# Ranks are 1–5; rank 1 = foundational competence.

GAME7_SKILLS: tuple[str, ...] = (
    "alchemy",
    "medicine",
    "meditation",
    "survival",
    "hack",
    "combat",
    "persuasion",
    "stealth",
    "crafting",
    "herbalism",
    "navigation",
    "lore",
    "music",
    "athletics",
    "perception",
    "smithing",
    "cooking",
    "trading",
    "engineering",
)


def game7_starting_skill_ranks(chargen=None) -> dict[str, int]:
    """
    Build starting skill ranks for Game 7.

    Without chargen: all skills start at rank 1.
    With chargen (from ChargenState after SKILL_SELECT):
      - VITRIOL-derived ranks are applied (auto-computed from VITRIOL profile)
      - Tag picks get an additional +1 rank boost
    """
    base: dict[str, int] = {skill: 1 for skill in GAME7_SKILLS}
    if chargen is None:
        return base

    # Layer 1 — VITRIOL-derived base ranks
    derived: dict[str, int] = getattr(chargen, "vitriol_skill_ranks", {})
    for skill_id, rank in derived.items():
        if skill_id in base:
            base[skill_id] = max(base[skill_id], rank)

    # Layer 2 — manual tag picks (+1 on top of derived)
    tag_picks: list[str] = getattr(chargen, "tag_picks", [])
    for skill_id in tag_picks:
        if skill_id in base:
            base[skill_id] = min(base[skill_id] + 1, 5)   # cap at max rank 5

    return base


# ── Starting meditation perks ─────────────────────────────────────────────────
#
# Only Breathwork is available before any quest — it requires no gate.
# All other perks are quest-gated and start locked.

def game7_starting_perks() -> frozenset[str]:
    return frozenset({"breathwork_meditation"})


# ── Convenience: full starting state bundle ───────────────────────────────────

def game7_starting_state() -> dict:
    return {
        "inventory":    game7_starting_inventory(),
        "skill_ranks":  game7_starting_skill_ranks(),
        "active_perks": list(game7_starting_perks()),
        "game_id":      "7_KLGS",
    }
