"""
Dungeon Generator
=================
Seeded BSP (Binary Space Partitioning) procedural dungeon generation.

Layout is ephemeral — it is never persisted.  Only run outcomes are
written to the Orrery stack.

Output:
  DungeonLayout
    voxels    : dict[(x, y)] → TileKind
    rooms     : list[Room]
    encounters: list[EncounterSlot]
    specials  : list[SpecialTile]
    metadata  : dict — includes seed, dungeon_id, floor, ephemeral=True
"""

from __future__ import annotations

import struct
import math
from dataclasses import dataclass, field
from typing import Iterator
from enum import Enum


# ── PRNG ──────────────────────────────────────────────────────────────────────

def _mulberry32(seed: int) -> Iterator[float]:
    """
    mulberry32 — fast 32-bit PRNG.
    Yields floats in [0, 1).  Matches the JS implementation in dungeonGenerator.js.
    """
    h = seed & 0xFFFFFFFF
    while True:
        h = (h + 0x6D2B79F5) & 0xFFFFFFFF
        t = h ^ (h >> 15)
        t = (t * ((t >> 4 | 0xFFFF8000) | 1)) & 0xFFFFFFFF
        t ^= t + (((t * ((t >> 7 | 0xFFFF0100) | 1)) & 0xFFFFFFFF) ^ (t >> 12))
        yield ((t ^ (t >> 15)) & 0xFFFFFFFF) / 0xFFFFFFFF


# ── Tile kinds ─────────────────────────────────────────────────────────────────

class TileKind(str, Enum):
    WALL       = "wall"
    FLOOR      = "floor"
    DOOR       = "door"
    ENTRY      = "entry"
    EXIT       = "exit"
    CHEST      = "chest"
    FORGE      = "forge"
    CRYSTAL    = "desire_crystal"
    ALTAR      = "altar"
    SPECIAL    = "special"


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class Room:
    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2

    def tiles(self) -> Iterator[tuple[int, int]]:
        for dx in range(self.w):
            for dy in range(self.h):
                yield self.x + dx, self.y + dy


@dataclass
class EncounterSlot:
    x: int
    y: int
    encounter_type: str   # "combat" | "negotiation" | "observation" | "trap" | "lore"
    difficulty: float     # 0.0–1.0


@dataclass
class SpecialTile:
    x: int
    y: int
    kind: str   # matches DungeonDef.special_tiles entries


@dataclass
class DungeonLayout:
    voxels: dict[tuple[int, int], TileKind]
    rooms: list[Room]
    encounters: list[EncounterSlot]
    specials: list[SpecialTile]
    metadata: dict


# ── BSP ────────────────────────────────────────────────────────────────────────

_MIN_ROOM_DIM  = 4
_MAX_ROOM_DIM  = 12
_GRID_W        = 64
_GRID_H        = 64
_MAX_BSP_DEPTH = 5


@dataclass
class _BSPNode:
    x: int
    y: int
    w: int
    h: int
    left:  "_BSPNode | None" = None
    right: "_BSPNode | None" = None
    room:  Room | None       = None


def _bsp_split(node: _BSPNode, depth: int, rng: Iterator[float]) -> None:
    if depth >= _MAX_BSP_DEPTH:
        return
    if node.w < _MIN_ROOM_DIM * 2 + 2 and node.h < _MIN_ROOM_DIM * 2 + 2:
        return

    horizontal = next(rng) < 0.5
    if node.w < _MIN_ROOM_DIM * 2 + 2:
        horizontal = True
    elif node.h < _MIN_ROOM_DIM * 2 + 2:
        horizontal = False

    if horizontal:
        split = int(_MIN_ROOM_DIM + next(rng) * (node.h - _MIN_ROOM_DIM * 2))
        split = max(_MIN_ROOM_DIM, min(node.h - _MIN_ROOM_DIM, split))
        node.left  = _BSPNode(node.x, node.y, node.w, split)
        node.right = _BSPNode(node.x, node.y + split, node.w, node.h - split)
    else:
        split = int(_MIN_ROOM_DIM + next(rng) * (node.w - _MIN_ROOM_DIM * 2))
        split = max(_MIN_ROOM_DIM, min(node.w - _MIN_ROOM_DIM, split))
        node.left  = _BSPNode(node.x, node.y, split, node.h)
        node.right = _BSPNode(node.x + split, node.y, node.w - split, node.h)

    _bsp_split(node.left,  depth + 1, rng)
    _bsp_split(node.right, depth + 1, rng)


def _carve_room(node: _BSPNode, rng: Iterator[float]) -> list[Room]:
    if node.left is None and node.right is None:
        rw = int(_MIN_ROOM_DIM + next(rng) * min(_MAX_ROOM_DIM - _MIN_ROOM_DIM, node.w - 2))
        rh = int(_MIN_ROOM_DIM + next(rng) * min(_MAX_ROOM_DIM - _MIN_ROOM_DIM, node.h - 2))
        rx = node.x + int(next(rng) * (node.w - rw))
        ry = node.y + int(next(rng) * (node.h - rh))
        room = Room(rx, ry, rw, rh)
        node.room = room
        return [room]

    rooms: list[Room] = []
    if node.left:
        rooms += _carve_room(node.left, rng)
    if node.right:
        rooms += _carve_room(node.right, rng)
    return rooms


def _carve_corridor(
    voxels: dict[tuple[int, int], TileKind],
    a: Room,
    b: Room,
) -> None:
    # L-shaped corridor: horizontal then vertical
    for x in range(min(a.cx, b.cx), max(a.cx, b.cx) + 1):
        voxels[(x, a.cy)] = TileKind.FLOOR
    for y in range(min(a.cy, b.cy), max(a.cy, b.cy) + 1):
        voxels[(b.cx, y)] = TileKind.FLOOR


# ── Encounter placement ────────────────────────────────────────────────────────

_ENCOUNTER_TYPES = ["combat", "negotiation", "observation", "trap", "lore"]
_ENCOUNTER_WEIGHTS = [0.40, 0.20, 0.20, 0.10, 0.10]


def _pick_encounter_type(r: float) -> str:
    cumulative = 0.0
    for kind, w in zip(_ENCOUNTER_TYPES, _ENCOUNTER_WEIGHTS):
        cumulative += w
        if r < cumulative:
            return kind
    return "combat"


def _spawn_encounters(
    rooms: list[Room],
    encounter_density: float,
    rng: Iterator[float],
) -> list[EncounterSlot]:
    slots: list[EncounterSlot] = []
    # Skip first room (entry) and last room (exit)
    for room in rooms[1:-1]:
        if next(rng) > encounter_density:
            continue
        ex = room.x + int(next(rng) * room.w)
        ey = room.y + int(next(rng) * room.h)
        slots.append(EncounterSlot(
            x=ex, y=ey,
            encounter_type=_pick_encounter_type(next(rng)),
            difficulty=0.2 + next(rng) * 0.6,
        ))
    return slots


# ── Special tile placement ─────────────────────────────────────────────────────

def _place_specials(
    rooms: list[Room],
    special_tile_kinds: list[str],
    rng: Iterator[float],
) -> list[SpecialTile]:
    if not special_tile_kinds or len(rooms) < 2:
        return []

    specials: list[SpecialTile] = []
    # Distribute specials across non-entry/exit rooms
    candidate_rooms = rooms[1:-1] if len(rooms) > 2 else rooms
    for kind in special_tile_kinds:
        room = candidate_rooms[int(next(rng) * len(candidate_rooms))]
        sx = room.x + 1 + int(next(rng) * max(1, room.w - 2))
        sy = room.y + 1 + int(next(rng) * max(1, room.h - 2))
        specials.append(SpecialTile(x=sx, y=sy, kind=kind))
    return specials


# ── Public API ─────────────────────────────────────────────────────────────────

def generate(dungeon_id: str, seed: int, floor: int, encounter_density: float, special_tiles: list[str]) -> DungeonLayout:
    """
    Generate a single floor layout.

    Parameters
    ----------
    dungeon_id:
        Canonical dungeon id (from registry).
    seed:
        32-bit integer seed.  Same seed → same layout.
    floor:
        Floor number (0-indexed).  Affects seed offset.
    encounter_density:
        Fraction of rooms that get an encounter (from DungeonDef).
    special_tiles:
        List of special tile kind strings (from DungeonDef.special_tiles).
    """
    floor_seed = (seed ^ (floor * 0x9E3779B9)) & 0xFFFFFFFF
    rng = _mulberry32(floor_seed)

    # BSP
    root = _BSPNode(0, 0, _GRID_W, _GRID_H)
    _bsp_split(root, 0, rng)
    rooms = _carve_room(root, rng)

    if not rooms:
        rooms = [Room(2, 2, 6, 6)]

    # Voxels — start all walls, carve rooms
    voxels: dict[tuple[int, int], TileKind] = {}
    for room in rooms:
        for tx, ty in room.tiles():
            voxels[(tx, ty)] = TileKind.FLOOR

    # Corridors — connect adjacent rooms
    for i in range(len(rooms) - 1):
        _carve_corridor(voxels, rooms[i], rooms[i + 1])

    # Entry / Exit
    entry_room = rooms[0]
    exit_room  = rooms[-1]
    voxels[(entry_room.cx, entry_room.cy)] = TileKind.ENTRY
    voxels[(exit_room.cx,  exit_room.cy)]  = TileKind.EXIT

    encounters = _spawn_encounters(rooms, encounter_density, rng)
    specials   = _place_specials(rooms, special_tiles, rng)

    # Mark special positions in voxels
    for sp in specials:
        voxels[(sp.x, sp.y)] = TileKind.SPECIAL

    return DungeonLayout(
        voxels=voxels,
        rooms=rooms,
        encounters=encounters,
        specials=specials,
        metadata={
            "dungeon_id": dungeon_id,
            "seed": seed,
            "floor": floor,
            "ephemeral": True,
        },
    )
