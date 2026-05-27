"""
home_zone.py — Canonical player home zones for 7_KLGS.

Ground floor: player_home_ground   40 wide × 13 tall
Upper floor:  player_home_upper    40 wide × 10 tall

These zones are the single authoritative source of truth for home zone
geometry, exits, and spawn positions.  Both FateKnocksGLPlay (opening
cinematic) and the navigable world use these zones.  ASCII scaffolding
in player_home.py has been retired in favour of this module.

Zone topology (walls, floors, exits, spawn) is generated programmatically
as Kobra placement notation and loaded via load_zone_from_kobra().
Furniture geometry (FurniturePlacement) and interaction hotspots remain as
Python data in player_home.py — Kobra handles structural walkability only.

Ground floor canonical layout (40 × 13):
  Row 0:  north wall (full)
  Rows 1–7:
    x=0:     west wall
    x=1–9:   bedroom
    x=10:    bedroom/kitchen divider
    x=11–24: kitchen + alchemy workbench
    x=25:    kitchen/meditation divider
    x=26–38: meditation room
    x=39:    east wall
  Row 8:  inner dividing wall; doors at x=5 (bedroom), x=18 (kitchen), x=32 (meditation)
  Rows 9–11: foyer  (counter furniture handled separately — zone tiles are FLOOR)
  Row 12: south wall; front door at x=19

Upper floor canonical layout (40 × 10):
  Row 0:  north wall
  Rows 1–7: study (open floor; bookshelves/workbench as furniture, not zone tiles)
  Row 8:  stair down at x=24
  Row 9:  south wall

Canonical spawns:
  player_home_ground: (19, 11)  — centre foyer, pre-letter and post-stair
  player_home_upper:  (24, 7)   — arrive from ground-floor stair up
"""

from __future__ import annotations

from ..world.kobra_zone_loader import load_zone_from_kobra
from ..world.map import Realm, Zone, ZoneExit


# ── Dimensions ────────────────────────────────────────────────────────────────

GROUND_W, GROUND_H = 48, 13
UPPER_W,  UPPER_H  = 48, 10

# ── Room layout (48-wide ground floor) ───────────────────────────────────────
#   x=0:     west wall
#   x=1–11:  bedroom        (11 wide — matches original 44-wide aesthetic)
#   x=12:    bedroom/kitchen divider
#   x=13–28: kitchen        (16 wide — room for two furnaces + workbench)
#   x=29:    kitchen/meditation divider
#   x=30–46: meditation     (17 wide — altar + circulation space)
#   x=47:    east wall
#
#   Row 8:   inner dividing wall; doors at x=6 (bedroom), x=21 (kitchen), x=38 (meditation)
#   Row 10:  foyer counter x=4–43; passages at x=1–3 (west) and x=44–46 (east)
#   Row 12:  south wall; front door at x=23

# Canonical spawn positions (x, y)
GROUND_SPAWN: tuple[int, int] = (23, 11)   # centre foyer, south of counter
UPPER_SPAWN:  tuple[int, int] = (28, 7)    # arrive from stair up

# Beat-trigger tiles for FateKnocksScene.
# Counter at z=10; player approaches front door from z=11.
KNOCK_TILES:        frozenset[tuple[int, int]] = frozenset({(22, 11), (23, 11), (24, 11)})
COURIER_TILE:       tuple[int, int] = (23, 12)   # front door
BEDROOM_SPAWN:      tuple[int, int] = (5, 3)     # player wakes here in opening sequence
GROUND_STAIR_LAND:  tuple[int, int] = (11, 3)   # arrival tile when descending from upper floor


# ── Ground floor Kobra source ─────────────────────────────────────────────────

def _gen_ground_kobra() -> str:
    """
    Generate Kobra placement notation for the 48×13 ground floor.

    Structural walkability only — furniture and interactions defined separately.
    """
    W, H = GROUND_W, GROUND_H
    lines: list[str] = []

    FRONT_DOOR = (COURIER_TILE[0], H - 1)   # (23, 12)
    STAIR_UP   = (11, 2)                     # northeast corner of bedroom
    INNER_DOORS = {6, 21, 38}               # bedroom / kitchen / meditation doors
    DIVIDERS    = {12, 29}                   # room divider columns

    def is_wall(x: int, y: int) -> bool:
        if x == 0 or x == W - 1:
            return True
        if y == 0:
            return True
        if y == H - 1 and x != FRONT_DOOR[0]:
            return True
        if x in DIVIDERS and y <= 8:
            return True
        if y == 8 and x not in INNER_DOORS:
            return True
        return False

    for y in range(H):
        for x in range(W):
            coord = f"ground|{x},{y}"
            if is_wall(x, y):
                lines.append(f"{coord} : [Vo Ka]")
            elif (x, y) == GROUND_SPAWN:
                lines.append(f"{coord} : [Va Ha St]")
            elif (x, y) == STAIR_UP:
                lines.append(
                    f"{coord} : [Va Ha Ne north player_home_upper "
                    f"{UPPER_SPAWN[0]} {UPPER_SPAWN[1]} stairs_up]"
                )
            elif (x, y) == FRONT_DOOR:
                lines.append(
                    f"{coord} : [Va Ha Ne south lapidus_wiltoll_lane 3 8]"
                )
            else:
                lines.append(f"{coord} : [Va Ha]")

    return "\n".join(lines)


# ── Upper floor Kobra source ──────────────────────────────────────────────────

def _gen_upper_kobra() -> str:
    """
    Generate Kobra placement notation for the 48×10 upper floor (Study).

    Structural walkability only — bookshelves and workbenches are furniture.
    """
    W, H = UPPER_W, UPPER_H
    lines: list[str] = []

    STAIR_DOWN = (UPPER_SPAWN[0], H - 2)   # (28, 8)

    def is_wall(x: int, y: int) -> bool:
        return x == 0 or x == W - 1 or y == 0 or y == H - 1

    for y in range(H):
        for x in range(W):
            coord = f"upper|{x},{y}"
            if is_wall(x, y):
                lines.append(f"{coord} : [Vo Ka]")
            elif (x, y) == UPPER_SPAWN:
                lines.append(f"{coord} : [Va Ha St]")
            elif (x, y) == STAIR_DOWN:
                lines.append(
                    f"{coord} : [Va Ha Ne south player_home_ground "
                    f"{GROUND_STAIR_LAND[0]} {GROUND_STAIR_LAND[1]} stairs_down]"
                )
            else:
                lines.append(f"{coord} : [Va Ha]")

    return "\n".join(lines)


# ── Zone builders ─────────────────────────────────────────────────────────────

def build_ground_floor() -> Zone:
    """Build and return the canonical player_home_ground Zone."""
    return load_zone_from_kobra(
        source       = _gen_ground_kobra(),
        zone_id      = "player_home_ground",
        name         = "Player Home",
        realm        = Realm.LAPIDUS,
        player_spawn = GROUND_SPAWN,
    )


def build_upper_floor() -> Zone:
    """Build and return the canonical player_home_upper Zone."""
    return load_zone_from_kobra(
        source       = _gen_upper_kobra(),
        zone_id      = "player_home_upper",
        name         = "Player Home — Study",
        realm        = Realm.LAPIDUS,
        player_spawn = UPPER_SPAWN,
    )


# ── Cached singletons ─────────────────────────────────────────────────────────
#
# Built once at import time and shared across all consumers — FateKnocksGLPlay,
# navigable world, and test suites all get the same Zone instances.

PLAYER_HOME_GROUND: Zone = build_ground_floor()
PLAYER_HOME_UPPER:  Zone = build_upper_floor()
