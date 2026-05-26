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
# Derived directly from the canonical skill registry — no separate list to drift.
# All skills begin at rank 5 (1–100 scale) — foundational competence.
# VITRIOL-derived skills reach 10–25; tagged skills reach 30.

from ambroflow.skills.registry import SKILLS as _SKILLS

GAME7_SKILLS: tuple[str, ...] = tuple(s.id for s in _SKILLS)

# Base starting rank on the 1–100 scale
_BASE_RANK     = 5
_VITRIOL_LOW   = 10   # VITRIOL score 1–4
_VITRIOL_MID   = 18   # VITRIOL score 5–7
_VITRIOL_HIGH  = 25   # VITRIOL score 8–10
_TAG_RANK      = 30   # manually tagged skill floor


def game7_starting_skill_ranks(chargen=None) -> dict[str, int]:
    """
    Build starting skill ranks for Game 7 on the 1–100 scale.

    Without chargen: all skills start at rank 5.
    With chargen (from ChargenState after SKILL_SELECT):
      - VITRIOL-derived ranks replace the base (10 / 18 / 25 by tier)
      - Tag picks floor the skill at 30, regardless of derived rank
    """
    base: dict[str, int] = {skill: _BASE_RANK for skill in GAME7_SKILLS}
    if chargen is None:
        return base

    # Layer 1 — VITRIOL-derived ranks
    derived: dict[str, int] = getattr(chargen, "vitriol_skill_ranks", {})
    for skill_id, rank in derived.items():
        if skill_id in base:
            # rank is 1–3 from _derive_rank(); map to 1–100 tiers
            tier_rank = (_VITRIOL_LOW if rank == 1 else
                         _VITRIOL_MID if rank == 2 else
                         _VITRIOL_HIGH)
            base[skill_id] = max(base[skill_id], tier_rank)

    # Layer 2 — manual tag picks: floor at _TAG_RANK
    tag_picks: list[str] = getattr(chargen, "tag_picks", [])
    for skill_id in tag_picks:
        if skill_id in base:
            base[skill_id] = max(base[skill_id], _TAG_RANK)

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
