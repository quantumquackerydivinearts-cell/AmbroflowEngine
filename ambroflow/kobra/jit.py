"""
ambroflow.kobra.jit — Kobra data model and compiler
====================================================
Defines the 12-layer nested stack, grammar types, and JIT compiler
that compiles Shygazun (or English) bracket compounds to layer entries.

The canonical execution spec lives in kobra_jit.ko.
This module is the Python shim that mirrors that spec.
Replace with a Kobra-native bootstrap once runtime is self-hosting.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


# ---------------------------------------------------------------------------
# Opcode table — loaded once from the authoritative byte table
# ---------------------------------------------------------------------------

_OPCODE: dict[str, tuple[int, str, str]] = {}  # symbol -> (decimal, tongue, meaning)

def _load_opcodes() -> None:
    if _OPCODE:
        return
    import sys
    for root in (r'C:\DjinnOS\DjinnOS_Shyagzun', r'C:\DjinnOS'):
        if root not in sys.path:
            sys.path.insert(0, root)
    from shygazun.kernel.constants.byte_table import _BYTE_TABLE_CSV
    for line in _BYTE_TABLE_CSV.strip().split('\n')[1:]:
        parts = line.split(',', 4)
        if len(parts) < 4:
            continue
        dec, tongue, symbol = int(parts[0]), parts[2], parts[3]
        meaning = parts[4].strip() if len(parts) > 4 else ''
        _OPCODE[symbol] = (dec, tongue, meaning)


# ---------------------------------------------------------------------------
# Layer — the 12-layer nested DB
# ---------------------------------------------------------------------------

class Layer(IntEnum):
    BIT       = 1   # Lotus — primitive type kernel
    DECIMAL   = 2   # Rose numerics (Gaoh→Aonkiel)
    BOOLEAN   = 3   # Rose Ha/Ga, Sakura Va/Vo
    COORDINATE = 4  # Sakura directionals + Lotus Ti/Ze
    OBJECT    = 5   # Daisy Lo/To/Fn/St
    ENTITY    = 6   # Daisy Ne/Ro/Gl
    COLOR     = 7   # Rose Ru→AE vectors
    MOVEMENT  = 8   # Grapevine Mio + Lotus Ty/Zu
    PATTERN   = 9   # Grapevine Dyf/Dyo/Dyth
    NAMES     = 10  # Grapevine Myk/Seth/Mavo (language mode buffer)
    SCENE     = 11  # Grapevine Samos/Sava/Sael/Myr/Myrun (Orrery)
    FUNCTION  = 12  # Rose Wu + Grapevine Mek/Mekha/Kysael


# Symbol sets that anchor each layer (from kobra_opcode_map)
_LAYER_ANCHORS: dict[Layer, frozenset[int]] = {
    Layer.FUNCTION:   frozenset([45, 166, 168, 183]),        # Wu, Mek, Mekha, Kysael
    Layer.SCENE:      frozenset([160, 161, 162, 164, 169]),  # Samos,Sava,Sael,Myr,Myrun
    Layer.NAMES:      frozenset([163, 159, 167]),            # Myk, Seth, Mavo
    Layer.PATTERN:    frozenset([170, 171, 172]),            # Dyf, Dyo, Dyth
    Layer.MOVEMENT:   frozenset([165, 0, 4]),                # Mio, Ty, Zu
    Layer.COLOR:      frozenset(range(24, 31)),              # Ru→AE (24-30)
    Layer.ENTITY:     frozenset([83, 84, 87]),               # Ro, Gl, Ne
    Layer.OBJECT:     frozenset([72, 85, 95, 96]),           # Lo, To, St, Fn
    Layer.COORDINATE: frozenset(range(48, 60)),              # Jy-Du (48-59)
    Layer.BOOLEAN:    frozenset([43, 44, 66, 67]),           # Ha, Ga, Va, Vo
    Layer.DECIMAL:    frozenset(range(31, 43)),              # Gaoh→Aonkiel (31-42)
    Layer.BIT:        frozenset(range(0, 24)),               # Lotus (0-23)
}

# YeShu byte range — routed via Ne (byte 87) = Entity layer upward
_YESHU_START = 2048

def _route_layer(decimals: list[int]) -> Layer:
    """Find the highest-priority layer for a list of byte addresses."""
    for layer in (
        Layer.FUNCTION, Layer.SCENE, Layer.NAMES, Layer.PATTERN,
        Layer.MOVEMENT, Layer.COLOR, Layer.ENTITY, Layer.OBJECT,
        Layer.COORDINATE, Layer.BOOLEAN, Layer.DECIMAL, Layer.BIT,
    ):
        anchors = _LAYER_ANCHORS[layer]
        if any(d in anchors for d in decimals):
            return layer
    # YeShu tokens route to Entity (Ne gateway) by default
    if any(d >= _YESHU_START for d in decimals):
        return Layer.ENTITY
    return Layer.BIT


# ---------------------------------------------------------------------------
# Grammar types
# ---------------------------------------------------------------------------

class GrammarRole(IntEnum):
    NOUN         = 0   # bare akinen
    ACTIVE_VERB  = 1   # Wu + akinen
    PASSIVE_VERB = 2   # akinen + wuga (Wu Ga)
    GENITIVE     = 3   # akinen + Ung (epenthetic u when needed)
    ACCUSATIVE   = 4   # Ha + akinen + Wu
    ABLATIVE     = 5   # Ga + akinen + Wu
    DATIVE       = 6   # passive_verb + akinen
    MODIFIER     = 7   # adjective/adverb by placement


class Mood(IntEnum):
    DECLARATIVE = 0   # descending tongue order (high T# → low T#)
    INQUIRY     = 1   # ascending tongue order (low T# → high T#)
    NEUTRAL     = 2   # mixed / single-token


# Tongue index map — tongue name → T-number (1-78)
_TONGUE_INDEX: dict[str, int] = {}

def _load_tongue_index() -> None:
    if _TONGUE_INDEX:
        return
    ordered = [
        "Lotus", "Rose", "Sakura", "Daisy", "AppleBlossom",
        "Aster", "Grapevine", "Cannabis",
        "Dragon", "Virus", "Bacteria", "Excavata", "Archaeplastida",
        "Myxozoa", "Archaea", "Protist", "Immune", "Neural",
        "Serpent", "Beast", "Cherub", "Chimera", "Faerie", "Djinn",
        "Fold", "Topology", "Phase", "Gradient", "Curvature",
        "Prion", "Blood", "Moon", "Koi", "Rope",
        "Hook", "Fang", "Circle", "Ledger", "Bond",
        "Venus", "Gaia", "Janus", "Thanatos", "Saturn",
        "Corpse", "Furnace", "Square", "Flesh", "Eye", "Blade",
        "Ouranos", "Pontus", "Ourea", "Oceanus", "Coeus",
        "Crius", "Hyperion", "Iapetus", "Theia", "Rhea",
        "Themis", "Mnemosyne", "Phoebe", "Tethys", "Cronus",
        "Brontes", "Steropes", "Arges", "Cottus", "Briareos",
        "Gyges", "Nereus", "Thaumas", "Phorcys", "Ceto",
        "Eurybia", "Typhon", "Antaeus",
    ]
    for i, t in enumerate(ordered):
        _TONGUE_INDEX[t] = i + 1


def _detect_mood(tongue_indices: list[int]) -> Mood:
    if len(tongue_indices) < 2:
        return Mood.NEUTRAL
    if tongue_indices == sorted(tongue_indices, reverse=True):
        return Mood.DECLARATIVE
    if tongue_indices == sorted(tongue_indices):
        return Mood.INQUIRY
    return Mood.NEUTRAL


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ByteEntry:
    decimal: int
    hex_addr: str
    binary: str
    symbol: str
    tongue: str
    meaning: str

    @classmethod
    def from_symbol(cls, symbol: str) -> "ByteEntry":
        _load_opcodes()
        if symbol not in _OPCODE:
            raise KeyError(f"Unknown akinen: {symbol!r}")
        dec, tongue, meaning = _OPCODE[symbol]
        return cls(
            decimal=dec,
            hex_addr=f"0x{dec:04X}",
            binary=format(dec, 'b'),
            symbol=symbol,
            tongue=tongue,
            meaning=meaning,
        )


@dataclass
class CompiledToken:
    entry: ByteEntry
    role: GrammarRole = GrammarRole.NOUN


@dataclass
class CompiledCompound:
    tokens: list[CompiledToken]
    mood: Mood
    target_layer: Layer
    source: str = ""

    @property
    def decimals(self) -> list[int]:
        return [t.entry.decimal for t in self.tokens]

    @property
    def symbols(self) -> list[str]:
        return [t.entry.symbol for t in self.tokens]


# ---------------------------------------------------------------------------
# 12-layer stack (the DB target)
# ---------------------------------------------------------------------------

@dataclass
class KobraStack:
    """The 12-layer nested DB. Each layer holds a list of compiled compounds."""
    layers: dict[Layer, list[CompiledCompound]] = field(
        default_factory=lambda: {l: [] for l in Layer}
    )

    def write(self, compound: CompiledCompound) -> None:
        self.layers[compound.target_layer].append(compound)

    def read(self, layer: Layer) -> list[CompiledCompound]:
        return self.layers[layer]

    def flush(self, layer: Layer) -> None:
        self.layers[layer].clear()

    def snapshot(self) -> dict[int, list[str]]:
        return {
            int(l): [" ".join(c.symbols) for c in compounds]
            for l, compounds in self.layers.items()
            if compounds
        }


# ---------------------------------------------------------------------------
# JIT compiler
# ---------------------------------------------------------------------------

# Grammar marker byte addresses (Rose tongue)
_HA  = 43   # Accusative prefix
_GA  = 44   # Ablative prefix
_WU  = 45   # Active verb / Function marker
_NA  = 46   # Neutral
_UNG = 47   # Genitive suffix

_WUGA = (_WU, _GA)  # passive verb sequence


def _classify_role(decimals: list[int]) -> GrammarRole:
    if not decimals:
        return GrammarRole.NOUN
    if decimals[0] == _WU:
        return GrammarRole.ACTIVE_VERB
    if decimals[0] == _HA and decimals[-1] == _WU:
        return GrammarRole.ACCUSATIVE
    if decimals[0] == _GA and decimals[-1] == _WU:
        return GrammarRole.ABLATIVE
    if decimals[-1] == _UNG:
        return GrammarRole.GENITIVE
    if len(decimals) >= 2 and (decimals[-2], decimals[-1]) == _WUGA:
        return GrammarRole.PASSIVE_VERB
    return GrammarRole.NOUN


class KobraJIT:
    """Compiles bracket compounds (token sequences) to CompiledCompounds."""

    def __init__(self) -> None:
        _load_opcodes()
        _load_tongue_index()
        self.stack = KobraStack()

    def compile_compound(self, tokens: list[str], source: str = "") -> CompiledCompound:
        entries = [ByteEntry.from_symbol(t) for t in tokens]
        role = _classify_role([e.decimal for e in entries])
        tongue_indices = [
            _TONGUE_INDEX.get(e.tongue, 0) for e in entries
            if e.tongue in _TONGUE_INDEX
        ]
        mood = _detect_mood(tongue_indices)
        layer = _route_layer([e.decimal for e in entries])
        compiled_tokens = [CompiledToken(entry=e, role=role) for e in entries]
        return CompiledCompound(
            tokens=compiled_tokens,
            mood=mood,
            target_layer=layer,
            source=source,
        )

    def compile_and_write(self, tokens: list[str], source: str = "") -> CompiledCompound:
        compound = self.compile_compound(tokens, source)
        self.stack.write(compound)
        return compound
