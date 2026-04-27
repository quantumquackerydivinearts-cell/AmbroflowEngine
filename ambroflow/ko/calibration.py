"""
24-Layer Dream Calibration
==========================
The game begins in dream because dream is where the coil's structure becomes visible.
Waking is the state where all layers are unified and opaque to themselves.

The 24 layers expand the 12 coil layers into waking and dreaming faces:

  Layers  1–8  → Lotus faces  (slow,   waking)   — material ground, last to dissolve
  Layers  9–16 → Rose faces   (medium, dreaming)  — relational/spectral, partially fluid
  Layers 17–24 → Sakura faces (fast,   both)      — orientation, first to dissolve

The three calibration phases run in order: Sakura → Rose → Lotus.
Each phase produces a density score [0.0–1.0] for that tongue.

The densities feed into:
  - VITRIOL stat assignment (Ko assigns from calibration)
  - World starting conditions (Lotus density sets material ground)
  - BreathOfKo layer density tracking (persists across all 31 games)
  - KoFlag attestation (layer resonance gates flag availability)

Depth Meditation perk: enables reading deeper into Rose and Lotus layers.
Without it, Lotus density is partially occluded.

The 12 Coil Layers (from CONTEXT.md §5.2):
  1  Gaoh       Bit              Rose                Pure polarity
  2  Ao-Seth    Decimal          Rose + Grapevine    Enumeration
  3  Tyzu-Soa   Boolean          Lotus + Grapevine   Elemental charge
  4  Ja-Foa     Coordinate       Sakura + Daisy      Spatial orientation
  5  Kael-Seth  Object           Daisy + Grapevine   Structure/objecthood
  6  Shak-Lo    Entity           AppleBlossom+Daisy  Identity
  7  Ru-Mavo    Color Metadata   Rose + Grapevine    Spectral identity
  8  Si-Myza    Movement Diffs   Aster+AppleBlossom  Change
  9  Dyf-Vr     Pattern Flows    Grapevine + Daisy   Emergent correspondence
  10 Ne-Soa     Names/Metadata   Daisy + Grapevine   Field acquires language
  11 Sy-Mek     Scene Diffs      Aster + Grapevine   Delta between states
  12 Wu-Yl      Function         Rose + Aster        Cobra executes / Möbius pair of L1
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Coil layer definitions ────────────────────────────────────────────────────

class CalibrationTongue(str, Enum):
    LOTUS  = "lotus"    # slow — material ground
    ROSE   = "rose"     # medium — relational/spectral
    SAKURA = "sakura"   # fast — orientation


class CalibrationRate(str, Enum):
    SLOW   = "slow"
    MEDIUM = "medium"
    FAST   = "fast"


@dataclass(frozen=True)
class CoilLayer:
    index:        int             # 1–12
    shygazun:     str             # Shygazun name
    content_type: str             # Bit | Decimal | Boolean | Coordinate | ...
    primary_tongue: str           # canonical tongue(s) from CONTEXT.md
    domain:       str             # human-readable semantic
    note:         str = ""


COIL_LAYERS: tuple[CoilLayer, ...] = (
    CoilLayer(1,  "Gaoh",      "Bit",            "Rose",                  "Pure polarity — Ha+Ga as Möbius zero",
              "Layer 1 and Layer 12 are the same surface at different densities (Möbius pair)"),
    CoilLayer(2,  "Ao-Seth",   "Decimal",        "Rose + Grapevine",      "Enumeration emerges from polarity"),
    CoilLayer(3,  "Tyzu-Soa",  "Boolean",        "Lotus + Grapevine",     "Elemental charge applied to number"),
    CoilLayer(4,  "Ja-Foa",    "Coordinate",     "Sakura + Daisy",        "Spatial orientation becomes addressable"),
    CoilLayer(5,  "Kael-Seth", "Object",         "Daisy + Grapevine",     "Structure clusters coordinates into things — Quintessence binding"),
    CoilLayer(6,  "Shak-Lo",   "Entity",         "AppleBlossom + Daisy",  "Objects gain identity, become beings",
              "Threshold between structure and entity — recognition is mutual constitution"),
    CoilLayer(7,  "Ru-Mavo",   "Color Metadata", "Rose + Grapevine",      "Spectral identity — ontological not decorative"),
    CoilLayer(8,  "Si-Myza",   "Movement Diffs", "Aster + AppleBlossom",  "Change recorded as first-class datum"),
    CoilLayer(9,  "Dyf-Vr",    "Pattern Flows",  "Grapevine + Daisy",     "Emergent correspondence across layers"),
    CoilLayer(10, "Ne-Soa",    "Names/Metadata", "Daisy + Grapevine",     "The Field acquires language"),
    CoilLayer(11, "Sy-Mek",    "Scene Diffs",    "Aster + Grapevine",     "Delta between Field states across fold time"),
    CoilLayer(12, "Wu-Yl",     "Function",       "Rose + Aster",          "Cobra executes here — Gaoh made operative",
              "FrontierOpen states live here. Same surface as Layer 1 at different density."),
)

COIL_BY_INDEX: dict[int, CoilLayer] = {c.index: c for c in COIL_LAYERS}


# ── Dream layer definitions (the 24) ─────────────────────────────────────────

@dataclass(frozen=True)
class DreamLayer:
    index:       int                 # 1–24 (calibration position)
    coil_index:  int                 # 1–12 (parent coil layer)
    face:        str                 # "waking" | "dreaming" | "sakura"
    tongue:      CalibrationTongue
    rate:        CalibrationRate
    domain:      str

    @property
    def coil(self) -> CoilLayer:
        return COIL_BY_INDEX[self.coil_index]


def _build_dream_layers() -> tuple[DreamLayer, ...]:
    layers: list[DreamLayer] = []

    # Layers 1–8: Lotus faces — coil layers 1–8 waking faces
    for i, coil_i in enumerate(range(1, 9), start=1):
        layers.append(DreamLayer(
            index=i, coil_index=coil_i,
            face="waking",
            tongue=CalibrationTongue.LOTUS,
            rate=CalibrationRate.SLOW,
            domain=f"material ground — {COIL_BY_INDEX[coil_i].domain}",
        ))

    # Layers 9–16: Rose faces — coil layers 1–8 dreaming faces
    for i, coil_i in enumerate(range(1, 9), start=9):
        layers.append(DreamLayer(
            index=i, coil_index=coil_i,
            face="dreaming",
            tongue=CalibrationTongue.ROSE,
            rate=CalibrationRate.MEDIUM,
            domain=f"relational/spectral — {COIL_BY_INDEX[coil_i].domain}",
        ))

    # Layers 17–24: Sakura faces — coil layers 9–12, both faces (4 × 2 = 8)
    idx = 17
    for coil_i in range(9, 13):
        for face in ("waking", "dreaming"):
            layers.append(DreamLayer(
                index=idx, coil_index=coil_i,
                face=face,
                tongue=CalibrationTongue.SAKURA,
                rate=CalibrationRate.FAST,
                domain=f"orientation — {COIL_BY_INDEX[coil_i].domain}",
            ))
            idx += 1

    return tuple(layers)


DREAM_LAYERS: tuple[DreamLayer, ...] = _build_dream_layers()
DREAM_LAYER_BY_INDEX: dict[int, DreamLayer] = {d.index: d for d in DREAM_LAYERS}


# ── Calibration result ────────────────────────────────────────────────────────

@dataclass
class DreamCalibration:
    """
    Result of a single dream calibration sequence.
    Produced once per game start by the Ko dream sequence.

    Densities are [0.0, 1.0]:
      sakura_density  — how fluid orientation is for this player
      rose_density    — how directly they perceive Primordial quality
      lotus_density   — how grounded their material starting state is

    layer_densities is the full 24-position readout.
    active_perks records which meditation perks were active — load-bearing for
    downstream systems that need to know which calibration boosts were applied.
    """
    sakura_density:  float
    rose_density:    float
    lotus_density:   float
    layer_densities: dict[int, float]   # key = DreamLayer.index (1–24)
    game_id:         str
    active_perks:    frozenset[str]     = frozenset()

    def generate_world_conditions(self) -> dict[str, float]:
        """
        The waking world is the dream's residue.
          Lotus density  → physical starting conditions
          Rose density   → relational starting conditions
          Sakura density → player's initial orientation capacity
        """
        return {
            "physical_ground":   self.lotus_density,
            "relational_ground": self.rose_density,
            "orientation":       self.sakura_density,
        }

    def dominant_tongue(self) -> CalibrationTongue:
        scores = {
            CalibrationTongue.LOTUS:  self.lotus_density,
            CalibrationTongue.ROSE:   self.rose_density,
            CalibrationTongue.SAKURA: self.sakura_density,
        }
        return max(scores, key=scores.__getitem__)


# ── Calibration session ───────────────────────────────────────────────────────

class DreamCalibrationSession:
    """
    Runs a three-phase dream calibration sequence.

    Phase 1 — Sakura (fast):  "Which way are you facing?"
    Phase 2 — Rose (medium):  "What is the quality of this?"
    Phase 3 — Lotus (slow):   "Where do you begin?"

    Each phase presents prompts (delivered by Ko's dialogue system).
    The caller feeds player responses back via `respond()`.
    When all three phases are complete, `complete()` returns a DreamCalibration.

    Parameters
    ----------
    game_id:
        Active game slug.
    active_perks:
        Set of active meditation perk IDs.  Calibration effects:
          depth_meditation       → +0.08 Lotus and Rose (deeper material/relational read)
          infernal_meditation    → +0.08 Sakura (deeper orientation/underworld read)
          transcendental_meditation → +0.05 all phases (content richness — more of the
                                     day's events are captured across every layer)
    """

    PHASES = [
        CalibrationTongue.SAKURA,
        CalibrationTongue.ROSE,
        CalibrationTongue.LOTUS,
    ]

    # Generic prompts — used when no game-specific prompts are registered.
    # These are structural placeholders that read the correct architecture
    # but carry no game context. Replace with GAME_PROMPTS entries for
    # each game in the series.
    PROMPTS: dict[CalibrationTongue, list[str]] = {
        CalibrationTongue.SAKURA: [
            "Which way are you facing?",
            "Before you know where you are — which direction pulls?",
            "What is your first orientation?",
        ],
        CalibrationTongue.ROSE: [
            "What is the quality of this?",
            "Something is present. What is its nature?",
            "The poles are felt before they are named. What do you feel?",
        ],
        CalibrationTongue.LOTUS: [
            "Where do you begin?",
            "The ground arrives last. What is it made of?",
            "What does the material world assemble itself from?",
        ],
    }

    # Game-specific prompt sets, keyed by game slug.
    #
    # Sakura reads: liminal boundary architecture handling capacity.
    #   Does the player have any capacity to remain present at a threshold
    #   without resolving it prematurely? The six ontological boundary words
    #   (Va/Vo/Ve/Vu/Vi/Vy) are the underlying register being probed.
    #   Questions must place the player in the threshold condition without
    #   naming it, and without installing subject/object binary frames.
    #
    # Rose reads: intersubjective layer sensitivity.
    #   Is the player's internal spectral/frequency register already active
    #   before the question arrives? The chromatic and polarity strips
    #   (Ru→AE, Ha/Ga/Wu/Na/Ung) are the underlying register.
    #   Questions probe whether the register is already embodied, not
    #   whether the player can describe or construct it on demand.
    #
    # Lotus reads: self-definition and coarse-grain boundary condition architecture.
    #   Are the elemental thresholds (Ty/Zu/Ly/Mu/Fy/Pu/Shy/Ku),
    #   presence qualities (Known/Unknown/Related/Sha), and experiential
    #   ground states (Ko/Zo/Ke) embodied or conceptual in this player?
    #   Questions must reach the three Lotus strips directly without
    #   installing new frameworks during the measurement.
    GAME_PROMPTS: dict[str, dict[CalibrationTongue, list[str]]] = {

        "7_KLGS": {
            # Ko's Labyrinth — first dream sequence.
            # Player: total unknowing. No named location, no named caller,
            # no apprenticeship context. Ko reads before the player has
            # any orientation to perform.
            CalibrationTongue.SAKURA: [
                # Reads: can the player remain present at a moving boundary?
                # Va (Order) is not offered as rescue. Vo (Chaos/mutation)
                # is simply present. The question reads whether the player
                # can stay with that or immediately reaches for resolution.
                "The edge is moving. Not toward you — it is simply moving. "
                "What is already happening in you in response?",

                # Reads: directional pull without named destination.
                # Traveling/Meeting/Parting (Di/Da/Do) without a fixed origin.
                # The player is already oriented before the question arrives —
                # the prompt reads which way, not whether.
                "There is a direction here that has no name. "
                "You are already turned toward something. Notice what.",

                # Reads: presence at a threshold versus collapse into content.
                # Something breaks open — player is present but not the cause.
                # The question reads whether the player stays at the event
                # or immediately relocates into the event's content.
                "Something is breaking open. You are present at this. "
                "What is present in you?",
            ],

            CalibrationTongue.ROSE: [
                # Reads: pre-linguistic spectral register.
                # Something has arrived. Does the player have an internal
                # frequency response before they have words for what it is?
                # Probes the chromatic strip (Ru through AE) as felt register.
                "Something has arrived before you have words for it. "
                "What does it register as — not what is it, but what registers?",

                # Reads: polarity sensitivity.
                # Ha/Ga (Absolute Positive/Negative) as felt weight, not
                # named concept. Are the poles already present in the player's
                # sensing, or does the question create them?
                "There are two poles to what you are sensing. "
                "You do not need to name them. "
                "Are they in balance, or is one pulling?",

                # Reads: qualitative rather than causal orientation.
                # Not why something called the player here, but the felt
                # quality of the call. Rose's Na/Wu/Ung strip — process,
                # integration, point — as pre-reflective sensation.
                "The quality of what called you here — "
                "not the reason, not the purpose. "
                "The quality. What is it?",
            ],

            CalibrationTongue.LOTUS: [
                # Reads: elemental threshold character.
                # The Ty/Zu/Ly/Mu/Fy/Pu/Shy/Ku strip — each threshold pair
                # has a character (material beginning, feeling toward, thought
                # toward, pattern toward). The question reads which character
                # the player's ground state is made of.
                "What is the character of the beginning you are standing in? "
                "Not its content — its character.",

                # Reads: Known/Unknown boundary (Fi/Pe strip).
                # Sha (Intellect of spirit) and Ko (Experience/intuition)
                # are also present. The question reads whether the player's
                # boundary between known and unknown is a felt architecture
                # or an imported map.
                "What do you already know here? "
                "And what is already outside what you know?",

                # Reads: Ko (byte 19 — Experience/intuition as ground).
                # The deepest Lotus register: not what is happening,
                # but what is the ground that has assembled under this moment.
                # Zo (absence) and Ke (incoherence/illness) are also readable
                # here if the player's ground is absent or fractured.
                "What is the ground that has assembled itself under this moment? "
                "Not the moment — the ground.",
            ],
        },
    }

    # ── Ko's arrival — spoken before calibration begins ──────────────────────
    #
    # Three lines, in order. Ko does not announce itself.
    # No names, no context, no comfort. Ko is simply present
    # and the reading has already started.
    GAME_OPENING_LINES: dict[str, list[str]] = {
        "7_KLGS": [
            "You are here.",
            "The ground has not assembled yet. Stay in that.",
            "The reading begins from what is already true. "
            "The questions are not the reading — you are.",
        ],
    }

    # ── Ko's VITRIOL assignment — spoken after calibration, one line per stat ─
    #
    # Structure: GAME_ASSIGNMENT_LINES[game_id][stat][tier]
    # Tiers: "low" (1–4), "mid" (5–7), "high" (8–10)
    #
    # Ko speaks recognition, not gift.
    # Ko does not say "you have" or "I give you."
    # Ko states what is already true.
    GAME_ASSIGNMENT_LINES: dict[str, dict[str, dict[str, str]]] = {
        "7_KLGS": {
            "vitality": {
                "low":  "The body is present. It is not your first instrument here.",
                "mid":  "The body is present and active. It knows where it is.",
                "high": "The body is fully present. It arrived before you did.",
            },
            "introspection": {
                "low":  "The inner register is quiet. That is not absence — it is spacing.",
                "mid":  "The inner register is active. You hear yourself.",
                "high": "The inner register is dense. That listening is not recent.",
            },
            "tactility": {
                "low":  "Your hands know less than your eyes. That is the current shape.",
                "mid":  "Physical sensation is direct. You land in what you touch.",
                "high": "You are in contact with surfaces. Not everything — much.",
            },
            "reflectivity": {
                "low":  "The transformation capacity is open but not loaded. Things pass through.",
                "mid":  "Transformation is available. You can hold an opposing charge.",
                "high": "The transformation capacity is dense. "
                        "Opposing things do not cancel in you — they become material.",
            },
            "ingenuity": {
                "low":  "Lateral movement is possible but not habitual. The straight line comes first.",
                "mid":  "Lateral movement is active. You see across as well as through.",
                "high": "Lateral movement is primary. "
                        "You find the perpendicular before the direct path.",
            },
            "ostentation": {
                "low":  "The world-facing surface is thin. "
                        "What is inside does not yet know it is being seen.",
                "mid":  "The world-facing surface is present. "
                        "You take up the correct amount of space.",
                "high": "The world-facing surface is fully active. "
                        "You know you are visible and you accept that.",
            },
            "levity": {
                "low":  "Gravity is present and familiar. You know the weight of things.",
                "mid":  "Gravity and lightness are in dialogue. Neither has won.",
                "high": "Lightness is primary. "
                        "You know how to escape the weight of a thing without losing it.",
            },
        },
    }

    # ── Ko's closing — spoken after VITRIOL assignment, before player wakes ──
    #
    # Three lines, in order. Ko names the gap that is about to open.
    # Then releases. The final line is a single word.
    GAME_CLOSING_LINES: dict[str, list[str]] = {
        "7_KLGS": [
            "What you do with this reading is not my concern.",
            "The distance between what I see and what you choose to carry — "
            "that is where you will be living.",
            "Wake.",
        ],
    }

    def __init__(self, game_id: str, active_perks: frozenset[str] = frozenset()) -> None:
        self._game_id = game_id
        self._perks   = active_perks
        self._phase_idx = 0
        self._responses: dict[CalibrationTongue, list[float]] = {
            CalibrationTongue.SAKURA: [],
            CalibrationTongue.ROSE:   [],
            CalibrationTongue.LOTUS:  [],
        }
        self._complete = False

    @property
    def current_phase(self) -> Optional[CalibrationTongue]:
        if self._phase_idx >= len(self.PHASES):
            return None
        return self.PHASES[self._phase_idx]

    @property
    def current_prompts(self) -> list[str]:
        phase = self.current_phase
        if phase is None:
            return []
        game_set = self.GAME_PROMPTS.get(self._game_id)
        if game_set and phase in game_set:
            return game_set[phase]
        return self.PROMPTS[phase]

    def respond(self, resonance: float) -> bool:
        """
        Submit a response to the current phase.
        resonance: float [0.0–1.0] encoding how strongly the player responded.

        Returns True if the phase is now complete (advance to next prompt).
        Returns False if more responses are needed for this phase.
        """
        phase = self.current_phase
        if phase is None:
            return False

        resonance = max(0.0, min(1.0, resonance))
        self._responses[phase].append(resonance)

        # Each phase requires 3 responses (one per prompt)
        if len(self._responses[phase]) >= 3:
            self._phase_idx += 1
            return True
        return False

    def is_complete(self) -> bool:
        return self._phase_idx >= len(self.PHASES)

    def complete(self) -> DreamCalibration:
        """Finalise and return the DreamCalibration."""
        if not self.is_complete():
            raise RuntimeError("Calibration not yet complete.")

        def _density(tongue: CalibrationTongue) -> float:
            vals = self._responses[tongue]
            base = sum(vals) / len(vals) if vals else 0.5
            # Depth Meditation: deeper Lotus/Rose read (material + relational layers)
            if tongue in (CalibrationTongue.LOTUS, CalibrationTongue.ROSE):
                if "depth_meditation" in self._perks:
                    base += 0.08
            # Infernal Meditation: deeper Sakura read (orientation/underworld-facing layers)
            if tongue == CalibrationTongue.SAKURA:
                if "infernal_meditation" in self._perks:
                    base += 0.08
            # Transcendental Meditation: content richness — all phases capture more of the day
            if "transcendental_meditation" in self._perks:
                base += 0.05
            return round(min(1.0, base), 4)

        sakura = _density(CalibrationTongue.SAKURA)
        rose   = _density(CalibrationTongue.ROSE)
        lotus  = _density(CalibrationTongue.LOTUS)

        # Distribute densities across 24 layers
        layer_densities: dict[int, float] = {}
        for dl in DREAM_LAYERS:
            if dl.tongue == CalibrationTongue.LOTUS:
                base = lotus
            elif dl.tongue == CalibrationTongue.ROSE:
                base = rose
            else:
                base = sakura
            # Minor perturbation by coil layer index for intra-group variation
            perturb = (dl.coil_index - 6.5) / 100.0   # ±0.055 range
            layer_densities[dl.index] = round(max(0.0, min(1.0, base + perturb)), 4)

        return DreamCalibration(
            sakura_density=sakura,
            rose_density=rose,
            lotus_density=lotus,
            layer_densities=layer_densities,
            game_id=self._game_id,
            active_perks=self._perks,
        )


# ── Dialogue helpers ──────────────────────────────────────────────────────────

def _stat_tier(value: int) -> str:
    """Map a VITRIOL stat value (1–10) to the Ko assignment tier."""
    if value <= 4:
        return "low"
    elif value <= 7:
        return "mid"
    else:
        return "high"


def get_assignment_line(game_id: str, stat: str, value: int) -> str:
    """
    Return Ko's assignment line for a stat at a given value.

    Falls back to a generic line if the game or stat is not registered.
    ``stat`` should be a full stat name (e.g. ``"reflectivity"``).
    ``value`` is the Ko-assigned integer value (1–10).
    """
    tier = _stat_tier(value)
    game_lines = DreamCalibrationSession.GAME_ASSIGNMENT_LINES.get(game_id, {})
    stat_lines = game_lines.get(stat, {})
    if tier in stat_lines:
        return stat_lines[tier]
    # Generic fallback — structurally valid but carries no game context
    return f"{stat.capitalize()}: {value}."
