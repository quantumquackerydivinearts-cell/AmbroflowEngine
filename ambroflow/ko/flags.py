"""
KoFlags — Cross-Game State Flags
=================================
KoFlags are the interchange logic of Ko's Labyrinth.
They are not achievements. They are epistemological states —
the system witnesses the player arriving at a layer's truth
through how they act, not through puzzle solution.

A KoFlag is earned through Attestation: when the player's behavior at any layer
demonstrates sufficient understanding to increase their density of correspondence
at that layer, the system witnesses this and raises the flag.

Flags:
  - Have a Shygazun compound name (load-bearing, not decorative)
  - Have a decimal address (position in the byte space)
  - Know which games can produce them (source_games)
  - Know which games they affect and how (target_games with weight)
  - Have a decay rate: 0.0 = permanent, 1.0 = single-game
  - Have a layer resonance: which of the 12 coil layers this flag primarily affects

The exoteric release sequence is fixed.
The esoteric sequence is different for every player —
determined by their flagged states and the order they chose to play.

Books 5 and 7 are the network hubs:
  Book 5 (Truth Be Told)            — lower plot arc (assembling what is true)
  Book 7 (Alchemist's Labor of Love) — upper plot arc (working with truth)
These two hubs form a figure-eight topology: two loops sharing a crossing point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .calibration import DREAM_LAYER_BY_INDEX


@dataclass
class KoFlag:
    id:                str
    shygazun_compound: str           # The flag's name in Shygazun
    decimal_address:   int           # Position in the byte space
    description:       str           # What epistemological state this represents
    source_games:      set[int]      # Game numbers that can produce this flag
    target_games:      dict[int, float]  # game_number → modification weight
    decay_rate:        float         # 0.0 = permanent, 1.0 = single-game
    layer_resonance:   int           # Which coil layer (1–12) this flag primarily affects


# ── Flag registry (seeded with structural flags; expanded as games are authored) ──

KO_FLAGS: tuple[KoFlag, ...] = (
    KoFlag(
        id="polarities_held",
        shygazun_compound="Gaoh-Ha-Ga",
        decimal_address=31,
        description="The player can hold both poles without resolving them into opposition.",
        source_games={1, 7},
        target_games={i: 0.3 for i in range(1, 32)},
        decay_rate=0.0,    # permanent
        layer_resonance=1,  # Gaoh / polarity
    ),
    KoFlag(
        id="objects_alive",
        shygazun_compound="Kael-Wu",
        decimal_address=45,
        description="Player treats all objects as Quintessence-bearing — no dead matter in play.",
        source_games={5, 7},
        target_games={i: 0.4 for i in range(1, 32)},
        decay_rate=0.0,
        layer_resonance=5,  # Kael-Seth / objecthood
    ),
    KoFlag(
        id="recognition_mutual",
        shygazun_compound="Shak-Lo-Soa",
        decimal_address=193,
        description="Player understands that recognition between entity and world is mutual constitution.",
        source_games={6, 7},
        target_games={6: 0.5, 7: 0.5, 31: 0.8},
        decay_rate=0.0,
        layer_resonance=6,  # Shak-Lo / entity
    ),
    KoFlag(
        id="absence_practiced",
        shygazun_compound="Vios-Ne",
        decimal_address=88,
        description="Player's omission patterns are consistent enough to constitute a practice. Vios observes.",
        source_games=set(range(1, 32)),
        target_games={i: 0.2 for i in range(1, 32)},
        decay_rate=0.1,    # slow decay — omission practice can fade
        layer_resonance=10,  # Ne-Soa / names and what goes unspoken
    ),
    KoFlag(
        id="mobius_witnessed",
        shygazun_compound="Wu-Yl-Gaoh",
        decimal_address=154,
        description="Player has experienced Layer 12 as the same surface as Layer 1. The Möbius pair perceived.",
        source_games={7, 12, 31},
        target_games={31: 1.0, 12: 0.6, 7: 0.4},
        decay_rate=0.0,
        layer_resonance=12,  # Wu-Yl / Möbius function layer
    ),
    KoFlag(
        id="infernal_presence_sustained",
        shygazun_compound="Si-Myza-Kael",
        decimal_address=77,
        description="Player cleared at least one Sulphera ring — can sustain consciousness in the Underworld's register.",
        source_games={7},
        target_games={i: 0.35 for i in range(8, 32)},
        decay_rate=0.0,
        layer_resonance=8,  # Si-Myza / movement and change
    ),
    KoFlag(
        id="grief_without_dissolution",
        shygazun_compound="Zen-Na-Gaoh",
        decimal_address=60,
        description="Player completed quest 0026_KLST (Good Grief) — presence without object achieved.",
        source_games={7},
        target_games={7: 0.4, 26: 0.6, 31: 0.5},
        decay_rate=0.0,
        layer_resonance=9,  # Dyf-Vr / emergent pattern
    ),
    KoFlag(
        id="negaya_appeased",
        shygazun_compound="Zo-Ku-Ko",   # Absence–End–Experience: absence terminated through knowing
        decimal_address=166,
        description=(
            "Player completed the necromancy ritual via the Shakzefan / Lakota path. "
            "Negaya is appeased and bound — meditation sessions are restored."
        ),
        source_games={7},
        target_games={i: 0.0 for i in range(7, 32)},   # gate only, no weight modification
        decay_rate=0.0,
        layer_resonance=6,   # Shak-Lo / entity threshold — body made present again
    ),
)

KO_FLAG_BY_ID: dict[str, KoFlag] = {f.id: f for f in KO_FLAGS}


# ── Flag state tracker ────────────────────────────────────────────────────────

class FlagState:
    """
    Tracks which KoFlags are currently raised for a player.

    Flags are Shygazun compound names — their meaning is load-bearing.
    Decay: on each game completion, decaying flags reduce by their decay_rate.
    A flag with weight < 0.05 is considered inactive.
    """

    def __init__(self, initial: dict[str, float] | None = None) -> None:
        # flag_id → current weight (0.0 = inactive, 1.0 = full)
        self._weights: dict[str, float] = dict(initial or {})

    def raise_flag(self, flag_id: str, weight: float = 1.0) -> None:
        current = self._weights.get(flag_id, 0.0)
        self._weights[flag_id] = min(1.0, max(current, weight))

    def is_active(self, flag_id: str) -> bool:
        return self._weights.get(flag_id, 0.0) >= 0.05

    def weight(self, flag_id: str) -> float:
        return self._weights.get(flag_id, 0.0)

    def active_flags(self) -> list[str]:
        return [fid for fid, w in self._weights.items() if w >= 0.05]

    def decay(self) -> None:
        """Apply one game's worth of decay to all decaying flags."""
        for flag in KO_FLAGS:
            if flag.id in self._weights and flag.decay_rate > 0:
                self._weights[flag.id] = max(0.0, self._weights[flag.id] - flag.decay_rate)

    def modification_weight(self, game_number: int) -> float:
        """
        Total modification weight of all active flags targeting a specific game.
        Used by game state machines to tune starting conditions.
        """
        total = 0.0
        for flag in KO_FLAGS:
            if self.is_active(flag.id) and game_number in flag.target_games:
                total += flag.target_games[game_number] * self._weights[flag.id]
        return total

    def snapshot(self) -> dict[str, float]:
        return {k: v for k, v in self._weights.items() if v >= 0.05}
