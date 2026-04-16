"""
Live Sanity System
==================
Tracks the player's 4-fold sanity as a live float score [0.0, 1.0] per dimension.

Dimensions:
  alchemical   — transformation coherence; pressed by crafting, alchemy skill
  narrative    — story coherence; pressed by quests, speech, character encounters
  terrestrial  — embodied stability; pressed by combat, survival, medicine
  cosmic       — scalar coherence with the Orrery's scope; pressed by meditation

Key mechanic:
  - Each encounter applies sanity_deltas (positive or negative) per dimension.
  - Scores are clamped to [0.0, 1.0].
  - Consonance = variance across four dimensions < 0.05
  - Dissonance = variance ≥ 0.05

This feeds directly into the Game 1 timeline selection:
  safety_axis (from Luminyx outcome) × sanity_axis → 4 Earthly cities
    sovereign   + consonance  → La Paz, Peru
    sovereign   + dissonance  → Kyoto
    wounded_sov + consonance  → New York
    wounded_sov + dissonance  → London

LiveSanity is in-memory only.  The Orrery (via OrreryClient) is the persistent
backing store; this class is the runtime face of the sanity system.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

from ..orrery.client import OrreryClient

_DIMENSIONS = ("alchemical", "narrative", "terrestrial", "cosmic")
_CONSONANCE_THRESHOLD = 0.05


@dataclass
class SanitySnapshot:
    alchemical:  float
    narrative:   float
    terrestrial: float
    cosmic:      float

    def variance(self) -> float:
        return statistics.variance([
            self.alchemical, self.narrative,
            self.terrestrial, self.cosmic,
        ])

    def as_dict(self) -> dict[str, float]:
        return {
            "alchemical": self.alchemical,
            "narrative": self.narrative,
            "terrestrial": self.terrestrial,
            "cosmic": self.cosmic,
        }


def consonance_axis(snapshot: SanitySnapshot) -> str:
    """Return 'consonance' or 'dissonance' based on variance across 4 dimensions."""
    return "consonance" if snapshot.variance() < _CONSONANCE_THRESHOLD else "dissonance"


class LiveSanity:
    """
    In-session live sanity tracker.

    Parameters
    ----------
    actor_id:
        Player identifier.
    orrery:
        OrreryClient — deltas are persisted here.
    initial:
        Starting scores.  Defaults to 0.5 on all dimensions (neutral).
    """

    _DEFAULTS = {d: 0.5 for d in _DIMENSIONS}

    def __init__(
        self,
        actor_id: str,
        orrery: OrreryClient,
        initial: Optional[dict[str, float]] = None,
    ) -> None:
        self._actor_id = actor_id
        self._orrery   = orrery
        self._scores   = {d: (initial or self._DEFAULTS).get(d, 0.5) for d in _DIMENSIONS}

    def apply_delta(self, deltas: dict[str, float], context: Optional[dict] = None) -> SanitySnapshot:
        """
        Apply encounter-driven deltas.  Clamps each dimension to [0.0, 1.0].
        Records the delta to the Orrery.
        """
        for dim in _DIMENSIONS:
            if dim in deltas:
                self._scores[dim] = max(0.0, min(1.0, self._scores[dim] + deltas[dim]))

        self._orrery.record_sanity_delta(
            actor_id=self._actor_id,
            deltas=deltas,
            context=context or {},
        )
        return self.snapshot()

    def snapshot(self) -> SanitySnapshot:
        return SanitySnapshot(**self._scores)

    def consonance(self) -> str:
        return consonance_axis(self.snapshot())

    def sync_from_orrery(self) -> SanitySnapshot:
        """Pull current live sanity from the Orrery and update in-memory scores."""
        remote = self._orrery.get_sanity()
        for dim in _DIMENSIONS:
            if dim in remote:
                self._scores[dim] = float(remote[dim])
        return self.snapshot()
