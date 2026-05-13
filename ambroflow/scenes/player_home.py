"""
ambroflow/scenes/player_home.py
================================
Zone data and furniture for the player's residence at Wiltoll Lane.

Coordinate space matches lapidus_wiltoll_home (40 wide × 13 tall):

  Row 0   North wall     #×40
  Row 1   Back wall face  #W…W#W…W#W…W#   (WALL_FACE — wallpaper substrate)
  Rows 2–7  Three rooms:
              Bedroom    x=1–10   (10 wide)
              Kitchen    x=12–25  (14 wide)
              Meditation x=27–38  (12 wide)
  Row 8   Inner dividing wall, doors at cols 5 / 19 / 33
  Rows 9–11 Foyer (open, NPC vendor at 15,10)
  Row 12  South wall, door at cols 20–21

Stair up: tile ^ at (9, 2) in lapidus_wiltoll_home → player_home_upper (24, 7).

Furniture atlas IDs (0-indexed, must match _INTERIOR_ATLAS_COLORS):
   0 FLOOR   1 GRASS   2 ROAD    3 WALL    4 WATER   5 STONE   6 VOID
   7 BED     8 TABLE   9 JOURNAL 10 FURNACE 11 ANVIL
  12 COUNTER 13 REGISTER 14 ALTAR 15 BOOKSHELF 16 DESK

Zone IDs
--------
  lapidus_wiltoll_home     ground floor (canonical game zone)
  player_home_upper        upper floor / Study
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from ..world.map import (
    Realm, Zone, ZoneExit, WorldMap,
    build_zone_from_ascii,
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
    DESK       = 16   # column 16 — added to _INTERIOR_ATLAS_COLORS in gl_world_play


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


# ── Fate Knocks scene zone (44 wide × 13 tall) ───────────────────────────────
# Used only by the opening sequence (FateKnocksGLPlay), not by the navigable
# world.  Layout preserved from the original authored version.

_GROUND_ROWS = [
    "############################################",  # y=0  north wall
    "#...........##.............#...............#",  # y=1
    "#...........##..........^..#...............#",  # y=2  ^ stair (x=24)
    "#...........##.............#...............#",  # y=3
    "#...........##.............#...............#",  # y=4
    "#...........##.............#...............#",  # y=5
    "#...........##.............#...............#",  # y=6
    "#####+##############+#######...............#",  # y=7  room separator
    "#..........................................#",  # y=8  foyer
    "#...####################################...#",  # y=9  service counter
    "#..........................................#",  # y=10
    "#.....................@....................#",  # y=11 @ = spawn (x=22)
    "######################+#####################",  # y=12 front door
]

assert all(len(r) == 44 for r in _GROUND_ROWS), \
    "Ground floor row width mismatch — all rows must be 44 characters"

PLAYER_HOME_GROUND: Zone = build_zone_from_ascii(
    zone_id = "player_home_ground",
    realm   = Realm.LAPIDUS,
    name    = "Player Home",
    rows    = _GROUND_ROWS,
    exits   = [
        ZoneExit(x=22, y=12, direction="south",
                 target_zone="lapidus_wiltoll_ext", target_x=3, target_y=15),
        ZoneExit(x=24, y=2, direction="north",
                 target_zone="player_home_upper", target_x=24, target_y=7),
    ],
)


# ── Upper floor ASCII (44 wide × 10 tall) ────────────────────────────────────

_UPPER_ROWS = [
    "############################################",  # y=0  north wall
    "#..........................................#",  # y=1
    "#..........................................#",  # y=2
    "#..........................................#",  # y=3
    "#..........................................#",  # y=4
    "#..........................................#",  # y=5
    "#..........................................#",  # y=6
    "#..........................................#",  # y=7  arrive from ground
    "#.......................v..................#",  # y=8  v stair down (x=24)
    "############################################",  # y=9  south wall
]

assert all(len(r) == 44 for r in _UPPER_ROWS), "Upper floor row width mismatch"


# ── Zone: upper floor (Study) ─────────────────────────────────────────────────

PLAYER_HOME_UPPER: Zone = build_zone_from_ascii(
    zone_id = "player_home_upper",
    realm   = Realm.LAPIDUS,
    name    = "Player Home — Study",
    rows    = _UPPER_ROWS,
    exits   = [
        ZoneExit(
            x=24, y=8, direction="south",
            target_zone="lapidus_wiltoll_home",
            target_x=9, target_y=3,
        ),
    ],
)


# ── Fate Knocks world map (for opening sequence only) ────────────────────────

PLAYER_HOME_WORLD: WorldMap = WorldMap(
    zones = {
        "player_home_ground": PLAYER_HOME_GROUND,
        "player_home_upper":  PLAYER_HOME_UPPER,
    },
    starting_zone_id = "player_home_ground",
)


# ── Ground floor furniture (lapidus_wiltoll_home, 40 × 13) ───────────────────
#
# Room layout:
#   Bedroom    cols  1–10   rows 2–7
#   Kitchen    cols 12–25   rows 2–7
#   Meditation cols 27–38   rows 2–7
#   Foyer      cols  1–38   rows 9–11

GROUND_FURNITURE: list[FurniturePlacement] = [

    # ── Bedroom (cols 1–10) ───────────────────────────────────────────────────
    FurniturePlacement(x=2, z=3, y=0.0, tile_id=FurnitureTile.BED,
                       height=0.5, passable=False, room="bedroom", slot_id="bed_w"),
    FurniturePlacement(x=3, z=3, y=0.0, tile_id=FurnitureTile.BED,
                       height=0.5, passable=False, room="bedroom", slot_id="bed_e"),
    # Journal table — east wall of bedroom
    FurniturePlacement(x=8, z=5, y=0.0, tile_id=FurnitureTile.TABLE,
                       height=0.8, passable=False, room="bedroom", slot_id="journal_table"),
    FurniturePlacement(x=8, z=5, y=0.8, tile_id=FurnitureTile.JOURNAL,
                       height=0.1, passable=True,  room="bedroom", slot_id="journal"),
    # Stair step — NE corner of bedroom (tile (9,2) is ^ STAIRS_UP in the zone)
    FurniturePlacement(x=9, z=2, y=0.0, tile_id=FurnitureTile.DESK,
                       height=0.3, passable=True,  room="bedroom", slot_id="stairs_up"),

    # ── Kitchen / Alchemy lab (cols 12–25) ────────────────────────────────────
    # Furnace pair against back wall (NW corner of kitchen)
    FurniturePlacement(x=13, z=2, y=0.0, tile_id=FurnitureTile.FURNACE,
                       height=1.0, passable=False, room="kitchen", slot_id="furnace_w"),
    FurniturePlacement(x=14, z=2, y=0.0, tile_id=FurnitureTile.FURNACE,
                       height=1.0, passable=False, room="kitchen", slot_id="furnace_e"),
    # Alchemy workbench — centre of kitchen
    FurniturePlacement(x=20, z=5, y=0.0, tile_id=FurnitureTile.TABLE,
                       height=0.8, passable=False, room="kitchen", slot_id="workbench"),

    # ── Meditation room (cols 27–38) ──────────────────────────────────────────
    FurniturePlacement(x=33, z=4, y=0.0, tile_id=FurnitureTile.ALTAR,
                       height=0.4, passable=True,  room="meditation", slot_id="altar"),

    # ── Foyer service counter (cols 4–35, row 9) ──────────────────────────────
    *[
        FurniturePlacement(x=xi, z=9, y=0.0, tile_id=FurnitureTile.COUNTER,
                           height=0.9, passable=False, room="foyer",
                           slot_id=f"counter_{xi}")
        for xi in range(4, 36)
    ],
    # Register at the east end of the counter
    FurniturePlacement(x=35, z=9, y=0.9, tile_id=FurnitureTile.REGISTER,
                       height=0.3, passable=False, room="foyer", slot_id="register"),
]


# ── Upper floor furniture ─────────────────────────────────────────────────────

UPPER_FURNITURE: list[FurniturePlacement] = [
    # Bookshelves along the west wall (x=1)
    *[
        FurniturePlacement(x=1, z=zi, y=0.0, tile_id=FurnitureTile.BOOKSHELF,
                           height=1.8, passable=False, room="study",
                           slot_id=f"shelf_w_{zi}")
        for zi in range(1, 8)
    ],
    # Bookshelves along the east wall (x=42)
    *[
        FurniturePlacement(x=42, z=zi, y=0.0, tile_id=FurnitureTile.BOOKSHELF,
                           height=1.8, passable=False, room="study",
                           slot_id=f"shelf_e_{zi}")
        for zi in range(1, 8)
    ],
    # Desk at centre of study
    FurniturePlacement(x=22, z=4, y=0.0, tile_id=FurnitureTile.DESK,
                       height=0.8, passable=False, room="study", slot_id="study_desk"),
    # Stair step down — marks the v tile at (24,8)
    FurniturePlacement(x=24, z=8, y=0.0, tile_id=FurnitureTile.DESK,
                       height=0.3, passable=True,  room="study", slot_id="stairs_down"),
]


# ── Interaction entity lists ──────────────────────────────────────────────────
#
# Same dict shape as .scene.ko interaction nodes.  Loaded by GLWorldPlay as
# _entities for these zones so Space/Enter near furniture opens the right UI.
# Distance threshold in GLWorldPlay._find_interaction_at is 1.5 tiles.

HOME_INTERACTIONS: list[dict] = [
    # Bed — rest and save
    {"x": 2.5,  "y": 3.0,  "kind": "interaction", "node_id": "bed",
     "metadata": {"action": "rest"}},
    # Journal table — open journal screen
    {"x": 8.0,  "y": 5.0,  "kind": "interaction", "node_id": "journal_table",
     "metadata": {"action": "read_journal"}},
    # Stair up — go to upper study
    {"x": 9.0,  "y": 2.0,  "kind": "interaction", "node_id": "stairs_up",
     "metadata": {"action": "stairs_up"}},
    # Furnace — open alchemy
    {"x": 13.5, "y": 2.0,  "kind": "interaction", "node_id": "furnace",
     "metadata": {"action": "open_alchemy_ui"}},
    # Alchemy workbench — also opens alchemy
    {"x": 20.0, "y": 5.0,  "kind": "interaction", "node_id": "workbench",
     "metadata": {"action": "open_alchemy_ui"}},
    # Meditation altar — meditate
    {"x": 33.0, "y": 4.0,  "kind": "interaction", "node_id": "altar",
     "metadata": {"action": "meditate"}},
    # Counter — open shop
    {"x": 19.5, "y": 9.0,  "kind": "interaction", "node_id": "counter",
     "metadata": {"action": "open_shop_ui"}},
    # Register — also open shop
    {"x": 35.0, "y": 9.0,  "kind": "interaction", "node_id": "register",
     "metadata": {"action": "open_shop_ui"}},
]

HOME_UPPER_INTERACTIONS: list[dict] = [
    # Bookshelves — read lore
    {"x": 1.0,  "y": 4.0,  "kind": "interaction", "node_id": "shelf_w",
     "metadata": {"action": "lore_books"}},
    {"x": 42.0, "y": 4.0,  "kind": "interaction", "node_id": "shelf_e",
     "metadata": {"action": "lore_books"}},
    # Desk — open journal
    {"x": 22.0, "y": 4.0,  "kind": "interaction", "node_id": "study_desk",
     "metadata": {"action": "read_journal"}},
    # Stair down — return to ground floor
    {"x": 24.0, "y": 8.0,  "kind": "interaction", "node_id": "stairs_down",
     "metadata": {"action": "stairs_down"}},
]


# ── Altar API (backward-compat) ───────────────────────────────────────────────

def altar_placements(items: Optional[list[str]] = None) -> list[FurniturePlacement]:
    """Return the base altar placement plus up to four item-slot placements."""
    base = FurniturePlacement(
        x=33, z=4, y=0.0, tile_id=FurnitureTile.ALTAR,
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


# ── Dispatch helper ───────────────────────────────────────────────────────────

def get_player_home_furniture(zone_id: str) -> list[FurniturePlacement]:
    """Return the furniture list for the given player home zone."""
    if zone_id == "lapidus_wiltoll_home":
        return list(GROUND_FURNITURE)
    if zone_id == "player_home_upper":
        return list(UPPER_FURNITURE)
    return []


def get_player_home_interactions(zone_id: str) -> list[dict]:
    """Return the interaction entity list for the given player home zone."""
    if zone_id == "lapidus_wiltoll_home":
        return list(HOME_INTERACTIONS)
    if zone_id == "player_home_upper":
        return list(HOME_UPPER_INTERACTIONS)
    return []