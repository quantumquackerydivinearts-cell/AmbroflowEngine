"""
Divine Encounter
================
Voluntary daytime meditation encounters with cosmic entities at the altar.

Distinct from the nightly MeditationSession (BoK calibration + Negaya gate).
The altar in the player's home is accessible before the first letter and
opens two encounters available from game start:

  Ko           — Moon Goddess, Experience and Intuition.  Ko does not
                 explain; Ko reflects.  Her words are always already
                 what the player needed before they knew to need them.

  Moshize Jabiru — Moshize manifest as a Jabiru bird.  The God whose name
                   Saffron abuses, present here in their actual form —
                   patient, large-eyed, structurally honest.  Encountering
                   the real Moshize before Saffron's institutional version
                   is introduced lets the player know the difference.

Encounter structure
-------------------
Each encounter has a pool of short exchanges keyed by BoK weight and
sanity state.  The system selects from available exchanges based on the
player's current state and returns dialogue lines.  No lock-in, no
progression — the altar is always open and always honest.

A completed encounter applies a small sanity restoration and records
to the Orrery.  No perk required.  Breathwork meditation perk deepens
the available exchange pool slightly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any


# ── Exchange pool ─────────────────────────────────────────────────────────────
#
# Each exchange is a (condition, lines) pair.
# condition: lambda(ko_weight, sanity_avg) → bool
# lines: list of dialogue strings (speaker is implicit from the encounter)
#
# The selector picks all exchanges whose condition passes, then returns
# the one that best matches the player's state (highest condition specificity).
# Falls back to the "always" exchange if nothing matches.

@dataclass(frozen=True)
class Exchange:
    condition_key: str     # human-readable label for the condition
    lines:         tuple[str, ...]
    sanity_delta:  dict[str, float]   # applied on completion


# ── Ko exchanges ──────────────────────────────────────────────────────────────

KO_EXCHANGES: tuple[Exchange, ...] = (
    Exchange(
        condition_key="always",
        lines=(
            "You are here.",
            "That is enough to begin with.",
        ),
        sanity_delta={"alchemical": 0.02, "terrestrial": 0.02},
    ),
    Exchange(
        condition_key="low_sanity",
        lines=(
            "The noise is very loud today.",
            "That is not a failure.",
            "Noise is what the field sounds like before it finds its shape.",
        ),
        sanity_delta={"narrative": 0.03, "terrestrial": 0.03},
    ),
    Exchange(
        condition_key="high_ko_weight",
        lines=(
            "You have been carrying something for a long time.",
            "I know what it is.",
            "You do not have to name it here.",
        ),
        sanity_delta={"cosmic": 0.04, "alchemical": 0.02},
    ),
    Exchange(
        condition_key="early_game_fresh",
        lines=(
            "The letter has not arrived yet.",
            "This moment — before the asking — is yours.",
            "Remember what it feels like.",
        ),
        sanity_delta={"alchemical": 0.03, "narrative": 0.02},
    ),
    Exchange(
        condition_key="breathwork_active",
        lines=(
            "You have been practicing.",
            "I can tell.",
            "The field opens differently for someone who has learned to wait.",
        ),
        sanity_delta={"alchemical": 0.04, "cosmic": 0.03},
    ),
)


# ── Moshize Jabiru exchanges ───────────────────────────────────────────────────

MOSHIZE_JABIRU_EXCHANGES: tuple[Exchange, ...] = (
    Exchange(
        condition_key="always",
        lines=(
            "The Jabiru regards you without blinking.",
            "It does not move.",
            "It is simply present in the way that very old things are present.",
        ),
        sanity_delta={"terrestrial": 0.03, "cosmic": 0.02},
    ),
    Exchange(
        condition_key="low_sanity",
        lines=(
            "The Jabiru steps closer.",
            "One large eye, level with yours.",
            "You feel located.",
        ),
        sanity_delta={"terrestrial": 0.04, "narrative": 0.02},
    ),
    Exchange(
        condition_key="high_ko_weight",
        lines=(
            "The Jabiru makes a sound — not quite language, not quite silence.",
            "Something in it recognises what you have been through.",
            "It does not offer absolution. It offers company.",
        ),
        sanity_delta={"cosmic": 0.05, "terrestrial": 0.02},
    ),
    Exchange(
        condition_key="early_game_fresh",
        lines=(
            "The Jabiru stands at the altar as though it has always been there.",
            "It watches the door.",
            "Something is coming. It is not afraid.",
        ),
        sanity_delta={"terrestrial": 0.03, "alchemical": 0.02},
    ),
    Exchange(
        condition_key="breathwork_active",
        lines=(
            "The Jabiru tilts its head.",
            "Your breath has changed.",
            "It approves of this in the way that things which know deep time approve of small steadiness.",
        ),
        sanity_delta={"terrestrial": 0.03, "cosmic": 0.03},
    ),
)


# ── Condition evaluator ───────────────────────────────────────────────────────

def _select_exchange(
    pool:          tuple[Exchange, ...],
    ko_weight:     float,
    sanity_avg:    float,
    active_perks:  frozenset[str],
    letter_arrived: bool,
) -> Exchange:
    """
    Select the most contextually appropriate exchange from the pool.

    Priority order (highest specificity first):
    1. breathwork_active   — breathwork perk held
    2. high_ko_weight      — ko_weight > 0.4 (significant series history)
    3. low_sanity          — sanity_avg < 0.45
    4. early_game_fresh    — letter has not arrived
    5. always              — fallback
    """
    has_breathwork = "breathwork_meditation" in active_perks

    priority = [
        ("breathwork_active", has_breathwork),
        ("high_ko_weight",    ko_weight > 0.4),
        ("low_sanity",        sanity_avg < 0.45),
        ("early_game_fresh",  not letter_arrived),
        ("always",            True),
    ]

    for key, passes in priority:
        if passes:
            for exchange in pool:
                if exchange.condition_key == key:
                    return exchange

    return pool[-1]   # guaranteed "always" fallback


# ── Encounter types ───────────────────────────────────────────────────────────

class DivineEncounterKind:
    KO             = "ko"
    MOSHIZE_JABIRU = "moshize_jabiru"


@dataclass
class DivineEncounterResult:
    entity:       str                # DivineEncounterKind value
    lines:        tuple[str, ...]    # dialogue lines to render
    sanity_delta: dict[str, float]   # applied by caller to LiveSanity
    exchange_key: str                # condition_key of the selected exchange


# ── Main encounter function ───────────────────────────────────────────────────

def encounter_ko(
    ko_weight:     float,
    sanity_avg:    float,
    active_perks:  frozenset[str],
    letter_arrived: bool = False,
    orrery: Optional[Any] = None,
    actor_id: str = "player",
) -> DivineEncounterResult:
    """Conduct a voluntary Ko encounter at the altar."""
    exchange = _select_exchange(
        KO_EXCHANGES, ko_weight, sanity_avg, active_perks, letter_arrived
    )
    if orrery is not None:
        orrery.record("divine_encounter.ko", {
            "actor_id":     actor_id,
            "exchange_key": exchange.condition_key,
            "ko_weight":    ko_weight,
            "sanity_avg":   sanity_avg,
        })
    return DivineEncounterResult(
        entity=DivineEncounterKind.KO,
        lines=exchange.lines,
        sanity_delta=exchange.sanity_delta,
        exchange_key=exchange.condition_key,
    )


def encounter_moshize_jabiru(
    ko_weight:     float,
    sanity_avg:    float,
    active_perks:  frozenset[str],
    letter_arrived: bool = False,
    orrery: Optional[Any] = None,
    actor_id: str = "player",
) -> DivineEncounterResult:
    """Conduct a voluntary Moshize Jabiru encounter at the altar."""
    exchange = _select_exchange(
        MOSHIZE_JABIRU_EXCHANGES, ko_weight, sanity_avg, active_perks, letter_arrived
    )
    if orrery is not None:
        orrery.record("divine_encounter.moshize_jabiru", {
            "actor_id":     actor_id,
            "exchange_key": exchange.condition_key,
            "ko_weight":    ko_weight,
            "sanity_avg":   sanity_avg,
        })
    return DivineEncounterResult(
        entity=DivineEncounterKind.MOSHIZE_JABIRU,
        lines=exchange.lines,
        sanity_delta=exchange.sanity_delta,
        exchange_key=exchange.condition_key,
    )


# ── Altar dispatch ────────────────────────────────────────────────────────────

ALTAR_ENTITIES: tuple[str, ...] = (
    DivineEncounterKind.KO,
    DivineEncounterKind.MOSHIZE_JABIRU,
)

ALTAR_ENTITY_LABELS: dict[str, str] = {
    DivineEncounterKind.KO:             "Ko",
    DivineEncounterKind.MOSHIZE_JABIRU: "Moshize Jabiru",
}


def altar_encounter(
    entity:        str,
    ko_weight:     float,
    sanity_avg:    float,
    active_perks:  frozenset[str],
    letter_arrived: bool = False,
    orrery: Optional[Any] = None,
    actor_id: str = "player",
) -> Optional[DivineEncounterResult]:
    """
    Dispatch an altar encounter by entity name.
    Returns None for unknown entity names.
    """
    if entity == DivineEncounterKind.KO:
        return encounter_ko(ko_weight, sanity_avg, active_perks,
                            letter_arrived, orrery, actor_id)
    if entity == DivineEncounterKind.MOSHIZE_JABIRU:
        return encounter_moshize_jabiru(ko_weight, sanity_avg, active_perks,
                                        letter_arrived, orrery, actor_id)
    return None
