"""
physics_integration.py — Alchemy × Physics bridge.

The alchemy system describes subjects in terms of Shygazun field properties
and element interactions.  This module grounds those descriptions in actual
physics simulation: when elements interact during a treatment, the physics
engine runs a short simulation and the outcome modifies resonance.

Architecture
============
An AlchemicalSubject can optionally carry `element_forces` — a tuple of
element byte addresses (104–107) involved in the treatment.  When two or
more elements are present, they react (via the compound reaction table) and
the physics engine simulates the reaction for a configurable number of steps.

Physics outcome → resonance modifier:
  stable   (settled, low energy)   → +0.10 bonus on raw resonance
  active   (high energy, ordered)  → no modifier (neutral)
  chaotic  (high energy, disordered) → −0.10 penalty
  explosive (extreme energy spike) → −0.25 penalty (epiphanic cap reduced)

The physics simulation is deterministic (same seed as Kobra): two players
performing the same treatment with the same materials get the same physics
result.  Presence and diagnostic quality still drive the primary resonance
calculation.  Physics is the substrate check, not the override.

Compound subjects
=================
Certain AlchemicalSubjects are defined as compound events — they require
specific element combinations to be physically realised.  For example, the
Infernal Salve requires Earth×Fire = Radiation (byte 120), which means the
treatment requires physically simulating magmatic force application to
maintain structural stability.

The `compound_subject` factory function creates subjects whose resonance
calculation includes the physics stability check automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..physics import PhysicsWorld, get_backend, react, COMPOUND_PHYSICS
from ..physics.elements import ADDR_SHAK, ADDR_PUF, ADDR_MEL, ADDR_ZOT
from .system import AlchemicalSubject, InformationField


# ── Simulation config ─────────────────────────────────────────────────────────

_SIM_STEPS = 60              # one second at 60fps
_SIM_BODIES = 4              # representative test body count
_STABLE_THRESHOLD   = 0.002  # kinetic energy considered "at rest"
_EXPLOSIVE_THRESHOLD = 2.0   # peak KE considered "explosive" (4 bodies at ~1 m/s)

# Resonance modifiers from physics outcome
_PHYSICS_MOD: dict[str, float] = {
    "stable":    +0.10,
    "active":     0.00,
    "chaotic":   -0.10,
    "explosive": -0.25,
}


# ── Physics treatment context ─────────────────────────────────────────────────

@dataclass
class PhysicsTreatmentContext:
    """
    Physics simulation result attached to an alchemy treatment.

    outcome:        "stable" | "active" | "chaotic" | "explosive"
    resonance_mod:  modifier applied to raw resonance (+/- float)
    compound_addr:  byte address of the compound produced (108–123), or None
    compound_name:  human name of the compound
    fingerprint:    physics world state for BreathOfKo Bridge
    steps_to_settle: how many ticks before energy stabilised (or _SIM_STEPS)
    peak_energy:    maximum kinetic energy observed during simulation
    """
    outcome:          str
    resonance_mod:    float
    compound_addr:    Optional[int]
    compound_name:    str
    fingerprint:      dict
    steps_to_settle:  int
    peak_energy:      float


# ── Simulation ────────────────────────────────────────────────────────────────

def simulate_treatment(
    element_forces: tuple[int, ...],
    steps:          int = _SIM_STEPS,
    world:          Optional[PhysicsWorld] = None,
) -> PhysicsTreatmentContext:
    """
    Run a short physics simulation for an element combination.

    Creates a small test world (floor + a few bodies), applies the specified
    element forces, and reads the outcome.  The world uses the deterministic
    Kael seed so results are reproducible.

    element_forces: tuple of element byte addresses (104-107)
    steps:          simulation ticks (default 60 = 1 second)
    world:          reuse an existing world if provided (will be reset)
    """
    if world is None:
        world = get_backend()
    else:
        world.reset()

    # Build test scene: floor + bodies stacked above it
    world.add_static(0.0, -3.0, 0.0, 10.0, 0.5, 10.0)
    for i in range(min(_SIM_BODIES, 4)):
        world.add_body(1.0, 0.0, float(i) * 1.5 + 0.5, 0.0)

    # Find compound from element pair (first two elements)
    compound_addr = None
    if len(element_forces) >= 2:
        compound_addr = react(element_forces[0], element_forces[1])

    # Determine force profile from compound physics (or element directly)
    if compound_addr is not None:
        phys = COMPOUND_PHYSICS.get(compound_addr, {})
        impulse_scale = phys.get("impulse", 1.0)
        thermal       = phys.get("thermal", 0.0)
    else:
        # Single element — map to its natural force profile
        impulse_scale = _element_impulse(element_forces[0]) if element_forces else 1.0
        thermal       = 0.0

    # Apply compound impulse as an upward Shak force on all bodies
    for i in range(1, world.body_count):  # skip floor (body 0)
        world.apply_shak(i, 0.0, impulse_scale * 5.0, 0.0)
        if thermal > 0:
            # Fire component adds horizontal turbulence
            world.apply_shak(i, thermal * 3.0, 0.0, thermal * 2.0)

    # Run simulation — no gravity (Zot=False): measure compound reaction stability.
    # Photonic forces (phase coupling + spin exclusion) active: compounds that form
    # in constructive phase are truly stable; those in destructive phase are not.
    peak_energy = 0.0
    settle_step = steps
    for step in range(steps):
        world.wu_tick_extended(zot=False, mel=True, puf=True, photon=True, chiral=True)
        ke = world.total_kinetic_energy()
        if ke > peak_energy:
            peak_energy = ke
        if world.is_settled(_STABLE_THRESHOLD) and settle_step == steps:
            settle_step = step

    # Classify outcome by WHEN the system settled, not just whether it did.
    # settle_ratio = 0 = immediate / 1 = never settled within sim window.
    # This gives meaningful differentiation between gentle (stable) and
    # violent (chaotic/explosive) compound reactions.
    settle_ratio = settle_step / max(steps, 1)
    if peak_energy >= _EXPLOSIVE_THRESHOLD:
        outcome = "explosive"
    elif settle_ratio <= 0.30:
        outcome = "stable"     # settled in first third — cooperative elements
    elif settle_ratio <= 0.65:
        outcome = "active"     # moderate — neutral modifier
    else:
        outcome = "chaotic"    # never settled or very late — resistant elements

    from ..physics.elements import compound_name as _cn
    cname = _cn(compound_addr) if compound_addr else ""

    return PhysicsTreatmentContext(
        outcome         = outcome,
        resonance_mod   = _PHYSICS_MOD[outcome],
        compound_addr   = compound_addr,
        compound_name   = cname,
        fingerprint     = world.fingerprint(),
        steps_to_settle = settle_step,
        peak_energy     = round(peak_energy, 4),
    )


def _element_impulse(addr: int) -> float:
    """Default impulse scale for a standalone element (no reaction)."""
    return {
        ADDR_SHAK: 2.0,   # Fire — strong impulse
        ADDR_PUF:  0.5,   # Air  — gentle drag, low impulse
        ADDR_MEL:  0.1,   # Water — damping, very low impulse
        ADDR_ZOT:  1.0,   # Earth — gravity-scale force
    }.get(addr, 1.0)


# ── Resonance integration ─────────────────────────────────────────────────────

def apply_physics_to_resonance(
    raw_resonance:  float,
    element_forces: tuple[int, ...],
    world:          Optional[PhysicsWorld] = None,
) -> tuple[float, PhysicsTreatmentContext]:
    """
    Run physics simulation and apply outcome modifier to raw resonance.

    Returns (modified_resonance, context).

    The modifier is additive on the 0.0–1.0 scale, clamped to [0.0, 1.0].
    Physical instability (chaos, explosion) reduces resonance regardless of
    how good the diagnostic reading was — the elements resist the treatment.
    Physical stability adds a small bonus — the elements cooperate.
    """
    if not element_forces:
        # No element forces — no physics modifier
        null_ctx = PhysicsTreatmentContext(
            outcome="active", resonance_mod=0.0,
            compound_addr=None, compound_name="",
            fingerprint={}, steps_to_settle=0, peak_energy=0.0,
        )
        return raw_resonance, null_ctx

    ctx = simulate_treatment(element_forces, world=world)
    modified = max(0.0, min(1.0, raw_resonance + ctx.resonance_mod))
    return modified, ctx


# ── Compound subject factory ──────────────────────────────────────────────────

def compound_subject(
    subject: AlchemicalSubject,
    element_forces: tuple[int, ...],
) -> "PhysicsAwareSubject":
    """
    Wrap an AlchemicalSubject to make its resonance calculation physics-aware.

    The returned PhysicsAwareSubject carries element_forces and exposes
    physics_context after a treatment, which the Bridge reads for BreathOfKo.
    """
    return PhysicsAwareSubject(subject=subject, element_forces=element_forces)


@dataclass
class PhysicsAwareSubject:
    """
    An AlchemicalSubject augmented with element physics.

    element_forces: element byte addresses involved in treatment (104–107)
    physics_context: set after simulate_treatment() is called, holds
                     the outcome for BreathOfKo Bridge integration.
    """
    subject:          AlchemicalSubject
    element_forces:   tuple[int, ...]
    physics_context:  Optional[PhysicsTreatmentContext] = None

    def __getattr__(self, name: str):
        """Delegate to the wrapped subject for all AlchemicalSubject attributes."""
        return getattr(self.subject, name)

    def run_physics(self, world: Optional[PhysicsWorld] = None) -> PhysicsTreatmentContext:
        """Run simulation and cache the context."""
        self.physics_context = simulate_treatment(self.element_forces, world=world)
        return self.physics_context


# ── Extended SUBJECTS registry ────────────────────────────────────────────────
# Physics-aware wrappers for existing subjects where element forces are known.
# These supplement (not replace) the existing SUBJECTS in system.py.

from .system import SUBJECT_BY_ID as _BASE_SUBJECTS

PHYSICS_AWARE_SUBJECTS: dict[str, PhysicsAwareSubject] = {
    # Basic Tincture: temporal/ko — Water-dominant (Mel), subtle Earth (Zot)
    "0034_KLIT": compound_subject(
        _BASE_SUBJECTS["0034_KLIT"],
        element_forces=(ADDR_MEL, ADDR_ZOT),  # Water×Earth = Erosion (gradual transformation)
    ),
    # Restorative Tincture: mental/gasha — Water clearing noise (Mel + Puf)
    "0035_KLIT": compound_subject(
        _BASE_SUBJECTS["0035_KLIT"],
        element_forces=(ADDR_MEL, ADDR_PUF),  # Water×Air = Vapor (gentle dispersal)
    ),
    # Desire Crystal: spatial/Wunashako — Fire dominant, Earth structural (Shak + Zot)
    "0036_KLIT": compound_subject(
        _BASE_SUBJECTS["0036_KLIT"],
        element_forces=(ADDR_SHAK, ADDR_ZOT),  # Fire×Earth = Magma (intense structural transformation)
    ),
    # Infernal Salve: temporal/na — Earth×Fire = Radiation (structure emitting towards origin)
    "0037_KLIT": compound_subject(
        _BASE_SUBJECTS["0037_KLIT"],
        element_forces=(ADDR_ZOT, ADDR_SHAK),  # Earth×Fire = Radiation
    ),
    # Angelic Revival Salve: spatial+temporal — Fire×Water = Alkahest (desire dissolving sealed wound)
    "0038_KLIT": compound_subject(
        _BASE_SUBJECTS["0038_KLIT"],
        element_forces=(ADDR_SHAK, ADDR_MEL),  # Fire×Water = Alkahest
    ),
}
