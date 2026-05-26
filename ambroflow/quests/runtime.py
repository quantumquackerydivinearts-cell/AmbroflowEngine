"""
QuestRuntime — single bundle wiring the key-lock system for a game session.

Owns:
  registry  — KeyRegistry loaded from keys/<game_slug>/
  keyring   — KeyRing (player's current key set)
  tracker   — QuestTracker (quest started/complete/failed state)
  runner    — SceneRunner (lock eval, scene firing, key propagation)

Usage
-----
    rt = QuestRuntime.for_game(
        game_slug = "7_KLGS",
        player_id = "abc123",
        orrery    = orrery_client,
    )
    wp = WorldPlay(..., quest_runtime=rt)

Save/restore
------------
    save_dict = rt.as_save_dict()
    rt = QuestRuntime.for_game(..., save_dict=save_dict)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)

# Repository root: two levels up from this file (ambroflow/quests/runtime.py)
_ENGINE_ROOT = Path(__file__).parent.parent.parent


class QuestRuntime:
    """
    Bundled quest system for one game session.

    Do not instantiate directly — use QuestRuntime.for_game().
    """

    def __init__(self, registry, keyring, tracker, runner) -> None:
        self.registry = registry
        self.keyring  = keyring
        self.tracker  = tracker
        self.runner   = runner

    # ── Public API ────────────────────────────────────────────────────────────

    def grant(self, key: str) -> bool:
        """
        Grant a yeigo key outside of scene context (e.g. from advance_quest).
        Keys not declared in the registry are silently ignored — they live only
        in the quest_state dict (e.g. dynamic keys like "met_0004_TOWN").
        Propagates — may complete or fail quests.
        Returns True if newly granted.
        """
        if key not in self.registry:
            return False
        try:
            return self.runner.grant_key(key)
        except Exception:
            return False

    def on_zone_entry(self, zone_id: str) -> list[str]:
        """
        Called each time the player enters a zone.
        Fires any available auto-scenes (ENV-only, non-interactive).
        Returns list of newly granted keys.
        """
        if not self.runner._scripts:
            return []
        granted: list[str] = []
        try:
            scenes = self.runner.available_scenes(zone_id)
            for scene in scenes:
                # Only auto-fire scenes where no beat requires PLAYER as addressee
                if any(getattr(b, "addressee", "") == "PLAYER" for b in scene.beats):
                    continue
                new_keys = self.runner.fire_scene(scene)
                granted.extend(new_keys)
        except Exception as e:
            _log.debug("on_zone_entry error: %s", e)
        return granted

    def available_topics(self, char_id: str) -> list:
        """Return dialogue topics available for char_id right now."""
        try:
            return self.runner.available_topics(char_id)
        except Exception:
            return []

    def set_hour(self, hour: int) -> None:
        try:
            self.runner.set_hour(hour)
        except Exception:
            pass

    def as_save_dict(self) -> dict:
        return {
            "completed_quests": self.tracker.completed,
            "active_quests":    self.tracker.active,
            "granted_keys":     self.keyring.to_list(),
            "fired_scenes":     self.runner.fired_scenes(),
        }

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def for_game(
        cls,
        game_slug:  str,
        player_id:  str,
        orrery,                              # OrreryClient
        save_dict:  Optional[dict] = None,
        keys_dir:   Optional[Path] = None,
        scripts_dir: Optional[Path] = None,
        hour:       int = 8,
    ) -> "QuestRuntime":
        """
        Build a QuestRuntime for the given game.

        keys_dir defaults to <engine_root>/keys/<game_slug>/
        scripts_dir defaults to <engine_root>/scripts/<game_slug>/
        """
        from .key_registry import load_registry
        from .keyring      import KeyRing
        from .tracker      import QuestTracker
        from .quest_loader import load_quest_scripts
        from .scene_runner import SceneRunner

        save = save_dict or {}

        # ── Registry ──────────────────────────────────────────────────────────
        keys_path = keys_dir or (_ENGINE_ROOT / "keys" / game_slug)
        try:
            registry = load_registry(keys_path)
        except Exception as e:
            _log.warning("KeyRegistry load failed (%s): %s — using empty registry", keys_path, e)
            from .key_registry import KeyRegistry
            registry = KeyRegistry({})

        # ── KeyRing ───────────────────────────────────────────────────────────
        granted = save.get("granted_keys", [])
        keyring = KeyRing(keys=set(granted), registry=registry)

        # ── QuestTracker ──────────────────────────────────────────────────────
        tracker = QuestTracker(
            actor_id         = player_id,
            orrery           = orrery,
            completed_quests = save.get("completed_quests", []),
            active_quests    = save.get("active_quests",    []),
        )

        # ── QuestScripts ──────────────────────────────────────────────────────
        scripts_path = scripts_dir or (_ENGINE_ROOT / "scripts" / game_slug)
        try:
            scripts = load_quest_scripts(scripts_path, registry=registry)
        except Exception as e:
            _log.warning("QuestScript load failed (%s): %s — using no scripts", scripts_path, e)
            scripts = []

        # ── SceneRunner ───────────────────────────────────────────────────────
        runner = SceneRunner(
            keyring       = keyring,
            quest_tracker = tracker,
            scripts       = scripts,
            registry      = registry,
            hour          = hour,
        )
        # Restore fired scenes from save
        fired = save.get("fired_scenes", [])
        if fired:
            SceneRunner.restore_fired(runner, fired)

        _log.info(
            "QuestRuntime ready — %d keys loaded, %d scripts, %d completed quests",
            len(registry), len(scripts), len(tracker.completed),
        )
        return cls(registry, keyring, tracker, runner)
