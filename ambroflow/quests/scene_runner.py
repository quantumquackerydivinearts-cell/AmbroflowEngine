"""
scene_runner.py — Evaluates scene locks and drives the key-lock system at runtime.

The SceneRunner is consulted whenever:
  - The player enters a zone
  - A key is granted (which may unlock new scenes)
  - The in-game hour changes (time-gated scenes)

It does NOT handle rendering — it produces lists of fireable Scenes and
grants keys when scenes fire. The game loop is responsible for presenting
scenes to the player and calling fire_scene() / fire_beat() when witnessed.

Key propagation:
  When a key is granted, SceneRunner._propagate() checks whether it matches
  any QuestScript's completion_key or failure_key and calls the QuestTracker
  accordingly.

Usage
-----
    runner = SceneRunner(
        keyring=ring,
        quest_tracker=tracker,
        scripts=loaded_scripts,
        registry=reg,
        hour=14,
    )

    # On zone entry:
    fireable = runner.available_scenes(zone="wiltoll_lane")

    # When the player witnesses a scene:
    new_keys = runner.fire_scene(fireable[0])

    # When the player witnesses a specific beat:
    new_keys = runner.fire_beat(beat)

    # When the player chooses a dialogue response:
    new_keys = runner.fire_response(response)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .key_registry import KeyRegistry
    from .keyring import KeyRing
    from .schema import Beat, DialogueResponse, DialogueTopic, Lock, Scene, QuestScript
    from ..quests.tracker import QuestTracker


class SceneRunner:
    """
    Runtime engine that evaluates Locks, fires Scenes, and propagates key grants.

    Parameters
    ----------
    keyring:       The player's current KeyRing.
    quest_tracker: The player's QuestTracker — completion keys drive it.
    scripts:       All loaded QuestScript objects for the current game.
    registry:      Optional KeyRegistry for key validation on grant.
    hour:          Current in-game hour (0-23). Update via set_hour().
    """

    def __init__(
        self,
        keyring:       "KeyRing",
        quest_tracker: "QuestTracker",
        scripts:       list["QuestScript"],
        registry:      Optional["KeyRegistry"] = None,
        hour:          int = 12,
    ) -> None:
        self._ring     = keyring
        self._tracker  = quest_tracker
        self._scripts  = scripts
        self._registry = registry
        self._hour     = hour
        self._fired:   set[str] = set()   # scene IDs already fired (non-repeatable)

        # Build completion/failure key lookup for fast propagation
        self._completion_keys: dict[str, str] = {}   # key → quest_id
        self._failure_keys:    dict[str, str] = {}   # key → quest_id
        for script in scripts:
            self._completion_keys[script.completion_key] = script.quest_id
            if script.failure_key:
                self._failure_keys[script.failure_key] = script.quest_id

    # ── Time ──────────────────────────────────────────────────────────────────

    def set_hour(self, hour: int) -> None:
        self._hour = max(0, min(23, hour))

    # ── Lock evaluation ───────────────────────────────────────────────────────

    def _lock_open(self, lock: "Lock") -> bool:
        if not self._ring.satisfies(lock):
            return False
        if lock.time_window:
            s, e = lock.time_window
            if s <= e:
                return s <= self._hour <= e
            # Wraps midnight (e.g. 22–04)
            return self._hour >= s or self._hour <= e
        return True

    # ── Scene availability ────────────────────────────────────────────────────

    def available_scenes(self, zone: str) -> list["Scene"]:
        """
        Return all scenes that can fire in the given zone right now.
        Filters by: zone match, lock satisfied, not already fired (if not repeatable).
        """
        out: list["Scene"] = []
        for script in self._scripts:
            for scene in script.scenes:
                if scene.id in self._fired and not scene.repeatable:
                    continue
                if scene.zone != zone:
                    continue
                if self._lock_open(scene.lock):
                    out.append(scene)
        return out

    def available_topics(self, char_id: str) -> list["DialogueTopic"]:
        """Return dialogue topics available for a character right now."""
        out: list["DialogueTopic"] = []
        for script in self._scripts:
            for topic in script.topics:
                if topic.char_id != char_id:
                    continue
                if self._lock_open(topic.lock):
                    out.append(topic)
        return out

    # ── Firing ────────────────────────────────────────────────────────────────

    def fire_scene(self, scene: "Scene") -> list[str]:
        """
        Mark a scene as witnessed. Grant its completion keys.
        Returns list of newly granted keys.
        """
        if not scene.repeatable:
            self._fired.add(scene.id)
        new_keys = self._ring.grant_many(scene.grants)
        self._propagate(new_keys)
        return new_keys

    def fire_beat(self, beat: "Beat") -> list[str]:
        """Grant per-beat keys when a beat is witnessed."""
        new_keys = self._ring.grant_many(beat.grants)
        self._propagate(new_keys)
        return new_keys

    def fire_response(self, response: "DialogueResponse") -> list[str]:
        """Grant keys when a player dialogue response is chosen."""
        new_keys = self._ring.grant_many(response.grants)
        self._propagate(new_keys)
        return new_keys

    def fire_topic(self, topic: "DialogueTopic") -> list[str]:
        """Grant topic-level keys when a dialogue topic is accessed."""
        new_keys = self._ring.grant_many(topic.grants)
        self._propagate(new_keys)
        return new_keys

    def grant_key(self, key: str) -> bool:
        """
        Directly grant a key outside of scene/beat context.
        Returns True if newly granted, False if already held.
        Propagates completion/failure as usual.
        """
        if self._ring.grant(key):
            self._propagate([key])
            return True
        return False

    # ── Propagation ───────────────────────────────────────────────────────────

    def _propagate(self, new_keys: list[str]) -> None:
        """
        After any key grants, check for quest completion and failure triggers.
        """
        for key in new_keys:
            if key in self._completion_keys:
                quest_id = self._completion_keys[key]
                self._tracker.complete(quest_id)
            if key in self._failure_keys:
                quest_id = self._failure_keys[key]
                self._tracker.fail(quest_id)

    # ── Fired scene state ─────────────────────────────────────────────────────

    def is_fired(self, scene_id: str) -> bool:
        return scene_id in self._fired

    def mark_fired(self, scene_id: str) -> None:
        """Manually mark a scene as fired (e.g. on save restore)."""
        self._fired.add(scene_id)

    def fired_scenes(self) -> list[str]:
        """Return sorted list of fired scene IDs — for save state."""
        return sorted(self._fired)

    @classmethod
    def restore_fired(cls, runner: "SceneRunner", fired: list[str]) -> None:
        """Restore fired scene state from a saved list."""
        runner._fired = set(fired)
