"""
Encounter Resolver
==================
Resolves player actions within encounters.

Encounter types:
  combat       — Fight resolution, health/stamina checks
  negotiation  — Speech/barter checks; VITRIOL-modulated outcomes
  observation  — Perception / lore; Void Wraith may watch
  trap         — Survival/lockpick checks; damage on failure
  lore         — Pure narrative; always yields sanity delta + journal entry

Each encounter type exposes a handler function.  `resolve()` dispatches to
the correct handler based on action string and encounter context.

This module is deliberately minimal — outcome logic will expand as each game's
encounter tables are designed.  Right now it returns well-typed scaffolding
that the runtime can act on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class EncounterContext:
    encounter_type: str
    difficulty: float            # 0.0–1.0
    dungeon_id: str
    actor_skill_ranks: dict[str, int] = field(default_factory=dict)
    actor_perks: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EncounterResult:
    outcome: str                  # "success" | "partial" | "failure" | "fled"
    sanity_delta: dict[str, float] = field(default_factory=dict)
    token_granted: Optional[str] = None
    loot: list[str] = field(default_factory=list)
    journal_entry: Optional[str] = None
    void_wraith_observation: Optional[str] = None


# ── Handlers ──────────────────────────────────────────────────────────────────

def _resolve_combat(action: str, ctx: EncounterContext) -> EncounterResult:
    rank = ctx.actor_skill_ranks.get("melee_weapons", 0) or \
           ctx.actor_skill_ranks.get("guns", 0) or \
           ctx.actor_skill_ranks.get("unarmed", 0)
    effective = rank / 5.0
    if effective >= ctx.difficulty:
        return EncounterResult(
            outcome="success",
            sanity_delta={"terrestrial": 0.02},
        )
    elif effective >= ctx.difficulty * 0.6:
        return EncounterResult(
            outcome="partial",
            sanity_delta={"terrestrial": -0.01},
        )
    else:
        return EncounterResult(
            outcome="failure",
            sanity_delta={"terrestrial": -0.04, "narrative": -0.02},
        )


def _resolve_negotiation(action: str, ctx: EncounterContext) -> EncounterResult:
    speech = ctx.actor_skill_ranks.get("speech", 0)
    barter = ctx.actor_skill_ranks.get("barter", 0)
    effective = max(speech, barter) / 5.0
    if effective >= ctx.difficulty:
        return EncounterResult(
            outcome="success",
            sanity_delta={"narrative": 0.03},
        )
    return EncounterResult(
        outcome="failure",
        sanity_delta={"narrative": -0.02},
    )


def _resolve_observation(action: str, ctx: EncounterContext) -> EncounterResult:
    # Observation encounters always partially succeed — they are about witnessing,
    # not winning.  Depth Meditation perk deepens the yield.
    deep = "depth_meditation" in ctx.actor_perks
    delta = {"cosmic": 0.02, "narrative": 0.02}
    if deep:
        delta = {"cosmic": 0.04, "narrative": 0.03}
    return EncounterResult(
        outcome="success",
        sanity_delta=delta,
        void_wraith_observation="encounter.observation.witnessed",
    )


def _resolve_trap(action: str, ctx: EncounterContext) -> EncounterResult:
    survival = ctx.actor_skill_ranks.get("survival", 0)
    lockpick = ctx.actor_skill_ranks.get("lockpick", 0)
    effective = max(survival, lockpick) / 5.0
    if effective >= ctx.difficulty:
        return EncounterResult(outcome="success")
    return EncounterResult(
        outcome="failure",
        sanity_delta={"terrestrial": -0.03},
    )


def _resolve_lore(action: str, ctx: EncounterContext) -> EncounterResult:
    # Lore encounters always succeed; they are narrative gifts.
    return EncounterResult(
        outcome="success",
        sanity_delta={"narrative": 0.04, "cosmic": 0.01},
        journal_entry="lore_fragment",
    )


# ── Dispatch ──────────────────────────────────────────────────────────────────

_HANDLERS = {
    "combat":      _resolve_combat,
    "negotiation": _resolve_negotiation,
    "observation": _resolve_observation,
    "trap":        _resolve_trap,
    "lore":        _resolve_lore,
}


def resolve(action: str, player: Any, dungeon_def: Any, context: dict[str, Any]) -> dict[str, Any]:
    """
    Thin adapter used by DungeonRuntime.act().

    Returns a plain dict for compatibility with the runtime layer.
    """
    enc_type = context.get("encounter_type", "combat")
    difficulty = context.get("difficulty", 0.5)

    ctx = EncounterContext(
        encounter_type=enc_type,
        difficulty=difficulty,
        dungeon_id=dungeon_def.id if dungeon_def else "",
        actor_skill_ranks=getattr(player, "skill_ranks", {}),
        actor_perks=getattr(player, "unlocked_perks", []),
        extra=context,
    )

    handler = _HANDLERS.get(enc_type, _HANDLERS["combat"])
    result = handler(action, ctx)

    out: dict[str, Any] = {"outcome": result.outcome}
    if result.sanity_delta:
        out["sanity_delta"] = result.sanity_delta
    if result.token_granted:
        out["token_granted"] = result.token_granted
    if result.loot:
        out["loot"] = result.loot
    if result.journal_entry:
        out["journal_entry"] = result.journal_entry
    return out
