"""
cube_sphere.py — Bounded spherical world geometry for the Ambroflow engine.

Each bounded world (Aeralune, Mercurie, Earth-periods, Sulphera rings, etc.)
is a cube sphere: 6 square faces projected onto sphere geometry.  One face =
one flat TPN atlas.  1 tile = 1 block.  1 pixel = 1 atlas face.

Face definitions come from the Sakura j-series (Tongue 3, bytes 48–53).
The first 6 Sakura candidates encode spatial orientation — they ARE the
directions, not labels for them.  Their byte addresses in the full byte table
streaming coordinate (nibble-split 16×16 grid) become the Julia parameters
c₁–c₆ for terrain generation on each face.

Byte-to-Julia mapping (tongue activation streaming coordinate):
    high nibble → Re axis, normalized [0,15] → [-2.0, 2.0]
    low nibble  → Im axis, normalized [0,15] → [-2.0, 2.0]

For the j-series (bytes 48–53, high nibble = 3 for all):
    Re = 3/15 × 4 - 2 = -1.2  (fixed — same Tongue 3 real coordinate)
    Im varies with low nibble 0–5 → [-2.0, -1.733, -1.467, -1.2, -0.933, -0.667]

All 6 face parameters share the real coordinate of Sakura in the streaming
grid.  The world's 6 faces are a vertical slice through the Julia parameter
space at the Tongue 3 real axis position.

World-specific character (terrain type, sanity pressure, entity population,
eigenstate baseline) is layered on top via the world's physics config.
The face geometry is universal structural substrate; the world's soul varies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Streaming coordinate mapping ──────────────────────────────────────────────

def byte_to_julia(b: int) -> complex:
    """
    Map a byte table address to a Julia parameter using nibble-split coordinate
    geometry.  This is the tongue activation streaming coordinate: byte b
    occupies position (b >> 4, b & 0xF) in the 16×16 streaming grid.

    High nibble → real axis [-2, 2], low nibble → imaginary axis [-2, 2].
    """
    hi = (b >> 4) & 0xF
    lo = b & 0xF
    re = hi / 15.0 * 4.0 - 2.0
    im = lo / 15.0 * 4.0 - 2.0
    return complex(re, im)


# ── Sakura j-series face byte addresses ───────────────────────────────────────

FACE_BYTES = {
    "top":       48,  # Jy — Top
    "starboard": 49,  # Ji — Starboard (right when facing front)
    "front":     50,  # Ja — Front
    "back":      51,  # Jo — Back
    "port":      52,  # Je — Port (left when facing front)
    "bottom":    53,  # Ju — Bottom
}

# Precomputed Julia parameters for each face
FACE_JULIA: dict[str, complex] = {
    face: byte_to_julia(b) for face, b in FACE_BYTES.items()
}
# Result:
#   top:       -1.2 - 2.000j
#   starboard: -1.2 - 1.733j
#   front:     -1.2 - 1.467j
#   back:      -1.2 - 1.200j
#   port:      -1.2 - 0.933j
#   bottom:    -1.2 - 0.667j
#
# All faces share Re = -1.2 (Tongue 3 Sakura real coordinate in streaming grid).
# Im varies along the vertical from most disconnected (top) to most connected (bottom).
# This gives each face a distinct Julia attractor geometry while keeping the set
# geometrically coherent as a single Tongue 3 vertical slice.


# ── CubeFace ──────────────────────────────────────────────────────────────────

class CubeFace(Enum):
    TOP       = "top"
    BOTTOM    = "bottom"
    FRONT     = "front"
    BACK      = "back"
    STARBOARD = "starboard"
    PORT      = "port"

    @property
    def byte_address(self) -> int:
        return FACE_BYTES[self.value]

    @property
    def julia(self) -> complex:
        return FACE_JULIA[self.value]

    @property
    def shygazun(self) -> str:
        return {
            "top":       "Jy",
            "bottom":    "Ju",
            "front":     "Ja",
            "back":      "Jo",
            "starboard": "Ji",
            "port":      "Je",
        }[self.value]


# ── Julia iteration ───────────────────────────────────────────────────────────

def julia_escape(z: complex, c: complex, max_iter: int = 256) -> int:
    """
    Return the escape iteration count for point z under Julia set c.
    Returns max_iter if z does not escape (inside the set).
    Used to compute terrain height/density at each tile position (u, v).
    """
    for i in range(max_iter):
        if abs(z) > 2.0:
            return i
        z = z * z + c
    return max_iter


def face_terrain_value(face: CubeFace, u: float, v: float,
                        max_iter: int = 256) -> float:
    """
    Compute a terrain value in [0, 1] for tile position (u, v) on a cube face.
    u, v ∈ [0, 1] — normalized tile coordinates on this face.

    Maps (u, v) to the complex plane z₀ = (u*4-2) + (v*4-2)i and runs the
    Julia iteration with this face's Sakura parameter.

    Returns 0.0 at Mandelbrot-set-like interior (bounded — flat terrain),
    1.0 at fast escape (open — elevated terrain).  The boundary (moderate
    escape counts) produces the interesting terrain: coastlines, ridges,
    biome transitions.
    """
    z0 = complex(u * 4.0 - 2.0, v * 4.0 - 2.0)
    count = julia_escape(z0, face.julia, max_iter)
    return count / max_iter


# ── World definition ──────────────────────────────────────────────────────────

@dataclass
class WorldPhysicsConfig:
    """Physics configuration layered on top of the universal face geometry."""
    gravity:          float = 9.8
    kael_amplitude:   float = 0.15
    freq_ref:         float = 440.0
    linear_damping:   float = 0.02
    sanity_pressure:  dict  = field(default_factory=dict)  # dimension → base pressure
    eigenstate_seed:  list  = field(default_factory=list)  # override weights by tongue index


@dataclass
class BoundedWorld:
    """
    A single bounded spherical world in the dimension registry.

    name:           canonical identifier (e.g. "aeralune", "mercurie", "sulphera_ring_1")
    radius_tiles:   world radius in tiles — determines how many days of exploration
    physics:        world-specific physics config
    tpn_atlases:    dict mapping CubeFace → TPN atlas path (6 faces per world)
    forward_face:   which face is canonical "north" / pole-facing
    """
    name:          str
    radius_tiles:  int
    physics:       WorldPhysicsConfig = field(default_factory=WorldPhysicsConfig)
    tpn_atlases:   dict = field(default_factory=dict)   # CubeFace → atlas path
    forward_face:  CubeFace = CubeFace.FRONT

    def face_julia(self, face: CubeFace) -> complex:
        return face.julia

    def tile_terrain(self, face: CubeFace, u: float, v: float) -> float:
        return face_terrain_value(face, u, v)

    def breath_of_ko_coordinate(self, face: CubeFace, u: float, v: float) -> complex:
        """
        Return the BreathOfKo complex coordinate for a tile position on this world.
        The cube face Julia parameter anchors the coordinate; (u, v) are the
        Mandelbrot iteration inputs.  Dimension crossing from this tile seeds the
        next eigenstate configuration via this coordinate.
        """
        return complex(u * 4.0 - 2.0, v * 4.0 - 2.0)


# ── Dimension registry ────────────────────────────────────────────────────────

_REGISTRY: dict[str, BoundedWorld] = {}


def register_world(world: BoundedWorld) -> None:
    _REGISTRY[world.name] = world


def get_world(name: str) -> Optional[BoundedWorld]:
    return _REGISTRY.get(name)


def all_worlds() -> list[BoundedWorld]:
    return list(_REGISTRY.values())
