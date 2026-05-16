"""
schema.py — Quest script data structures.

A QuestScript is a collection of Scenes and DialogueTopics for one quest.
Scenes are owned by participants and a zone — not by the quest. The quest
observes them: when a scene's completion grants the quest's completion_key,
QuestTracker.complete() is called.

Key design rules:
  - Lock.requires / Lock.excludes reference yeigo strings from KeyRegistry
  - Beat.grants and Scene.grants reference yeigo strings
  - DialogueResponse.lock allows additional conditions on player choices
  - QuestScript.completion_key / failure_key are yeigo strings

All from_dict() classmethods deserialise from the JSON quest script format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ── Lock ──────────────────────────────────────────────────────────────────────

@dataclass
class Lock:
    """
    Condition that must be satisfied for a scene or dialogue topic to fire.

    requires:     all these yeigo keys must be present in the KeyRing
    excludes:     none of these yeigo keys may be present
    time_window:  optional (start_hour, end_hour) in 0-23 inclusive.
                  Wrap-around midnight is supported: (22, 4) means 22:00–04:00.
    """
    requires:    list[str]              = field(default_factory=list)
    excludes:    list[str]              = field(default_factory=list)
    time_window: Optional[tuple[int, int]] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Lock":
        tw = d.get("time_window")
        return cls(
            requires    = d.get("requires", []),
            excludes    = d.get("excludes", []),
            time_window = tuple(tw) if tw else None,
        )

    def to_dict(self) -> dict:
        out: dict[str, Any] = {
            "requires": self.requires,
            "excludes": self.excludes,
        }
        if self.time_window:
            out["time_window"] = list(self.time_window)
        return out


# ── Beat ──────────────────────────────────────────────────────────────────────

@dataclass
class Beat:
    """
    One line or action within a scene or dialogue response.

    speaker:   char_id | "ENV" | "PLAYER"
    text:      the spoken or described content
    addressee: char_id | "AMBIENT" | "PLAYER"
               AMBIENT = between NPCs, player is an optional witness
    action:    optional stage direction / animation cue
    grants:    yeigo keys granted when this beat is witnessed
    """
    speaker:   str
    text:      str
    addressee: str       = "AMBIENT"
    action:    Optional[str] = None
    grants:    list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Beat":
        return cls(
            speaker   = d["speaker"],
            text      = d["text"],
            addressee = d.get("addressee", "AMBIENT"),
            action    = d.get("action"),
            grants    = d.get("grants", []),
        )

    def to_dict(self) -> dict:
        out: dict[str, Any] = {
            "speaker":   self.speaker,
            "text":      self.text,
            "addressee": self.addressee,
        }
        if self.action:
            out["action"] = self.action
        if self.grants:
            out["grants"] = self.grants
        return out


# ── DialogueResponse ──────────────────────────────────────────────────────────

@dataclass
class DialogueResponse:
    """
    One player-selectable response in a dialogue topic.

    text:   what appears in the player's choice menu
    beats:  NPC reply beats after the player selects this
    lock:   additional condition on when this response is available
    grants: yeigo keys granted when this response is chosen
    """
    text:   str
    beats:  list[Beat]    = field(default_factory=list)
    lock:   Lock          = field(default_factory=Lock)
    grants: list[str]     = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "DialogueResponse":
        return cls(
            text   = d["text"],
            beats  = [Beat.from_dict(b) for b in d.get("beats", [])],
            lock   = Lock.from_dict(d["lock"]) if "lock" in d else Lock(),
            grants = d.get("grants", []),
        )

    def to_dict(self) -> dict:
        return {
            "text":   self.text,
            "beats":  [b.to_dict() for b in self.beats],
            "lock":   self.lock.to_dict(),
            "grants": self.grants,
        }


# ── DialogueTopic ─────────────────────────────────────────────────────────────

@dataclass
class DialogueTopic:
    """
    What a character says when directly addressed by the player.

    id:            unique identifier, e.g. "alfir_infernal_teaching"
    char_id:       character registry ID, e.g. "0006_WTCH"
    prompt:        text that appears in the player's dialogue menu
    lock:          when this topic is available
    opening_beats: NPC speaks before the player responds
    responses:     player choice branches
    grants:        yeigo keys granted when the topic is accessed
                   (regardless of which response is chosen)
    """
    id:            str
    char_id:       str
    prompt:        str
    lock:          Lock
    opening_beats: list[Beat]            = field(default_factory=list)
    responses:     list[DialogueResponse] = field(default_factory=list)
    grants:        list[str]              = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "DialogueTopic":
        return cls(
            id            = d["id"],
            char_id       = d["char_id"],
            prompt        = d["prompt"],
            lock          = Lock.from_dict(d.get("lock", {})),
            opening_beats = [Beat.from_dict(b) for b in d.get("opening_beats", [])],
            responses     = [DialogueResponse.from_dict(r) for r in d.get("responses", [])],
            grants        = d.get("grants", []),
        )

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "char_id":       self.char_id,
            "prompt":        self.prompt,
            "lock":          self.lock.to_dict(),
            "opening_beats": [b.to_dict() for b in self.opening_beats],
            "responses":     [r.to_dict() for r in self.responses],
            "grants":        self.grants,
        }


# ── Scene ─────────────────────────────────────────────────────────────────────

@dataclass
class Scene:
    """
    An event owned by participants and a zone, not by a quest.
    The quest is a side-effect observer: when a scene grants the quest's
    completion_key, QuestTracker.complete() is called.

    id:           unique identifier, e.g. "0003_KLST.sidhal_intro"
    zone:         zone_id where the scene fires
    participants: list of char_ids present
    lock:         conditions for the scene to be available
    beats:        the sequence of dialogue/action beats
    grants:       yeigo keys granted when ALL beats are witnessed
    repeatable:   if False (default), fires once then is marked fired
    """
    id:           str
    zone:         str
    participants: list[str]  = field(default_factory=list)
    lock:         Lock       = field(default_factory=Lock)
    beats:        list[Beat] = field(default_factory=list)
    grants:       list[str]  = field(default_factory=list)
    repeatable:   bool       = False

    @classmethod
    def from_dict(cls, d: dict) -> "Scene":
        return cls(
            id           = d["id"],
            zone         = d["zone"],
            participants = d.get("participants", []),
            lock         = Lock.from_dict(d.get("lock", {})),
            beats        = [Beat.from_dict(b) for b in d.get("beats", [])],
            grants       = d.get("grants", []),
            repeatable   = d.get("repeatable", False),
        )

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "zone":         self.zone,
            "participants": self.participants,
            "lock":         self.lock.to_dict(),
            "beats":        [b.to_dict() for b in self.beats],
            "grants":       self.grants,
            "repeatable":   self.repeatable,
        }


# ── QuestScript ───────────────────────────────────────────────────────────────

@dataclass
class QuestScript:
    """
    All scenes and dialogue topics for one quest.

    quest_id:       e.g. "0003_KLST"
    game_slug:      e.g. "7_KLGS"
    title:          human-readable name
    completion_key: granting this yeigo calls QuestTracker.complete()
    failure_key:    granting this yeigo calls QuestTracker.fail() (optional)
    scenes:         list of Scene objects
    topics:         list of DialogueTopic objects
    """
    quest_id:       str
    game_slug:      str
    title:          str
    completion_key: str
    failure_key:    Optional[str]         = None
    scenes:         list[Scene]           = field(default_factory=list)
    topics:         list[DialogueTopic]   = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "QuestScript":
        return cls(
            quest_id       = d["quest_id"],
            game_slug      = d["game_slug"],
            title          = d["title"],
            completion_key = d["completion_key"],
            failure_key    = d.get("failure_key"),
            scenes         = [Scene.from_dict(s) for s in d.get("scenes", [])],
            topics         = [DialogueTopic.from_dict(t) for t in d.get("topics", [])],
        )

    def to_dict(self) -> dict:
        out: dict[str, Any] = {
            "quest_id":       self.quest_id,
            "game_slug":      self.game_slug,
            "title":          self.title,
            "completion_key": self.completion_key,
            "scenes":         [s.to_dict() for s in self.scenes],
            "topics":         [t.to_dict() for t in self.topics],
        }
        if self.failure_key:
            out["failure_key"] = self.failure_key
        return out
