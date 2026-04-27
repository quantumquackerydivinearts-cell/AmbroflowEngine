"""
Meditation Session
==================
Wraps the BreathOfKo calibration with the Negaya kill-count gate and all
7 meditation perk effects.

Ko dream sequences are nightly — a daywise recap and force-save mechanic.
The player does not trigger them; they happen at the end of each in-game day.
This means:
  - All perk effects (calibration depth, sanity restoration) fire every night.
  - The Negaya gate fires every night. 72+ kills = permanently blocked saves
    until the necromancy ritual is completed.
  - Sanity deltas are nightly rest mechanics, not a separate activity.

Session flow
------------
1. Query kill_count from TileTracer (local ZO attestation sum).
2. Check negaya_appeased flag in FlagState.
3. If triggered (21+ kills, not appeased):
     a. Run Negaya encounter (sob loop or permanent block).
     b. Concentration is broken — calibration does not run, no sanity restoration.
     c. Return MeditationOutcome.BROKEN or MeditationOutcome.BLOCKED.
4. If not triggered: run DreamCalibrationSession (perk-boosted), integrate into
   BreathOfKo, apply sanity deltas to LiveSanity if provided.
   Return MeditationOutcome.COMPLETED.

Meditation perk effects
-----------------------
Calibration effects (structural — change what the session can read):
  depth_meditation          → +0.08 Lotus, Rose (deeper material/relational)
  infernal_meditation       → +0.08 Sakura (deeper orientation/underworld)
  transcendental_meditation → +0.05 all phases (content richness)

Sanity restoration effects (fire on COMPLETED only):
  breathwork_meditation     → terrestrial+0.04, alchemical+0.03
  alchemical_meditation     → alchemical+0.06 × (1 + alchemy_rank/50)  [synergy]
  hypnotic_meditation       → narrative+0.04, cosmic+0.02
  depth_meditation          → all dims+0.03
  infernal_meditation       → cosmic+0.08
  transcendental_meditation → cosmic+0.05
  zen_meditation            → narrative+0.05
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, TYPE_CHECKING

from .breath import BreathOfKo
from .calibration import DreamCalibrationSession, CalibrationTongue
from .flags import FlagState
from .negaya import (
    NegayaEncounterScreen,
    negaya_triggered,
    negaya_permanent,
    negaya_duration,
)

if TYPE_CHECKING:
    from ..sanity.live import LiveSanity


# ── Perk sanity delta table ───────────────────────────────────────────────────
# Matches skillRegistry.js sanity_delta entries exactly.
# Alchemical perk is base only — synergy is applied in compute_session_sanity_delta.

_PERK_SANITY_DELTAS: dict[str, dict[str, float]] = {
    "breathwork_meditation":     {"terrestrial": 0.04, "alchemical": 0.03},
    "alchemical_meditation":     {"alchemical": 0.06},   # scaled by alchemy rank
    "hypnotic_meditation":       {"narrative": 0.04, "cosmic": 0.02},
    "depth_meditation":          {"alchemical": 0.03, "narrative": 0.03,
                                  "terrestrial": 0.03, "cosmic": 0.03},
    "infernal_meditation":       {"cosmic": 0.08},
    "transcendental_meditation": {"cosmic": 0.05},
    "zen_meditation":            {"narrative": 0.05},
}


def compute_session_sanity_delta(
    active_perks: frozenset[str],
    skill_ranks:  dict[str, int],
) -> dict[str, float]:
    """
    Accumulate the combined sanity restoration for a completed session.

    Alchemical cross-skill synergy: the alchemical delta scales linearly with
    alchemy rank — 0.06 at rank 0 up to 0.12 at rank 50.

    Returns a dict of {dimension: total_delta} for all active perks.
    Does not apply them — caller is responsible for LiveSanity.apply_delta().
    """
    combined: dict[str, float] = {}
    alchemy_rank = skill_ranks.get("alchemy", 0)

    for perk_id in active_perks:
        for dim, value in _PERK_SANITY_DELTAS.get(perk_id, {}).items():
            if perk_id == "alchemical_meditation" and dim == "alchemical":
                value = value * (1.0 + alchemy_rank / 50.0)
            combined[dim] = combined.get(dim, 0.0) + value

    return combined


# ── Outcomes ──────────────────────────────────────────────────────────────────

class MeditationOutcome(str, Enum):
    COMPLETED = "completed"  # calibration ran, save state accumulated
    BROKEN    = "broken"     # Negaya interrupted (21–71), concentration lost
    BLOCKED   = "blocked"    # Negaya permanent (72+), session impossible


# ── Session ───────────────────────────────────────────────────────────────────

class MeditationSession:
    """
    Gate layer between the game loop and BreathOfKo calibration.

    Parameters
    ----------
    breath:
        The player's live BreathOfKo state.  Updated in-place on COMPLETED.
    game_id:
        Active game slug (e.g. "7_KLGS").
    negaya_screen:
        Renderer for the Negaya encounter.  May be None — gate logic still
        runs but no frames are produced.
    """

    def __init__(
        self,
        breath:        BreathOfKo,
        game_id:       str          = "7_KLGS",
        negaya_screen: Optional[NegayaEncounterScreen] = None,
    ) -> None:
        self._breath        = breath
        self._game_id       = game_id
        self._negaya_screen = negaya_screen or NegayaEncounterScreen()

    # ── Gate query ────────────────────────────────────────────────────────────

    def check_gate(self, kill_count: int, flag_state: FlagState) -> MeditationOutcome:
        """Determine outcome before rendering anything — pure logic."""
        appeased = flag_state.is_active("negaya_appeased")
        if not negaya_triggered(kill_count, appeased):
            return MeditationOutcome.COMPLETED
        if negaya_permanent(kill_count):
            return MeditationOutcome.BLOCKED
        return MeditationOutcome.BROKEN

    # ── Negaya encounter frames ───────────────────────────────────────────────

    def negaya_frames(self, kill_count: int, width: int = 1280, height: int = 800) -> list[bytes]:
        """
        Full sequence of encounter frames for an external render loop.

        21–71 kills → kill_count frames (one per sob).
        72+ kills   → single permanent frame.
        """
        duration = negaya_duration(kill_count)
        if duration is None:
            frame = self._negaya_screen.render_permanent_frame(width, height)
            return [frame] if frame is not None else []
        frames: list[bytes] = []
        for sob in range(1, duration + 1):
            frame = self._negaya_screen.render_frame(kill_count, sob, width, height)
            if frame is not None:
                frames.append(frame)
        return frames

    # ── Full session run ──────────────────────────────────────────────────────

    def run(
        self,
        kill_count:   int,
        flag_state:   FlagState,
        *,
        active_perks: frozenset[str]       = frozenset(),
        skill_ranks:  dict[str, int]       = {},
        live_sanity:  Optional["LiveSanity"] = None,
        resonance:    float                = 0.7,
        width:  int = 1280,
        height: int = 800,
    ) -> tuple[MeditationOutcome, list[bytes]]:
        """
        Run a complete nightly meditation session.

        Parameters
        ----------
        kill_count:   Total ZO deposits from TileTracer (tile_tracer.kill_count()).
        flag_state:   Player's current FlagState.
        active_perks: Set of unlocked meditation perk IDs.
        skill_ranks:  Full skill rank dict — used for alchemical cross-skill synergy.
        live_sanity:  If provided, sanity deltas are applied in-place on COMPLETED.
        resonance:    Base resonance for calibration responses [0.0–1.0].

        Returns
        -------
        (outcome, frames)
          COMPLETED  → frames=[], calibration integrated, sanity applied if live_sanity given.
          BROKEN     → frames=Negaya sob sequence, BreathOfKo unchanged.
          BLOCKED    → frames=[permanent Negaya frame], BreathOfKo unchanged.
        """
        outcome = self.check_gate(kill_count, flag_state)

        if outcome == MeditationOutcome.COMPLETED:
            session = DreamCalibrationSession(
                game_id=self._game_id,
                active_perks=active_perks,
            )
            for _phase in (CalibrationTongue.SAKURA, CalibrationTongue.ROSE, CalibrationTongue.LOTUS):
                for _ in range(3):
                    session.respond(resonance)
            calibration = session.complete()
            self._breath.integrate_calibration(calibration)

            if live_sanity is not None and active_perks:
                delta = compute_session_sanity_delta(active_perks, dict(skill_ranks))
                if delta:
                    live_sanity.apply_delta(delta, context={"source": "meditation_session"})

            return MeditationOutcome.COMPLETED, []

        frames = self.negaya_frames(kill_count, width, height)
        return outcome, frames