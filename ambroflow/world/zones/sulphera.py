"""
Sulphera Zones -- Ko's Labyrinth (7_KLGS)
==========================================
The Underworld.  Gated by the infernal_meditation perk (quest 0010_KLST).

Entry: via meditation (BreathOfKo dream sequence → Visitor Ring).
Exit: Visitor Ring → meditation back to surface.

Ring structure (7 sin rings + Visitor Ring + Royal Ring):
  visitor_ring          Entry hub, safe rest, waypoints, Sulphera market
  pride_ring_entry      Pride Ring approach (pentagram city, Lucifer's castle)
  greed_ring_entry      Greed Ring approach (counting house foyer)
  envy_ring_entry       Envy Ring approach
  gluttony_ring_entry   Gluttony Ring approach (banquet smell)
  sloth_ring_entry      The Sitting Place (genuine rest zone)
  wrath_ring_entry      Wrath threshold
  lust_ring_entry       Lust Ring approach (largest ring)
  royal_ring            Accessible after Asmodeus's blessing (quest 0036_KLST)

Individual dungeon areas within each ring are handled by the dungeon generator.
These zone definitions are the navigable overworld layer of each ring.

ASCII tile key:
  .  FLOOR     #  WALL    D  DARK_STONE
  S  SULPHUR_STONE        F  FAELIGHT (used here for infernal glow)
  N  NPC       @  player spawn
  ~  WATER (brimstone pools)
"""

from __future__ import annotations
from ..map import Realm, Zone, ZoneExit, build_zone_from_ascii


# ── Visitor Ring ──────────────────────────────────────────────────────────────
#
# 60 wide × 20 tall.
# The entry ring — safe, inhabited by demons running stalls.
# Waypoint stones provide the meditation return to surface.
# Seven radial exits to each sin ring.
#
# Exits (seven ring exits + no surface exit — meditation only):
#   Ring exits are arranged radially around the ring hub.

_VR_MAP = [
    "D" * 60,                          # row  0
    "D" + "." * 58 + "D",              # row  1
    "D" + "." * 58 + "D",              # row  2
    "D" + ".N.." + "." * 50 + "..N.D", # row  3  Sulphera market vendors
    "D" + "." * 58 + "D",              # row  4
    "D" + "." * 4 + "SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS" + "." * 4 + "D",  # row  5
    "D" + "." * 4 + "S" + "." * 48 + "S" + "." * 4 + "D",  # row  6  waypoint ring
    "D" + "." * 4 + "S" + "." * 48 + "S" + "." * 4 + "D",  # row  7
    "D" + "." * 4 + "S" + ".....F....F....F....F....F....F....F....." + "S" + "." * 4 + "D",  # row 8
    "D" + "." * 4 + "S" + "." * 48 + "S" + "." * 4 + "D",  # row  9
    "D" + "." * 4 + "S" + "." * 20 + "@" + "." * 27 + "S" + "." * 4 + "D",  # row 10  spawn
    "D" + "." * 4 + "S" + "." * 48 + "S" + "." * 4 + "D",  # row 11
    "D" + "." * 4 + "S" + "." * 48 + "S" + "." * 4 + "D",  # row 12
    "D" + "." * 4 + "SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS" + "." * 4 + "D",  # row 13
    "D" + "." * 58 + "D",              # row 14
    "D" + "." * 58 + "D",              # row 15
    "D" + "." * 58 + "D",              # row 16
    # Exits to rings at row 17: 7 gaps spread across the row
    "D.." + "DD" * 5 + ".." + "DD" * 5 + ".." + "DD" * 5 + ".." + "DD" * 5 + ".." + "DD" * 5 + ".." + "DD" * 5 + ".." + "DD" * 3 + "D",
    "D" + "." * 58 + "D",              # row 18
    "D" * 60,                          # row 19
]

# Ring entry positions along row 17
_RING_EXIT_COLS = [3, 13, 23, 33, 43, 53, 56]
_RING_TARGET_ZONES = [
    "sulphera_pride_entry",
    "sulphera_greed_entry",
    "sulphera_envy_entry",
    "sulphera_gluttony_entry",
    "sulphera_sloth_entry",
    "sulphera_wrath_entry",
    "sulphera_lust_entry",
]

_VR_EXITS = []
for _col, _target in zip(_RING_EXIT_COLS, _RING_TARGET_ZONES):
    _VR_EXITS += [
        ZoneExit(x=_col,   y=17, direction="south", target_zone=_target, target_x=5, target_y=0),
        ZoneExit(x=_col+1, y=17, direction="south", target_zone=_target, target_x=6, target_y=0),
    ]

_VR_NPCS = []   # Market vendor NPCs assigned in Atelier authoring


def build_visitor_ring() -> Zone:
    return build_zone_from_ascii(
        zone_id = "sulphera_visitor_ring",
        realm   = Realm.SULPHERA,
        name    = "The Visitor Ring",
        rows    = _VR_MAP,
        exits   = _VR_EXITS,
        npc_ids = _VR_NPCS,
    )


# ── Ring entry zones ──────────────────────────────────────────────────────────
#
# Each ring gets a simple 20 wide × 10 tall entry zone.
# These are the atmospheric threshold spaces — non-combat unless the BSP dungeon
# generator is invoked from within the zone.
#
# Structure: open floor with atmospheric description tile (D=dark stone),
# North exit back to Visitor Ring, South exit to dungeon areas (handled separately).

def _ring_entry(
    zone_id:   str,
    name:      str,
    vr_col:    int,         # column in Visitor Ring to return to
    desc_row:  str = "",
    has_npc:   str = "",
) -> Zone:
    dr = desc_row if desc_row else "D" + "." * 18 + "D"
    rows = [
        "D" + ".." + "D" * 16,
        "D" + "." * 18 + "D",
        "D" + "." * 18 + "D",
        "D" + "." * 18 + "D",
        dr,
        "D" + "." * 6 + "@" + "." * 11 + "D",
        "D" + "." * 18 + "D",
        "D" + "." * 18 + "D",
        "D" + "." * 18 + "D",
        "D" * 20,
    ]
    exits = [
        ZoneExit(x=1, y=0, direction="north",
                 target_zone="sulphera_visitor_ring", target_x=vr_col,   target_y=16),
        ZoneExit(x=2, y=0, direction="north",
                 target_zone="sulphera_visitor_ring", target_x=vr_col+1, target_y=16),
    ]
    npc_ids = [has_npc] if has_npc else []
    return build_zone_from_ascii(
        zone_id = zone_id,
        realm   = Realm.SULPHERA,
        name    = name,
        rows    = rows,
        exits   = exits,
        npc_ids = npc_ids,
    )


def build_sulphera_ring_entries() -> list[Zone]:
    """Return entry zones for the seven sin rings plus the Royal Ring."""
    ring_specs = [
        ("sulphera_pride_entry",    "Pride Ring — Promenade",              _RING_EXIT_COLS[0], "D.F.F.F.F.F.F.F.F.D"),
        ("sulphera_greed_entry",    "Greed Ring — Counting House Foyer",   _RING_EXIT_COLS[1], "D.S.S.S.S.S.S.S.S.D"),
        ("sulphera_envy_entry",     "Envy Ring — Approach",                _RING_EXIT_COLS[2], ""),
        ("sulphera_gluttony_entry", "Gluttony Ring — Banquet Approach",    _RING_EXIT_COLS[3], ""),
        ("sulphera_sloth_entry",    "The Sitting Place",                   _RING_EXIT_COLS[4], "D.F..F..F..F..F..F.D"),
        ("sulphera_wrath_entry",    "Wrath Ring — Threshold",              _RING_EXIT_COLS[5], "D" + "~" * 18 + "D"),
        ("sulphera_lust_entry",     "Lust Ring — Outer Approach",          _RING_EXIT_COLS[6], "D.F.F.F.F.F.F.F.F.D"),
    ]
    zones = [_ring_entry(zid, nm, col, dr) for zid, nm, col, dr in ring_specs]

    # Royal Ring — accessible after Asmodeus's blessing (quest 0036_KLST).
    # No Visitor Ring exit; entered via quest event only.
    # Hypatia is here (as demoness); Drovitth stands at the Orrery.
    royal_rows = [
        "D" + ".." + "D" * 16,
        "D" + "." * 18 + "D",
        "D" + ".F.F.F.F.F.F.F.F." + "D",
        "D" + "." * 18 + "D",
        "D" + "." * 18 + "D",
        "D" + "." * 6 + "@" + "." * 11 + "D",
        "D" + "." * 18 + "D",
        "D" + ".N.............N.." + "D",   # Hypatia left, Drovitth right
        "D" + "." * 18 + "D",
        "D" * 20,
    ]
    royal = build_zone_from_ascii(
        zone_id = "sulphera_royal_ring",
        realm   = Realm.SULPHERA,
        name    = "The Royal Ring",
        rows    = royal_rows,
        exits   = [],   # entered via quest event; no tile exit
        npc_ids = ["0000_0451", "1018_DJNN"],  # Hypatia (demoness form), Drovitth
    )
    zones.append(royal)
    return zones
