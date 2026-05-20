"""
elements.py — Shygazun element constants and compound reaction table.

The five AppleBlossom forces (bytes 104–107 + Wu 45) are the canonical
force types in both the Kobra physics engine (kernel) and the Python mirror.
The 16 compound states (bytes 108–123) are the products of element×element
reactions — directly readable from the AppleBlossom tongue.

When two forces interact, the result is deterministic from the byte table:
    Shak × Mel  =  110 Alky  (Fire × Water = Alkahest / universal solvent)
    Mel  × Shak =  116 Shem  (Water × Fire = Steam)
    Shak × Shak =  108 Zhuk  (Fire × Fire  = Plasma)
    Shak × Puf  =  109 Kypa  (Fire × Air   = Sulphur)
    ...etc.

This is not metaphor: the byte table encodes the phase chemistry of the
five elements as a lookup table.  The physics engine reads this table when
resolving compound forces in alchemical treatment.
"""

from __future__ import annotations

# ── Element byte addresses ────────────────────────────────────────────────────
# AppleBlossom tongue (98–123).  First 6 bytes are ontic vowels; elements start at 104.

ADDR_SHAK: int = 104   # Fire  — applied impulse, pattern force
ADDR_PUF:  int = 105   # Air   — aerodynamic drag
ADDR_MEL:  int = 106   # Water — linear damping, flow resistance
ADDR_ZOT:  int = 107   # Earth — gravity, weight
ADDR_WU:   int = 45    # Process (Rose) — integration tick
# Kael is the 5th element but lives in compound interactions rather than a
# standalone force address — it emerges from the reaction table as the generative
# excess that no single element×element pair fully contains.

ELEMENT_ADDRS: frozenset[int] = frozenset({ADDR_SHAK, ADDR_PUF, ADDR_MEL, ADDR_ZOT})
ELEMENT_NAMES: dict[int, str] = {
    ADDR_SHAK: "Shak",
    ADDR_PUF:  "Puf",
    ADDR_MEL:  "Mel",
    ADDR_ZOT:  "Zot",
    ADDR_WU:   "Wu",
}

# ── Compound states (AppleBlossom 108–123) ───────────────────────────────────
# Each compound is a phase product of two elemental forces interacting.
# The ordering (A×B vs B×A) produces different compounds — direction matters.

COMPOUNDS: dict[int, tuple[str, str, str]] = {
    # addr : (symbol, name, semantic)
    108: ("Zhuk",  "Plasma",         "Fire×Fire   — pure pattern recursion, ionised state"),
    109: ("Kypa",  "Sulphur",        "Fire×Air    — ignited gas, volatile threshold"),
    110: ("Alky",  "Alkahest",       "Fire×Water  — universal solvent, pattern dissolution"),
    111: ("Kazho", "Magma",          "Fire×Earth  — molten structure, slow transformation"),
    112: ("Puky",  "Smoke",          "Air×Fire    — dispersed combustion, signal in noise"),
    113: ("Pyfu",  "Gas",            "Air×Air     — pure expansion, pressure without form"),
    114: ("Mipa",  "Carbonation",    "Air×Water   — trapped gas, pressurised dissolution"),
    115: ("Zitef", "Mercury",        "Air×Earth   — fluid metal, conductance at threshold"),
    116: ("Shem",  "Steam",          "Water×Fire  — phase transition, released pressure"),
    117: ("Lefu",  "Vapor",          "Water×Air   — ambient dissolution, diffuse presence"),
    118: ("Milo",  "Mixed Fluids",   "Water×Water — immiscible layers, stable suspension"),
    119: ("Myza",  "Erosion",        "Water×Earth — slow dissolution of structure by flow"),
    120: ("Zashu", "Radiation",      "Earth×Fire  — structural pattern emitting energy"),
    121: ("Fozt",  "Dust",           "Earth×Air   — dispersed structure, suspended form"),
    122: ("Mazi",  "Sediment",       "Earth×Water — structure deposited by receding flow"),
    123: ("Zaot",  "Salt",           "Earth×Earth — crystallised double structure, stable pair"),
}

COMPOUND_BY_SYMBOL: dict[str, int] = {v[0]: k for k, v in COMPOUNDS.items()}

# ── Reaction table ────────────────────────────────────────────────────────────
# (element_a_addr, element_b_addr) → compound_addr
# Direction matters: Shak×Mel ≠ Mel×Shak (Alkahest vs Steam)

REACTION_TABLE: dict[tuple[int, int], int] = {
    (ADDR_SHAK, ADDR_SHAK): 108,   # Fire×Fire   = Plasma
    (ADDR_SHAK, ADDR_PUF):  109,   # Fire×Air    = Sulphur
    (ADDR_SHAK, ADDR_MEL):  110,   # Fire×Water  = Alkahest
    (ADDR_SHAK, ADDR_ZOT):  111,   # Fire×Earth  = Magma
    (ADDR_PUF,  ADDR_SHAK): 112,   # Air×Fire    = Smoke
    (ADDR_PUF,  ADDR_PUF):  113,   # Air×Air     = Gas
    (ADDR_PUF,  ADDR_MEL):  114,   # Air×Water   = Carbonation
    (ADDR_PUF,  ADDR_ZOT):  115,   # Air×Earth   = Mercury
    (ADDR_MEL,  ADDR_SHAK): 116,   # Water×Fire  = Steam
    (ADDR_MEL,  ADDR_PUF):  117,   # Water×Air   = Vapor
    (ADDR_MEL,  ADDR_MEL):  118,   # Water×Water = Mixed Fluids
    (ADDR_MEL,  ADDR_ZOT):  119,   # Water×Earth = Erosion
    (ADDR_ZOT,  ADDR_SHAK): 120,   # Earth×Fire  = Radiation
    (ADDR_ZOT,  ADDR_PUF):  121,   # Earth×Air   = Dust
    (ADDR_ZOT,  ADDR_MEL):  122,   # Earth×Water = Sediment
    (ADDR_ZOT,  ADDR_ZOT):  123,   # Earth×Earth = Salt
}


def react(addr_a: int, addr_b: int) -> int | None:
    """Return the compound address from reacting two elements, or None."""
    return REACTION_TABLE.get((addr_a, addr_b))


def compound_name(addr: int) -> str:
    """Human name of a compound by byte address."""
    c = COMPOUNDS.get(addr)
    return c[1] if c else f"unknown@{addr}"


def compound_symbol(addr: int) -> str:
    """Shygazun symbol of a compound by byte address."""
    c = COMPOUNDS.get(addr)
    return c[0] if c else ""


# ── Physics character of each compound ───────────────────────────────────────
# Used by the alchemy physics integration: what does this compound DO physically?
# Each entry: (stability, impulse_scale, dissipation, thermal)
#   stability:     0=chaotic, 1=metastable, 2=stable (affects resonance modifier)
#   impulse_scale: force multiplier on bodies in contact
#   dissipation:   how quickly the compound state decays
#   thermal:       heat generated (feeds into Shak accumulation)

COMPOUND_PHYSICS: dict[int, dict] = {
    108: {"stability": 0, "impulse": 3.0, "dissipation": 0.9, "thermal": 1.5},  # Plasma
    109: {"stability": 0, "impulse": 2.0, "dissipation": 0.7, "thermal": 1.2},  # Sulphur
    110: {"stability": 2, "impulse": 0.2, "dissipation": 0.1, "thermal": 0.1},  # Alkahest
    111: {"stability": 1, "impulse": 0.8, "dissipation": 0.3, "thermal": 0.8},  # Magma
    112: {"stability": 0, "impulse": 1.5, "dissipation": 0.8, "thermal": 0.6},  # Smoke
    113: {"stability": 0, "impulse": 1.2, "dissipation": 0.6, "thermal": 0.0},  # Gas
    114: {"stability": 1, "impulse": 0.6, "dissipation": 0.4, "thermal": 0.0},  # Carbonation
    115: {"stability": 2, "impulse": 0.4, "dissipation": 0.2, "thermal": 0.3},  # Mercury
    116: {"stability": 0, "impulse": 2.5, "dissipation": 0.8, "thermal": 1.0},  # Steam
    117: {"stability": 1, "impulse": 0.3, "dissipation": 0.5, "thermal": 0.1},  # Vapor
    118: {"stability": 2, "impulse": 0.1, "dissipation": 0.1, "thermal": 0.0},  # Mixed Fluids
    119: {"stability": 1, "impulse": 0.5, "dissipation": 0.3, "thermal": 0.0},  # Erosion
    120: {"stability": 0, "impulse": 1.8, "dissipation": 0.7, "thermal": 0.9},  # Radiation
    121: {"stability": 1, "impulse": 0.4, "dissipation": 0.6, "thermal": 0.0},  # Dust
    122: {"stability": 2, "impulse": 0.2, "dissipation": 0.2, "thermal": 0.0},  # Sediment
    123: {"stability": 2, "impulse": 0.0, "dissipation": 0.0, "thermal": 0.0},  # Salt
}
