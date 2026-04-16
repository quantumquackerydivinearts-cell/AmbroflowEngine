"""
Skill Runtime
=============
Live skill and perk state for an active player session.

Tracks:
  - Skill ranks (0 = untrained, 1–5 = trained)
  - Unlocked perks
  - Completed quests
  - Perk unlock eligibility

Writes perk unlock events to the Orrery when a perk is unlocked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .registry import PERK_BY_ID, SkillDef
from ..orrery.client import OrreryClient


@dataclass
class PerkUnlockResult:
    success: bool
    perk_id: str
    reason: str
    sanity_delta: dict[str, float] = field(default_factory=dict)
    gates: Optional[dict[str, bool]] = None


class SkillRuntime:
    """
    Mutable skill/perk state for one player in one session.

    Parameters
    ----------
    actor_id:
        Player identifier.
    orrery:
        OrreryClient — perk unlock events are recorded here.
    skill_ranks:
        Initial ranks dict.  Skills absent from the dict are untrained.
    unlocked_perks:
        Perks already unlocked at session start.
    completed_quests:
        Quest IDs completed before or during this session.
    """

    def __init__(
        self,
        actor_id: str,
        orrery: OrreryClient,
        skill_ranks: dict[str, int] | None = None,
        unlocked_perks: list[str] | None = None,
        completed_quests: list[str] | None = None,
    ) -> None:
        self._actor_id        = actor_id
        self._orrery          = orrery
        self._ranks:   dict[str, int]  = dict(skill_ranks or {})
        self._perks:   set[str]        = set(unlocked_perks or [])
        self._quests:  set[str]        = set(completed_quests or [])

    # ── Queries ───────────────────────────────────────────────────────────────

    def has_skill(self, skill_id: str) -> bool:
        return self._ranks.get(skill_id, 0) > 0

    def rank(self, skill_id: str) -> int:
        return self._ranks.get(skill_id, 0)

    def has_perk(self, perk_id: str) -> bool:
        return perk_id in self._perks

    def has_quest(self, quest_id: str) -> bool:
        return quest_id in self._quests

    def has_sulphera_access(self) -> bool:
        return "infernal_meditation" in self._perks

    # ── Mutations ─────────────────────────────────────────────────────────────

    def train_skill(self, skill_id: str, to_rank: int = 1) -> None:
        """Set skill rank.  Clamps to [0, 5]."""
        self._ranks[skill_id] = max(0, min(5, to_rank))

    def complete_quest(self, quest_id: str) -> None:
        self._quests.add(quest_id)
        self._orrery.record("quest.completed", {
            "actor_id": self._actor_id,
            "quest_id": quest_id,
        })

    def unlock_perk(self, perk_id: str) -> PerkUnlockResult:
        """
        Attempt to unlock a perk.

        Returns a PerkUnlockResult indicating success or the reason for failure.
        On success, fires the perk's stack_event to the Orrery and applies
        sanity_delta via record_sanity_delta.
        """
        perk = PERK_BY_ID.get(perk_id)
        if perk is None:
            return PerkUnlockResult(success=False, perk_id=perk_id, reason="Unknown perk.")

        if perk_id in self._perks:
            return PerkUnlockResult(success=False, perk_id=perk_id, reason="Already unlocked.")

        if not self.has_skill(perk.required_skill):
            return PerkUnlockResult(
                success=False, perk_id=perk_id,
                reason=f"Requires skill: {perk.required_skill}",
            )

        if perk.required_quest and perk.required_quest not in self._quests:
            return PerkUnlockResult(
                success=False, perk_id=perk_id,
                reason=f"Requires quest: {perk.required_quest}",
            )

        missing = [p for p in perk.required_perks if p not in self._perks]
        if missing:
            return PerkUnlockResult(
                success=False, perk_id=perk_id,
                reason=f"Missing prerequisite perks: {', '.join(missing)}",
            )

        # Unlock
        self._perks.add(perk_id)

        if perk.sanity_delta:
            self._orrery.record_sanity_delta(
                actor_id=self._actor_id,
                deltas=perk.sanity_delta,
                context={"event": perk.stack_event},
            )

        if perk.stack_event:
            self._orrery.record(perk.stack_event, {
                "actor_id": self._actor_id,
                "perk_id": perk_id,
                "gates": perk.gates,
            })

        return PerkUnlockResult(
            success=True, perk_id=perk_id,
            reason="Unlocked.",
            sanity_delta=dict(perk.sanity_delta),
            gates=perk.gates,
        )

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        return {
            "actor_id": self._actor_id,
            "skill_ranks": dict(self._ranks),
            "unlocked_perks": sorted(self._perks),
            "completed_quests": sorted(self._quests),
        }
