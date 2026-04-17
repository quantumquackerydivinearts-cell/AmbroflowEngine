"""
Character Creation Data
=======================
Canonical data for Game 7 (7_KLGS) character creation.

Lineage options (5)
-------------------
Starting context for Hypatia's apprentice.  Lineage shapes initial
relationships, some starting inventory, and a few locked/unlocked
dialogue options — not stats.  VITRIOL is assigned by Ko from
calibration; lineage does not modify it.

Gender options (7+)
-------------------
Presented through Ko during the arrival sequence, before calibration
begins.  Ko's framing is phenomenological, not administrative.
The selection is recorded in game state and surfaced in dialogue where
relevant.  NPCs address the player accordingly.

Ko's gender prompt: "The shape you move through the world with."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Lineage ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LineageOption:
    id:            str
    name:          str
    description:   str          # shown on selection screen
    ko_note:       str          # what Ko observes about this ground — brief
    starting_items: list[str]   = field(default_factory=list)
    unlocks:        list[str]   = field(default_factory=list)  # dialogue flags


LINEAGE_OPTIONS: tuple[LineageOption, ...] = (
    LineageOption(
        id="azonithian_native",
        name="Azonithian Native",
        description=(
            "Born on Wiltoll Lane. You know which cobblestones are loose "
            "and which neighbours will lend you flour at midnight. "
            "The city is your body's memory, not your mind's."
        ),
        ko_note="The ground under you is the ground you grew in.",
        starting_items=["Wormwood (x2)", "Local Market Token"],
        unlocks=["azonithian_native_dialogue"],
    ),
    LineageOption(
        id="merchant_family",
        name="Merchant Family",
        description=(
            "Raised in trade. You know how things move — goods, coin, "
            "information. The shop is not strange to you. "
            "Neither is the art of a deal made at the edge of fair."
        ),
        ko_note="You arrived here the way goods arrive: purposefully.",
        starting_items=["Gold Coin (x3)", "Anise (x1)"],
        unlocks=["merchant_lineage_dialogue"],
    ),
    LineageOption(
        id="scholars_house",
        name="Scholar's House",
        description=(
            "Letters before work. You read before you were useful, "
            "and it made you useful differently. "
            "The apprenticeship is not a surprise — it is the next page."
        ),
        ko_note="The book was already open when you arrived.",
        starting_items=["Research Notes (partial)", "Fennel (x1)"],
        unlocks=["scholar_lineage_dialogue"],
    ),
    LineageOption(
        id="no_fixed_past",
        name="No Fixed Past",
        description=(
            "You arrived in Azonithia. That is all anyone needs to know. "
            "No one here is owed your history and you have not volunteered it. "
            "The shop is yours because you are here and you work."
        ),
        ko_note="The past is present but not announced.",
        starting_items=["White Wine (x1)"],
        unlocks=["no_past_lineage_dialogue"],
    ),
    LineageOption(
        id="lapidus_touched",
        name="Lapidus-Touched",
        description=(
            "The Overworld has always felt closer than it should. "
            "You have never been able to explain this to anyone's satisfaction, "
            "including your own. Lapidus notices you back."
        ),
        ko_note="The Overworld already has a read on you.",
        starting_items=["Quartz (x1)"],
        unlocks=["lapidus_touched_dialogue", "early_lapidus_affinity"],
    ),
)

LINEAGE_BY_ID: dict[str, LineageOption] = {l.id: l for l in LINEAGE_OPTIONS}


# ── Gender ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GenderOption:
    id:           str
    label:        str           # displayed on the selection list
    ko_phrasing:  str           # Ko acknowledges the selection in her voice
    pronoun_set:  str           # "she/her" | "he/him" | "they/them" | "custom"


GENDER_OPTIONS: tuple[GenderOption, ...] = (
    GenderOption(
        id="woman",
        label="Woman",
        ko_phrasing="Woman. The shape is clear.",
        pronoun_set="she/her",
    ),
    GenderOption(
        id="man",
        label="Man",
        ko_phrasing="Man. The shape is clear.",
        pronoun_set="he/him",
    ),
    GenderOption(
        id="neither",
        label="Neither",
        ko_phrasing="Neither. The shape refuses the binary. That is its own precision.",
        pronoun_set="they/them",
    ),
    GenderOption(
        id="both",
        label="Both",
        ko_phrasing="Both. The shape holds the whole of it simultaneously.",
        pronoun_set="they/them",
    ),
    GenderOption(
        id="fluid",
        label="Fluid — the shape is not fixed",
        ko_phrasing="Fluid. The shape moves. I will read what is present each time.",
        pronoun_set="they/them",
    ),
    GenderOption(
        id="void_form",
        label="Void-form — no social shape",
        ko_phrasing=(
            "Void-form. No social shape — only function and presence. "
            "The Djinn understand this. I do as well."
        ),
        pronoun_set="they/them",
    ),
    GenderOption(
        id="unnamed",
        label="Something that doesn't translate here",
        ko_phrasing=(
            "Something that doesn't translate. "
            "I will not name it for you. It is yours."
        ),
        pronoun_set="they/them",
    ),
)

GENDER_BY_ID: dict[str, GenderOption] = {g.id: g for g in GENDER_OPTIONS}

# Ko's opening prompt for the gender question
KO_GENDER_PROMPT = "The shape you move through the world with."


# ── Chargen state ─────────────────────────────────────────────────────────────

@dataclass
class ChargenState:
    """
    Mutable state accumulated during character creation.
    Passed between screens as the player makes choices.

    name:           player-entered name
    gender_id:      selected gender option id
    lineage_id:     selected lineage option id
    player_vitriol: manually-assigned VITRIOL stats (empty until assigned)
    """
    name:           str              = ""
    gender_id:      str              = ""
    lineage_id:     str              = ""
    player_vitriol: dict[str, int]   = field(default_factory=dict)

    def is_complete(self) -> bool:
        from ambroflow.ko.vitriol import VITRIOL_STATS
        return (
            bool(self.name.strip())
            and bool(self.gender_id)
            and bool(self.lineage_id)
            and set(self.player_vitriol.keys()) == set(VITRIOL_STATS)
        )

    @property
    def lineage(self) -> Optional[LineageOption]:
        return LINEAGE_BY_ID.get(self.lineage_id)

    @property
    def gender(self) -> Optional[GenderOption]:
        return GENDER_BY_ID.get(self.gender_id)