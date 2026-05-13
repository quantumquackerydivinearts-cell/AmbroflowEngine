"""
Akashic Memory
==============
Cross-timeline record of the player's choices, absences, and deaths.

Access is strictly gated: player + Chazak, Faygoru, Negaya, Haldoro, Vios,
Ohadame, Shakzefan, Lakota.  All others see only Narrative and Relational memory.

Architecture
------------
AkashicRecord   — live in-session tracker; mutable.
                  Attached to BreathOfKo and mutated by WorldPlay.
AkashicDeath    — one entry per player death, logged immediately on death.
AkashicSave     — one entry per bed save, written on flush_save().
                  Captures deaths and witnessed choices since the last save.
AkashicContext  — immutable read view, handed to Akashic-access entities.

Run semantics
-------------
A "run" is the stretch of play between a new-game start and the current
moment.  Deaths respawn at the last save but do NOT start a new run —
the run counter only advances when the player starts the game fresh
(not on resume).  The Akashic entities observe deaths within a run as
accumulation, not as timeline resets.

Absences
--------
An absence is a witnessed-entry that was *available* to the player
(its required_witnesses were met) at save time but was not witnessed.
Full absence tracking requires a query into the quest availability
engine; a stub field is included for future wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Akashic-access entity IDs ─────────────────────────────────────────────────

AKASHIC_ENTITIES: frozenset[str] = frozenset({
    "player",
    "1010_SALA",   # Chazak — Greater Siren, Transcendental Meditation teacher
    "1009_UNDI",   # Faygoru — steward of death, Ohadame devotee
    "negaya",      # Void Wraith of Temporal Recursion
    "haldoro",     # Void Wraith of Spatial Dissolution
    "vios",        # Void Wraith of Mental Fracture
    "ohadame",     # Goddess of Past-life Memories
    "shakzefan",   # Necromantic path deity
    "lakota",      # Demon of Life, Negaya's consort
})


def has_akashic_access(entity_id: str) -> bool:
    return entity_id in AKASHIC_ENTITIES


# ── Record types ──────────────────────────────────────────────────────────────

@dataclass
class AkashicDeath:
    """One death event — logged immediately when the player's HP reaches zero."""
    zone_id:    str
    run_number: int
    game_day:   int    # Aeralune day within the run (0 if clock unavailable)
    cause:      str    # "combat:{npc_id}", "void", "fall", or free-form

    def to_dict(self) -> dict:
        return {
            "zone_id":    self.zone_id,
            "run_number": self.run_number,
            "game_day":   self.game_day,
            "cause":      self.cause,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AkashicDeath":
        return cls(
            zone_id    = str(d.get("zone_id", "")),
            run_number = int(d.get("run_number", 0)),
            game_day   = int(d.get("game_day", 0)),
            cause      = str(d.get("cause", "unknown")),
        )


@dataclass
class AkashicSave:
    """One save event — written to the record when the player sleeps in a bed."""
    run_number:             int
    game_day:               int
    zone_id:                str
    death_count_since_last: int
    choices_made:           list[str]   # quest entry IDs witnessed since last save
    absences:               list[str]   # available entries NOT witnessed (future)

    def to_dict(self) -> dict:
        return {
            "run_number":             self.run_number,
            "game_day":               self.game_day,
            "zone_id":                self.zone_id,
            "death_count_since_last": self.death_count_since_last,
            "choices_made":           list(self.choices_made),
            "absences":               list(self.absences),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AkashicSave":
        return cls(
            run_number             = int(d.get("run_number", 0)),
            game_day               = int(d.get("game_day", 0)),
            zone_id                = str(d.get("zone_id", "")),
            death_count_since_last = int(d.get("death_count_since_last", 0)),
            choices_made           = list(d.get("choices_made") or []),
            absences               = list(d.get("absences") or []),
        )


# ── Live tracker ──────────────────────────────────────────────────────────────

@dataclass
class AkashicRecord:
    """
    Mutable in-session Akashic tracker.  Attached to BreathOfKo.

    Mutated by WorldPlay on deaths and quest choices.
    Flushed to a save entry by GLWorldPlay when the player sleeps in a bed.
    """
    game_slug:    str
    run_number:   int            = 0
    total_deaths: int            = 0
    deaths:       list[AkashicDeath] = field(default_factory=list)
    saves:        list[AkashicSave]  = field(default_factory=list)

    # In-session buffers — cleared on flush_save
    _deaths_since_save:  int       = field(default=0,                    repr=False)
    _choices_since_save: list[str] = field(default_factory=list,         repr=False)

    # ── Mutation API (called by WorldPlay) ────────────────────────────────────

    def begin_run(self) -> None:
        """Call once at the start of a new game (not on resume)."""
        self.run_number += 1
        self._deaths_since_save  = 0
        self._choices_since_save = []

    def record_death(
        self,
        zone_id:  str,
        cause:    str = "unknown",
        game_day: int = 0,
    ) -> None:
        """Log a player death immediately.  Does not flush — survives to next save."""
        self.total_deaths       += 1
        self._deaths_since_save += 1
        self.deaths.append(AkashicDeath(
            zone_id    = zone_id,
            run_number = self.run_number,
            game_day   = game_day,
            cause      = cause,
        ))

    def record_choice(self, entry_id: str) -> None:
        """Record a witnessed quest entry.  Deduplicated within a save window."""
        if entry_id not in self._choices_since_save:
            self._choices_since_save.append(entry_id)

    def flush_save(
        self,
        zone_id:   str,
        game_day:  int       = 0,
        absences:  list[str] = (),
    ) -> None:
        """
        Write a save entry and reset the in-session buffers.
        Call this when the player sleeps in a bed.
        """
        self.saves.append(AkashicSave(
            run_number             = self.run_number,
            game_day               = game_day,
            zone_id                = zone_id,
            death_count_since_last = self._deaths_since_save,
            choices_made           = list(self._choices_since_save),
            absences               = list(absences),
        ))
        self._deaths_since_save  = 0
        self._choices_since_save = []

    # ── Read API ──────────────────────────────────────────────────────────────

    def context(self) -> "AkashicContext":
        """Return the immutable read view for Akashic-access entities."""
        return AkashicContext(
            game_slug    = self.game_slug,
            run_number   = self.run_number,
            total_deaths = self.total_deaths,
            deaths       = list(self.deaths),
            saves        = list(self.saves),
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "game_slug":    self.game_slug,
            "run_number":   self.run_number,
            "total_deaths": self.total_deaths,
            "deaths":       [d.to_dict() for d in self.deaths],
            "saves":        [s.to_dict() for s in self.saves],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AkashicRecord":
        rec = cls(game_slug=str(d.get("game_slug", "7_KLGS")))
        rec.run_number   = int(d.get("run_number",   0))
        rec.total_deaths = int(d.get("total_deaths", 0))
        rec.deaths = [AkashicDeath.from_dict(x) for x in (d.get("deaths") or [])]
        rec.saves  = [AkashicSave.from_dict(x)  for x in (d.get("saves")  or [])]
        return rec


# ── Context (read view) ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class AkashicContext:
    """
    Immutable snapshot of the Akashic Record handed to entities with access.

    Used by Negaya, Haldoro, Vios, Chazak, Faygoru, Ohadame, Shakzefan,
    Lakota, and the player themselves when they have the awareness to read it.
    """
    game_slug:    str
    run_number:   int
    total_deaths: int
    deaths:       tuple[AkashicDeath, ...] = field(default_factory=tuple)
    saves:        tuple[AkashicSave,  ...] = field(default_factory=tuple)

    def __init__(
        self,
        game_slug:    str,
        run_number:   int,
        total_deaths: int,
        deaths:       list[AkashicDeath],
        saves:        list[AkashicSave],
    ) -> None:
        object.__setattr__(self, "game_slug",    game_slug)
        object.__setattr__(self, "run_number",   run_number)
        object.__setattr__(self, "total_deaths", total_deaths)
        object.__setattr__(self, "deaths",       tuple(deaths))
        object.__setattr__(self, "saves",        tuple(saves))

    @property
    def is_first_run(self) -> bool:
        return self.run_number <= 1 and self.total_deaths == 0

    @property
    def last_death_zone(self) -> Optional[str]:
        return self.deaths[-1].zone_id if self.deaths else None

    def deaths_in_zone(self, zone_id: str) -> int:
        return sum(1 for d in self.deaths if d.zone_id == zone_id)

    def died_to(self, npc_id: str) -> int:
        prefix = f"combat:{npc_id}"
        return sum(1 for d in self.deaths if d.cause.startswith(prefix))

    def choices_in_run(self, run_number: Optional[int] = None) -> list[str]:
        """All witnessed entry IDs in a given run (default: current run)."""
        rn = run_number if run_number is not None else self.run_number
        out: list[str] = []
        for s in self.saves:
            if s.run_number == rn:
                out.extend(s.choices_made)
        return out

    def clean_runs(self) -> int:
        """Number of runs with zero deaths."""
        runs_with_deaths = {d.run_number for d in self.deaths}
        all_runs = {s.run_number for s in self.saves} | {d.run_number for d in self.deaths}
        return len(all_runs - runs_with_deaths)