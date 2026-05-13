"""
Mercurie Zones -- Ko's Labyrinth (7_KLGS)
==========================================
The Faewilds.  Gated by the hypnotic_meditation perk (quest 0007_KLST).

Two entry points from Lapidus:
  - Ocean shore at low tide  (lapidus_ocean_shore → mercurie_threshold)
  - Lapidus mines deepest level (not yet built — stub exit)

Zone topology:
  mercurie_threshold   ← liminal crossing point
      ↓ South  → lapidus_ocean_shore
      ↓ North  → tideglass / rootbloom
  tideglass            ← water/glass Fae zone
  cindergrove          ← ember/ash Fae zone
  rootbloom            ← inhabited Fae settlement (most approachable)
  thornveil            ← shrouded, hostile-leaning Fae zone
  dewspire             ← Fae Queen Amelia's domain (temple-like)

ASCII tile key (shared with lapidus.py, extended):
  ~  WATER     T  TREE   ,  GRASS
  .  FLOOR     #  WALL   F  FAELIGHT  (glowing floor, special)
  N  NPC       @  player spawn
"""

from __future__ import annotations
from ..map import Realm, Zone, ZoneExit, build_zone_from_ascii


# ── Mercurie Threshold ────────────────────────────────────────────────────────
#
# 52 wide × 14 tall.  Liminal space — the light bends here.
# Entry from south (ocean shore).  Exits north to tideglass and rootbloom.
# No NPC — the space itself is the event.
#
# Exits:
#   South (25,13)+(26,13) → lapidus_ocean_shore (24,1)+(25,1)
#   NW    (1,0)+(2,0)     → mercurie_tideglass (25,13)+(26,13)
#   NE    (49,0)+(50,0)   → mercurie_rootbloom (25,13)+(26,13)

_THRESHOLD_MAP = [
    "T" + ",," + "T" * 46 + ",,",  # row  0  exits to tideglass (1-2) and rootbloom (49-50)
    "," * 52,                       # row  1
    "," * 52,                       # row  2
    ",F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,,",  # row  3  faelight path
    "," * 52,                       # row  4
    ",F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,,",  # row  5
    "," * 52,                       # row  6
    "," * 52,                       # row  7
    ",F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,F,,",  # row  8
    "," * 52,                       # row  9
    "," * 52,                       # row 10
    "~" * 52,                       # row 11  tide-water below
    "~" * 52,                       # row 12
    "~" * 25 + ",," + "~" * 25,     # row 13  S exit at 25-26
]

_THRESHOLD_EXITS = [
    ZoneExit(x=25, y=13, direction="south",
             target_zone="lapidus_ocean_shore", target_x=24, target_y=1),
    ZoneExit(x=26, y=13, direction="south",
             target_zone="lapidus_ocean_shore", target_x=25, target_y=1),
    ZoneExit(x=1, y=0, direction="north",
             target_zone="mercurie_tideglass", target_x=25, target_y=13),
    ZoneExit(x=2, y=0, direction="north",
             target_zone="mercurie_tideglass", target_x=26, target_y=13),
    ZoneExit(x=49, y=0, direction="north",
             target_zone="mercurie_rootbloom", target_x=25, target_y=13),
    ZoneExit(x=50, y=0, direction="north",
             target_zone="mercurie_rootbloom", target_x=26, target_y=13),
]


def build_mercurie_threshold() -> Zone:
    return build_zone_from_ascii(
        zone_id = "mercurie_threshold",
        realm   = Realm.MERCURIE,
        name    = "Mercurie Threshold",
        rows    = _THRESHOLD_MAP,
        exits   = _THRESHOLD_EXITS,
    )


# ── Tideglass ─────────────────────────────────────────────────────────────────
#
# 40 wide × 16 tall.  Still water, glass light, water-Fae refracted.
# Exits: South → threshold, East → cindergrove, West → rootbloom

_TG_MAP = [
    "~" * 40,          # row  0
    "~" * 40,          # row  1
    "~" + "," * 38 + "~",  # row  2
    "~" + "," * 38 + "~",  # row  3
    "~" + "," * 38 + "~",  # row  4  (pool edges)
    "~" * 40,          # row  5
    "," * 40,          # row  6  S/E/W transition
    "," * 40,          # row  7
    ",F,,F,,F,,F,,F,,F,,F,,F,,F,,F,,F,,F,,F,,F,,F,,F,,F,",  # row 8 faelight path
    "," * 40,          # row  9
    "T" * 40,          # row 10
    "T" * 40,          # row 11
    "T" * 40,          # row 12
    "," * 18 + ",," + "," * 20,  # row 13
    "," * 18 + ",," + "," * 20,  # row 14
    "," * 40,          # row 15
]

_TG_EXITS = [
    ZoneExit(x=1,  y=15, direction="south",
             target_zone="mercurie_threshold", target_x=25, target_y=0),
    ZoneExit(x=2,  y=15, direction="south",
             target_zone="mercurie_threshold", target_x=26, target_y=0),
    ZoneExit(x=39, y=6, direction="east",
             target_zone="mercurie_cindergrove", target_x=1, target_y=6),
    ZoneExit(x=39, y=7, direction="east",
             target_zone="mercurie_cindergrove", target_x=1, target_y=7),
    ZoneExit(x=0,  y=6, direction="west",
             target_zone="mercurie_rootbloom", target_x=38, target_y=6),
    ZoneExit(x=0,  y=7, direction="west",
             target_zone="mercurie_rootbloom", target_x=38, target_y=7),
]


def build_tideglass() -> Zone:
    return build_zone_from_ascii(
        zone_id = "mercurie_tideglass",
        realm   = Realm.MERCURIE,
        name    = "Tideglass",
        rows    = _TG_MAP,
        exits   = _TG_EXITS,
    )


# ── Cindergrove ───────────────────────────────────────────────────────────────
#
# 40 wide × 16 tall.  Warm-barked ash trees, drifting embers.
# Exits: South → threshold, West → tideglass, East → thornveil

_CG_MAP = [
    "T" * 40,   # row  0
    "T" * 40,   # row  1
    "T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T",
    "T" + "," * 38 + "T",  # row  3
    "T" + "," * 38 + "T",  # row  4
    "T" + "," * 38 + "T",  # row  5
    "," * 40,               # row  6  W/E exits
    "," * 40,               # row  7
    "T" + "," * 38 + "T",  # row  8
    "T" + "," * 38 + "T",  # row  9
    "T" * 40,   # row 10
    "T" * 40,   # row 11
    "," * 40,   # row 12  S exits
    "," * 40,   # row 13
    "," * 40,   # row 14
    "," * 40,   # row 15
]

_CG_EXITS = [
    ZoneExit(x=0, y=6, direction="west",
             target_zone="mercurie_tideglass", target_x=38, target_y=6),
    ZoneExit(x=0, y=7, direction="west",
             target_zone="mercurie_tideglass", target_x=38, target_y=7),
    ZoneExit(x=39, y=6, direction="east",
             target_zone="mercurie_thornveil", target_x=1, target_y=6),
    ZoneExit(x=39, y=7, direction="east",
             target_zone="mercurie_thornveil", target_x=1, target_y=7),
    ZoneExit(x=19, y=15, direction="south",
             target_zone="mercurie_rootbloom", target_x=19, target_y=0),
    ZoneExit(x=20, y=15, direction="south",
             target_zone="mercurie_rootbloom", target_x=20, target_y=0),
]


def build_cindergrove() -> Zone:
    return build_zone_from_ascii(
        zone_id = "mercurie_cindergrove",
        realm   = Realm.MERCURIE,
        name    = "Cindergrove",
        rows    = _CG_MAP,
        exits   = _CG_EXITS,
    )


# ── Rootbloom ─────────────────────────────────────────────────────────────────
#
# 48 wide × 18 tall.  Fae settlement woven between tree roots.  Most approachable.
# Fae children, bioluminescent lanterns, genuine hospitality (if Fae relations allow).
# Exits: North → cindergrove, East → tideglass, South → threshold, NE → thornveil

_RB_MAP = [
    "T" * 12 + ",," * 2 + "T" * 8 + ",," * 2 + "T" * 16,  # row  0  N exits
    "T" + "F" * 46 + "T",   # row  1  faelight ring
    "T" + "," * 46 + "T",   # row  2
    "T" + ",#####,,,#####,,,#####,,,#####,,,#####,,," + "T",  # row  3  Fae structures
    "T" + ",#...#,,,#...#,,,#...#,,,#...#,,,#...#,,," + "T",  # row  4
    "T" + ",#...#,,,#...#,,,#...#,,,#...#,,,#...#,,," + "T",  # row  5
    "T" + ",#...#,,,#...#,,,#...#,,,#...#,,,#...#,,," + "T",  # row  6
    "T" + ",#...N,,,#...#,,,#...#,,,#...#,,,#...#,,," + "T",  # row  7  NPC in first hut
    "T" + ",#####,,,#####,,,#####,,,#####,,,#####,,," + "T",  # row  8
    "T" + "," * 46 + "T",   # row  9  central path
    "T" + "@" + "," * 45 + "T",  # row 10  player spawn
    "T" + "," * 46 + "T",   # row 11
    "T" * 48,                # row 12
    "T" * 48,                # row 13
    "," * 48,                # row 14  S/E/W exits
    "," * 48,                # row 15
    "," * 48,                # row 16
    "," * 48,                # row 17
]

_RB_EXITS = [
    ZoneExit(x=12, y=0, direction="north",
             target_zone="mercurie_cindergrove", target_x=19, target_y=14),
    ZoneExit(x=13, y=0, direction="north",
             target_zone="mercurie_cindergrove", target_x=20, target_y=14),
    ZoneExit(x=0,  y=14, direction="west",
             target_zone="mercurie_tideglass", target_x=38, target_y=6),
    ZoneExit(x=0,  y=15, direction="west",
             target_zone="mercurie_tideglass", target_x=38, target_y=7),
    ZoneExit(x=23, y=17, direction="south",
             target_zone="mercurie_threshold", target_x=49, target_y=0),
    ZoneExit(x=24, y=17, direction="south",
             target_zone="mercurie_threshold", target_x=50, target_y=0),
    ZoneExit(x=47, y=14, direction="east",
             target_zone="mercurie_thornveil", target_x=1, target_y=6),
    ZoneExit(x=47, y=15, direction="east",
             target_zone="mercurie_thornveil", target_x=1, target_y=7),
]

# Rootbloom has a Fae Elder NPC — placeholder ID for now; will be assigned
# from the full kos_labyrnth.py registry during authoring.
_RB_NPCS: list[str] = []


def build_rootbloom() -> Zone:
    return build_zone_from_ascii(
        zone_id = "mercurie_rootbloom",
        realm   = Realm.MERCURIE,
        name    = "Rootbloom",
        rows    = _RB_MAP,
        exits   = _RB_EXITS,
        npc_ids = _RB_NPCS,
    )


# ── Thornveil ────────────────────────────────────────────────────────────────
#
# 40 wide × 14 tall.  Deliberate thorned bramble — Fae warning-and-wall.
# Hostile-leaning if Fae relations are poor; navigable if Rootbloom quest active.
# Exits: West → cindergrove, South → rootbloom, North → dewspire

_TV_MAP = [
    "#" * 40,                      # row  0  thorn wall (impassable until quested)
    "#" + "," * 38 + "#",          # row  1
    "#" + "," * 38 + "#",          # row  2
    "#" + "," * 38 + "#",          # row  3
    "#" + "," * 38 + "#",          # row  4
    "#" + "," * 38 + "#",          # row  5
    "," * 40,                      # row  6  W/E passable
    "," * 40,                      # row  7
    "#" + "," * 38 + "#",          # row  8
    "#" + "," * 38 + "#",          # row  9
    "#" * 18 + ",," + "#" * 20,    # row 10  S exit gap
    "," * 18 + ",," + "," * 20,    # row 11
    "#" * 18 + ",," + "#" * 20,    # row 12  N exit gap
    "," * 18 + ",," + "," * 20,    # row 13
]

_TV_EXITS = [
    ZoneExit(x=0, y=6, direction="west",
             target_zone="mercurie_cindergrove", target_x=38, target_y=6),
    ZoneExit(x=0, y=7, direction="west",
             target_zone="mercurie_cindergrove", target_x=38, target_y=7),
    ZoneExit(x=18, y=11, direction="south",
             target_zone="mercurie_rootbloom", target_x=46, target_y=14),
    ZoneExit(x=19, y=11, direction="south",
             target_zone="mercurie_rootbloom", target_x=47, target_y=14),
    ZoneExit(x=18, y=13, direction="north",
             target_zone="mercurie_dewspire", target_x=19, target_y=11),
    ZoneExit(x=19, y=13, direction="north",
             target_zone="mercurie_dewspire", target_x=20, target_y=11),
]


def build_thornveil() -> Zone:
    return build_zone_from_ascii(
        zone_id = "mercurie_thornveil",
        realm   = Realm.MERCURIE,
        name    = "Thornveil",
        rows    = _TV_MAP,
        exits   = _TV_EXITS,
    )


# ── Dewspire ──────────────────────────────────────────────────────────────────
#
# 40 wide × 14 tall.  Sacred Fae spire — Fae Queen Amelia's domain.
# At the crown of the oldest tree, dewdrops held in permanent suspension.
# Amelia (1004_NYMP) is present here — key NPC for quest 0013_KLST.
# Exits: South → thornveil

_DS_MAP = [
    "," * 16 + "FFFFFFFF" + "," * 16,   # row  0  spire peak (faelight)
    "," * 14 + "FFFFFFFFFFFF" + "," * 14,  # row  1
    "," * 12 + "FFFFFFFFFFFFFFFF" + "," * 12,  # row  2
    "," * 10 + "FFFFFFFFFFFFFFFFFFFF" + "," * 10,  # row  3
    "," * 10 + "FFFFFFNFFFFFFFFFFFFF" + "," * 10,  # row  4  Amelia NPC
    "," * 10 + "FFFFFFFFFFFFFFFFFFFF" + "," * 10,  # row  5
    "," * 12 + "FFFFFFFFFFFFFFFF" + "," * 12,  # row  6
    "," * 14 + "FFFFFFFFFFFF" + "," * 14,  # row  7
    "," * 16 + "FFFFFFFF" + "," * 16,  # row  8
    "," * 40,               # row  9
    "," * 40,               # row 10
    "," * 19 + ",," + "," * 19,  # row 11  S exits
    "," * 40,               # row 12
    "," * 40,               # row 13
]

_DS_EXITS = [
    ZoneExit(x=19, y=11, direction="south",
             target_zone="mercurie_thornveil", target_x=18, target_y=12),
    ZoneExit(x=20, y=11, direction="south",
             target_zone="mercurie_thornveil", target_x=19, target_y=12),
]

_DS_NPCS = ["1004_NYMP"]   # Fae Queen Amelia — quest 0013_KLST fulcrum


def build_dewspire() -> Zone:
    return build_zone_from_ascii(
        zone_id = "mercurie_dewspire",
        realm   = Realm.MERCURIE,
        name    = "Dewspire",
        rows    = _DS_MAP,
        exits   = _DS_EXITS,
        npc_ids = _DS_NPCS,
    )
