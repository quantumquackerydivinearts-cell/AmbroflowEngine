"""
Skill Registry (Python)
=======================
Canonical skill and perk definitions for the KLGS series.
Mirrors skillRegistry.js — authoritative source is the JS file;
this Python copy is used by the Ambroflow Engine at runtime.

Meditation perks are quest-gated, NOT rank-gated.
Each meditation perk unlocks when the associated quest is completed.
No meditation perk requires another meditation perk as a prerequisite.

VITRIOL: V=Vitality I=Introspection R=Reflectivity T=Tactility
         I=Ingenuity  O=Ostentation  L=Levity
         (Ingenuity is the second I — context distinguishes)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class PerkDef:
    id: str
    name: str
    required_skill: str
    required_quest: Optional[str]
    required_perks: tuple[str, ...]
    effect: str
    sanity_delta: dict[str, float]
    stack_event: Optional[str]
    gates: Optional[dict[str, bool]]


@dataclass(frozen=True)
class SkillDef:
    id: str
    name: str
    max_rank: int
    vitriol_affinity: str   # single letter from VITRIOL
    sanity_dimension: str   # alchemical | narrative | terrestrial | cosmic
    perks: tuple[PerkDef, ...]
    note: str = ""


# ── Meditation perks ──────────────────────────────────────────────────────────

MEDITATION_PERKS: tuple[PerkDef, ...] = (
    PerkDef(
        id="breathwork_meditation",
        name="Breathwork Meditation",
        required_skill="meditation",
        required_quest=None,
        required_perks=(),
        effect=(
            "Conscious breath control as meditative anchor. Stabilizes sanity during high-pressure "
            "encounters — reduces dissonance drift on the Terrestrial and Alchemical axes. "
            "The body is the first instrument."
        ),
        sanity_delta={"terrestrial": 0.04, "alchemical": 0.03},
        stack_event="skill.perk.breathwork_meditation.unlocked",
        gates=None,
    ),
    PerkDef(
        id="alchemical_meditation",
        name="Alchemical Meditation",
        required_skill="meditation",
        required_quest="0008_KLST",    # Bunsen For Hire
        required_perks=(),
        effect=(
            "Meditation as transmutation process — the inner coil mirrors the outer work. "
            "Boosts Alchemical sanity. When both meditation and alchemy skills are trained, "
            "each reinforces the other. Hypatia's native method."
        ),
        sanity_delta={"alchemical": 0.06},
        stack_event="skill.perk.alchemical_meditation.unlocked",
        gates=None,
    ),
    PerkDef(
        id="hypnotic_meditation",
        name="Hypnotic Meditation",
        required_skill="meditation",
        required_quest="0007_KLST",    # Dream of Glass (narrative pos. ~0008-0009)
        required_perks=(),
        effect=(
            "Directed trance states. Unlocks dialogue options with entities that only speak "
            "to minds that have voluntarily softened their threshold. "
            "Enables deeper Undine and Faerie encounter outcomes. "
            "Presses Narrative sanity upward — trance coherence generates story clarity."
        ),
        sanity_delta={"narrative": 0.04, "cosmic": 0.02},
        stack_event="skill.perk.hypnotic_meditation.unlocked",
        gates=None,
    ),
    PerkDef(
        id="infernal_meditation",
        name="Infernal Meditation",
        required_skill="meditation",
        required_quest="0009_KLST",    # Demons and Diamonds
        required_perks=(),
        effect=(
            "The ability to hold consciousness in the Underworld's register without dissolution. "
            "This perk gates Sulphera access — opens the Visitor's Ring (Ring 8). "
            "In Game 7, Alfir (0006_WTCH) delivers the teaching embedded in quest 0009_KLST. "
            "Boosts Cosmic sanity substantially — sustaining infernal presence is a cosmic act."
        ),
        sanity_delta={"cosmic": 0.08},
        stack_event="skill.perk.infernal_meditation.unlocked",
        gates={"sulphera_access": True},
    ),
    PerkDef(
        id="depth_meditation",
        name="Depth Meditation",
        required_skill="meditation",
        required_quest="0011_KLST",    # The Siren Sounds
        required_perks=(),
        effect=(
            "Access to the sub-threshold layers — the place below identity where the coil "
            "becomes visible. The 24-layer dream calibration reads deeper with this perk active. "
            "All four sanity dimensions are boosted moderately. "
            "The Void Wraiths take notice of players who reach this depth."
        ),
        sanity_delta={"alchemical": 0.03, "narrative": 0.03, "terrestrial": 0.03, "cosmic": 0.03},
        stack_event="skill.perk.depth_meditation.unlocked",
        gates=None,
    ),
    PerkDef(
        id="transcendental_meditation",
        name="Transcendental Meditation",
        required_skill="meditation",
        required_quest="0016_KLST",    # Transcendental
        required_perks=(),
        effect=(
            "Mantra-based access to deep rest states. Boosts Cosmic sanity — the player "
            "sits more comfortably inside the Orrery's scale. Ko is more legible in dream sequences."
        ),
        sanity_delta={"cosmic": 0.05},
        stack_event="skill.perk.transcendental_meditation.unlocked",
        gates=None,
    ),
    PerkDef(
        id="zen_meditation",
        name="Zen Meditation",
        required_skill="meditation",
        required_quest="0026_KLST",    # Good Grief
        required_perks=(),
        effect=(
            "Presence without object. Reduces encounter-induced Narrative dissonance — "
            "the player accepts contradiction without fragmenting their story sense. "
            "The latest-unlocking meditation perk; grief is its prerequisite in the world."
        ),
        sanity_delta={"narrative": 0.05},
        stack_event="skill.perk.zen_meditation.unlocked",
        gates=None,
    ),
)

# ── Full skill registry ────────────────────────────────────────────────────────

SKILLS: tuple[SkillDef, ...] = (
    SkillDef("barter",          "Barter",          5, "O", "narrative",   ()),
    SkillDef("energy_weapons",  "Energy Weapons",  5, "I", "cosmic",      ()),
    SkillDef("explosives",      "Explosives",      5, "T", "terrestrial", ()),
    SkillDef("guns",            "Guns",            5, "T", "terrestrial", ()),
    SkillDef("lockpick",        "Lockpick",        5, "I", "narrative",   ()),
    SkillDef("medicine",        "Medicine",        5, "R", "terrestrial", ()),
    SkillDef("melee_weapons",   "Melee Weapons",   5, "V", "terrestrial", ()),
    SkillDef("repair",          "Repair",          5, "T", "alchemical",  ()),
    SkillDef("alchemy",         "Alchemy",         5, "R", "alchemical",  (),
             note="Hypatia's primary skill. Synergizes with alchemical_meditation perk."),
    SkillDef("sneak",           "Sneak",           5, "L", "narrative",   ()),
    SkillDef("hack",            "Hack",            5, "I", "alchemical",  ()),
    SkillDef("speech",          "Speech",          5, "L", "narrative",   ()),
    SkillDef("survival",        "Survival",        5, "V", "terrestrial", ()),
    SkillDef("unarmed",         "Unarmed",         5, "V", "terrestrial", ()),
    SkillDef("meditation",      "Meditation",      5, "I", "cosmic",      MEDITATION_PERKS,
             note="Only skill with a full perk tree. Infernal Meditation gates Sulphera."),
    SkillDef("magic",           "Magic",           5, "L", "cosmic",      ()),
    SkillDef("blacksmithing",   "Blacksmithing",   5, "T", "alchemical",  ()),
    SkillDef("silversmithing",  "Silversmithing",  5, "O", "alchemical",  ()),
    SkillDef("goldsmithing",    "Goldsmithing",    5, "O", "alchemical",  (),
             note="Desire Crystal (Asmodean material) is goldsmithing-adjacent."),
)

# ── Lookups ───────────────────────────────────────────────────────────────────

SKILL_BY_ID: dict[str, SkillDef] = {s.id: s for s in SKILLS}
ALL_PERKS: tuple[PerkDef, ...] = tuple(p for s in SKILLS for p in s.perks)
PERK_BY_ID: dict[str, PerkDef] = {p.id: p for p in ALL_PERKS}
