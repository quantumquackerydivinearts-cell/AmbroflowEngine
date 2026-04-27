"""
Dream Response Annotator
========================
Translates English player responses into Shygazun symbol signatures.

The measurement layer of the Ko dream sequence. When a player answers a
calibration prompt in English, this module:

  1. Matches the response against a curated semantic anchor map.
  2. Returns the Shygazun byte addresses (decimals) whose cognitive register
     was live in the response.
  3. Derives a resonance float [0.0–1.0] for the calibration session.
  4. Constructs the Shygazun reflection — what Ko read, in the language that
     reads it — for return to the player.

The anchor map is authored, not inferred. Each anchor is a set of English
keywords whose presence in a response indicates that a particular cognitive
register is operative. The anchors do not evaluate whether a response is
"correct" — they read what architecture is already present.

The translation is bidirectional:
  English response → Shygazun symbol signature → resonance score
  Shygazun signature → prose akinen → English reflection

The player sees their words and Ko's reading side by side. The reading
lands in the ego's own language as a recognition it could not preempt.

Architecture notes
------------------
- Anchor keywords are common English words — no technical vocabulary.
- No anchor cluster is "better" than another. Different registers produce
  different signatures, not better or worse calibrations.
- Dissonant entries (-lo) are flagged in the annotation but do not reduce
  resonance — they are information, not penalties.
- The Shygazun reflection requires the shygazun kernel to be importable.
  If unavailable, the annotation still completes — reflection is optional.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .calibration import CalibrationTongue


# ── Semantic anchor ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SemanticAnchor:
    """
    One mapping from English semantic field to Shygazun byte addresses.

    keywords    — English words/phrases whose presence activates this anchor.
                  Matching is case-insensitive, whole-word.
    decimals    — Shygazun byte addresses whose cognitive register the keywords
                  indicate is live in the response.
    home_tongue — which calibration phase this anchor primarily belongs to.
                  "home" anchors contribute more resonance to their phase.
    weight      — relative contribution to resonance when matched (0.0–1.0).
    """
    keywords:    tuple[str, ...]
    decimals:    tuple[int, ...]
    home_tongue: CalibrationTongue
    weight:      float = 0.25


# ── Annotation result ─────────────────────────────────────────────────────────

@dataclass
class ResponseAnnotation:
    """
    Result of annotating one player response.

    decimals          — unique Shygazun byte addresses found active.
    resonance         — float [0.0–1.0], feeds DreamCalibrationSession.respond().
    matched_anchors   — the anchors that fired.
    shygazun_symbols  — symbol names for each matched decimal (populated if
                        kernel is available).
    prose_reflection  — Ko's Shygazun prose rendering of the signature
                        (populated if kernel is available).
    english_gloss     — plain English paraphrase of what the signature carries
                        (always populated).
    """
    decimals:         tuple[int, ...]
    resonance:        float
    matched_anchors:  tuple[SemanticAnchor, ...]
    shygazun_symbols: tuple[str, ...] = field(default_factory=tuple)
    prose_reflection: str = ""
    english_gloss:    str = ""


# ── Anchor map ────────────────────────────────────────────────────────────────
#
# Organised by CalibrationTongue (the phase the anchor primarily belongs to).
# Each anchor covers a semantic field — not a single word but a cluster of
# words that indicate the same underlying cognitive register is active.
#
# Anchor design constraints:
#   - Keywords are common English words, not technical or Shygazun vocabulary.
#   - No cluster is evaluatively privileged over another.
#   - Keywords are mutually distinguishable — minimal overlap between anchors
#     in the same phase so the measurement isn't redundant.
#   - Each prompt's relevant anchors span multiple elements (Fire/Water/Air/
#     Earth/Kael/Shakti) so all response styles can be read.

_ANCHORS: tuple[SemanticAnchor, ...] = (

    # ── LOTUS anchors (bytes 0–23) ────────────────────────────────────────────
    # Elemental threshold strip (bytes 0–7): Ty/Zu/Ly/Mu/Fy/Pu/Shy/Ku
    SemanticAnchor(
        keywords=("earth", "solid", "ground", "weight", "stone", "body", "heavy",
                  "material", "physical", "dense", "substance", "flesh", "bone"),
        decimals=(0, 1),    # Ty / Zu — Earth Initiator / Earth Terminator
        home_tongue=CalibrationTongue.LOTUS, weight=0.30,
    ),
    SemanticAnchor(
        keywords=("water", "feeling", "flow", "emotion", "memory", "tears",
                  "sensation", "soft", "liquid", "wave", "dissolve", "fluid"),
        decimals=(2, 3),    # Ly / Mu — Water Initiator / Water Terminator
        home_tongue=CalibrationTongue.LOTUS, weight=0.30,
    ),
    SemanticAnchor(
        keywords=("air", "thought", "mind", "thinking", "clear", "breath",
                  "knowing", "idea", "aware", "light", "open", "spacious"),
        decimals=(4, 5),    # Fy / Pu — Air Initiator / Air Terminator
        home_tongue=CalibrationTongue.LOTUS, weight=0.30,
    ),
    SemanticAnchor(
        keywords=("fire", "pattern", "recognition", "insight", "spark", "ignite",
                  "understand", "see", "suddenly", "clarity", "bright", "hot"),
        decimals=(6, 7),    # Shy / Ku — Fire Initiator / Fire Terminator
        home_tongue=CalibrationTongue.LOTUS, weight=0.30,
    ),

    # Presence quality strip (bytes 8–15): Ti/Ta/Li/La/Fi/Fa/Shi/Sha
    SemanticAnchor(
        keywords=("here", "present", "near", "close", "now", "immediate",
                  "this", "right here", "in this"),
        decimals=(8, 9),    # Ti / Ta — Here / Active being
        home_tongue=CalibrationTongue.LOTUS, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("new", "strange", "odd", "unexpected", "excited", "tense",
                  "unfamiliar", "never before", "first time"),
        decimals=(10, 11),  # Li / La — New/odd / Tense/excited
        home_tongue=CalibrationTongue.LOTUS, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("known", "familiar", "context", "complex", "old", "recognize",
                  "remember", "related", "clear", "connected"),
        decimals=(12, 13, 14),  # Fi / Fa / Shi — Known / Complex/old / Related/clear
        home_tongue=CalibrationTongue.LOTUS, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("spirit", "intellect", "understanding", "wisdom", "deep knowing",
                  "intelligence", "aware", "consciousness"),
        decimals=(15,),     # Sha — Intellect of spirit
        home_tongue=CalibrationTongue.LOTUS, weight=0.30,
    ),

    # Experiential ground strip (bytes 16–23): Zo/Mo/Po/Ko/Ze/Me/Pe/Ke
    SemanticAnchor(
        keywords=("nothing", "empty", "absence", "void", "silent", "quiet",
                  "blank", "hollow", "still", "gone"),
        decimals=(16, 17),  # Zo / Mo — Absence / Relaxed/silent
        home_tongue=CalibrationTongue.LOTUS, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("simple", "plain", "basic", "clear", "direct", "uncomplicated",
                  "easy", "obvious", "straightforward"),
        decimals=(18,),     # Po — Simple/new
        home_tongue=CalibrationTongue.LOTUS, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("intuition", "experience", "sense", "feel", "gut", "instinct",
                  "know without knowing", "already know", "perception"),
        decimals=(19,),     # Ko — Experience/intuition
        home_tongue=CalibrationTongue.LOTUS, weight=0.35,
    ),
    SemanticAnchor(
        keywords=("far", "distant", "home", "familiar place", "there", "away",
                  "elsewhere", "unknown", "outside", "foreign"),
        decimals=(20, 21, 22),  # Ze / Me / Pe — Far / Familiar/home / Unknown
        home_tongue=CalibrationTongue.LOTUS, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("broken", "ill", "confused", "incoherent", "disoriented",
                  "fractured", "wrong", "scattered", "lost"),
        decimals=(23,),     # Ke — Incoherent/ill
        home_tongue=CalibrationTongue.LOTUS, weight=0.20,
    ),

    # ── ROSE anchors (bytes 24–47) ────────────────────────────────────────────
    # Chromatic strip (bytes 24–30): Ru/Ot/El/Ki/Fu/Ka/AE
    SemanticAnchor(
        keywords=("red", "warm", "intense", "urgent", "hot", "burning",
                  "sharp", "immediate force"),
        decimals=(24,),     # Ru — Vector Lowest Red
        home_tongue=CalibrationTongue.ROSE, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("orange", "vivid", "energetic", "active", "dynamic",
                  "moving", "alive"),
        decimals=(25,),     # Ot — Vector Orange
        home_tongue=CalibrationTongue.ROSE, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("yellow", "bright", "illuminated", "clear light", "visible",
                  "exposed", "lit"),
        decimals=(26,),     # El — Vector Yellow
        home_tongue=CalibrationTongue.ROSE, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("green", "growing", "living", "generative", "alive",
                  "growing thing", "organic"),
        decimals=(27,),     # Ki — Vector Green
        home_tongue=CalibrationTongue.ROSE, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("blue", "cool", "calm", "depth", "deep", "still water",
                  "distance", "far field"),
        decimals=(28,),     # Fu — Vector Blue
        home_tongue=CalibrationTongue.ROSE, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("indigo", "heavy", "pressure", "weight of", "dense quality",
                  "dark", "gravity"),
        decimals=(29,),     # Ka — Vector Indigo
        home_tongue=CalibrationTongue.ROSE, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("violet", "vast", "infinite", "high", "ceiling", "above",
                  "expansive", "open sky", "transcendent"),
        decimals=(30,),     # AE — Vector Highest Violet
        home_tongue=CalibrationTongue.ROSE, weight=0.25,
    ),

    # Number strip (bytes 31–42): Gaoh/Ao/Ye/Ui/Shu/Kiel...
    SemanticAnchor(
        keywords=("zero", "nothing", "none", "null", "origin", "beginning",
                  "before any", "one"),
        decimals=(31, 32),  # Gaoh / Ao — 0/12 / 1
        home_tongue=CalibrationTongue.ROSE, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("two", "pair", "both", "split", "divided", "dual",
                  "opposite", "either", "together"),
        decimals=(33,),     # Ye — Number 2
        home_tongue=CalibrationTongue.ROSE, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("many", "several", "multiple", "complex", "numerous",
                  "layers", "more than one"),
        decimals=(37, 38, 39),  # Yeshu/Lao/Shushy — 6/7/8
        home_tongue=CalibrationTongue.ROSE, weight=0.15,
    ),

    # Polarity strip (bytes 43–47): Ha/Ga/Wu/Na/Ung
    SemanticAnchor(
        keywords=("yes", "positive", "toward", "with", "affirm", "accept",
                  "open", "receiving", "add"),
        decimals=(43,),     # Ha — Absolute Positive
        home_tongue=CalibrationTongue.ROSE, weight=0.30,
    ),
    SemanticAnchor(
        keywords=("no", "against", "away from", "resist", "refuse", "close",
                  "block", "negative", "subtract"),
        decimals=(44,),     # Ga — Absolute Negative
        home_tongue=CalibrationTongue.ROSE, weight=0.30,
    ),
    SemanticAnchor(
        keywords=("process", "way", "through", "moving through", "traversal",
                  "path", "method", "how", "the way of"),
        decimals=(45,),     # Wu — Process/Way
        home_tongue=CalibrationTongue.ROSE, weight=0.30,
    ),
    SemanticAnchor(
        keywords=("balance", "neutral", "integrate", "both", "neither",
                  "between", "middle", "equal", "together"),
        decimals=(46,),     # Na — Neutral/Integration
        home_tongue=CalibrationTongue.ROSE, weight=0.30,
    ),
    SemanticAnchor(
        keywords=("point", "specific", "exact", "particular", "this one",
                  "singular", "precise", "that", "distinct"),
        decimals=(47,),     # Ung — Piece/Point
        home_tongue=CalibrationTongue.ROSE, weight=0.25,
    ),

    # ── SAKURA anchors (bytes 48–71) ──────────────────────────────────────────
    # Spatial direction strip (bytes 48–53): Jy/Ji/Ja/Jo/Je/Ju
    SemanticAnchor(
        keywords=("up", "above", "high", "top", "overhead", "above me",
                  "sky", "ceiling", "upward"),
        decimals=(48,),     # Jy — Top
        home_tongue=CalibrationTongue.SAKURA, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("right", "side", "starboard", "beside", "lateral",
                  "to the right", "alongside"),
        decimals=(49,),     # Ji — Starboard
        home_tongue=CalibrationTongue.SAKURA, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("forward", "ahead", "front", "before me", "toward",
                  "in front", "facing"),
        decimals=(50,),     # Ja — Front
        home_tongue=CalibrationTongue.SAKURA, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("back", "behind", "past", "before", "previous", "what was",
                  "already happened", "behind me"),
        decimals=(51,),     # Jo — Back
        home_tongue=CalibrationTongue.SAKURA, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("left", "port", "other side", "to the left"),
        decimals=(52,),     # Je — Port
        home_tongue=CalibrationTongue.SAKURA, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("down", "below", "under", "beneath", "underground",
                  "downward", "depth", "low"),
        decimals=(53,),     # Ju — Bottom
        home_tongue=CalibrationTongue.SAKURA, weight=0.25,
    ),

    # Movement state strip (bytes 54–59): Dy/Di/Da/Do/De/Du
    SemanticAnchor(
        keywords=("coming from", "because of", "therefore", "heretofore",
                  "from this", "arising from"),
        decimals=(54,),     # Dy — Hence/Heretofore
        home_tongue=CalibrationTongue.SAKURA, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("moving", "traveling", "going", "leaving", "away",
                  "departing", "distance", "walking", "moving away"),
        decimals=(55,),     # Di — Traveling/Distancing
        home_tongue=CalibrationTongue.SAKURA, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("meeting", "joining", "together", "arriving", "reaching",
                  "connecting", "contact", "coming together", "approaching"),
        decimals=(56,),     # Da — Meeting/Conjoined
        home_tongue=CalibrationTongue.SAKURA, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("parting", "separating", "apart", "splitting", "divided",
                  "separate", "diverging", "diverge"),
        decimals=(57,),     # Do — Parting/Divorced
        home_tongue=CalibrationTongue.SAKURA, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("staying", "remaining", "settling", "home", "staying here",
                  "not moving", "resting", "dwelling"),
        decimals=(58,),     # De — Domesticating/Staying
        home_tongue=CalibrationTongue.SAKURA, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("status", "state", "where is", "what is happening",
                  "what is this", "what are you", "whither"),
        decimals=(59,),     # Du — Whither/Status of
        home_tongue=CalibrationTongue.SAKURA, weight=0.20,
    ),

    # Ownership/temporal strip (bytes 60–65): By/Bi/Ba/Bo/Be/Bu
    SemanticAnchor(
        keywords=("eventual", "eventually", "will happen", "future",
                  "coming", "yet to", "anticipate", "upcoming"),
        decimals=(60,),     # By — When-hence/Eventual
        home_tongue=CalibrationTongue.SAKURA, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("owned", "mine", "belonging", "have", "possess", "crown",
                  "authority", "my own"),
        decimals=(61,),     # Bi — Crowned/Owning
        home_tongue=CalibrationTongue.SAKURA, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("plain", "explicit", "obvious", "stated", "clear",
                  "visible", "apparent", "open", "exposed"),
        decimals=(62,),     # Ba — Plain/Explicit
        home_tongue=CalibrationTongue.SAKURA, weight=0.20,
    ),
    SemanticAnchor(
        keywords=("hidden", "occult", "concealed", "beneath", "unseen",
                  "secret", "beneath the surface", "invisible", "latent"),
        decimals=(63,),     # Bo — Hidden/Occulted
        home_tongue=CalibrationTongue.SAKURA, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("common", "shared", "outside", "wild", "public", "outer",
                  "general", "everywhere", "ordinary"),
        decimals=(64,),     # Be — Common/Outer/Wild
        home_tongue=CalibrationTongue.SAKURA, weight=0.15,
    ),
    SemanticAnchor(
        keywords=("since", "relation", "because", "connected to", "relative",
                  "in relation", "since then", "regarding"),
        decimals=(65,),     # Bu — Since/Relational
        home_tongue=CalibrationTongue.SAKURA, weight=0.20,
    ),

    # Ontological boundary strip (bytes 66–71): Va/Vo/Ve/Vu/Vi/Vy
    SemanticAnchor(
        keywords=("order", "structure", "life", "stability", "organize",
                  "hold", "keep", "maintain", "pattern", "form"),
        decimals=(66,),     # Va — Order/Structure/Life
        home_tongue=CalibrationTongue.SAKURA, weight=0.30,
    ),
    SemanticAnchor(
        keywords=("chaos", "breaking", "change", "mutation", "disorder",
                  "boundary breaking", "unexpected", "shift", "transform",
                  "unstable", "opening", "unraveling"),
        decimals=(67,),     # Vo — Chaos/Boundary-breakage/Mutation
        home_tongue=CalibrationTongue.SAKURA, weight=0.35,
    ),
    SemanticAnchor(
        keywords=("pieces", "parts", "where", "fragmented", "scattered",
                  "not quite", "partial", "incomplete", "somewhere"),
        decimals=(68,),     # Ve — Pieces/Not-wherever/Where
        home_tongue=CalibrationTongue.SAKURA, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("death", "now", "this moment", "end", "never",
                  "the moment of", "right now", "the instant"),
        decimals=(69,),     # Vu — Death-moment/Never/Now
        home_tongue=CalibrationTongue.SAKURA, weight=0.30,
    ),
    SemanticAnchor(
        keywords=("body", "wherever", "what", "physical presence",
                  "somewhere", "in the body", "what is this", "where am i"),
        decimals=(70,),     # Vi — Body/Wherever/What
        home_tongue=CalibrationTongue.SAKURA, weight=0.25,
    ),
    SemanticAnchor(
        keywords=("lifespan", "whenever", "how", "duration", "over time",
                  "through time", "how long", "lifetime", "across"),
        decimals=(71,),     # Vy — Lifespan/Whenever/How
        home_tongue=CalibrationTongue.SAKURA, weight=0.20,
    ),
)


# ── Annotation engine ─────────────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Lower-case, strip punctuation, return word-set including bigrams."""
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    words = clean.split()
    unigrams = set(words)
    bigrams = {f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)}
    return unigrams | bigrams


def annotate_response(
    text: str,
    phase: CalibrationTongue,
    *,
    include_cross_tongue: bool = True,
) -> ResponseAnnotation:
    """
    Annotate a player's English response for a given calibration phase.

    text                 — the player's free-text response.
    phase                — the current calibration phase (determines home anchors).
    include_cross_tongue — whether to also match anchors from other tongues
                           (cross-tongue matches contribute less resonance but
                           are included in the decimal signature).

    Returns a ResponseAnnotation with matched decimals, resonance, and
    a plain English gloss of what the signature carries.
    The Shygazun prose reflection is populated separately by the pipeline
    if the kernel is available (see DreamResponsePipeline).
    """
    tokens = _tokenize(text)
    if not tokens:
        return ResponseAnnotation(
            decimals=(), resonance=0.1,
            matched_anchors=(), english_gloss="(no response detected)",
        )

    matched: list[SemanticAnchor] = []
    for anchor in _ANCHORS:
        if not include_cross_tongue and anchor.home_tongue != phase:
            continue
        for kw in anchor.keywords:
            if kw in tokens:
                matched.append(anchor)
                break

    # Resonance: home anchors weighted at full value, cross-tongue at half
    resonance_sum = 0.0
    for anchor in matched:
        if anchor.home_tongue == phase:
            resonance_sum += anchor.weight
        else:
            resonance_sum += anchor.weight * 0.5
    resonance = round(min(1.0, max(0.1, resonance_sum)), 4)

    # Collect unique decimals preserving home-tongue ordering
    home_decimals: list[int] = []
    cross_decimals: list[int] = []
    seen: set[int] = set()
    for anchor in matched:
        target = home_decimals if anchor.home_tongue == phase else cross_decimals
        for d in anchor.decimals:
            if d not in seen:
                seen.add(d)
                target.append(d)
    all_decimals = tuple(home_decimals + cross_decimals)

    gloss = _english_gloss(matched, phase)

    return ResponseAnnotation(
        decimals=all_decimals,
        resonance=resonance,
        matched_anchors=tuple(matched),
        english_gloss=gloss,
    )


def _english_gloss(matched: list[SemanticAnchor], phase: CalibrationTongue) -> str:
    """Construct a plain English gloss of what the signature carries."""
    if not matched:
        return "The response did not activate a named register."

    home = [a for a in matched if a.home_tongue == phase]
    cross = [a for a in matched if a.home_tongue != phase]

    home_decimals = {d for a in home for d in a.decimals}
    cross_decimals = {d for a in cross for d in a.decimals}

    parts: list[str] = []

    # Describe the home-tongue register
    home_gloss = _decimal_set_gloss(home_decimals, phase)
    if home_gloss:
        parts.append(home_gloss)
    if cross_decimals:
        cross_names = _decimal_names(cross_decimals)
        if cross_names:
            parts.append(f"alongside registers from {_phase_name(phase, cross)}.")

    if not parts:
        return "A response was recorded."
    return " ".join(parts)


def _phase_name(home: CalibrationTongue, cross_anchors: list[SemanticAnchor]) -> str:
    tongues = {a.home_tongue.value for a in cross_anchors}
    return ", ".join(sorted(tongues))


def _decimal_names(decimals: set[int]) -> list[str]:
    """Return symbol names for a set of decimals without requiring kernel import."""
    # Inline minimal lookup for gloss purposes only
    _QUICK: dict[int, str] = {
        0: "Earth-beginning", 1: "Earth-closure", 2: "Water-beginning",
        3: "Water-memory", 4: "Air-thought", 5: "Air-stasis",
        6: "Fire-pattern", 7: "Fire-end", 8: "Here", 9: "Active-being",
        10: "New", 11: "Tense", 12: "Known", 13: "Complex",
        14: "Related", 15: "Sha-spirit", 16: "Absence", 17: "Relaxed",
        18: "Simple", 19: "Ko-intuition", 20: "Far", 21: "Familiar",
        22: "Unknown", 23: "Incoherent",
        24: "Red", 25: "Orange", 26: "Yellow", 27: "Green",
        28: "Blue", 29: "Indigo", 30: "Violet",
        43: "Ha-positive", 44: "Ga-negative", 45: "Wu-process",
        46: "Na-integration", 47: "Ung-point",
        48: "Top", 49: "Starboard", 50: "Front", 51: "Back",
        52: "Port", 53: "Bottom", 54: "Hence", 55: "Traveling",
        56: "Meeting", 57: "Parting", 58: "Staying", 59: "Whither",
        60: "Eventual", 61: "Owning", 62: "Explicit", 63: "Hidden",
        64: "Common", 65: "Relational",
        66: "Order", 67: "Chaos", 68: "Pieces", 69: "Now",
        70: "Body", 71: "Lifespan",
    }
    return [_QUICK[d] for d in sorted(decimals) if d in _QUICK]


def _decimal_set_gloss(decimals: set[int], phase: CalibrationTongue) -> str:
    names = _decimal_names(decimals)
    if not names:
        return ""
    tongue_name = {
        CalibrationTongue.LOTUS:  "ground",
        CalibrationTongue.ROSE:   "relational",
        CalibrationTongue.SAKURA: "orientation",
    }[phase]
    return f"The response carries {tongue_name} register: {', '.join(names)}."


# ── Dream response pipeline ───────────────────────────────────────────────────

class DreamResponsePipeline:
    """
    Combines annotation, calibration, and optional Shygazun reflection into
    a single call for the game engine.

    Usage
    -----
        pipeline = DreamResponsePipeline("7_KLGS", active_perks=frozenset())
        while not pipeline.complete:
            prompts = pipeline.current_prompts
            # ... present prompts to player ...
            result = pipeline.submit("I feel something pulling forward.")
            # result.annotation.english_gloss  — plain English reflection
            # result.annotation.prose_reflection — Shygazun prose (if kernel available)
            # result.annotation.decimals — for record_tongue_pressure()
        calibration = pipeline.finish()
        vitriol = pipeline.vitriol_profile(calibration)
    """

    @dataclass
    class StepResult:
        phase_complete: bool
        annotation:     ResponseAnnotation
        current_prompt: str

    def __init__(self, game_id: str, active_perks: frozenset[str] = frozenset()) -> None:
        from .calibration import DreamCalibrationSession
        self._session    = DreamCalibrationSession(game_id, active_perks)
        self._game_id    = game_id
        self._prompt_idx = 0
        self._kernel_available: Optional[bool] = None

    @property
    def complete(self) -> bool:
        return self._session.is_complete()

    @property
    def current_prompts(self) -> list[str]:
        return self._session.current_prompts

    @property
    def current_phase(self):
        return self._session.current_phase

    def submit(self, english_response: str) -> "DreamResponsePipeline.StepResult":
        """
        Submit one English response.

        Annotates, feeds resonance to the calibration session, optionally
        enriches with Shygazun prose reflection.  Returns a StepResult.
        """
        phase = self._session.current_phase
        if phase is None:
            raise RuntimeError("Pipeline is already complete.")

        prompts = self._session.current_prompts
        current_prompt = prompts[self._prompt_idx % len(prompts)]

        annotation = annotate_response(english_response, phase)
        annotation = self._enrich_with_shygazun(annotation)

        phase_complete = self._session.respond(annotation.resonance)
        if phase_complete:
            self._prompt_idx = 0
        else:
            self._prompt_idx += 1

        return DreamResponsePipeline.StepResult(
            phase_complete=phase_complete,
            annotation=annotation,
            current_prompt=current_prompt,
        )

    def finish(self):
        """Complete the session and return the DreamCalibration."""
        return self._session.complete()

    def vitriol_profile(self, calibration, coil_position: float = 6.0):
        """Assign VITRIOL from the completed calibration."""
        from .vitriol import assign_vitriol
        return assign_vitriol(calibration, coil_position)

    def _enrich_with_shygazun(self, annotation: ResponseAnnotation) -> ResponseAnnotation:
        """
        Attempt to populate prose_reflection and shygazun_symbols via the kernel.
        Returns annotation unchanged if kernel is unavailable.
        """
        if not annotation.decimals:
            return annotation

        if self._kernel_available is False:
            return annotation

        try:
            from shygazun.kernel.policy.recombiner import recombine
            from shygazun.kernel.constants.byte_table import byte_entry

            assembly = recombine(annotation.decimals, mode="prose")
            symbols = tuple(e["symbol"] for e in assembly.entries)
            prose   = assembly.line

            self._kernel_available = True
            return ResponseAnnotation(
                decimals=annotation.decimals,
                resonance=annotation.resonance,
                matched_anchors=annotation.matched_anchors,
                shygazun_symbols=symbols,
                prose_reflection=prose,
                english_gloss=annotation.english_gloss,
            )
        except Exception:
            self._kernel_available = False
            return annotation