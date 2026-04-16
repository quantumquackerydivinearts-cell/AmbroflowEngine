"""
Alchemy System
==============
Alchemy is diagnostic presence, not formula application.

The alchemist perceives an information field — a subject's actual nature across
mental, spatial, and temporal axes — and treats it by resonating with what is
actually there.  Skill rank and ingredient checklists are replaced by diagnostic
accuracy and presence quality.

Shygazun ontological foundation
--------------------------------
  Soul    = the function of persistence
  Spirit  = the shape of the information field
  Psyche  = the spatiotemporal affect of the information field locally
  Alchemy = the practice of perceiving and working with these correctly

Information field
-----------------
Each subject's InformationField is described in three authored modes:

  shygazun   — the word from the byte table: the ontological claim         (weight 0.40)
  narrative  — the lore fragment: the story resonance                      (weight 0.20)
  somatic    — the sensory / embodied experience                           (weight 0.15)

The fourth engagement mode is *cosmological*:

  cosmological — consulting the Dragon Tongue register for the organism    (weight 0.25)
                 that embodies this void-state in morphospace.
                 This is a PLAYER ACTION against the kernel register,
                 not an authored FieldProperty field.  The Dragon Tongue
                 organism IS the shygazun word expressed biologically —
                 they are the same ontological claim at different scales.
                 Authoring a dragon_tongue text field would be redundant
                 with (and potentially inconsistent with) the register.

Why the separation was errant
------------------------------
The prior system had `dragon_tongue` as both an authored FieldProperty field
AND a separate engagement mode.  That is a category error: you cannot "engage
with the dragon_tongue description" as a distinct act from "reading the field's
shygazun identity."  The organism IS the void-state embodied; separating them
implies they could diverge, which they cannot.  The Dragon Tongue register is
the single authoritative source.

Engagement modes → sanity dimensions
--------------------------------------
  ontological  → alchemical  (reading the shygazun identity of the field)
  cosmological → cosmic      (consulting the Dragon Tongue register)
  narrative    → narrative   (engaging the lore/story resonance)
  somatic      → terrestrial (the embodied/sensory experience)

Approach modes
--------------
  presence   — full diagnostic engagement, field perceived directly   (1.00×)
  intuition  — partial engagement, pattern recognised without full read (0.75×)
  formula    — mechanistic locality; materials applied without diagnosis (0.40×)

Formula approach always undershoots the field.  Physical materials are a
substrate requirement for material outputs — their absence caps resonance at
0.40 regardless of diagnostic quality.

Provenance
----------
Every item in play carries provenance — where and how it was obtained.  Provenance
modulates material potency during resonance calculation:

  Realm alignment with the field axis gives a bonus (Lapidus→mental,
  Mercurie→spatial, Sulphera→temporal).
  Source type further modifies: foraged > inherited > gifted > crafted > purchased.

Discovered recipes
------------------
Recipes are not given at game start.  They are discovered through successful
field diagnosis (resonance ≥ _RECIPE_DISCOVERY_THRESHOLD).  Once discovered,
a recipe enters the player's RecipeBook and can be executed in formula mode —
but formula approach still applies its lower resonance modifier.  The recipe
is the materialised record of what field knowledge yields, not a bypass of the
diagnostic practice.

Mania contagion: epiphanic results spread the presence-state to nearby entities.
The radius scales with mania_level × resonance quality.

VITRIOL note: Alchemy has Reflectivity (R) affinity.
Hypatia's primary skill — she is the player character, ID 0000_0451.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Literal, Optional

from ..orrery.client import OrreryClient


# ── Type aliases ───────────────────────────────────────────────────────────────

FieldAxis    = Literal["mental", "spatial", "temporal"]
ApproachMode = Literal["presence", "intuition", "formula"]
SourceType   = Literal["foraged", "purchased", "gifted", "inherited", "crafted"]
RealmId      = Literal["lapidus", "mercurie", "sulphera"]


# ── Constants ─────────────────────────────────────────────────────────────────

#: Engagement mode weights must sum to 1.0.
_MODE_WEIGHTS: dict[str, float] = {
    "ontological":  0.40,   # primary — the shygazun identity claim
    "cosmological": 0.25,   # Dragon Tongue register consultation
    "narrative":    0.20,   # lore/story resonance
    "somatic":      0.15,   # embodied/sensory
}

_MODE_TO_SANITY: dict[str, str] = {
    "ontological":  "alchemical",
    "cosmological": "cosmic",
    "narrative":    "narrative",
    "somatic":      "terrestrial",
}

_APPROACH_MOD: dict[str, float] = {
    "presence":  1.00,
    "intuition": 0.75,
    "formula":   0.40,
}

#: Realm whose sourced materials align with each field axis.
_REALM_AXIS_AFFINITY: dict[str, str] = {
    "lapidus":  "mental",    # Overworld — consciousness, presence
    "mercurie": "spatial",   # Faewilds  — orthogonal space, traversal
    "sulphera": "temporal",  # Underworld — time, transformation, persistence
}

#: Source type multipliers on material intensity contribution.
_SOURCE_INTENSITY_MOD: dict[str, float] = {
    "foraged":   1.30,   # direct field connection — highest potency
    "inherited": 1.15,   # temporal depth / lineage charge
    "gifted":    1.10,   # relational field of the giver
    "crafted":   1.00,   # neutral — depends on the resonance of the crafting event
    "purchased": 0.85,   # transactional — lower field connection
}

_REALM_ALIGNMENT_BONUS  = 0.15   # added to source modifier when realm aligns with axis
_PROVENANCE_MOD_MIN     = 0.70
_PROVENANCE_MOD_MAX     = 1.30

_MATERIALS_ABSENT_CAP   = 0.40   # resonance ceiling when required materials missing
_FALSE_AXIS_PENALTY     = 0.15   # per wrongly-identified axis
_EPIPHANY_THRESHOLD     = 0.85   # resonance required for epiphanic result
_EPIPHANIC_CHARGE_REQ   = 0.70   # accumulated charge required for epiphany to fire
_FIELD_TRANSFORM_THRESH = 0.65   # resonance required to transform the field
_RECIPE_DISCOVERY_THRESH= 0.55   # resonance at which a recipe is discovered
_SANITY_BASE_PER_MODE   = 0.05   # max sanity delta per mode at full engagement
_EPIPHANIC_SANITY_MULT  = 2.0    # sanity delta multiplier on epiphanic result
_EPIPHANIC_ALL_BONUS    = 0.02   # flat bonus to all four dims on epiphany


# ── Provenance ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ItemProvenance:
    """
    Source record for a quantity of items in the player's inventory.

    realm_id     — where the item was obtained (lapidus / mercurie / sulphera)
    source_type  — how it was obtained
    quantity     — how many items this provenance record covers
    chunk_id     — optional: specific location chunk within the realm
    npc_id       — for gifted or purchased from a specific NPC
    vendor_id    — for market purchases (vendor or stall identifier)
    epoch_marker — game-time marker (quest slug, event ID, etc.) for provenance chain
    """
    realm_id:     RealmId
    source_type:  SourceType
    quantity:     int            = 1
    chunk_id:     str | None     = None
    npc_id:       str | None     = None
    vendor_id:    str | None     = None
    epoch_marker: str | None     = None


#: Maps item_id → list of provenance records covering quantities of that item.
#: When materials are consumed in alchemy, provenance records are consumed
#: in order (highest quality first).
ProvenanceStore = dict[str, list[ItemProvenance]]


def _provenance_score(prov: ItemProvenance, field_axes: frozenset[str]) -> float:
    """
    Scalar quality score for one provenance record relative to a field's axes.
    Used for selecting the best available provenance and for the intensity modifier.
    """
    base = _SOURCE_INTENSITY_MOD.get(prov.source_type, 1.0)
    aligned = _REALM_AXIS_AFFINITY.get(prov.realm_id, "")
    if aligned in field_axes:
        base += _REALM_ALIGNMENT_BONUS
    return base


def _aggregate_provenance_mod(
    subject_field_axes: frozenset[str],
    required_materials: dict[str, int],
    provenance_store: ProvenanceStore,
) -> float:
    """
    Return a modifier [_PROVENANCE_MOD_MIN, _PROVENANCE_MOD_MAX] representing the
    aggregate quality of the materials about to be consumed.

    For each required material, the best available provenance record (by quality
    score relative to the field's axes) contributes to the aggregate.  Items with
    no provenance record contribute a neutral 1.0.
    """
    mods: list[float] = []
    for item_id, qty_needed in required_materials.items():
        records = provenance_store.get(item_id, [])
        if not records:
            mods.append(1.0)
            continue
        # Find the record with highest coverage of the needed quantity
        scored = sorted(records, key=lambda p: _provenance_score(p, subject_field_axes), reverse=True)
        remaining = qty_needed
        weighted_sum = 0.0
        covered = 0
        for rec in scored:
            take = min(rec.quantity, remaining)
            weighted_sum += _provenance_score(rec, subject_field_axes) * take
            covered += take
            remaining -= take
            if remaining <= 0:
                break
        # Any uncovered quantity (shouldn't happen if materials check passed) → 1.0
        if covered < qty_needed:
            weighted_sum += 1.0 * (qty_needed - covered)
            covered = qty_needed
        mods.append(weighted_sum / covered)

    if not mods:
        return 1.0
    avg = sum(mods) / len(mods)
    return max(_PROVENANCE_MOD_MIN, min(_PROVENANCE_MOD_MAX, avg))


def consume_provenance(
    item_id: str,
    qty: int,
    provenance_store: ProvenanceStore,
) -> None:
    """
    Consume ``qty`` units of ``item_id`` from the provenance store, highest quality first.
    Records with quantity reaching 0 are removed.  Safe to call when item_id not in store.
    """
    records = provenance_store.get(item_id)
    if not records:
        return
    remaining = qty
    # Consume highest-quality first so the better provenance is the one used in the craft
    # (it burns as the active material, leaving weaker provenance for subsequent uses)
    records_sorted = sorted(records, key=lambda p: (
        _SOURCE_INTENSITY_MOD.get(p.source_type, 1.0)
    ), reverse=True)
    updated: list[ItemProvenance] = []
    for rec in records_sorted:
        if remaining <= 0:
            updated.append(rec)
            continue
        take = min(rec.quantity, remaining)
        remaining -= take
        leftover = rec.quantity - take
        if leftover > 0:
            # Replace with reduced quantity (frozen dataclass — reconstruct)
            updated.append(ItemProvenance(
                realm_id=rec.realm_id,
                source_type=rec.source_type,
                quantity=leftover,
                chunk_id=rec.chunk_id,
                npc_id=rec.npc_id,
                vendor_id=rec.vendor_id,
                epoch_marker=rec.epoch_marker,
            ))
    if updated:
        provenance_store[item_id] = updated
    else:
        provenance_store.pop(item_id, None)


# ── Field types ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FieldProperty:
    """
    One property of an information field, described in three authored modes.

    The Dragon Tongue organism is NOT authored here — it is derived from the
    shygazun word via the kernel register.  `cosmological` engagement (mode 4)
    is a player action against the register, not a text field on the property.

    axis:      mental | spatial | temporal — the ontological axis of this property
    shygazun:  word from the Shygazun byte table — the ontological claim
    narrative: lore fragment / story resonance
    somatic:   sensory / embodied description of how this property manifests
    intensity: 0.0–1.0 — how strongly this property manifests in the subject
    """
    axis:      FieldAxis
    shygazun:  str
    narrative: str
    somatic:   str
    intensity: float   # 0.0–1.0


@dataclass(frozen=True)
class InformationField:
    """The actual nature of an alchemical subject."""
    properties: tuple[FieldProperty, ...]

    def axes(self) -> frozenset[str]:
        return frozenset(p.axis for p in self.properties)


# ── Reading and approach ───────────────────────────────────────────────────────

@dataclass
class DiagnosticReading:
    """
    The player's perception of a field, constructed by the game UI layer.

    identified_axes — axes the player correctly named
    false_axes      — axes the player named that are not in the field (penalty)
    mode_engagement — per-mode engagement score 0.0–1.0 from UI tracking

    Modes: ``ontological``, ``cosmological``, ``narrative``, ``somatic``

    ``cosmological`` engagement is scored by the UI layer after the player
    consults the Dragon Tongue register and identifies the organism for the
    field's shygazun word.  The score is 1.0 for correct identification,
    partial for a related organism, 0.0 for wrong genus entirely.
    """
    subject_id:      str
    identified_axes: frozenset[str]
    mode_engagement: dict[str, float]
    presence_score:  float
    false_axes:      frozenset[str] = dc_field(default_factory=frozenset)


@dataclass
class PresenceState:
    """
    The player's current alchemical permeability.

    permeability     — how much of the information field can be perceived (0.0–1.0)
    epiphanic_charge — accumulated toward next epiphany (0.0–1.0)
    mania_level      — contagion radius multiplier on epiphanic results (0.0–1.0)
    """
    permeability:     float = 0.5
    epiphanic_charge: float = 0.0
    mania_level:      float = 0.0


@dataclass(frozen=True)
class TreatmentApproach:
    """What the player brings to the treatment."""
    approach_mode:        ApproachMode
    shygazun_invocations: tuple[str, ...] = ()   # words from byte table


# ── Subject definition ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AlchemicalSubject:
    """
    An alchemical subject — something that can be perceived, diagnosed, and treated.

    required_materials  — physical substrate; empty for purely energetic treatments.
                          When non-empty and unsatisfied, resonance is capped at
                          _MATERIALS_ABSENT_CAP regardless of diagnostic quality.
    base_outputs        — yields at resonance >= 0.50
    enhanced_outputs    — yields at epiphanic quality
    """
    id:                 str
    name:               str
    field:              InformationField
    required_materials: dict[str, int]
    base_outputs:       dict[str, int]
    enhanced_outputs:   dict[str, int]
    lore:               str


# ── Discovered recipes ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AlchemicalRecipe:
    """
    A recipe crystallised from successful field diagnosis.

    Not a crafting shortcut — executing a known recipe in formula mode still
    applies the formula resonance modifier (0.40×).  The recipe is the
    materialised record of what field knowledge yields: you know *what* goes in
    and *what* comes out, but you still bring only yourself to the treatment.

    Discovered when resonance >= _RECIPE_DISCOVERY_THRESH during treat().
    """
    subject_id:           str
    required_materials:   dict[str, int]
    output_items:         dict[str, int]
    discovered_resonance: float   # quality at time of discovery


@dataclass
class RecipeBook:
    """
    Per-player discovered recipes.  Recipes are earned through field diagnosis,
    not given at game start.  Formula-mode execution of a known recipe is valid
    but yields at 0.40× resonance ceiling.
    """
    known: dict[str, AlchemicalRecipe] = dc_field(default_factory=dict)

    def discover(self, recipe: AlchemicalRecipe) -> bool:
        """
        Record a recipe discovery.
        Returns True if this is a new discovery, False if already known.
        """
        if recipe.subject_id not in self.known:
            self.known[recipe.subject_id] = recipe
            return True
        return False

    def is_known(self, subject_id: str) -> bool:
        return subject_id in self.known

    def get(self, subject_id: str) -> AlchemicalRecipe | None:
        return self.known.get(subject_id)

    def all_known(self) -> list[AlchemicalRecipe]:
        return list(self.known.values())


# ── Subject registry ───────────────────────────────────────────────────────────

SUBJECTS: tuple[AlchemicalSubject, ...] = (
    AlchemicalSubject(
        id="tincture_basic",
        name="Basic Tincture",
        field=InformationField(properties=(
            FieldProperty(
                axis="temporal",
                shygazun="ko",
                narrative="The herb does not die in the flask. It redirects. "
                          "What it learned from its whole life becomes what it gives.",
                somatic="Warmth that arrives before the liquid touches the tongue.",
                intensity=0.6,
            ),
        )),
        required_materials={"herb_common": 2, "water_flask": 1},
        base_outputs={"tincture_basic": 1},
        enhanced_outputs={"tincture_basic": 2},
        lore="The simplest reduction. Start here.",
    ),
    AlchemicalSubject(
        id="tincture_restorative",
        name="Restorative Tincture",
        field=InformationField(properties=(
            FieldProperty(
                axis="mental",
                shygazun="gasha",
                narrative="The body already knows how to heal. The tincture does not "
                          "instruct it. It removes the noise that made the body forget.",
                somatic="The moment a held breath releases without deciding to.",
                intensity=0.7,
            ),
        )),
        required_materials={"herb_restorative": 3, "water_flask": 1, "tincture_basic": 1},
        base_outputs={"tincture_restorative": 1},
        enhanced_outputs={"tincture_restorative": 2},
        lore="Hypatia knows this one before the tutor does.",
    ),
    AlchemicalSubject(
        id="desire_crystal_fragment",
        name="Desire Crystal Fragment",
        field=InformationField(properties=(
            FieldProperty(
                axis="spatial",
                shygazun="Wunashako",
                narrative="Desire has no walls. It takes the shape of whatever "
                          "contains it, then exceeds the container.",
                somatic="The ache that has no fixed location in the body.",
                intensity=0.8,
            ),
        )),
        required_materials={"raw_desire_stone": 1, "asmodean_essence": 1},
        base_outputs={"desire_crystal_fragment": 1},
        enhanced_outputs={"desire_crystal": 1},
        lore="Asmodean material. Gold-adjacent in its craft demands.",
    ),
    AlchemicalSubject(
        id="infernal_salve",
        name="Infernal Salve",
        field=InformationField(properties=(
            FieldProperty(
                axis="temporal",
                shygazun="na",
                narrative="Sulphur recognises its origin. The salve does not heal "
                          "by repairing — it heals by returning something to where "
                          "it already knew it belonged.",
                somatic="Heat that moves toward the wound rather than away from it.",
                intensity=0.75,
            ),
        )),
        required_materials={"sulphur_essence": 2, "binding_wax": 1, "tincture_restorative": 1},
        base_outputs={"infernal_salve": 1},
        enhanced_outputs={"infernal_salve": 2},
        lore="Usable in Sulphera's rings. Sulphur recognises its origin.",
    ),
)

SUBJECT_BY_ID: dict[str, AlchemicalSubject] = {s.id: s for s in SUBJECTS}


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class AlchemicalResult:
    success:             bool
    subject_id:          str
    resonance_quality:   float             # 0.0–1.0 final resonance after all modifiers
    epiphanic:           bool
    outputs:             dict[str, int]
    sanity_delta:        dict[str, float]
    contagion_radius:    float             # 0.0 unless epiphanic
    field_transformed:   bool
    mode_insights:       list[str]         # modes where engagement >= 0.6
    reason:              str
    recipe_discovered:   bool  = False     # True if this treatment discovered a new recipe
    provenance_modifier: float = 1.0      # the aggregate provenance modifier applied


@dataclass
class PresenceDelta:
    """Changes to apply to PresenceState after a treatment."""
    permeability_delta:     float
    epiphanic_charge_delta: float
    mania_level_delta:      float


# ── Alchemy system ─────────────────────────────────────────────────────────────

class AlchemySystem:
    """
    Presence-based alchemical treatment resolver.

    The system receives a DiagnosticReading (constructed by the UI layer from
    player engagement) and a TreatmentApproach, calculates resonance against
    the subject's InformationField, and resolves outputs, sanity, and contagion.

    Provenance and recipe discovery are optional: pass ``provenance_store`` and
    ``recipe_book`` to enable them.  Omitting both preserves backward compatibility.
    """

    def __init__(self, orrery: OrreryClient) -> None:
        self._orrery = orrery

    # ── Resonance calculation ─────────────────────────────────────────────────

    def calculate_resonance(
        self,
        subject:          AlchemicalSubject,
        reading:          DiagnosticReading,
        approach:         TreatmentApproach,
        presence:         PresenceState,
        inventory:        dict[str, int],
        provenance_store: Optional[ProvenanceStore] = None,
    ) -> tuple[float, float]:
        """
        Return ``(resonance, provenance_modifier)`` where resonance is 0.0–1.0.

        Axis accuracy × mode engagement × presence permeability × approach mode,
        then multiplied by provenance modifier if a store is provided.
        Materials absence caps resonance at _MATERIALS_ABSENT_CAP.
        """
        field_axes = subject.field.axes()

        # Axis accuracy
        correct   = reading.identified_axes & field_axes
        false_pos = reading.false_axes
        axis_accuracy  = len(correct) / max(len(field_axes), 1)
        axis_accuracy -= len(false_pos) * _FALSE_AXIS_PENALTY
        axis_accuracy  = max(0.0, axis_accuracy)

        # Mode engagement (weighted)
        mode_score = sum(
            reading.mode_engagement.get(m, 0.0) * w
            for m, w in _MODE_WEIGHTS.items()
        )

        # Presence permeability multiplier: [0.5, 1.0]
        permeability_mult = 0.5 + (presence.permeability * 0.5)

        # Raw resonance before approach modifier
        raw = axis_accuracy * mode_score * permeability_mult

        # Approach modifier
        raw *= _APPROACH_MOD.get(approach.approach_mode, 0.40)

        # Materials cap: if required materials absent, hard cap at _MATERIALS_ABSENT_CAP
        if subject.required_materials:
            materials_met = all(
                inventory.get(item_id, 0) >= qty
                for item_id, qty in subject.required_materials.items()
            )
            if not materials_met:
                raw = min(raw, _MATERIALS_ABSENT_CAP)
                return max(0.0, min(1.0, raw)), 1.0

        # Provenance modifier (only when materials are present)
        prov_mod = 1.0
        if provenance_store is not None and subject.required_materials:
            prov_mod = _aggregate_provenance_mod(
                field_axes, subject.required_materials, provenance_store
            )
            raw *= prov_mod

        return max(0.0, min(1.0, raw)), prov_mod

    # ── Sanity delta ──────────────────────────────────────────────────────────

    def _derive_sanity_delta(
        self,
        reading:  DiagnosticReading,
        epiphanic: bool,
    ) -> dict[str, float]:
        delta: dict[str, float] = {}
        for mode, sanity_dim in _MODE_TO_SANITY.items():
            engagement = reading.mode_engagement.get(mode, 0.0)
            if engagement >= 0.4:
                d = engagement * _SANITY_BASE_PER_MODE
                if epiphanic:
                    d *= _EPIPHANIC_SANITY_MULT
                delta[sanity_dim] = delta.get(sanity_dim, 0.0) + d
        if epiphanic:
            for dim in _MODE_TO_SANITY.values():
                delta[dim] = delta.get(dim, 0.0) + _EPIPHANIC_ALL_BONUS
        return delta

    # ── Output resolution ─────────────────────────────────────────────────────

    @staticmethod
    def _resolve_outputs(
        subject:   AlchemicalSubject,
        resonance: float,
        epiphanic: bool,
    ) -> dict[str, int]:
        if epiphanic:
            return dict(subject.enhanced_outputs)
        if resonance >= 0.50:
            return dict(subject.base_outputs)
        if resonance >= 0.25:
            return {k: max(0, v // 2) for k, v in subject.base_outputs.items()}
        return {}

    # ── Presence delta ────────────────────────────────────────────────────────

    @staticmethod
    def derive_presence_delta(
        resonance: float,
        epiphanic: bool,
    ) -> PresenceDelta:
        if epiphanic:
            return PresenceDelta(
                permeability_delta=0.03,
                epiphanic_charge_delta=-1.0,   # resets charge
                mania_level_delta=min(0.1, resonance * 0.12),
            )
        if resonance >= _FIELD_TRANSFORM_THRESH:
            return PresenceDelta(
                permeability_delta=0.01,
                epiphanic_charge_delta=resonance * 0.2,
                mania_level_delta=0.0,
            )
        return PresenceDelta(
            permeability_delta=0.0,
            epiphanic_charge_delta=resonance * 0.05,
            mania_level_delta=0.0,
        )

    # ── Main treatment entry point ────────────────────────────────────────────

    def treat(
        self,
        subject_id:       str,
        actor_id:         str,
        reading:          DiagnosticReading,
        approach:         TreatmentApproach,
        presence:         PresenceState,
        inventory:        dict[str, int],
        provenance_store: Optional[ProvenanceStore] = None,
        recipe_book:      Optional[RecipeBook]      = None,
    ) -> AlchemicalResult:
        """
        Attempt alchemical treatment of a subject.

        Consumes required materials from inventory (and provenance_store if provided)
        when resonance produces output.  Records to Orrery.  Discovers recipe in
        recipe_book if resonance >= _RECIPE_DISCOVERY_THRESH.
        """
        subject = SUBJECT_BY_ID.get(subject_id)
        if subject is None:
            return AlchemicalResult(
                success=False, subject_id=subject_id,
                resonance_quality=0.0, epiphanic=False,
                outputs={}, sanity_delta={},
                contagion_radius=0.0, field_transformed=False,
                mode_insights=[], reason=f"Unknown subject: {subject_id!r}",
            )

        resonance, prov_mod = self.calculate_resonance(
            subject, reading, approach, presence, inventory, provenance_store
        )

        # Epiphanic: high resonance AND sufficient accumulated charge
        epiphanic = (
            resonance >= _EPIPHANY_THRESHOLD
            and presence.epiphanic_charge >= _EPIPHANIC_CHARGE_REQ
        )

        outputs      = self._resolve_outputs(subject, resonance, epiphanic)
        sanity_delta = self._derive_sanity_delta(reading, epiphanic)

        field_transformed = resonance >= _FIELD_TRANSFORM_THRESH
        contagion_radius  = presence.mania_level * resonance * 5.0 if epiphanic else 0.0
        mode_insights     = [m for m, s in reading.mode_engagement.items() if s >= 0.6]

        # Recipe discovery
        recipe_discovered = False
        if recipe_book is not None and resonance >= _RECIPE_DISCOVERY_THRESH:
            recipe = AlchemicalRecipe(
                subject_id=subject_id,
                required_materials=dict(subject.required_materials),
                output_items=dict(subject.base_outputs),
                discovered_resonance=resonance,
            )
            recipe_discovered = recipe_book.discover(recipe)
            if recipe_discovered:
                self._orrery.record("alchemy.recipe_discovered", {
                    "actor_id":   actor_id,
                    "subject_id": subject_id,
                    "resonance":  resonance,
                })

        # Consume materials only if treatment produces output
        if outputs and subject.required_materials:
            materials_met = all(
                inventory.get(item_id, 0) >= qty
                for item_id, qty in subject.required_materials.items()
            )
            if materials_met:
                for item_id, qty in subject.required_materials.items():
                    inventory[item_id] = inventory.get(item_id, 0) - qty
                    if provenance_store is not None:
                        consume_provenance(item_id, qty, provenance_store)

        # Add outputs
        for item_id, qty in outputs.items():
            if qty > 0:
                inventory[item_id] = inventory.get(item_id, 0) + qty

        # Record to Orrery
        self._orrery.record("alchemy.treated", {
            "actor_id":           actor_id,
            "subject_id":         subject_id,
            "resonance":          resonance,
            "epiphanic":          epiphanic,
            "approach_mode":      approach.approach_mode,
            "outputs":            outputs,
            "field_transformed":  field_transformed,
            "provenance_modifier": prov_mod,
        })

        if sanity_delta:
            self._orrery.record_sanity_delta(
                actor_id=actor_id,
                deltas=sanity_delta,
                context={"event": "alchemy.treated", "subject_id": subject_id},
            )

        reason = (
            "epiphanic"    if epiphanic
            else "transformed" if field_transformed
            else "resonant"    if resonance >= 0.50
            else "partial"     if resonance >= 0.25
            else "no_resonance"
        )

        return AlchemicalResult(
            success=resonance >= 0.25,
            subject_id=subject_id,
            resonance_quality=resonance,
            epiphanic=epiphanic,
            outputs=outputs,
            sanity_delta=sanity_delta,
            contagion_radius=contagion_radius,
            field_transformed=field_transformed,
            mode_insights=mode_insights,
            reason=reason,
            recipe_discovered=recipe_discovered,
            provenance_modifier=prov_mod,
        )

    def available_subjects(
        self,
        inventory: dict[str, int],
    ) -> list[AlchemicalSubject]:
        """
        Return subjects whose required materials are present in inventory.
        (Energetic subjects with no required materials are always available.)
        """
        result = []
        for s in SUBJECTS:
            if not s.required_materials:
                result.append(s)
            elif all(inventory.get(k, 0) >= v for k, v in s.required_materials.items()):
                result.append(s)
        return result