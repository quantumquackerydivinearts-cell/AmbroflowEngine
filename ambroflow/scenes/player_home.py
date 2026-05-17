"""
ambroflow/scenes/player_home.py
================================
Player home furniture, interactions, and zone exports for 7_KLGS.

Zone topology (walls, floors, exits, spawn) is defined canonically in
home_zone.py using Kobra placement notation.  This module re-exports those
zones and provides the complementary furniture geometry (FurniturePlacement)
and interaction hotspot (HOME_INTERACTIONS) lists that the GL renderer needs.

ASCII zone scaffolding has been removed.  Do not re-introduce _GROUND_ROWS or
_UPPER_ROWS — any geometry change goes into home_zone.py.

Zone ID reference
-----------------
  player_home_ground  — ground floor (40 × 13): bedroom, kitchen, meditation, foyer
  player_home_upper   — upper floor  (40 × 10): study, fine-processing bench

Canonical spawn positions live in home_zone:
  GROUND_SPAWN = (19, 11)   — centre foyer
  UPPER_SPAWN  = (24, 7)    — top of stair
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from .home_zone import (
    PLAYER_HOME_GROUND,
    PLAYER_HOME_UPPER,
    GROUND_SPAWN,
    UPPER_SPAWN,
)
from ..world.map import WorldMap


# ── Re-export canonical zones ─────────────────────────────────────────────────
# Consumers that import PLAYER_HOME_GROUND / PLAYER_HOME_UPPER from here get
# the Kobra-canonical zones without needing to know about home_zone.py.

__all__ = [
    "PLAYER_HOME_GROUND",
    "PLAYER_HOME_UPPER",
    "PLAYER_HOME_WORLD",
    "GROUND_FURNITURE",
    "UPPER_FURNITURE",
    "HOME_INTERACTIONS",
    "HOME_UPPER_INTERACTIONS",
    "FurniturePlacement",
    "FurnitureTile",
    "get_player_home_furniture",
    "get_player_home_interactions",
    "altar_placements",
]


# ── World map (opening sequence + navigable world share the same zones) ───────

PLAYER_HOME_WORLD: WorldMap = WorldMap(
    zones = {
        "player_home_ground": PLAYER_HOME_GROUND,
        "player_home_upper":  PLAYER_HOME_UPPER,
    },
    starting_zone_id = "player_home_ground",
)


# ── Furniture tile IDs (atlas column indices) ─────────────────────────────────

class FurnitureTile(IntEnum):
    BED        = 7
    TABLE      = 8
    JOURNAL    = 9
    FURNACE    = 10
    ANVIL      = 11
    COUNTER    = 12
    REGISTER   = 13
    ALTAR      = 14
    BOOKSHELF  = 15
    DESK       = 16   # writing desk (Study)
    MORTAR     = 17   # grinding bowl on Study workbench
    WORKBENCH  = 18   # fine-processing / distillation bench (Study)


# ── Furniture placement record ────────────────────────────────────────────────

@dataclass(frozen=True)
class FurniturePlacement:
    """
    A single furniture instance in the 3-D scene.

    x / z  — tile grid coordinates (z = row / south axis, matching Zone's y).
    y      — elevation above the ground plane (0.0 = floor level).
    tile_id — atlas column index fed to the instanced GL renderer.
    height  — visual tile height in world units.
    passable — False = blocks movement on that tile.
    """
    x:        int
    z:        int
    y:        float
    tile_id:  FurnitureTile
    height:   float = 1.0
    passable: bool  = False
    room:     str   = ""
    slot_id:  str   = ""


# ── Ground floor furniture (player_home_ground, 48 × 13) ─────────────────────
#
# Room layout:
#   Bedroom    x=1–11   z=1–7   (11 wide)
#   Kitchen    x=13–28  z=1–7   (16 wide)
#   Meditation x=30–46  z=1–7   (17 wide)
#   Foyer      x=1–46   z=9–11
#
# Counter at z=10, x=4–43; passages at x=1–3 (west) and x=44–46 (east).

GROUND_FURNITURE: list[FurniturePlacement] = [

    # ── Bedroom ───────────────────────────────────────────────────────────────
    FurniturePlacement(x=2, z=3, y=0.0, tile_id=FurnitureTile.BED,
                       height=0.5, passable=False, room="bedroom", slot_id="bed_w"),
    FurniturePlacement(x=3, z=3, y=0.0, tile_id=FurnitureTile.BED,
                       height=0.5, passable=False, room="bedroom", slot_id="bed_e"),
    # Journal table — east side of bedroom
    FurniturePlacement(x=10, z=5, y=0.0, tile_id=FurnitureTile.TABLE,
                       height=0.8, passable=False, room="bedroom", slot_id="journal_table"),
    FurniturePlacement(x=10, z=5, y=0.8, tile_id=FurnitureTile.JOURNAL,
                       height=0.1, passable=True,  room="bedroom", slot_id="journal"),

    # ── Kitchen / alchemy lab (cols 13–28) ────────────────────────────────────
    # Furnace pair built into the north wall
    FurniturePlacement(x=14, z=2, y=0.0, tile_id=FurnitureTile.FURNACE,
                       height=1.0, passable=False, room="kitchen", slot_id="furnace_w"),
    FurniturePlacement(x=15, z=2, y=0.0, tile_id=FurnitureTile.FURNACE,
                       height=1.0, passable=False, room="kitchen", slot_id="furnace_e"),
    # Alchemy workbench — centre of kitchen
    FurniturePlacement(x=21, z=5, y=0.0, tile_id=FurnitureTile.TABLE,
                       height=0.8, passable=False, room="kitchen", slot_id="workbench"),
    # Anvil — east side of kitchen (smithing adjacent to alchemy)
    FurniturePlacement(x=26, z=3, y=0.0, tile_id=FurnitureTile.ANVIL,
                       height=0.9, passable=False, room="kitchen", slot_id="anvil"),

    # ── Meditation room (cols 30–46) ──────────────────────────────────────────
    FurniturePlacement(x=39, z=4, y=0.0, tile_id=FurnitureTile.ALTAR,
                       height=0.4, passable=True,  room="meditation", slot_id="altar"),

    # ── Foyer service counter (cols 4–43, row 10) ─────────────────────────────
    # Counter at z=10; z=9 is the open navigation row from inner-wall doors.
    *[
        FurniturePlacement(x=xi, z=10, y=0.0, tile_id=FurnitureTile.COUNTER,
                           height=0.9, passable=False, room="foyer",
                           slot_id=f"counter_{xi}")
        for xi in range(4, 44)
    ],
    # Register at the east end of the counter
    FurniturePlacement(x=43, z=10, y=0.9, tile_id=FurnitureTile.REGISTER,
                       height=0.3, passable=False, room="foyer", slot_id="register"),
]


# ── Upper floor furniture (player_home_upper, 40 × 10) ───────────────────────

UPPER_FURNITURE: list[FurniturePlacement] = [
    # Bookshelves along the west wall (x=1)
    *[
        FurniturePlacement(x=1, z=zi, y=0.0, tile_id=FurnitureTile.BOOKSHELF,
                           height=1.8, passable=False, room="study",
                           slot_id=f"shelf_w_{zi}")
        for zi in range(1, 8)
    ],
    # Bookshelves along the east wall (x=46)
    *[
        FurniturePlacement(x=46, z=zi, y=0.0, tile_id=FurnitureTile.BOOKSHELF,
                           height=1.8, passable=False, room="study",
                           slot_id=f"shelf_e_{zi}")
        for zi in range(1, 8)
    ],
    # Writing desk — centre of study
    FurniturePlacement(x=26, z=4, y=0.0, tile_id=FurnitureTile.DESK,
                       height=0.8, passable=False, room="study", slot_id="study_desk"),
    # Fine-processing workbench — north wall, west of centre
    FurniturePlacement(x=12, z=2, y=0.0, tile_id=FurnitureTile.WORKBENCH,
                       height=0.9, passable=False, room="study", slot_id="fine_bench"),
    # Mortar on the workbench surface
    FurniturePlacement(x=12, z=2, y=0.9, tile_id=FurnitureTile.MORTAR,
                       height=0.3, passable=True,  room="study", slot_id="mortar"),
    # Distillation bench — further east along north wall
    FurniturePlacement(x=20, z=2, y=0.0, tile_id=FurnitureTile.WORKBENCH,
                       height=0.9, passable=False, room="study", slot_id="distill_bench"),
    # Stair step down — marks the stairs_down tile at (28, 8)
    FurniturePlacement(x=28, z=8, y=0.0, tile_id=FurnitureTile.DESK,
                       height=0.3, passable=True,  room="study", slot_id="stairs_down"),
]


# ── Interaction entity lists ──────────────────────────────────────────────────

HOME_INTERACTIONS: list[dict] = [
    # Bed — rest and save
    {"x": 2.5,  "y": 3.0,  "kind": "interaction", "node_id": "bed",
     "metadata": {"action": "rest"}},
    # Journal table — open journal screen
    {"x": 10.0, "y": 5.0,  "kind": "interaction", "node_id": "journal_table",
     "metadata": {"action": "read_journal"}},
    # Stair up — go to upper study (zone exit at (11, 2))
    {"x": 11.0, "y": 2.0,  "kind": "interaction", "node_id": "stairs_up",
     "metadata": {"action": "stairs_up"}},
    # Furnace — open heavy-process alchemy UI
    {"x": 14.5, "y": 2.0,  "kind": "interaction", "node_id": "furnace",
     "metadata": {"action": "open_alchemy_ui", "station": "kitchen"}},
    # Alchemy workbench — also opens alchemy
    {"x": 21.0, "y": 5.0,  "kind": "interaction", "node_id": "workbench",
     "metadata": {"action": "open_alchemy_ui", "station": "kitchen"}},
    # Anvil
    {"x": 26.0, "y": 3.0,  "kind": "interaction", "node_id": "anvil",
     "metadata": {"action": "open_smelt_ui"}},
    # Meditation altar — divine encounter (Ko + Moshize Jabiru)
    {"x": 39.0, "y": 4.0,  "kind": "interaction", "node_id": "altar",
     "metadata": {"action": "meditate"}},
    # Counter — open shop UI (counter at z=10; interact from z=9 side)
    {"x": 23.5, "y": 10.0, "kind": "interaction", "node_id": "counter",
     "metadata": {"action": "open_shop_ui"}},
    # Register — also open shop
    {"x": 43.0, "y": 10.0, "kind": "interaction", "node_id": "register",
     "metadata": {"action": "open_shop_ui"}},
]

HOME_UPPER_INTERACTIONS: list[dict] = [
    # Bookshelves — read lore
    {"x": 1.0,  "y": 4.0,  "kind": "interaction", "node_id": "shelf_w",
     "metadata": {"action": "lore_books"}},
    {"x": 46.0, "y": 4.0,  "kind": "interaction", "node_id": "shelf_e",
     "metadata": {"action": "lore_books"}},
    # Writing desk — open journal
    {"x": 26.0, "y": 4.0,  "kind": "interaction", "node_id": "study_desk",
     "metadata": {"action": "read_journal"}},
    # Fine-processing workbench — grinding / filtering / distillation alchemy
    {"x": 12.0, "y": 2.0,  "kind": "interaction", "node_id": "fine_bench",
     "metadata": {"action": "open_alchemy_ui", "station": "fine_processing"}},
    {"x": 12.0, "y": 2.5,  "kind": "interaction", "node_id": "mortar",
     "metadata": {"action": "open_alchemy_ui", "station": "fine_processing"}},
    # Distillation bench
    {"x": 20.0, "y": 2.0,  "kind": "interaction", "node_id": "distill_bench",
     "metadata": {"action": "open_alchemy_ui", "station": "fine_processing"}},
    # Stair down — return to ground floor (zone exit at (28, 8))
    {"x": 28.0, "y": 8.0,  "kind": "interaction", "node_id": "stairs_down",
     "metadata": {"action": "stairs_down"}},
]


# ── Altar API (backward-compat) ───────────────────────────────────────────────

def altar_placements(items: Optional[list[str]] = None) -> list[FurniturePlacement]:
    """Return the base altar placement plus up to four item-slot placements."""
    base = FurniturePlacement(
        x=39, z=4, y=0.0, tile_id=FurnitureTile.ALTAR,
        height=0.4, passable=True, room="meditation", slot_id="altar",
    )
    if not items:
        return [base]
    slots: list[FurniturePlacement] = [base]
    for i, _item_id in enumerate(items[:4]):
        slots.append(FurniturePlacement(
            x=32 + i, z=4, y=0.4, tile_id=FurnitureTile.ALTAR,
            height=0.1, passable=True, room="meditation",
            slot_id=f"altar_slot_{i}",
        ))
    return slots


# ── Dispatch helpers ──────────────────────────────────────────────────────────

def get_player_home_furniture(zone_id: str) -> list[FurniturePlacement]:
    """Return the furniture list for the given player home zone."""
    if zone_id == "player_home_ground":
        return list(GROUND_FURNITURE)
    if zone_id == "player_home_upper":
        return list(UPPER_FURNITURE)
    return []


def get_player_home_interactions(zone_id: str) -> list[dict]:
    """Return the interaction entity list for the given player home zone."""
    if zone_id == "player_home_ground":
        return list(HOME_INTERACTIONS)
    if zone_id == "player_home_upper":
        return list(HOME_UPPER_INTERACTIONS)
    return []
