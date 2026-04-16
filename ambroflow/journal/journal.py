"""
Journal System
==============
The player's in-world journal.  Records narrative events, lore fragments,
quest notes, character observations, and alchemical discoveries.

The journal has two faces:
  Waking journal  — events during dungeon runs, quests, encounters
  Dream journal   — entries written during Ko dream sequences; linked to
                    the 24-layer dream calibration (secondary system)

All entries are recorded to the Orrery so that the multiverse stack can
observe journal growth patterns.  The Void Wraiths pay attention to what
Hypatia writes down.

Entry kinds:
  quest_note       — quest progress and objective updates
  lore_fragment    — discovered lore from lore encounters
  character_note   — observations about characters
  encounter_note   — notable encounter outcomes
  alchemy_note     — crafting discoveries and recipe annotations
  dream_note       — Ko dream sequence entries (dream journal)
  reflection       — player-authored free text (in-game equivalent of diary)
  observation      — things witnessed but not yet understood
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..orrery.client import OrreryClient


class EntryKind(str, Enum):
    QUEST_NOTE     = "quest_note"
    LORE_FRAGMENT  = "lore_fragment"
    CHARACTER_NOTE = "character_note"
    ENCOUNTER_NOTE = "encounter_note"
    ALCHEMY_NOTE   = "alchemy_note"
    DREAM_NOTE     = "dream_note"
    REFLECTION     = "reflection"
    OBSERVATION    = "observation"


@dataclass
class JournalEntry:
    id: str
    kind: EntryKind
    title: str
    body: str
    tags: list[str]
    timestamp: float
    game_id: str
    dream_face: bool = False    # True = written in Ko dream state


class Journal:
    """
    Append-only player journal.

    Parameters
    ----------
    actor_id:
        Player identifier.
    game_id:
        Active game slug.
    orrery:
        OrreryClient — entries are recorded as orrery events.
    """

    def __init__(self, actor_id: str, game_id: str, orrery: OrreryClient) -> None:
        self._actor_id = actor_id
        self._game_id  = game_id
        self._orrery   = orrery
        self._entries: list[JournalEntry] = []
        self._seq: int = 0

    # ── Writing ───────────────────────────────────────────────────────────────

    def write(
        self,
        kind: EntryKind,
        title: str,
        body: str,
        tags: list[str] | None = None,
        dream_face: bool = False,
    ) -> JournalEntry:
        """
        Add an entry to the journal.

        Fires a journal.entry.written event to the Orrery.
        Dream-face entries also fire journal.dream.written (Void Wraiths observe these).
        """
        self._seq += 1
        entry = JournalEntry(
            id=f"{self._actor_id}.journal.{self._seq:04d}",
            kind=kind,
            title=title,
            body=body,
            tags=tags or [],
            timestamp=time.time(),
            game_id=self._game_id,
            dream_face=dream_face,
        )
        self._entries.append(entry)

        self._orrery.record("journal.entry.written", {
            "actor_id": self._actor_id,
            "entry_id": entry.id,
            "kind": kind.value,
            "title": title,
            "tags": tags or [],
            "dream_face": dream_face,
        })

        if dream_face:
            self._orrery.void_wraith_observe("journal.dream.written", {
                "actor_id": self._actor_id,
                "entry_id": entry.id,
                "title": title,
            })

        return entry

    # ── Convenience writers ───────────────────────────────────────────────────

    def quest_note(self, quest_id: str, title: str, body: str) -> JournalEntry:
        return self.write(EntryKind.QUEST_NOTE, title, body, tags=[quest_id])

    def lore_fragment(self, title: str, body: str, tags: list[str] | None = None) -> JournalEntry:
        return self.write(EntryKind.LORE_FRAGMENT, title, body, tags=tags)

    def character_note(self, character_id: str, title: str, body: str) -> JournalEntry:
        return self.write(EntryKind.CHARACTER_NOTE, title, body, tags=[character_id])

    def alchemy_note(self, recipe_id: str, title: str, body: str) -> JournalEntry:
        return self.write(EntryKind.ALCHEMY_NOTE, title, body, tags=[recipe_id])

    def dream_note(self, title: str, body: str, tags: list[str] | None = None) -> JournalEntry:
        return self.write(EntryKind.DREAM_NOTE, title, body, tags=tags, dream_face=True)

    def reflection(self, title: str, body: str) -> JournalEntry:
        return self.write(EntryKind.REFLECTION, title, body)

    # ── Queries ───────────────────────────────────────────────────────────────

    def entries_by_kind(self, kind: EntryKind) -> list[JournalEntry]:
        return [e for e in self._entries if e.kind == kind]

    def entries_by_tag(self, tag: str) -> list[JournalEntry]:
        return [e for e in self._entries if tag in e.tags]

    def dream_entries(self) -> list[JournalEntry]:
        return [e for e in self._entries if e.dream_face]

    @property
    def all_entries(self) -> list[JournalEntry]:
        return list(self._entries)

    @property
    def entry_count(self) -> int:
        return len(self._entries)
