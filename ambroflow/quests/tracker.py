"""
Quest Tracker
=============
Tracks quest state for a player in a session.

Quest IDs follow the format: {4-digit-zero-padded}_KLST  (e.g. 0009_KLST)
Game slugs follow:           {number}_KLGS               (e.g. 7_KLGS)

Quest completion gates:
  - Perk unlock (via SkillRuntime.complete_quest + unlock_perk)
  - Dungeon access (infernal_meditation perk ← 0009_KLST)
  - Narrative branch state

Completion events are recorded to the Orrery.  The multiverse stack stores
quest state in the workspace; this tracker is the in-session runtime face.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from ..orrery.client import OrreryClient


class QuestStatus(str, Enum):
    NOT_STARTED = "not_started"
    ACTIVE      = "active"
    COMPLETED   = "completed"
    FAILED      = "failed"


class QuestTracker:
    """
    In-session quest state.

    Parameters
    ----------
    actor_id:
        Player identifier.
    orrery:
        OrreryClient for recording quest events.
    completed_quests:
        Quest IDs completed before this session.
    active_quests:
        Quest IDs currently in progress.
    """

    def __init__(
        self,
        actor_id: str,
        orrery: OrreryClient,
        completed_quests: list[str] | None = None,
        active_quests: list[str] | None = None,
    ) -> None:
        self._actor_id  = actor_id
        self._orrery    = orrery
        self._completed = set(completed_quests or [])
        self._active    = set(active_quests or [])
        self._failed:   set[str] = set()

    # ── State queries ─────────────────────────────────────────────────────────

    def status(self, quest_id: str) -> QuestStatus:
        if quest_id in self._completed:
            return QuestStatus.COMPLETED
        if quest_id in self._failed:
            return QuestStatus.FAILED
        if quest_id in self._active:
            return QuestStatus.ACTIVE
        return QuestStatus.NOT_STARTED

    def is_completed(self, quest_id: str) -> bool:
        return quest_id in self._completed

    @property
    def completed(self) -> list[str]:
        return sorted(self._completed)

    @property
    def active(self) -> list[str]:
        return sorted(self._active)

    # ── Transitions ───────────────────────────────────────────────────────────

    def start(self, quest_id: str) -> None:
        if quest_id in self._completed:
            return
        self._active.add(quest_id)
        self._orrery.record("quest.started", {
            "actor_id": self._actor_id,
            "quest_id": quest_id,
        })

    def complete(self, quest_id: str, context: Optional[dict] = None) -> None:
        self._active.discard(quest_id)
        self._failed.discard(quest_id)
        self._completed.add(quest_id)
        self._orrery.record("quest.completed", {
            "actor_id": self._actor_id,
            "quest_id": quest_id,
            **(context or {}),
        })

    def fail(self, quest_id: str) -> None:
        self._active.discard(quest_id)
        self._failed.add(quest_id)
        self._orrery.record("quest.failed", {
            "actor_id": self._actor_id,
            "quest_id": quest_id,
        })
