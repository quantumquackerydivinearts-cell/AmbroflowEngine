"""
Laboratory Process Simulator
============================
Models the sequential equipment-grounded practice of alchemy in Ko's Labyrinth.

The laboratory session is the physical layer beneath the diagnostic system.
Each operation the practitioner performs against a substance contributes to their
engagement with the subject's information field. That accumulated engagement is
what AlchemySystem.treat() resolves into outputs and sanity effects.

The substance's trait state (mirrored from kos_labyrnth.py §11.3) constrains
which operations are available at each step — dissolution requires Powdered
substance, coagulation requires Molten substance. This preserves process
fidelity without prescribing outcomes. The sequence is the craft.

Engagement accumulation
-----------------------
Each operation generates a contribution to one engagement mode:
  ontological  — perceiving the subject's actual nature
  cosmological — consulting the Dragon Tongue register
  narrative    — engaging the lore/story resonance
  somatic      — the embodied, sensory labour

Contributions accumulate across all operations performed. At conclude(),
they become the mode_engagement scores in the DiagnosticReading passed to
AlchemySystem.treat(). Operations performed with skill contribute more;
botched operations contribute very little.

Skill checking
--------------
Each operation resolves a quality score 0.0–1.0:

    competence = (alchemy_rank / 100.0) * 0.7 + vitriol_score * 0.3
    quality    = max(0.0, min(1.0, competence - difficulty * (1.0 - competence)))

Where vitriol_score is the practitioner's score in the operation's VITRIOL letter.
Quality directly scales the engagement contribution. Quality below _BOTCH_THRESHOLD
is a catastrophic failure — the substance gains UNUSABLE.

VITRIOL-to-operation mapping (classical alchemical sequence)
------------------------------------------------------------
  V (Visita)       → dissolution      — the substance opens to inspection
  I (Interiora)    → filtration       — the interior perceived; impurity held back
  T (Terrae)       → calcination / grinding / smelting — reduced to earth
  R (Rectificando) → distillation     — rectified: the purest fraction separated
  I (Invenies)     → conjunction      — you will find: two substances become one
  O (Occultum)     → fermentation     — the hidden: transformation sealed in the dark
  L (Lapidem)      → coagulation / casting — the stone: final solidification

Field axis identification
-------------------------
Performing an operation with quality >= _AXIS_ID_THRESHOLD identifies its field_axis.
  T-group → temporal    V, I (filtration), R → mental    I (conjunction), L → spatial
  O → temporal (hidden transformation in time)
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Optional

from .system import DiagnosticReading, TreatmentApproach


# ── Trait ID namespace ─────────────────────────────────────────────────────────
# Mirrors kos_labyrnth.py §11.3 OBJECT_TRAITS. Source of truth: that file.

class _T:
    USABLE      = 0
    UNUSABLE    = 1
    FULL        = 2
    EMPTY       = 3
    ALIVE       = 4
    DEAD        = 5
    MOVABLE     = 6
    IMMOBILIZED = 7
    POISONOUS   = 8
    FLAMMABLE   = 9
    INERT       = 10
    EXPLOSIVE   = 11
    TOKEN       = 12
    COLLECTOR   = 13
    POWDERED    = 14
    MOLTEN      = 15


# ── Equipment KLOB ID namespace ────────────────────────────────────────────────
# Mirrors ambroflow/klob/registry.py ALL_OBJECTS. Source of truth: that file.

class _E:
    MORTAR         = "8000_KLOB"
    PESTLE         = "2000_KLOB"
    RAG            = "0001_KLOB"
    RETORT         = "0003_KLOB"
    VOLUME_FLASK   = "0004_KLOB"
    REAGENT_BOTTLE = "0005_KLOB"
    SAND           = "1001_KLOB"
    REFINED_SAND   = "1002_KLOB"
    FURNACE        = "0030_KLOB"
    BELLOWS        = "0006_KLOB"
    CRUCIBLE       = "0007_KLOB"
    JAR            = "0009_KLOB"
    DIATOM_EARTH   = "1003_KLOB"
    RING_MOLD      = "0011_KLOB"
    INGOT_MOLD     = "0012_KLOB"


# ── Thresholds ─────────────────────────────────────────────────────────────────

_BOTCH_THRESHOLD     = 0.05   # quality below → catastrophic: substance gains UNUSABLE
_AXIS_ID_THRESHOLD   = 0.45   # quality at or above → field axis identified in reading
_PRESENCE_THRESHOLD  = 0.75   # session avg quality → approach_mode "presence"
_INTUITION_THRESHOLD = 0.45   # session avg quality → approach_mode "intuition"
                               # below → "formula"


# ── Substance starting states ──────────────────────────────────────────────────
# Default trait sets by KLOB object ID. Source of truth: kos_labyrnth.py §11.2–3.

SUBSTANCE_DEFAULTS: dict[str, frozenset[int]] = {
    "0040_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Water Flask
    "1015_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Water
    "0073_KLOB": frozenset({_T.ALIVE, _T.USABLE, _T.MOVABLE, _T.FLAMMABLE}),                # Herb (Common)
    "0074_KLOB": frozenset({_T.ALIVE, _T.USABLE, _T.MOVABLE, _T.FLAMMABLE}),                # Herb (Restorative)
    "1006_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.FLAMMABLE, _T.EXPLOSIVE}),            # Saltpeter
    "1007_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.FLAMMABLE, _T.POISONOUS}),            # Sulphur
    "1008_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.FLAMMABLE, _T.INERT}),                # Charcoal
    "2001_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Tin
    "2002_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Iron
    "2003_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Gold
    "2004_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Copper
    "2005_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.POISONOUS}),                          # Mercury (liquid metal — no INERT)
    "2006_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Silver
    "2007_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT, _T.POISONOUS}),                # Lead
    "2008_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Nickel
    "1009_KLOB": frozenset({_T.DEAD, _T.USABLE, _T.MOVABLE, _T.POWDERED}),                  # Ashes (post-calcination product)
    "1011_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.EXPLOSIVE, _T.POISONOUS}),            # Potassium
    "1012_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.FLAMMABLE, _T.EXPLOSIVE, _T.POISONOUS}), # Phosphorus
    "1013_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT, _T.POISONOUS}),                # Arsenic
    "3003_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Chalk
    "3004_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Gypsum
    "3005_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Quartz
    "4007_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Moldavite
    "4008_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.INERT}),                              # Desert Glass
    "0075_KLOB": frozenset({_T.USABLE, _T.MOVABLE, _T.FLAMMABLE}),                          # Binding Wax
}

_GENERIC_START = frozenset({_T.USABLE, _T.MOVABLE})


# ── Substance state ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SubstanceState:
    """
    Current alchemical state of a substance under active laboratory work.

    object_id : KLOB ID of the source material (kos_labyrnth.py §11.2)
    traits    : active ObjectTrait IDs (kos_labyrnth.py §11.3)
    purity    : 0.0–1.0 — increases through filtration and distillation
    quantity  : unit count of this substance
    """
    object_id : str
    traits    : frozenset[int]
    purity    : float = 0.5
    quantity  : int   = 1

    def has_trait(self, trait_id: int) -> bool:
        return trait_id in self.traits

    def has_all(self, trait_ids: frozenset[int]) -> bool:
        return trait_ids.issubset(self.traits)

    def has_none(self, trait_ids: frozenset[int]) -> bool:
        return self.traits.isdisjoint(trait_ids)

    def with_traits(
        self,
        add:          frozenset[int] = frozenset(),
        remove:       frozenset[int] = frozenset(),
        purity_delta: float          = 0.0,
    ) -> "SubstanceState":
        return SubstanceState(
            object_id=self.object_id,
            traits=((self.traits | add) - remove),
            purity=max(0.0, min(1.0, self.purity + purity_delta)),
            quantity=self.quantity,
        )

    def trait_names(self) -> list[str]:
        _NAMES = {
            _T.USABLE: "Usable",       _T.UNUSABLE: "Unusable",
            _T.FULL: "Full",           _T.EMPTY: "Empty",
            _T.ALIVE: "Alive",         _T.DEAD: "Dead",
            _T.MOVABLE: "Movable",     _T.IMMOBILIZED: "Immobilized",
            _T.POISONOUS: "Poisonous", _T.FLAMMABLE: "Flammable",
            _T.INERT: "Inert",         _T.EXPLOSIVE: "Explosive",
            _T.TOKEN: "Token",         _T.COLLECTOR: "Collector",
            _T.POWDERED: "Powdered",   _T.MOLTEN: "Molten",
        }
        return [_NAMES.get(t, f"trait_{t}") for t in sorted(self.traits)]

    @classmethod
    def default_for(cls, object_id: str, quantity: int = 1) -> "SubstanceState":
        """Starting state for a known substance, or generic usable state."""
        return cls(
            object_id=object_id,
            traits=SUBSTANCE_DEFAULTS.get(object_id, _GENERIC_START),
            purity=0.5,
            quantity=quantity,
        )


# ── Operation definition ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class OperationDef:
    """
    Definition of one laboratory operation.

    op_id              : canonical identifier
    name               : display name
    vitriol_letter     : V/I/T/R/O/L — which VITRIOL affinity governs this
    field_axis         : mental | temporal | spatial — axis identified on clean execution
    required_equipment : all KLOB IDs must be present in the lab
    required_traits    : substance must have ALL of these traits
    forbidden_traits   : substance must have NONE of these traits
    adds_traits        : added to substance on execution
    removes_traits     : removed from substance on execution
    engagement_mode    : ontological | cosmological | narrative | somatic
    engagement_weight  : max contribution to that mode on perfect execution (0.0–1.0)
    base_difficulty    : 0.0–1.0 — cost subtracted from competence in skill check
    purity_delta       : change to substance purity (positive = purification)
    observation        : what the player sees when this operation runs
    failure_text       : what the player sees on catastrophic failure
    """
    op_id              : str
    name               : str
    vitriol_letter     : str
    field_axis         : str
    required_equipment : frozenset[str]
    required_traits    : frozenset[int]
    forbidden_traits   : frozenset[int]
    adds_traits        : frozenset[int]
    removes_traits     : frozenset[int]
    engagement_mode    : str
    engagement_weight  : float
    base_difficulty    : float
    purity_delta       : float = 0.0
    observation        : str   = ""
    failure_text       : str   = ""


# ── Operation library ──────────────────────────────────────────────────────────

OPERATIONS: tuple[OperationDef, ...] = (

    OperationDef(
        op_id="grinding",
        name="Grinding",
        vitriol_letter="T",
        field_axis="temporal",
        required_equipment=frozenset({_E.MORTAR, _E.PESTLE}),
        required_traits=frozenset({_T.USABLE, _T.MOVABLE}),
        forbidden_traits=frozenset({_T.POWDERED, _T.MOLTEN}),
        adds_traits=frozenset({_T.POWDERED}),
        removes_traits=frozenset(),
        engagement_mode="somatic",
        engagement_weight=0.65,
        base_difficulty=0.15,
        observation=(
            "The substance yields under the pestle. A fine powder collects in the bowl, "
            "releasing its smell as it breaks."
        ),
        failure_text=(
            "The grinding is uneven. Material escapes the mortar. "
            "The powder is coarse and inconsistent."
        ),
    ),

    OperationDef(
        op_id="calcination",
        name="Calcination",
        vitriol_letter="T",
        field_axis="temporal",
        required_equipment=frozenset({_E.FURNACE, _E.CRUCIBLE}),
        required_traits=frozenset({_T.FLAMMABLE}),
        forbidden_traits=frozenset({_T.MOLTEN, _T.INERT}),
        adds_traits=frozenset({_T.DEAD, _T.POWDERED}),
        removes_traits=frozenset({_T.ALIVE, _T.FLAMMABLE}),
        engagement_mode="somatic",
        engagement_weight=0.60,
        base_difficulty=0.30,
        observation=(
            "The volatile rises and burns away. What remains in the crucible is the fixed "
            "earth of the substance — grey, still, reduced."
        ),
        failure_text=(
            "The heat is wrong. The volatile is not fully expelled. "
            "The calcinate is incomplete — still partly alive."
        ),
    ),

    OperationDef(
        op_id="smelting",
        name="Smelting",
        vitriol_letter="T",
        field_axis="temporal",
        required_equipment=frozenset({_E.FURNACE, _E.CRUCIBLE, _E.BELLOWS}),
        required_traits=frozenset({_T.INERT, _T.MOVABLE}),
        forbidden_traits=frozenset({_T.ALIVE, _T.FLAMMABLE, _T.MOLTEN}),
        adds_traits=frozenset({_T.MOLTEN}),
        removes_traits=frozenset({_T.INERT}),
        engagement_mode="somatic",
        engagement_weight=0.55,
        base_difficulty=0.40,
        observation=(
            "The bellows drives the heat. The metal softens, then loses all rigidity. "
            "The crucible holds the flow."
        ),
        failure_text=(
            "The temperature is insufficient. The metal softens but does not fully flow. "
            "The smelt is incomplete."
        ),
    ),

    OperationDef(
        op_id="dissolution",
        name="Dissolution",
        vitriol_letter="V",
        field_axis="mental",
        required_equipment=frozenset({_E.VOLUME_FLASK}),
        required_traits=frozenset({_T.POWDERED}),
        forbidden_traits=frozenset({_T.FULL}),
        adds_traits=frozenset({_T.FULL}),
        removes_traits=frozenset({_T.POWDERED}),
        engagement_mode="ontological",
        engagement_weight=0.80,
        base_difficulty=0.25,
        observation=(
            "The powder releases into the solvent. The flask holds the substance "
            "dispersed — its nature now legible to the medium."
        ),
        failure_text=(
            "The substance clumps. The dissolution is incomplete — "
            "some matter resists the solvent and settles."
        ),
    ),

    OperationDef(
        op_id="filtration",
        name="Filtration",
        vitriol_letter="I",
        field_axis="mental",
        required_equipment=frozenset({_E.DIATOM_EARTH, _E.RAG}),
        required_traits=frozenset({_T.FULL}),
        forbidden_traits=frozenset(),
        adds_traits=frozenset(),
        removes_traits=frozenset(),
        engagement_mode="ontological",
        engagement_weight=0.60,
        base_difficulty=0.20,
        purity_delta=0.15,
        observation=(
            "The solution passes through the diatom earth. What does not belong is held back. "
            "What comes through is clearer."
        ),
        failure_text=(
            "The filtrate is cloudy. Impurity has passed through with the solution. "
            "The separation was incomplete."
        ),
    ),

    OperationDef(
        op_id="distillation_sand",
        name="Distillation",
        vitriol_letter="R",
        field_axis="mental",
        required_equipment=frozenset({_E.RETORT, _E.FURNACE, _E.SAND}),
        required_traits=frozenset({_T.FULL}),
        forbidden_traits=frozenset(),
        adds_traits=frozenset(),
        removes_traits=frozenset(),
        engagement_mode="ontological",
        engagement_weight=1.00,
        base_difficulty=0.55,
        purity_delta=0.28,
        observation=(
            "The vapour rises through the neck of the retort. The sand bath holds the heat even. "
            "The condensate collects — the essence has passed over."
        ),
        failure_text=(
            "The heat gradient collapses. The vapour and residue mix in the neck. "
            "The distillate is contaminated."
        ),
    ),

    OperationDef(
        op_id="distillation_refined",
        name="Distillation (Refined Sand)",
        vitriol_letter="R",
        field_axis="mental",
        required_equipment=frozenset({_E.RETORT, _E.FURNACE, _E.REFINED_SAND}),
        required_traits=frozenset({_T.FULL}),
        forbidden_traits=frozenset(),
        adds_traits=frozenset(),
        removes_traits=frozenset(),
        engagement_mode="ontological",
        engagement_weight=1.00,
        base_difficulty=0.42,
        purity_delta=0.35,
        observation=(
            "The refined sand distributes the heat with precision. The vapour rises cleanly. "
            "The condensate is the clearest fraction available."
        ),
        failure_text=(
            "Even with refined sand, the heat is misread. The distillate is uneven."
        ),
    ),

    OperationDef(
        op_id="conjunction",
        name="Conjunction",
        vitriol_letter="I",
        field_axis="spatial",
        required_equipment=frozenset({_E.VOLUME_FLASK}),
        required_traits=frozenset(),
        forbidden_traits=frozenset({_T.UNUSABLE}),
        adds_traits=frozenset(),
        removes_traits=frozenset(),
        engagement_mode="narrative",
        engagement_weight=0.70,
        base_difficulty=0.35,
        observation=(
            "The two substances meet in the flask. What they make together "
            "is not what either was alone."
        ),
        failure_text=(
            "The conjunction is wrong. The substances do not speak to each other. "
            "The mixture is inert."
        ),
    ),

    OperationDef(
        op_id="fermentation",
        name="Fermentation",
        vitriol_letter="O",
        field_axis="temporal",
        required_equipment=frozenset({_E.JAR}),
        required_traits=frozenset({_T.ALIVE}),
        forbidden_traits=frozenset({_T.DEAD, _T.INERT}),
        adds_traits=frozenset(),
        removes_traits=frozenset(),
        engagement_mode="cosmological",
        engagement_weight=0.80,
        base_difficulty=0.30,
        observation=(
            "The substance is sealed in the jar. The hidden transformation begins in the dark. "
            "The Dragon Tongue knows the organism this will become."
        ),
        failure_text=(
            "The fermentation fails. The substance putrefies without transformation. "
            "The seal was wrong or the timing was off."
        ),
    ),

    OperationDef(
        op_id="ring_casting",
        name="Ring Casting",
        vitriol_letter="L",
        field_axis="spatial",
        required_equipment=frozenset({_E.RING_MOLD}),
        required_traits=frozenset({_T.MOLTEN}),
        forbidden_traits=frozenset(),
        adds_traits=frozenset({_T.INERT}),
        removes_traits=frozenset({_T.MOLTEN}),
        engagement_mode="ontological",
        engagement_weight=0.90,
        base_difficulty=0.35,
        observation=(
            "The melt pours into the ring mold. As it cools it takes the form "
            "of the vessel — the stone finding its shape."
        ),
        failure_text=(
            "The pour is wrong. The metal sets unevenly in the mold — "
            "the ring has voids, the surface is irregular."
        ),
    ),

    OperationDef(
        op_id="ingot_casting",
        name="Ingot Casting",
        vitriol_letter="L",
        field_axis="spatial",
        required_equipment=frozenset({_E.INGOT_MOLD}),
        required_traits=frozenset({_T.MOLTEN}),
        forbidden_traits=frozenset(),
        adds_traits=frozenset({_T.INERT}),
        removes_traits=frozenset({_T.MOLTEN}),
        engagement_mode="ontological",
        engagement_weight=0.85,
        base_difficulty=0.30,
        observation=(
            "The melt fills the ingot mold. The solid bar that emerges "
            "is the substance made into a form that can be worked further."
        ),
        failure_text=(
            "The casting is imperfect. The ingot has internal stress — "
            "it will fracture under the hammer."
        ),
    ),
)

OP_BY_ID: dict[str, OperationDef] = {op.op_id: op for op in OPERATIONS}


# ── Operation result ───────────────────────────────────────────────────────────

@dataclass
class OperationResult:
    """
    Outcome of one laboratory operation step.

    success              : True unless equipment or trait requirements were unmet
    op_id                : which operation was performed
    quality              : 0.0–1.0 skill check result
    new_substance        : substance state after this operation
    engagement_contribution : dict[mode, amount] — added to session totals
    axis_identified      : field axis identified (if quality >= _AXIS_ID_THRESHOLD)
    catastrophic         : True if quality < _BOTCH_THRESHOLD (substance → UNUSABLE)
    observation          : text to show the player
    reason               : why success=False, if applicable
    """
    success                 : bool
    op_id                   : str
    quality                 : float
    new_substance           : SubstanceState
    engagement_contribution : dict[str, float]
    axis_identified         : Optional[str]
    catastrophic            : bool
    observation             : str
    reason                  : str = ""


# ── Laboratory session ─────────────────────────────────────────────────────────

class LaboratorySession:
    """
    Active laboratory session — tracks substance state and engagement accumulation.

    Initialise with the subject_id being worked on, the apparatus available in
    this lab, the starting substance, and the practitioner's actor_id.

    Call perform() for each operation the player executes.
    Call conclude() when the player finishes to get a DiagnosticReading and
    TreatmentApproach for passing to AlchemySystem.treat().

    Parameters
    ----------
    subject_id          : ID of the AlchemicalSubject being worked (from system.SUBJECT_BY_ID)
    available_equipment : frozenset of KLOB IDs present in this laboratory
    starting_substance  : initial SubstanceState (use SubstanceState.default_for())
    actor_id            : player entity ID
    """

    def __init__(
        self,
        subject_id          : str,
        available_equipment : frozenset[str],
        starting_substance  : SubstanceState,
        actor_id            : str,
    ) -> None:
        self._subject_id   = subject_id
        self._equipment    = available_equipment
        self._substance    = starting_substance
        self._actor_id     = actor_id

        self._mode_scores  : dict[str, float] = {}
        self._identified_axes: set[str]       = set()
        self._quality_history: list[float]    = []
        self._history      : list[OperationResult] = []

    # ── Queries ───────────────────────────────────────────────────────────────

    @property
    def substance(self) -> SubstanceState:
        return self._substance

    @property
    def history(self) -> list[OperationResult]:
        return list(self._history)

    @property
    def subject_id(self) -> str:
        return self._subject_id

    def available_operations(self) -> list[OperationDef]:
        """
        Return operations whose equipment and trait requirements are currently satisfied.

        Equipment check: all IDs in required_equipment must be in available_equipment.
        Trait check: substance has all required_traits and none of forbidden_traits.
        Unusable substance blocks all operations.
        """
        if self._substance.has_trait(_T.UNUSABLE):
            return []
        result = []
        for op in OPERATIONS:
            if not op.required_equipment.issubset(self._equipment):
                continue
            if not self._substance.has_all(op.required_traits):
                continue
            if not self._substance.has_none(op.forbidden_traits):
                continue
            result.append(op)
        return result

    # ── Skill check ───────────────────────────────────────────────────────────

    @staticmethod
    def _skill_check(
        alchemy_rank   : int,
        vitriol_score  : float,
        base_difficulty: float,
    ) -> float:
        """
        Deterministic quality score for one operation.

        High competence reduces the cost of difficulty. Low competence amplifies it.
        A rank-100 practitioner with full VITRIOL affinity always succeeds cleanly.
        A rank-20 practitioner will botch distillation.
        """
        competence = (alchemy_rank / 100.0) * 0.7 + max(0.0, min(1.0, vitriol_score)) * 0.3
        quality    = competence - base_difficulty * (1.0 - competence)
        return max(0.0, min(1.0, quality))

    # ── Perform ───────────────────────────────────────────────────────────────

    def perform(
        self,
        op_id         : str,
        alchemy_rank  : int,
        vitriol_scores: dict[str, float],
    ) -> OperationResult:
        """
        Attempt one laboratory operation.

        op_id          : operation to perform (must be in OP_BY_ID)
        alchemy_rank   : practitioner's alchemy skill rank (0–100)
        vitriol_scores : dict of VITRIOL letter → score (0.0–1.0)

        Returns OperationResult. On success, updates internal substance state
        and engagement totals. On failure (equipment/trait mismatch), returns
        success=False with the current substance unchanged.
        """
        op = OP_BY_ID.get(op_id)
        if op is None:
            return OperationResult(
                success=False, op_id=op_id, quality=0.0,
                new_substance=self._substance,
                engagement_contribution={}, axis_identified=None,
                catastrophic=False, observation="",
                reason=f"unknown_operation:{op_id!r}",
            )

        # Check equipment
        missing_eq = op.required_equipment - self._equipment
        if missing_eq:
            return OperationResult(
                success=False, op_id=op_id, quality=0.0,
                new_substance=self._substance,
                engagement_contribution={}, axis_identified=None,
                catastrophic=False, observation="",
                reason=f"missing_equipment:{','.join(sorted(missing_eq))}",
            )

        # Check required traits
        if not self._substance.has_all(op.required_traits):
            missing_tr = op.required_traits - self._substance.traits
            return OperationResult(
                success=False, op_id=op_id, quality=0.0,
                new_substance=self._substance,
                engagement_contribution={}, axis_identified=None,
                catastrophic=False, observation="",
                reason=f"missing_traits:{','.join(str(t) for t in sorted(missing_tr))}",
            )

        # Check forbidden traits
        blocking = op.forbidden_traits & self._substance.traits
        if blocking:
            return OperationResult(
                success=False, op_id=op_id, quality=0.0,
                new_substance=self._substance,
                engagement_contribution={}, axis_identified=None,
                catastrophic=False, observation="",
                reason=f"blocked_by_traits:{','.join(str(t) for t in sorted(blocking))}",
            )

        # Skill check
        vitriol_score = vitriol_scores.get(op.vitriol_letter, 0.0)
        quality       = self._skill_check(alchemy_rank, vitriol_score, op.base_difficulty)
        catastrophic  = quality < _BOTCH_THRESHOLD

        # Trait mutation — always occurs (operation was physically performed)
        add_traits    = op.adds_traits
        remove_traits = op.removes_traits
        if catastrophic:
            add_traits = add_traits | frozenset({_T.UNUSABLE})

        new_substance = self._substance.with_traits(
            add=add_traits,
            remove=remove_traits,
            purity_delta=op.purity_delta,
        )

        # Engagement contribution
        contribution = quality * op.engagement_weight
        engagement   = {op.engagement_mode: contribution}

        # Axis identification
        axis = op.field_axis if quality >= _AXIS_ID_THRESHOLD else None

        # Update session state
        self._substance = new_substance
        current = self._mode_scores.get(op.engagement_mode, 0.0)
        self._mode_scores[op.engagement_mode] = min(1.0, current + contribution)
        if axis:
            self._identified_axes.add(axis)
        self._quality_history.append(quality)

        observation = op.failure_text if catastrophic else op.observation

        result = OperationResult(
            success=True,
            op_id=op_id,
            quality=quality,
            new_substance=new_substance,
            engagement_contribution=engagement,
            axis_identified=axis,
            catastrophic=catastrophic,
            observation=observation,
        )
        self._history.append(result)
        return result

    # ── Conclude ──────────────────────────────────────────────────────────────

    def conclude(self) -> tuple[DiagnosticReading, TreatmentApproach]:
        """
        Build the DiagnosticReading and TreatmentApproach from accumulated session work.

        Returns (reading, approach) for passing directly to AlchemySystem.treat().

        approach_mode is determined by average quality across all operations performed:
          >= _PRESENCE_THRESHOLD  → "presence"
          >= _INTUITION_THRESHOLD → "intuition"
          otherwise               → "formula"

        A session with no operations performed yields formula-mode with zero engagement.
        """
        mode_engagement = dict(self._mode_scores)  # already capped at 1.0 during accumulation

        avg_quality = (
            sum(self._quality_history) / len(self._quality_history)
            if self._quality_history else 0.0
        )

        if avg_quality >= _PRESENCE_THRESHOLD:
            approach_mode = "presence"
        elif avg_quality >= _INTUITION_THRESHOLD:
            approach_mode = "intuition"
        else:
            approach_mode = "formula"

        # presence_score reflects both skill quality and purity of the worked substance
        presence_score = avg_quality * 0.65 + self._substance.purity * 0.35

        reading = DiagnosticReading(
            subject_id=self._subject_id,
            identified_axes=frozenset(self._identified_axes),
            mode_engagement=mode_engagement,
            presence_score=presence_score,
        )

        approach = TreatmentApproach(approach_mode=approach_mode)

        return reading, approach

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Current session state as a plain dict (for logging/debugging)."""
        return {
            "subject_id":        self._subject_id,
            "actor_id":          self._actor_id,
            "substance_object":  self._substance.object_id,
            "substance_traits":  self._substance.trait_names(),
            "substance_purity":  round(self._substance.purity, 3),
            "mode_scores":       {k: round(v, 3) for k, v in self._mode_scores.items()},
            "identified_axes":   sorted(self._identified_axes),
            "ops_performed":     len(self._history),
            "avg_quality":       round(
                sum(self._quality_history) / len(self._quality_history), 3
            ) if self._quality_history else 0.0,
        }
