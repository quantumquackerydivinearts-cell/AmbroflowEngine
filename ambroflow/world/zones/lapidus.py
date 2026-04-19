"""
Lapidus Zones — Game 7 Starter World
=====================================
Authored zones for the opening area of Ko's Labyrinth (7_KLGS).

Zones
-----
  lapidus_wiltoll_ext  — Wiltoll Lane exterior.  Player's home street in
                         Azonithia.  Starting zone.  Three residential buildings
                         on each side of the main road.  East exit leads toward
                         the city market district.
  lapidus_market       — Market district stub.  A single covered stall row and
                         the road returning west to Wiltoll Lane.

Tile key (ASCII authoring format)
----------------------------------
  #  WALL          .  FLOOR (interior)   +  DOOR
  ,  GRASS         =  ROAD               D  DIRT
  ~  WATER         /  BRIDGE             ^  STAIRS_UP
  v  STAIRS_DOWN   P  PORTAL             E  DUNGEON_ENTRANCE
  @  player spawn (→ FLOOR + spawn record)
  N  NPC spawn    (→ FLOOR + NPC record, matched to npc_ids list in order)
"""

from __future__ import annotations

from ..map import Realm, Zone, ZoneExit, build_zone_from_ascii


# ── Wiltoll Lane exterior ─────────────────────────────────────────────────────
#
# 36 wide × 18 tall.
# Three buildings north of the road, three south (player home = left/south).
# Main road (rows 8–9) runs east–west.  Exit east at col 35, rows 8–9.
# North / south perimeter is open grass — no exits (nowhere to go yet).
#
# Player spawn: row 13, col 3 (inside player home, south-left building)
# NPC slots marked N are placeholders — IDs assigned when characters are authored.

_WILTOLL_MAP = [
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 0
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 1
    ",######,,,,#########,,,,,######,,,,,",  # row 2  north buildings
    ",#....#,,,,#.......#,,,,,#....#,,,,,",  # row 3
    ",#....#,,,,#.......#,,,,,#....#,,,,,",  # row 4
    ",#....#,,,,#.......#,,,,,#....#,,,,,",  # row 5
    ",#++..#,,,,#++.....#,,,,,#++..#,,,,,",  # row 6  double-doors face road
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 7  grass verge
    "====================================",  # row 8  main road (exit east col 35)
    "====================================",  # row 9
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 10 grass verge
    ",######,,,,#########,,,,,######,,,,,",  # row 11 south buildings
    ",#....#,,,,#.......#,,,,,#....#,,,,,",  # row 12
    ",#.@..#,,,,#.......#,,,,,#....#,,,,,",  # row 13 player home / @ spawn
    ",#....#,,,,#.......#,,,,,#....#,,,,,",  # row 14
    ",#++..#,,,,#++.....#,,,,,#++..#,,,,,",  # row 15 double-doors face road
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 16
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 17
]

_WILTOLL_EXITS = [
    # East road exits (both road rows) → market district
    ZoneExit(x=35, y=8, direction="east",
             target_zone="lapidus_market", target_x=1, target_y=2),
    ZoneExit(x=35, y=9, direction="east",
             target_zone="lapidus_market", target_x=1, target_y=3),
]

_WILTOLL_NPCS: list[str] = []   # populated when Wiltoll Lane characters are authored


def build_wiltoll_lane() -> Zone:
    return build_zone_from_ascii(
        zone_id  = "lapidus_wiltoll_ext",
        realm    = Realm.LAPIDUS,
        name     = "Wiltoll Lane",
        rows     = _WILTOLL_MAP,
        exits    = _WILTOLL_EXITS,
        npc_ids  = _WILTOLL_NPCS,
    )


# ── Market district (stub) ────────────────────────────────────────────────────
#
# 20 wide × 10 tall.
# A single covered stall row and the connecting road back west.
# West road exits return to Wiltoll Lane.
# Player enters from east side of Wiltoll Road, spawns at col 1, row 2–3.

_MARKET_MAP = [
    ",,,,,,,,,,,,,,,,,,,,",  # row 0
    ",###################",  # row 1  market hall north wall
    ",#.@..............#",  # row 2  market hall interior, player spawn @ col 2
    ",#................#",  # row 3  stalls (NPC slots added when characters are authored)
    ",###################",  # row 4  market hall south wall
    ",,,,,,,,,,,,,,,,,,,,",  # row 5  grass
    ",,,,,,,,,,,,,,,,,,,,",  # row 6
    "====================",  # row 7  road (west exit row 7–8)
    "====================",  # row 8
    ",,,,,,,,,,,,,,,,,,,,",  # row 9
]

_MARKET_EXITS = [
    # West road exits → Wiltoll Lane road
    ZoneExit(x=0, y=7, direction="west",
             target_zone="lapidus_wiltoll_ext", target_x=34, target_y=8),
    ZoneExit(x=0, y=8, direction="west",
             target_zone="lapidus_wiltoll_ext", target_x=34, target_y=9),
]

_MARKET_NPCS: list[str] = []    # populated when market characters are authored


def build_market_district() -> Zone:
    return build_zone_from_ascii(
        zone_id  = "lapidus_market",
        realm    = Realm.LAPIDUS,
        name     = "Market District",
        rows     = _MARKET_MAP,
        exits    = _MARKET_EXITS,
        npc_ids  = _MARKET_NPCS,
    )