"""
VITRIOL Stat Assignment
=======================
Ko (2021_GODS) assigns VITRIOL stats in dream sequences.
Ko is the Black Ouroboros — 10 arms, 7 spirals — God of Dreams and the Unconscious.

VITRIOL — 7 stats, 31-point budget, range 1–10 per stat.
  V — Vitality        governed by Asmodeus (Lust)
  I — Introspection   governed by Satan (Wrath)
  T — Tactility       governed by Beelzebub (Gluttony)
  R — Reflectivity    governed by Belphegor (Sloth)
  I — Ingenuity       governed by Leviathan (Envy)
  O — Ostentation     governed by Mammon (Greed)
  L — Levity          governed by Lucifer (Pride)

Reading the secondary natures of the 7 Sin Rulers in reverse order
spells VITRIOL — the alchemical formula.

Ko does not "give" stats. Ko reads the player's dream calibration densities
and reflects back what is already true. The assignment is recognition, not gift.

Assignment mechanics:
  The three calibration densities (Sakura/Rose/Lotus) modulate the 7 stats:

  Sakura density (orientation/fast) → L (Levity), O (Ostentation)
    — orientation and display; how you face the world
  Rose density (relational/medium) → I (Introspection), I (Ingenuity), R (Reflectivity)
    — quality perception, pattern recognition, transformation
  Lotus density (material/slow)    → V (Vitality), T (Tactility)
    — groundedness, physical world engagement

  Coil position modulates whether the secondary stat in each pair
  gets more weight than the primary (higher coil position = deeper reading).

  Budget: 31 points distributed, each stat floored at 1 and capped at 10.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from .calibration import DreamCalibration


# ── VITRIOL constants (mirrors vitriol.py in DjinnOS_Shyagzun) ────────────────

VITRIOL_STATS: tuple[str, ...] = (
    "vitality",
    "introspection",
    "tactility",
    "reflectivity",
    "ingenuity",
    "ostentation",
    "levity",
)

VITRIOL_RULERS: dict[str, str] = {
    "vitality":     "Asmodeus",
    "introspection": "Satan",
    "tactility":    "Beelzebub",
    "reflectivity": "Belphegor",
    "ingenuity":    "Leviathan",
    "ostentation":  "Mammon",
    "levity":       "Lucifer",
}

TOTAL_BUDGET = 31
STAT_MIN     = 1
STAT_MAX     = 10


# ── Assignment result ─────────────────────────────────────────────────────────

@dataclass
class VITRIOLProfile:
    vitality:     int
    introspection: int
    tactility:    int
    reflectivity: int
    ingenuity:    int
    ostentation:  int
    levity:       int

    def as_dict(self) -> dict[str, int]:
        return {
            "vitality":      self.vitality,
            "introspection": self.introspection,
            "tactility":     self.tactility,
            "reflectivity":  self.reflectivity,
            "ingenuity":     self.ingenuity,
            "ostentation":   self.ostentation,
            "levity":        self.levity,
        }

    def total(self) -> int:
        return sum(self.as_dict().values())

    def dominant_stat(self) -> str:
        d = self.as_dict()
        return max(d, key=d.__getitem__)

    def formula_letters(self) -> str:
        """Returns V-I-T-R-I-O-L as a formatted string."""
        d = self.as_dict()
        return "-".join(
            f"{k[0].upper()}:{v}"
            for k, v in d.items()
        )


# ── Ko's assignment ────────────────────────────────────────────────────────────

def assign_vitriol(calibration: DreamCalibration, coil_position: float = 6.0) -> VITRIOLProfile:
    """
    Ko reads the DreamCalibration densities and assigns VITRIOL.

    coil_position: float [0.0–12.0] — current position on the Möbius coil.
      Closer to 0 or 12 = near the Möbius pair (Gaoh/Wu-Yl boundary).
      Closer to 6 = midpoint, balanced reading.

    The assignment is deterministic given calibration + coil_position.
    Ko does not randomise.
    """
    s = calibration.sakura_density
    r = calibration.rose_density
    l = calibration.lotus_density

    # Coil position modulation: near 0 or 12 (Möbius boundary) deepens Lotus reading
    mobius_proximity = 1.0 - abs(coil_position - 6.0) / 6.0   # 1.0 at midpoint, 0.0 at edge
    lotus_weight = l * (0.7 + 0.3 * (1.0 - mobius_proximity))

    # Raw scores per stat before clamping/budgeting
    raw: dict[str, float] = {
        "vitality":      lotus_weight * 10.0,
        "introspection": r * 10.0,
        "tactility":     lotus_weight * 9.0,
        "reflectivity":  r * 9.5,
        "ingenuity":     r * 8.5 + s * 1.5,
        "ostentation":   s * 10.0,
        "levity":        s * 9.5 + r * 0.5,
    }

    # Normalise to budget of 31
    total_raw = sum(raw.values())
    if total_raw == 0:
        total_raw = 1.0
    scale = TOTAL_BUDGET / total_raw
    scaled = {k: v * scale for k, v in raw.items()}

    # Floor to 1, cap at 10
    assigned: dict[str, int] = {k: max(STAT_MIN, min(STAT_MAX, round(v))) for k, v in scaled.items()}

    # Correct budget drift
    current_total = sum(assigned.values())
    diff = TOTAL_BUDGET - current_total
    if diff != 0:
        # Add/remove from stats furthest from their bounds
        order = sorted(assigned.keys(), key=lambda k: (
            -(STAT_MAX - assigned[k]) if diff > 0 else -(assigned[k] - STAT_MIN)
        ))
        for i in range(abs(diff)):
            stat = order[i % len(order)]
            step = 1 if diff > 0 else -1
            new_val = assigned[stat] + step
            if STAT_MIN <= new_val <= STAT_MAX:
                assigned[stat] = new_val

    return VITRIOLProfile(
        vitality=     assigned["vitality"],
        introspection=assigned["introspection"],
        tactility=    assigned["tactility"],
        reflectivity= assigned["reflectivity"],
        ingenuity=    assigned["ingenuity"],
        ostentation=  assigned["ostentation"],
        levity=       assigned["levity"],
    )
