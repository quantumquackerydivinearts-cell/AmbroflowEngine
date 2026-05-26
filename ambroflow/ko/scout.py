"""
ambroflow/ko/scout.py
=====================
StateScout — simulation-forward attractor mapping + elemental crossing matrix.

The scout runs the physics simulation AHEAD of the player to map which
attractor basins are reachable from a given BreathOfKo state × element
treatment combination.  The output drives dynamic content routing:
content is tagged with attractor coordinates; the scheduler matches
incoming player state to the right content at runtime.

Authoring model
---------------
Instead of authoring one piece of content per possible player state
(exponentially expensive across 31 games), authors tag content with
attractor coordinates and write one variant per basin.  The scout
identifies which basins matter for a given quest point; authors fill
those basins; the runtime routes.

Coherence derivation (standalone)
----------------------------------
The full Roko system derives coherence from a Hopfield pass over the
byte table.  The scout operates without the atelier API, so it derives
coherence from two orthogonal physical measurements instead:

  physics_coherence  — how quickly the compound reaction settled.
                        stable=1.0  active=0.7  chaotic=0.3  explosive=0.05
  mandelbrot_coherence — where the player's Azoth sits on the boundary.
                        edge=1.0  bounded=0.8  unbounded=0.2
                        (Edge is the Wunashakoun tell in Roko's model.)

  overall_coherence  = 0.6 × physics + 0.4 × mandelbrot

Gate levels mirror Roko exactly.  A scout result with gate="FyKo" means
"if this player ran this treatment at this BoK state, Roko would open
the FyKo gate" — a forward prediction the content router can act on.

Chiral depth estimation
-----------------------
True chiral depth requires the full tongue-activation history (Roko's
Giann+Keshi pass).  The scout estimates it from BreathOfKo state:
games played, Sakura layer density (orientation), and active flags.
The estimate is honest about its nature — use it for scouting and
authoring; use the live Roko assessment for gate enforcement.

Usage
-----
    from ambroflow.ko.scout import StateScout
    from ambroflow.ko.breath import BreathOfKo

    scout = StateScout()
    result = scout.scout(breath, element_forces=(ADDR_ZOT, ADDR_SHAK))
    print(result.attractor_basin)    # "stable.edge.fyko"
    print(result.is_fixed_point)     # True / False

    # Scan all physics-aware subjects for a quest point:
    basins = scout.scan_basins(breath)
    for subject_id, r in basins.items():
        print(subject_id, "→", r.attractor_basin)

    # Match authored content to current state:
    matching = StateScout.match_content(result, content_catalogue)
"""

from __future__ import annotations

import copy
import statistics
from dataclasses import dataclass, field
from typing import Any, Optional

from .breath import BreathOfKo
from ..physics.backend import get_backend
from ..physics.world import PhysicsWorld


# ── Gate constants (mirror Roko) ──────────────────────────────────────────────

GATE_TIWU = "Tiwu"   # newcomer, present — all gates open
GATE_TAWU = "Tawu"   # active, engaged, in motion
GATE_FYKO = "FyKo"   # reaching toward structural depth
GATE_MOWU = "Mowu"   # resting between active phases
GATE_ZOWU = "ZoWu"   # structurally absent — observation only

GATE_GLOSSES: dict[str, str] = {
    GATE_TIWU: "Ti·Wu — present; newcomer, all gates open",
    GATE_TAWU: "Ta·Wu — actively in the Way; engaged",
    GATE_FYKO: "Fy·Ko — reaching toward depth; structural opening",
    GATE_MOWU: "Mo·Wu — resting between phases",
    GATE_ZOWU: "Zo·Wu — absent from the Way; structural observation",
}


# ── Physics → coherence mapping ───────────────────────────────────────────────

_PHYSICS_COHERENCE: dict[str, float] = {
    "stable":    1.00,
    "active":    0.70,
    "chaotic":   0.30,
    "explosive": 0.05,
}

_MANDELBROT_COHERENCE: dict[str, float] = {
    "edge":      1.00,   # Wunashakoun tell — most alive
    "bounded":   0.80,   # integrated, coherent — but may be fixed
    "unbounded": 0.20,   # accumulation without comprehension
}


# ── ScoutResult ───────────────────────────────────────────────────────────────

@dataclass
class ScoutResult:
    """
    Complete attractor characterisation for one (BoK state, element_forces) pair.

    Fields
    ------
    Physics dimensions
      physics_outcome    — "stable" | "active" | "chaotic" | "explosive"
      physics_mod        — resonance modifier applied (+0.10 → −0.25)
      peak_energy        — maximum KE during simulation
      settle_step        — tick at which energy stabilised (or sim_steps if never)
      compound_addr      — byte address of compound formed (108–123) or None
      compound_name      — human name of compound

    BreathOfKo dimensions
      boundedness        — "bounded" | "edge" | "unbounded"
      azoth              — (real, imag) complex Azoth value
      coil_position      — current Möbius coil position [0.0–12.0]
      games_played       — number of games integrated into this BoK

    Coherence dimensions
      physics_coherence  — [0,1] derived from physics outcome
      mandelbrot_coherence — [0,1] derived from boundedness
      overall_coherence  — weighted combination
      roko_gate          — predicted Roko gate level
      gate_gloss         — one-line gate description

    Chiral dimensions (estimated)
      chiral_depth       — estimated number of active chiral pairs
      chiral_depth_basis — "estimated" always (scout doesn't have full history)

    Attractor summary
      attractor_basin    — "physics.boundedness.gate" e.g. "stable.edge.fyko"
      is_fixed_point     — True when all three dimensions align at their fixed points
                           (physics stable, Mandelbrot edge, chiral_depth >= 1)
    """
    # Physics
    physics_outcome:      str
    physics_mod:          float
    peak_energy:          float
    settle_step:          int
    compound_addr:        Optional[int]
    compound_name:        str

    # BreathOfKo
    boundedness:          str
    azoth:                tuple[float, float]
    coil_position:        float
    games_played:         int

    # Coherence
    physics_coherence:    float
    mandelbrot_coherence: float
    overall_coherence:    float
    roko_gate:            str
    gate_gloss:           str

    # Chiral (estimated)
    chiral_depth:         int
    chiral_depth_basis:   str = "estimated"

    # Summary
    attractor_basin:      str  = ""
    is_fixed_point:       bool = False

    def __post_init__(self) -> None:
        if not self.attractor_basin:
            self.attractor_basin = (
                f"{self.physics_outcome}.{self.boundedness}.{self.roko_gate.lower()}"
            )
        if not self.is_fixed_point:
            self.is_fixed_point = (
                self.physics_outcome in ("stable", "active")
                and self.boundedness == "edge"
                and self.chiral_depth >= 1
            )


# ── StateScout ────────────────────────────────────────────────────────────────

class StateScout:
    """
    Forward simulation scout for attractor mapping.

    Runs deterministic physics + BoK evaluation ahead of player arrival to
    identify which attractor basins are reachable from a given state.

    Parameters
    ----------
    sim_steps:
        Physics simulation ticks per scout run.  Default 60 (= 1 second at
        60 fps) matches the alchemy treatment simulation.
    world:
        Optional shared PhysicsWorld.  If None, a fresh backend is created
        per scout call.  Pass a shared world when calling scout() in a tight
        loop to avoid repeated initialisation.
    """

    def __init__(
        self,
        sim_steps: int = 60,
        world: Optional[PhysicsWorld] = None,
    ) -> None:
        self._sim_steps = sim_steps
        self._world     = world or get_backend()

    # ── Primary scout call ────────────────────────────────────────────────────

    def scout(
        self,
        breath:         BreathOfKo,
        element_forces: tuple[int, ...],
    ) -> ScoutResult:
        """
        Scout a single (BoK state, element_forces) combination.

        Runs the physics simulation, evaluates the BoK, derives coherence
        and gate level, and returns a complete ScoutResult.

        Does NOT mutate breath.  A temporary copy is used for physics
        fingerprint attachment.
        """
        from ..alchemy.physics_integration import simulate_treatment

        # ── Physics pass ──────────────────────────────────────────────────────
        phys = simulate_treatment(element_forces, steps=self._sim_steps,
                                  world=self._world)

        # ── BoK evaluation (non-mutating) ─────────────────────────────────────
        # Attach physics to a shallow copy so we can read the modified Azoth
        # without touching the caller's BreathOfKo.
        breath_copy = copy.copy(breath)
        breath_copy.layer_densities = dict(breath.layer_densities)
        breath_copy.attach_physics(self._world)

        azoth      = breath_copy.azoth()
        boundedness = breath_copy.boundedness()
        coil       = breath_copy.coil_position
        games      = len(breath.dream_calibrations)

        # ── Coherence derivation ─────────────────────────────────────────────
        p_coh = _PHYSICS_COHERENCE.get(phys.outcome, 0.5)
        m_coh = _MANDELBROT_COHERENCE.get(boundedness, 0.5)
        overall = round(0.6 * p_coh + 0.4 * m_coh, 4)

        # ── Chiral depth estimate ─────────────────────────────────────────────
        chiral = _estimate_chiral_depth(breath)

        # ── Gate determination ────────────────────────────────────────────────
        gate = _derive_gate(overall, games, boundedness, chiral)

        return ScoutResult(
            physics_outcome      = phys.outcome,
            physics_mod          = phys.resonance_mod,
            peak_energy          = phys.peak_energy,
            settle_step          = phys.steps_to_settle,
            compound_addr        = phys.compound_addr,
            compound_name        = phys.compound_name,
            boundedness          = boundedness,
            azoth                = (round(azoth.real, 6), round(azoth.imag, 6)),
            coil_position        = round(coil, 4),
            games_played         = games,
            physics_coherence    = round(p_coh, 4),
            mandelbrot_coherence = round(m_coh, 4),
            overall_coherence    = overall,
            roko_gate            = gate,
            gate_gloss           = GATE_GLOSSES[gate],
            chiral_depth         = chiral,
        )

    # ── Basin scan ────────────────────────────────────────────────────────────

    def scan_basins(
        self,
        breath:              BreathOfKo,
        element_force_sets:  Optional[list[tuple[int, ...]]] = None,
    ) -> dict[str, ScoutResult]:
        """
        Scout all physics-aware subjects (or a provided list) and return a
        dict mapping subject_id / element_forces key → ScoutResult.

        If element_force_sets is None, uses PHYSICS_AWARE_SUBJECTS to derive
        the full set of treatments that have physics grounding in this game.

        Returns
        -------
        dict: key = subject_id (if from PHYSICS_AWARE_SUBJECTS) or
              str(element_forces) (if custom list)
        """
        from ..alchemy.physics_integration import PHYSICS_AWARE_SUBJECTS

        if element_force_sets is not None:
            return {
                str(ef): self.scout(breath, ef)
                for ef in element_force_sets
            }

        return {
            subject_id: self.scout(breath, aware.element_forces)
            for subject_id, aware in PHYSICS_AWARE_SUBJECTS.items()
        }

    # ── Quest-point scan ──────────────────────────────────────────────────────

    def scan_quest_point(
        self,
        breath_snapshot: dict,
        element_forces:  tuple[int, ...],
        coil_variants:   int = 3,
    ) -> list[ScoutResult]:
        """
        Scout a quest point across multiple coil-position variants.

        A player arriving at the same quest in different games will have
        different coil positions.  This scan covers the plausible range
        (current position ± one game increment) to identify which basins
        are reachable regardless of exact arrival timing.

        Parameters
        ----------
        breath_snapshot:
            Output of BreathOfKo.snapshot() — restored for each variant.
        element_forces:
            The treatment being scouted.
        coil_variants:
            Number of coil position variants to test (default 3: current,
            −increment, +increment).
        """
        base = BreathOfKo.from_snapshot(breath_snapshot)
        increment = 12.0 / 31.0
        results: list[ScoutResult] = []

        offsets = [0.0] + [
            i * increment * ((-1) ** i)
            for i in range(1, coil_variants)
        ]
        for offset in offsets:
            variant = copy.copy(base)
            variant.layer_densities = dict(base.layer_densities)
            variant.coil_position   = (base.coil_position + offset) % 12.0
            results.append(self.scout(variant, element_forces))

        return results

    # ── Content matching ──────────────────────────────────────────────────────

    @staticmethod
    def match_content(
        result:   ScoutResult,
        catalogue: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Return items from catalogue whose attractor_tags match result.

        Content items may specify partial tag sets — an item tagged
        {"physics": ["stable", "active"]} matches any result with
        physics_outcome in that list, regardless of other dimensions.
        Items with no attractor_tags key are always included (universal
        content).

        Parameters
        ----------
        result:
            A ScoutResult from scout().
        catalogue:
            List of content dicts.  Each may have an "attractor_tags" key
            mapping dimension name → list of accepted values:
              {
                "attractor_tags": {
                  "physics":      ["stable", "active"],
                  "boundedness":  ["edge"],
                  "roko_gate":    ["FyKo", "ZoWu"],
                  "chiral_depth": [1, 2, 3],   # ints: min chiral_depth
                }
              }
        """
        matched: list[dict[str, Any]] = []
        for item in catalogue:
            tags = item.get("attractor_tags")
            if tags is None:
                matched.append(item)
                continue
            if _tags_match(result, tags):
                matched.append(item)
        return matched

    @staticmethod
    def basin_summary(results: dict[str, ScoutResult]) -> dict[str, list[str]]:
        """
        Invert a scan_basins() result: basin_name → list of subject_ids.

        Useful for authoring: "which subjects produce the same basin, so
        they can share authored content?"
        """
        summary: dict[str, list[str]] = {}
        for subject_id, r in results.items():
            summary.setdefault(r.attractor_basin, []).append(subject_id)
        return summary

    @staticmethod
    def fixed_points(results: dict[str, ScoutResult]) -> list[str]:
        """Return subject_ids whose ScoutResult is a fixed point."""
        return [sid for sid, r in results.items() if r.is_fixed_point]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _estimate_chiral_depth(breath: BreathOfKo) -> int:
    """
    Estimate chiral depth from BreathOfKo state.

    True chiral depth requires the full tongue-activation history (Roko's
    Hopfield pass).  This estimate uses games played and Sakura layer
    density (orientation axis) as proxies.

    Each ~4 games played opens roughly one chiral pair.
    High Sakura orientation (>0.6) accelerates the opening.
    Result is clamped to [0, 8] (one pair per forward/decay tongue pair).
    """
    games = len(breath.dream_calibrations)
    if games == 0:
        return 0
    sakura_vals = [breath.layer_densities.get(i, 0.5) for i in range(17, 25)]
    sakura_mean = statistics.mean(sakura_vals)
    # Base: one pair per 4 games, scaled by orientation above the midpoint
    orientation_factor = 0.5 + sakura_mean   # [0.5, 1.5]
    raw = (games / 4.0) * orientation_factor
    return min(int(raw), 8)


def _derive_gate(
    coherence:   float,
    games_played: int,
    boundedness:  str,
    chiral_depth: int,
) -> str:
    """
    Derive the predicted Roko gate from scout-available signals.

    Mirrors _gate_from_profile() in roko.py, adapted for the signals
    available without a live Roko assessment.
    """
    # Newcomer: very few games, no expectation of structural depth yet
    if games_played < 2:
        return GATE_TIWU

    # Chiral pair gates — same thresholds as Roko
    if chiral_depth >= 2 and coherence > 0.45:
        return GATE_FYKO
    if chiral_depth >= 1 and coherence > 0.50:
        return GATE_FYKO

    # Edge + coherence → FyKo (Wunashakoun tell)
    if boundedness == "edge" and coherence > 0.55:
        return GATE_FYKO

    # Solid coherence without depth markers → Tawu
    if coherence > 0.45 and games_played >= 3:
        return GATE_TAWU

    # Edge alone lifts to Tawu even with lower coherence
    if boundedness == "edge":
        return GATE_TAWU

    # Established practice, quiet phase
    if games_played >= 5 and coherence < 0.30:
        return GATE_MOWU

    # Structural absence — low coherence, many games, nothing moving
    if games_played >= 10 and coherence < 0.20 and boundedness == "unbounded":
        return GATE_ZOWU

    # Active engagement
    if coherence > 0.30 or games_played >= 1:
        return GATE_TAWU

    return GATE_TIWU


# ── Crossing matrix types ─────────────────────────────────────────────────────

_INVERSE_REACTION: dict[int, tuple[int, int]] = {
    v: k
    for k, v in __import__(
        "ambroflow.physics.elements", fromlist=["REACTION_TABLE"]
    ).REACTION_TABLE.items()
}

_ELEMENT_LONG_NAMES: dict[int, str] = {
    104: "Shak (Fire)",
    105: "Puf (Air)",
    106: "Mel (Water)",
    107: "Zot (Earth)",
}

# Which compounds contain each element (in either position)
_ELEMENT_COMPOUNDS: dict[int, list[int]] = {
    104: [108, 109, 110, 111, 112, 116, 120],   # Shak appears in these compounds
    105: [109, 112, 113, 114, 115, 117, 121],   # Puf
    106: [110, 114, 116, 117, 118, 119, 122],   # Mel
    107: [111, 115, 119, 120, 121, 122, 123],   # Zot
}

_COHERENCE_RANK: dict[str, float] = {
    "stable": 1.00, "active": 0.70, "chaotic": 0.30, "explosive": 0.05
}


@dataclass
class CrossingEntry:
    """One element or compound's crossing relationship with a BoK state."""
    addr:          int
    name:          str                     # human name
    symbol:        str                     # Shygazun symbol (compound) or addr str (element)
    element_forces: tuple[int, ...]        # forces used in simulation
    is_compound:   bool

    physics_outcome:   str
    physics_coherence: float               # 0.0–1.0 (stable=1, explosive=0.05)
    resonance_mod:     float               # +0.10 → −0.25
    peak_energy:       float
    settle_step:       int

    rank:  int = 0                         # 0 = most cooperative, 19 = most resistant


@dataclass
class ElementProfile:
    """Aggregate crossing posture of one base element across all its compounds."""
    addr:             int
    name:             str
    mean_coherence:   float      # mean physics_coherence across all compounds
    aligned_count:    int        # compounds that are stable or active
    opposed_count:    int        # compounds that are chaotic or explosive
    dominant_outcome: str        # most common outcome across this element's compounds

    @property
    def posture(self) -> str:
        """'aligned' | 'neutral' | 'opposed' based on mean coherence."""
        if self.mean_coherence >= 0.70:
            return "aligned"
        if self.mean_coherence >= 0.45:
            return "neutral"
        return "opposed"


@dataclass
class CrossingMatrix:
    """
    Complete elemental crossing relationship for one BreathOfKo state.

    entries:          All 20 entries (4 elements + 16 compounds), ranked
                      from most cooperative (rank 0) to most resistant (rank 19).
    coil_position:    BoK coil position at time of scout.
    games_played:     Number of games integrated.
    boundedness:      BoK Mandelbrot boundedness.
    element_profiles: Per-element aggregate posture (Shak/Puf/Mel/Zot).
    """
    entries:          list[CrossingEntry]
    coil_position:    float
    games_played:     int
    boundedness:      str
    element_profiles: dict[int, ElementProfile]

    # ── Convenience views ─────────────────────────────────────────────────────

    @property
    def aligned(self) -> list[CrossingEntry]:
        """Entries whose physics is stable or active (cooperative)."""
        return [e for e in self.entries if e.physics_outcome in ("stable", "active")]

    @property
    def opposed(self) -> list[CrossingEntry]:
        """Entries whose physics is chaotic or explosive (resistant)."""
        return [e for e in self.entries if e.physics_outcome in ("chaotic", "explosive")]

    @property
    def pivot(self) -> list[CrossingEntry]:
        """Entries at the active/chaotic boundary (outcome == 'active')."""
        return [e for e in self.entries if e.physics_outcome == "active"]

    def by_addr(self, addr: int) -> Optional[CrossingEntry]:
        """Lookup a specific entry by byte address."""
        for e in self.entries:
            if e.addr == addr:
                return e
        return None

    # ── Display ───────────────────────────────────────────────────────────────

    def display(self) -> str:
        lines: list[str] = []
        lines.append(
            f"Crossing Matrix — coil={self.coil_position:.3f}  "
            f"games={self.games_played}  BoK={self.boundedness}"
        )
        lines.append("-" * 60)

        lines.append("ELEMENT POSTURE")
        for addr, prof in self.element_profiles.items():
            filled = int(prof.mean_coherence * 10)
            bar = "#" * filled + "." * (10 - filled)
            lines.append(
                f"  {prof.name:<16} [{bar}]  {prof.posture:<8}  "
                f"aligned={prof.aligned_count}  opposed={prof.opposed_count}"
            )

        lines.append("")
        lines.append(f"ALIGNED ({len(self.aligned)})")
        for e in self.aligned:
            tag = "(compound)" if e.is_compound else "(element) "
            lines.append(
                f"  {e.name:<22} {tag}  [{e.addr}]  "
                f"{e.physics_outcome:<8}  {e.resonance_mod:+.2f}"
            )

        lines.append("")
        lines.append(f"OPPOSED ({len(self.opposed)})")
        for e in sorted(self.opposed, key=lambda x: x.physics_coherence, reverse=True):
            tag = "(compound)" if e.is_compound else "(element) "
            lines.append(
                f"  {e.name:<22} {tag}  [{e.addr}]  "
                f"{e.physics_outcome:<9}  {e.resonance_mod:+.2f}  "
                f"KE={e.peak_energy:.3f}"
            )
        return "\n".join(lines)


@dataclass
class BiographyPoint:
    """One coil position's crossing posture for a single element."""
    coil_position: float
    game_number:   int           # 1-based estimate of which game this coil belongs to
    posture:       str           # "aligned" | "neutral" | "opposed"
    mean_coherence: float


@dataclass
class CrossingBiography:
    """
    How each element's crossing posture changes across the full 31-game arc.

    tracks:  dict[element_addr → list[BiographyPoint]] — one point per game.
    Use to answer: "when does Fire start cooperating for this player?"
    """
    tracks:        dict[int, list[BiographyPoint]]
    games_sampled: int

    def crossing_game(self, element_addr: int, target: str = "aligned") -> Optional[int]:
        """
        Return the first game number where element_addr reaches target posture.
        target: "aligned" | "neutral" | "opposed"
        Returns None if the posture is never reached in the sampled range.
        """
        for point in self.tracks.get(element_addr, []):
            if point.posture == target:
                return point.game_number
        return None

    def display(self) -> str:
        lines = ["Crossing Biography — element posture across 31-game arc"]
        lines.append("-" * 60)
        for addr, points in self.tracks.items():
            name = _ELEMENT_LONG_NAMES.get(addr, str(addr))
            track_str = "".join(
                "A" if p.posture == "aligned"
                else "n" if p.posture == "neutral"
                else "o"
                for p in points
            )
            first_aligned = self.crossing_game(addr, "aligned")
            note = f"  -> aligns G{first_aligned}" if first_aligned else "  -> never fully aligns"
            lines.append(f"  {name:<16} [{track_str}]{note}")
        lines.append("")
        lines.append("  A=aligned  n=neutral  o=opposed  (one char per game)")
        return "\n".join(lines)


# ── StateScout crossing methods ───────────────────────────────────────────────
# Appended to StateScout via module-level patch after class definition.
# (Python doesn't allow extending a class definition after the fact cleanly,
# so these are defined as module functions and assigned to StateScout below.)

def _crossing_matrix(
    self: "StateScout",
    breath: BreathOfKo,
    include_elements: bool = True,
    include_compounds: bool = True,
) -> CrossingMatrix:
    """
    Run the full elemental crossing simulation for a BreathOfKo state.

    Tests all 4 standalone elements and all 16 compounds (20 total by
    default).  Returns a CrossingMatrix ranked from most cooperative
    (stable, low KE) to most resistant (explosive, high KE).

    Parameters
    ----------
    include_elements:  Include the 4 standalone elements (104–107).
    include_compounds: Include all 16 compounds (108–123).
    """
    from ..alchemy.physics_integration import simulate_treatment
    from ..physics.elements import (
        ADDR_SHAK, ADDR_PUF, ADDR_MEL, ADDR_ZOT,
        COMPOUNDS, compound_name, compound_symbol,
    )

    entries: list[CrossingEntry] = []

    # ── Standalone elements ───────────────────────────────────────────────────
    if include_elements:
        for addr in (ADDR_SHAK, ADDR_PUF, ADDR_MEL, ADDR_ZOT):
            phys = simulate_treatment((addr,), steps=self._sim_steps, world=self._world)
            entries.append(CrossingEntry(
                addr           = addr,
                name           = _ELEMENT_LONG_NAMES[addr],
                symbol         = str(addr),
                element_forces = (addr,),
                is_compound    = False,
                physics_outcome   = phys.outcome,
                physics_coherence = _COHERENCE_RANK[phys.outcome],
                resonance_mod     = phys.resonance_mod,
                peak_energy       = phys.peak_energy,
                settle_step       = phys.steps_to_settle,
            ))

    # ── Compounds ─────────────────────────────────────────────────────────────
    if include_compounds:
        for compound_addr, elem_pair in sorted(_INVERSE_REACTION.items()):
            phys = simulate_treatment(elem_pair, steps=self._sim_steps, world=self._world)
            c = COMPOUNDS[compound_addr]
            entries.append(CrossingEntry(
                addr           = compound_addr,
                name           = c[1],
                symbol         = c[0],
                element_forces = elem_pair,
                is_compound    = True,
                physics_outcome   = phys.outcome,
                physics_coherence = _COHERENCE_RANK[phys.outcome],
                resonance_mod     = phys.resonance_mod,
                peak_energy       = phys.peak_energy,
                settle_step       = phys.steps_to_settle,
            ))

    # ── Sort: most cooperative first ─────────────────────────────────────────
    # Primary: physics_coherence descending.
    # Secondary: peak_energy ascending (lower energy = more cooperative within tier).
    entries.sort(key=lambda e: (-e.physics_coherence, e.peak_energy))
    for i, e in enumerate(entries):
        e.rank = i

    # ── BoK evaluation ────────────────────────────────────────────────────────
    breath_copy = copy.copy(breath)
    breath_copy.layer_densities = dict(breath.layer_densities)
    breath_copy.attach_physics(self._world)
    boundedness = breath_copy.boundedness()

    # ── Element profiles ──────────────────────────────────────────────────────
    from ..physics.elements import ADDR_SHAK, ADDR_PUF, ADDR_MEL, ADDR_ZOT
    profiles: dict[int, ElementProfile] = {}
    for elem_addr in (ADDR_SHAK, ADDR_PUF, ADDR_MEL, ADDR_ZOT):
        compound_addrs = _ELEMENT_COMPOUNDS[elem_addr]
        relevant = [e for e in entries if e.addr in compound_addrs]
        if not relevant:
            continue
        coherences  = [e.physics_coherence for e in relevant]
        mean_coh    = round(statistics.mean(coherences), 4)
        aligned_n   = sum(1 for e in relevant if e.physics_outcome in ("stable", "active"))
        opposed_n   = sum(1 for e in relevant if e.physics_outcome in ("chaotic", "explosive"))
        outcomes    = [e.physics_outcome for e in relevant]
        dominant    = max(set(outcomes), key=outcomes.count)
        profiles[elem_addr] = ElementProfile(
            addr           = elem_addr,
            name           = _ELEMENT_LONG_NAMES[elem_addr],
            mean_coherence = mean_coh,
            aligned_count  = aligned_n,
            opposed_count  = opposed_n,
            dominant_outcome = dominant,
        )

    return CrossingMatrix(
        entries          = entries,
        coil_position    = round(breath.coil_position, 4),
        games_played     = len(breath.dream_calibrations),
        boundedness      = boundedness,
        element_profiles = profiles,
    )


def _crossing_biography(
    self: "StateScout",
    breath: BreathOfKo,
    games: int = 31,
) -> CrossingBiography:
    """
    Map how each element's crossing posture evolves across the 31-game arc.

    Starting from the current BoK state, advances the coil position by one
    game increment per step and runs crossing_matrix() for each.  Returns
    a CrossingBiography with one BiographyPoint per game per element.

    Use crossing_biography().crossing_game(ADDR_SHAK, "aligned") to find
    the game where Fire first stops opposing the player.
    """
    from ..physics.elements import ADDR_SHAK, ADDR_PUF, ADDR_MEL, ADDR_ZOT

    increment = 12.0 / 31.0
    tracks: dict[int, list[BiographyPoint]] = {
        a: [] for a in (ADDR_SHAK, ADDR_PUF, ADDR_MEL, ADDR_ZOT)
    }

    for game_n in range(1, games + 1):
        coil = (breath.coil_position + (game_n - 1) * increment) % 12.0
        variant = copy.copy(breath)
        variant.layer_densities = dict(breath.layer_densities)
        variant.coil_position   = coil

        matrix = self.crossing_matrix(variant)
        for elem_addr, prof in matrix.element_profiles.items():
            tracks[elem_addr].append(BiographyPoint(
                coil_position  = coil,
                game_number    = game_n,
                posture        = prof.posture,
                mean_coherence = prof.mean_coherence,
            ))

    return CrossingBiography(tracks=tracks, games_sampled=games)


# Patch methods onto StateScout
StateScout.crossing_matrix  = _crossing_matrix   # type: ignore[attr-defined]
StateScout.crossing_biography = _crossing_biography  # type: ignore[attr-defined]


def _tags_match(result: ScoutResult, tags: dict[str, Any]) -> bool:
    """Return True if result satisfies all tag constraints."""
    for dimension, accepted in tags.items():
        if dimension == "physics":
            if result.physics_outcome not in accepted:
                return False
        elif dimension == "boundedness":
            if result.boundedness not in accepted:
                return False
        elif dimension == "roko_gate":
            if result.roko_gate not in accepted:
                return False
        elif dimension == "chiral_depth":
            # accepted is a list of ints: match if chiral_depth >= min(accepted)
            if isinstance(accepted, list) and accepted:
                if result.chiral_depth < min(accepted):
                    return False
        elif dimension == "is_fixed_point":
            if result.is_fixed_point not in accepted:
                return False
    return True
