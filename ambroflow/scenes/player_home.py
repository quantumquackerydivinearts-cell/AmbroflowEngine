"""
ambroflow/scenes/player_home.py
================================
Zone data and furniture for Hypatia's residence at Wiltoll Lane (Player Home).

Replaces the static Wiltoll_Street_Interior PIL renders with a live,
walkable Zone pair that the player can move through freely.

Ground floor layout  (44 wide × 13 tall)
-----------------------------------------
  West → East column bands:
    Meditation room  x =  1–11
    double-wall gap  x = 12–13
    Bedroom          x = 14–26   (stairs up at x=24, y=2)
    wall partition   x = 27
    Kitchen          x = 28–42

  Rows (y=0 = north wall):

  x:  0         1         2         3         4
      0123456789012345678901234567890123456789012 3
  y=0  ############################################  north wall
  y=1  #...........##.............#...............#
  y=2  #...........##..........^..#...............#  ^ stair → Study (x=24)
  y=3  #...........##.............#...............#
  y=4  #...........##.............#...............#
  y=5  #...........##.............#...............#
  y=6  #...........##.............#...............#
  y=7  #####+##############+#######...............#  room separator
             ^            ^      ^^^^^^^^^^^^^^^^^^^^^^^
       med. door (x=5)   bed. door (x=20)  open kitchen passage
  y=8  #..........................................#  foyer
  y=9  #...####################################...#  service counter (x 4–39)
  y=10 #..........................................#
  y=11 #.....................@....................#  @ = entry spawn (x=22)
  y=12 ######################+#####################  + = front door (x=22)

Upper floor layout  (44 wide × 10 tall)
-----------------------------------------
  Study / Library.  Open floor with bookshelves (furniture) along the walls.
  Stairs down to Bedroom at x=24, y=8.

  x:  0         1         2         3         4
      0123456789012345678901234567890123456789012 3
  y=0  ############################################  north wall
  y=1  #..........................................#
  y=2  #..........................................#
  y=3  #..........................................#
  y=4  #..........................................#
  y=5  #..........................................#
  y=6  #..........................................#
  y=7  #..........................................#  player arrives here
  y=8  #.......................v..................#   v stair → Bedroom (x=24)
  y=9  ############################################  south wall

Furniture atlas IDs  (7–16)
----------------------------
   7 BED     8 TABLE    9 JOURNAL   10 FURNACE  11 ANVIL
  12 COUNTER 13 REGISTER 14 ALTAR  15 BOOKSHELF 16 DESK

Zone IDs
--------
  player_home_ground   —  ground floor
  player_home_upper    —  upper floor (Study)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from ..world.map import (
    Realm, Zone, ZoneExit, WorldMap,
    build_zone_from_ascii,
)


# ── Furniture tile IDs (atlas indices 7–16) ───────────────────────────────────

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
    DESK       = 16


# ── Furniture placement record ────────────────────────────────────────────────

@dataclass(frozen=True)
class FurniturePlacement:
    """
    A single furniture instance overlaid on top of a Zone floor tile.

    Coordinate space matches Zone voxels: x = east axis, z = south axis
    (zone's y column), y = elevation above ground.  height is the visual
    tile height fed to the instanced GL renderer.

    passable=False means the game engine treats this cell as blocked even
    when the underlying Zone tile is FLOOR.
    """
    x:        int
    z:        int             # south axis — maps to Zone's y coordinate
    y:        float           # elevation above ground  (0.0 = floor level)
    tile_id:  FurnitureTile
    height:   float = 1.0
    passable: bool  = False
    room:     str   = ""
    slot_id:  str   = ""


# ── Ground floor ASCII ────────────────────────────────────────────────────────
# 44 wide × 13 tall.  Each string must be exactly 44 characters.

_GROUND_ROWS = [
    "############################################",  # y=0  north wall
    "#...........##.............#...............#",  # y=1
    "#...........##..........^..#...............#",  # y=2  ^ stair up (bedroom, x=24)
    "#...........##.............#...............#",  # y=3
    "#...........##.............#...............#",  # y=4
    "#...........##.............#...............#",  # y=5
    "#...........##.............#...............#",  # y=6
    "#####+##############+#######...............#",  # y=7  room separator
    "#..........................................#",  # y=8  foyer
    "#...####################################...#",  # y=9  service counter
    "#..........................................#",  # y=10
    "#.....................@....................#",  # y=11 @ = spawn
    "######################+#####################",  # y=12 front door
]

assert all(len(r) == 44 for r in _GROUND_ROWS), \
    "Ground floor row width mismatch — all rows must be 44 characters"


# ── Upper floor ASCII ─────────────────────────────────────────────────────────
# 44 wide × 10 tall.

_UPPER_ROWS = [
    "############################################",  # y=0  north wall
    "#..........................................#",  # y=1
    "#..........................................#",  # y=2
    "#..........................................#",  # y=3
    "#..........................................#",  # y=4
    "#..........................................#",  # y=5
    "#..........................................#",  # y=6
    "#..........................................#",  # y=7  player arrives here
    "#.......................v..................#",   # y=8  v stair down (x=24)
    "############################################",  # y=9  south wall
]

assert all(len(r) == 44 for r in _UPPER_ROWS), \
    "Upper floor row width mismatch — all rows must be 44 characters"


# ── Zone: ground floor ────────────────────────────────────────────────────────

PLAYER_HOME_GROUND: Zone = build_zone_from_ascii(
    zone_id = "player_home_ground",
    realm   = Realm.LAPIDUS,
    name    = "Player Home",
    rows    = _GROUND_ROWS,
    exits   = [
        # Front door — exit south from the door tile (x=22, y=12)
        ZoneExit(
            x=22, y=12, direction="south",
            target_zone="lapidus_wiltoll_ext",
            target_x=3, target_y=15,
        ),
        # Stairs up — exit north from the stair tile (x=24, y=2)
        ZoneExit(
            x=24, y=2, direction="north",
            target_zone="player_home_upper",
            target_x=24, target_y=7,
        ),
    ],
)


# ── Zone: upper floor (Study) ─────────────────────────────────────────────────

PLAYER_HOME_UPPER: Zone = build_zone_from_ascii(
    zone_id = "player_home_upper",
    realm   = Realm.LAPIDUS,
    name    = "Player Home — Study",
    rows    = _UPPER_ROWS,
    exits   = [
        # Stairs down — exit south from the stair tile (x=24, y=8)
        ZoneExit(
            x=24, y=8, direction="south",
            target_zone="player_home_ground",
            target_x=24, target_y=3,
        ),
    ],
)


# ── World map ─────────────────────────────────────────────────────────────────

PLAYER_HOME_WORLD: WorldMap = WorldMap(
    zones = {
        "player_home_ground": PLAYER_HOME_GROUND,
        "player_home_upper":  PLAYER_HOME_UPPER,
    },
    starting_zone_id = "player_home_ground",
)


# ── Ground floor furniture ────────────────────────────────────────────────────

GROUND_FURNITURE: list[FurniturePlacement] = [
    # — Bedroom (x 14–26) ——————————————————————————————————————————
    FurniturePlacement(x=15, z=2, y=0.0, tile_id=FurnitureTile.BED,
                       height=0.5, passable=False, room="bedroom", slot_id="bed_w"),
    FurniturePlacement(x=16, z=2, y=0.0, tile_id=FurnitureTile.BED,
                       height=0.5, passable=False, room="bedroom", slot_id="bed_e"),
    FurniturePlacement(x=23, z=5, y=0.0, tile_id=FurnitureTile.TABLE,
                       height=0.8, passable=False, room="bedroom", slot_id="journal_table"),
    # Journal rests on top of the table surface
    FurniturePlacement(x=23, z=5, y=0.8, tile_id=FurnitureTile.JOURNAL,
                       height=0.1, passable=True, room="bedroom", slot_id="journal"),

    # — Kitchen (x 28–42) ——————————————————————————————————————————
    # Furnace built into north wall — two tiles wide at y=1 (one step from wall)
    FurniturePlacement(x=40, z=1, y=0.0, tile_id=FurnitureTile.FURNACE,
                       height=1.0, passable=False, room="kitchen", slot_id="furnace_w"),
    FurniturePlacement(x=41, z=1, y=0.0, tile_id=FurnitureTile.FURNACE,
                       height=1.0, passable=False, room="kitchen", slot_id="furnace_e"),
    FurniturePlacement(x=34, z=4, y=0.0, tile_id=FurnitureTile.ANVIL,
                       height=0.6, passable=False, room="kitchen", slot_id="anvil"),

    # — Foyer service counter (x 4–39, z=9) ———————————————————————
    # These positions are WALL tiles in the Zone; placements are visual overlays.
    *[
        FurniturePlacement(x=xi, z=9, y=0.0, tile_id=FurnitureTile.COUNTER,
                           height=0.9, passable=False, room="foyer",
                           slot_id=f"counter_{xi}")
        for xi in range(4, 40)
    ],
    # Register at the east end of the counter
    FurniturePlacement(x=39, z=9, y=0.9, tile_id=FurnitureTile.REGISTER,
                       height=0.3, passable=False, room="foyer", slot_id="register"),

    # — Meditation room (x 1–11) ———————————————————————————————————
    FurniturePlacement(x=6, z=4, y=0.0, tile_id=FurnitureTile.ALTAR,
                       height=0.4, passable=True, room="meditation", slot_id="altar"),
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
    # Desk — centre of the study
    FurniturePlacement(x=22, z=4, y=0.0, tile_id=FurnitureTile.DESK,
                       height=0.8, passable=False, room="study", slot_id="desk"),
]


# ── Altar API ─────────────────────────────────────────────────────────────────

def altar_placements(items: Optional[list[str]] = None) -> list[FurniturePlacement]:
    """
    Return the base altar placement plus up to four item-slot placements.

    items  — list of item_ids currently resting on the altar surface.
             Passed by the game engine at scene-load time; if None the
             altar is returned empty (modifiable by the player).
    """
    base = FurniturePlacement(
        x=6, z=4, y=0.0, tile_id=FurnitureTile.ALTAR,
        height=0.4, passable=True, room="meditation", slot_id="altar",
    )
    if not items:
        return [base]
    slots: list[FurniturePlacement] = [base]
    for i, _item_id in enumerate(items[:4]):
        slots.append(FurniturePlacement(
            x=5 + i, z=4, y=0.4, tile_id=FurnitureTile.ALTAR,
            height=0.1, passable=True, room="meditation",
            slot_id=f"altar_slot_{i}",
        ))
    return slots


# ── Dispatch helper ───────────────────────────────────────────────────────────

def get_player_home_furniture(zone_id: str) -> list[FurniturePlacement]:
    """Return the furniture list for the given player home zone."""
    if zone_id == "player_home_ground":
        return list(GROUND_FURNITURE)
    if zone_id == "player_home_upper":
        return list(UPPER_FURNITURE)
    return []