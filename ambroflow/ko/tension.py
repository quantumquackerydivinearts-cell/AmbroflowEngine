"""
VITRIOL Tension System
======================
Ko's initial reading is immutable — it is what was true before the player
had any say in the matter.

When the player assigns their own VITRIOL stats manually, a gap opens between
Ko's read and the player's chosen profile. That gap is not error and not
penalty — it is generative energy, the internal tension that drives the game.

A player who accepts Ko's read entirely: no tension, maximum coherence,
and a very particular kind of blindness.
A player who inverts Ko's read entirely: maximum tension, and a very
particular kind of expenditure.
Most players live somewhere in the middle. That is where the game finds them.

TensionVector per stat:
  aligned     — delta ≤ 1 in either direction (player and Ko agree)
  elevated    — player chose higher than Ko read (player claims more capacity)
  suppressed  — player chose lower than Ko read (player claims less capacity)

Magnitude: capped at 4, independent of direction.

Mechanical effects:
  Reflectivity suppressed → lower alchemy resonance (can't hold opposing charges)
  Reflectivity elevated   → modest resonance boost (more transformative than Ko read)
  Each stat contributes a small per-dimension sanity bias:
    introspection/reflectivity → narrative/alchemical strain
    vitality/tactility         → terrestrial strain
    levity/ostentation         → cosmic strain
    ingenuity                  → shared across all four (lateral capacity spans all)
"""

from __future__ import annotations

from dataclasses import dataclass

from .calibration import DreamCalibration
from .vitriol import VITRIOLProfile


# ── KoReading ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class KoReading:
    """
    Ko's immutable initial reading of the player.
    Produced at dream calibration completion, before the player wakes.
    Cannot be modified after the dream ends.
    """
    profile:       VITRIOLProfile
    calibration:   DreamCalibration
    game_id:       str
    coil_position: float


# ── TensionVector ─────────────────────────────────────────────────────────────

@dataclass
class TensionVector:
    """
    The tension on a single VITRIOL stat between Ko's read and the player's choice.
    """
    stat:         str
    ko_value:     int
    player_value: int

    @property
    def delta(self) -> int:
        """Signed difference: player_value - ko_value."""
        return self.player_value - self.ko_value

    @property
    def tension_type(self) -> str:
        """
        aligned    — within ±1 of Ko's read
        elevated   — player claimed more capacity than Ko read
        suppressed — player claimed less capacity than Ko read
        """
        d = self.delta
        if abs(d) <= 1:
            return "aligned"
        elif d > 0:
            return "elevated"
        else:
            return "suppressed"

    @property
    def magnitude(self) -> int:
        """Absolute distance, capped at 4."""
        return min(4, abs(self.delta))

    def is_aligned(self) -> bool:
        return self.tension_type == "aligned"


# ── VITRIOLTension ────────────────────────────────────────────────────────────

@dataclass
class VITRIOLTension:
    """
    The full 7-stat tension profile between Ko's reading and the player's choice.
    """
    vectors: dict[str, TensionVector]

    def total_magnitude(self) -> int:
        """Sum of all per-stat magnitudes. Range: 0–28."""
        return sum(v.magnitude for v in self.vectors.values())

    def is_high_tension(self) -> bool:
        """True when total magnitude ≥ 8 (threshold for systemic strain)."""
        return self.total_magnitude() >= 8

    def alignment_count(self) -> int:
        """Number of stats where player and Ko agree (aligned)."""
        return sum(1 for v in self.vectors.values() if v.is_aligned())

    def alchemy_resonance_mod(self, stat: str) -> float:
        """
        Alchemy resonance modifier for a stat.

        Only Reflectivity tension affects alchemy resonance directly.
        Reflectivity is the primary alchemy-facing stat because alchemy IS the
        field recognising itself through the practitioner — the capacity to hold
        an opposing charge is what makes transformation possible.

        Suppressed Reflectivity reduces resonance — the player has claimed less
        transformation capacity than Ko read, so material processing is shallower.

        Elevated Reflectivity gives a smaller bonus — claiming more is not the
        same as having it; overconfidence has a cost.

        All other stats return 1.0 — their tension surfaces in sanity and
        narrative, not in alchemy resonance.
        """
        if stat != "reflectivity":
            return 1.0
        v = self.vectors.get(stat)
        if v is None:
            return 1.0
        if v.tension_type == "aligned":
            return 1.0
        elif v.tension_type == "suppressed":
            # −5% per magnitude point
            return max(0.6, 1.0 - v.magnitude * 0.05)
        else:  # elevated
            # +3% per magnitude point — overconfidence is real
            return min(1.12, 1.0 + v.magnitude * 0.03)

    def sanity_bias(self) -> dict[str, float]:
        """
        Per-dimension sanity drift produced by the tension profile.

        All biases are negative — tension always creates some strain.
        The question is only which dimension carries it.

          introspection / reflectivity → alchemical + narrative
          vitality / tactility         → terrestrial
          levity / ostentation         → cosmic
          ingenuity                    → distributed across all four (small)
        """
        def _mag(stat: str) -> int:
            v = self.vectors.get(stat)
            return v.magnitude if v else 0

        ingenuity_spread = _mag("ingenuity") * 0.005  # shared small strain

        return {
            "alchemical": -(
                _mag("reflectivity") * 0.02
                + _mag("introspection") * 0.01
                + ingenuity_spread
            ),
            "narrative": -(
                _mag("introspection") * 0.02
                + _mag("reflectivity") * 0.01
                + ingenuity_spread
            ),
            "terrestrial": -(
                (_mag("vitality") + _mag("tactility")) / 2 * 0.02
                + ingenuity_spread
            ),
            "cosmic": -(
                (_mag("levity") + _mag("ostentation")) / 2 * 0.02
                + ingenuity_spread
            ),
        }


# ── derive_tension ────────────────────────────────────────────────────────────

def derive_tension(
    ko_reading:     KoReading,
    player_profile: VITRIOLProfile,
) -> VITRIOLTension:
    """
    Compute the tension between Ko's initial reading and the player's
    chosen VITRIOL profile.

    Call this once when the player finalises their stats — the resulting
    VITRIOLTension is attached to the game state and remains live
    throughout the game as mechanical context.
    """
    ko_dict     = ko_reading.profile.as_dict()
    player_dict = player_profile.as_dict()

    vectors = {
        stat: TensionVector(
            stat=stat,
            ko_value=ko_dict[stat],
            player_value=player_dict[stat],
        )
        for stat in ko_dict
    }

    return VITRIOLTension(vectors=vectors)