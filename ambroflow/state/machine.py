"""
Game State Machine
==================
Per-game state management and transition logic.

Every game in Ko's Labyrinth follows the same phase skeleton:
  UNSTARTED → DREAM_CALIBRATION → WAKING_PLAY → CONVERGENCE → ENDED

  UNSTARTED:          Game not yet begun. BreathOfKo is read to set starting conditions.
  DREAM_CALIBRATION:  Ko's dream sequence. Calibration session runs. VITRIOL assigned.
  WAKING_PLAY:        Main game play. Dungeon runs, quests, encounters, alchemy, journal.
  CONVERGENCE:        Endgame — the philosophical reckoning. No new dungeons.
  ENDED:              Game complete. KoFlags updated. BreathOfKo integrated. Decay applied.

The machine does not enforce the narrative — it tracks state and validates transitions.

Starting conditions from BreathOfKo:
  The modification_weight of active KoFlags for this game modulates:
  - Encounter difficulty base
  - Quest availability (some quests gated by cross-game flags)
  - Initial inventory augmentation
  - Dream calibration sensitivity (higher weight → sharper calibration)

Game 1 additionally uses the safety/sanity timeline selection:
  safety_axis × sanity_axis → starting city (La Paz / Kyoto / New York / London)
  This is resolved at the DREAM_CALIBRATION → WAKING_PLAY transition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

from ..ko.breath import BreathOfKo
from ..ko.calibration import DreamCalibration
from ..ko.vitriol import VITRIOLProfile
from ..sanity.live import LiveSanity

if TYPE_CHECKING:
    from ..quests.keyring import KeyRing
    from ..quests.scene_runner import SceneRunner
    from ..quests.tracker import QuestTracker
    from ..quests.schema import Beat, Scene


class GamePhase(str, Enum):
    UNSTARTED          = "unstarted"
    DREAM_CALIBRATION  = "dream_calibration"
    WAKING_PLAY        = "waking_play"
    CONVERGENCE        = "convergence"
    ENDED              = "ended"


# ── Game 1 timeline selection ──────────────────────────────────────────────────

_GAME1_TIMELINE: dict[tuple[str, str], str] = {
    ("sovereign",         "consonance"):  "La Paz, Peru",
    ("sovereign",         "dissonance"):  "Kyoto",
    ("wounded_sovereign", "consonance"):  "New York",
    ("wounded_sovereign", "dissonance"):  "London",
}

def resolve_game1_starting_city(safety_axis: str, sanity_axis: str) -> str:
    """
    safety_axis: "sovereign" | "wounded_sovereign"  (from Game 7 Luminyx outcome)
    sanity_axis: "consonance" | "dissonance"         (from live sanity variance)
    """
    return _GAME1_TIMELINE.get((safety_axis, sanity_axis), "La Paz, Peru")


# ── State and transition ───────────────────────────────────────────────────────

@dataclass
class GameState:
    game_id:         str
    game_number:     int
    phase:           GamePhase = GamePhase.UNSTARTED
    vitriol:         Optional[VITRIOLProfile] = None
    calibration:     Optional[DreamCalibration] = None
    starting_city:   Optional[str] = None     # Game 1 only
    ko_weight:       float = 0.0              # modification weight from BreathOfKo
    ended_at_phase:  Optional[str] = None     # which convergence path was taken
    metadata:        dict[str, Any] = field(default_factory=dict)


_VALID_TRANSITIONS: dict[GamePhase, set[GamePhase]] = {
    GamePhase.UNSTARTED:         {GamePhase.DREAM_CALIBRATION},
    GamePhase.DREAM_CALIBRATION: {GamePhase.WAKING_PLAY},
    GamePhase.WAKING_PLAY:       {GamePhase.CONVERGENCE},
    GamePhase.CONVERGENCE:       {GamePhase.ENDED},
    GamePhase.ENDED:             set(),   # terminal
}


class GameStateMachine:
    """
    Manages the lifecycle of a single game run.

    Parameters
    ----------
    game_id:
        Game slug (e.g. "7_KLGS").
    game_number:
        Integer game number (1–31).
    breath:
        The player's BreathOfKo — read at start, integrated at end.
    orrery:
        OrreryClient — phase transitions are recorded.
    """

    def __init__(
        self,
        game_id: str,
        game_number: int,
        breath: BreathOfKo,
        orrery: Any,
        scene_runner: Optional["SceneRunner"] = None,
        quest_tracker: Optional["QuestTracker"] = None,
        keyring: Optional["KeyRing"] = None,
    ) -> None:
        self._breath        = breath
        self._orrery        = orrery
        self._scene_runner  = scene_runner
        self._quest_tracker = quest_tracker
        self._keyring       = keyring
        self._state  = GameState(
            game_id=game_id,
            game_number=game_number,
            ko_weight=breath.flag_state.modification_weight(game_number),
        )

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def phase(self) -> GamePhase:
        return self._state.phase

    def _transition(self, to: GamePhase) -> None:
        valid = _VALID_TRANSITIONS.get(self._state.phase, set())
        if to not in valid:
            raise ValueError(
                f"Invalid transition: {self._state.phase} → {to}"
            )
        self._state.phase = to
        self._orrery.record(f"game.phase.{to.value}", {
            "game_id":  self._state.game_id,
            "phase":    to.value,
            "ko_weight": self._state.ko_weight,
        })

    # ── Lifecycle transitions ─────────────────────────────────────────────────

    def begin_dream_calibration(self) -> None:
        """Start → DreamCalibration."""
        self._transition(GamePhase.DREAM_CALIBRATION)

    def complete_dream_calibration(
        self,
        calibration: DreamCalibration,
        vitriol: VITRIOLProfile,
        safety_axis: Optional[str] = None,
        sanity_axis: Optional[str] = None,
    ) -> None:
        """
        DreamCalibration → WakingPlay.

        For Game 1: supply safety_axis and sanity_axis to resolve starting city.
        """
        self._state.calibration = calibration
        self._state.vitriol     = vitriol

        if self._state.game_number == 1 and safety_axis and sanity_axis:
            self._state.starting_city = resolve_game1_starting_city(safety_axis, sanity_axis)

        self._orrery.record("game.calibration.complete", {
            "game_id":       self._state.game_id,
            "sakura":        calibration.sakura_density,
            "rose":          calibration.rose_density,
            "lotus":         calibration.lotus_density,
            "vitriol":       vitriol.as_dict(),
            "starting_city": self._state.starting_city,
        })

        self._transition(GamePhase.WAKING_PLAY)

    def begin_convergence(self) -> None:
        """WakingPlay → Convergence (endgame trigger)."""
        self._transition(GamePhase.CONVERGENCE)

    def end_game(self, convergence_path: str) -> None:
        """
        Convergence → Ended.

        convergence_path: a short string identifying which ending was reached.
        Integrates calibration into BreathOfKo, decays flags.
        """
        self._state.ended_at_phase = convergence_path
        self._transition(GamePhase.ENDED)

        if self._state.calibration:
            self._breath.integrate_calibration(self._state.calibration)
        self._breath.apply_game_decay()

        self._orrery.record("game.ended", {
            "game_id":          self._state.game_id,
            "convergence_path": convergence_path,
            "breath_snapshot":  self._breath.snapshot(),
        })

    # ── Key-lock integration ──────────────────────────────────────────────────

    def enter_zone(self, zone_id: str) -> list["Scene"]:
        """
        Called when the player enters a zone.
        Returns the list of scenes that can fire right now in that zone.
        The game loop presents these to the player and calls fire_scene() when witnessed.
        Returns empty list if no SceneRunner is wired.
        """
        if self._scene_runner is None:
            return []
        return self._scene_runner.available_scenes(zone_id)

    def grant_key(self, key: str) -> bool:
        """
        Grant a key through the SceneRunner (so propagation fires).
        Returns True if newly granted.
        Falls back to direct KeyRing grant if no SceneRunner is wired.
        """
        if self._scene_runner is not None:
            return self._scene_runner.grant_key(key)
        if self._keyring is not None:
            return self._keyring.grant(key)
        return False

    def fire_scene(self, scene: "Scene") -> list[str]:
        """Fire a scene and return newly granted keys."""
        if self._scene_runner is None:
            return []
        return self._scene_runner.fire_scene(scene)

    def fire_beat(self, beat: "Beat") -> list[str]:
        """Fire a beat and return newly granted keys."""
        if self._scene_runner is None:
            return []
        return self._scene_runner.fire_beat(beat)

    def set_hour(self, hour: int) -> None:
        """Update the in-game hour for time-gated scene evaluation."""
        if self._scene_runner is not None:
            self._scene_runner.set_hour(hour)

    def has_key(self, key: str) -> bool:
        """Check whether the player currently holds a key."""
        if self._keyring is not None:
            return self._keyring.has(key)
        return False

    # ── Starting condition generation ─────────────────────────────────────────

    def starting_conditions(self) -> dict[str, Any]:
        """
        Return starting conditions for waking play.
        Modulated by BreathOfKo flags.
        """
        base_difficulty = max(0.1, 0.5 - self._state.ko_weight * 0.1)
        return {
            "encounter_difficulty_base": base_difficulty,
            "starting_city":             self._state.starting_city,
            "ko_weight":                 self._state.ko_weight,
            "boundedness":               self._breath.boundedness(),
        }
