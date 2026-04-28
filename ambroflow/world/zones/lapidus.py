"""
Lapidus Zones — Ko's Labyrinth (7_KLGS)
=========================================
Authored zones for the surface world of Azonithia.

Zone topology (West → East):
  lapidus_castle_azoth          Castle Azoth courtyard (Stelladeva family home,
                                Royal Lottery seat, Alfir's workplace).
                                Zodiac fountain — runs on solstices/equinoxes.
         ↕ North (marble sprint)
  lapidus_azoth_approach        Orchard approach + Azoth Sprint (marble).
  lapidus_azonithia_heartvein   Azonithia Avenue — Youthspring Road inlet (silica)
                                → Heartvein Heights, noble residential.
  lapidus_azonithia_temple      Azonithia Avenue — Goldshoot Street inlet (slate)
                                → Temple of the Gods.
  lapidus_azonithia_market      Azonithia Avenue — June Street inlet (ceramic)
                                → Market district.
  lapidus_azonithia_slum        Azonithia Avenue — Hopefare Street inlet (yellow brick)
                                → Azonithia Slum (9 warrens, 13 passages).
  lapidus_wiltoll_lane          Wiltoll Lane — player home.  Litleaf fork North.
                                Mt. Elaene trail East.  Starting zone.
         ↕ North (Litleaf fork)
  lapidus_litleaf_thoroughfare  N–S road connecting Wiltoll to Hopefare Street.
         ↕ East
  lapidus_mt_elaene_trail       Forest edge trail toward Mt. Elaene (stub).

Unimplemented targets (show "(nothing that way yet)" in-game):
  lapidus_dirt_trail            West of Castle Azoth — ocean-bound dirt caravan trail.
  lapidus_slum_interior         Azonithia Slum (9 warrens / 13 passages).
  lapidus_market_interior       Market district interior.
  lapidus_temple_interior       Temple of the Gods interior.
  lapidus_heartvein_interior    Heartvein Heights residential district.
  lapidus_mt_elaene_summit      Mt. Elaene summit / Elaene desert gateway.

ASCII tile key
--------------
  #  WALL          .  FLOOR          +  DOOR
  ,  GRASS         =  ROAD           D  DIRT
  S  STONE         ~  WATER          T  TREE (impassable)
  M  MARBLE        Y  YELLOW_BRICK   C  CERAMIC
  L  SLATE         X  SILICA
  @  player spawn (→ FLOOR)
  N  NPC spawn    (→ FLOOR, matched to npc_ids in order)
"""

from __future__ import annotations

from ..map import Realm, Zone, ZoneExit, ItemSpawn, build_zone_from_ascii


# ── Vendor catalogs ───────────────────────────────────────────────────────────
#
# Maps character_id → {item_id: coin_price}.
# Referenced by WorldPlay to open vendor mode on NPC interaction.

VENDOR_CATALOGS: dict[str, dict[str, int]] = {
    "0005_TOWN": {   # home apothecary (Wiltoll Lane home)
        "0073_KLOB": 5,    # Herb (Common)
        "0074_KLOB": 8,    # Herb (Restorative)
        "0040_KLOB": 3,    # Water Flask
        "0075_KLOB": 12,   # Binding Wax
        "0001_KLOB": 80,   # Mortar
        "0002_KLOB": 40,   # Pestle
        "0007_KLOB": 25,   # Reagent Bottle
    },
    "0006_TOWN": {   # general market vendor (June Street)
        "0073_KLOB": 5,
        "0074_KLOB": 8,
        "0040_KLOB": 3,
        "0075_KLOB": 12,
        "0076_KLOB": 60,   # Raw Desire Stone
        "0077_KLOB": 90,   # Asmodean Essence
    },
    "0007_TOWN": {   # herb specialist (June Street)
        "0073_KLOB": 4,
        "0074_KLOB": 6,
        "0075_KLOB": 10,
    },
}


# ── Wiltoll Lane ──────────────────────────────────────────────────────────────
#
# 60 wide × 22 tall.
# Sparse, lush green avenue — player home at the quiet East end of the city.
# Mt. Elaene is the constant background presence at the East.
#
# Road rows 10–11 (East–West, Azonithia axis).
# Litleaf Thoroughfare fork: cols 11–12, rows 0–9 (perpendicular road going North).
# Player home: cols 1–9, rows 13–18 (South of road, door in N wall at cols 3–4).
# Player spawns at (3,12) on the south verge, facing the home entrance.
# Dense woodland: rows 19–21 (South).
#
# Exits:
#   West  (0,10)+(0,11)   → lapidus_azonithia_slum      (46,5)+(46,6)
#   East  (59,10)+(59,11) → lapidus_mt_elaene_trail      (1,6)+(1,7)
#   North (11,0)+(12,0)   → lapidus_litleaf_thoroughfare (0,18)+(1,18)
#   South (3,12)+(4,12)   → lapidus_wiltoll_home         (20,1)+(21,1)

_WILTOLL_MAP = [
    #          1111111111222222222233333333334444444444555555555566
    # 0123456789012345678901234567890123456789012345678901234567890
    ",,,,,,,,,,,==,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  0  N exit Litleaf 11-12
    ",,,,,,,,,,,==,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  1
    ",,T,,,,,,,,==,,,,T,,,,,T,,,,,,T,,,,,T,,,,,,,,T,,,,,,T,,,,,,,",  # row  2  sparse trees N
    ",,T,,,,,,,,==,,,,T,,,,,T,,,,,,T,,,,,T,,,,,,,,T,,,,,,T,,,,,,,",  # row  3
    ",,,,,,,,,,,==,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  4  clearing
    ",,,,,,,,,,,==,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  5
    ",,,,,,,,,,,==,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  6
    ",,,,,,,,,,,==,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  7
    ",,,,,,,,,,,==,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  8
    ",,,,,,,,,,,==,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  9
    "============================================================",  # row 10  main road W/E exits
    "============================================================",  # row 11
    ",,,@,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 12  S verge — player spawn @(3,12)
    ",##++#####,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 13  home N facade, door at cols 3-4
    ",#.......#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 14
    ",#.......#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 15
    ",#.......#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 16
    ",#.......#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 17
    ",#.......#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 18  solid S wall
    ",,,TTTT,,,,,,,TTT,,,,TTT,,,,,,TTTTT,,,,,,TTT,,,,,,TTT,,,,,,,",  # row 19  sparse trees S
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",  # row 20  forest wall
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",  # row 21
]

_WILTOLL_EXITS = [
    # West road exits → Azonithia Avenue (slum section)
    ZoneExit(x= 0, y=10, direction="west",
             target_zone="lapidus_azonithia_slum", target_x=46, target_y=5),
    ZoneExit(x= 0, y=11, direction="west",
             target_zone="lapidus_azonithia_slum", target_x=46, target_y=6),
    # East road exits → Mt. Elaene forest trail
    ZoneExit(x=59, y=10, direction="east",
             target_zone="lapidus_mt_elaene_trail", target_x=1, target_y=6),
    ZoneExit(x=59, y=11, direction="east",
             target_zone="lapidus_mt_elaene_trail", target_x=1, target_y=7),
    # North fork exits → Litleaf Thoroughfare
    ZoneExit(x=11, y=0, direction="north",
             target_zone="lapidus_litleaf_thoroughfare", target_x=0, target_y=18),
    ZoneExit(x=12, y=0, direction="north",
             target_zone="lapidus_litleaf_thoroughfare", target_x=1, target_y=18),
    # South verge → player home interior
    ZoneExit(x=3, y=12, direction="south",
             target_zone="lapidus_wiltoll_home", target_x=20, target_y=1),
    ZoneExit(x=4, y=12, direction="south",
             target_zone="lapidus_wiltoll_home", target_x=21, target_y=1),
]


def build_wiltoll_lane() -> Zone:
    return build_zone_from_ascii(
        zone_id = "lapidus_wiltoll_lane",
        realm   = Realm.LAPIDUS,
        name    = "Wiltoll Lane",
        rows    = _WILTOLL_MAP,
        exits   = _WILTOLL_EXITS,
    )


# ── Player Home Interior (Wiltoll Lane) ───────────────────────────────────────
#
# 40 wide × 13 tall.
# Entered from the north facade door of the home on Wiltoll Lane.
# Three back rooms (Bedroom / Kitchen / Meditation) accessed via the Foyer.
#
# Layout:
#   rows 0–3  Foyer — entrance hall, vendor NPC (0005_TOWN)
#   row 4     Inner dividing wall with room openings at cols 5, 19, 33
#   rows 5–11 Three rooms: Bedroom (cols 1–10), Kitchen (cols 12–25),
#             Meditation (cols 27–38)
#   row 12    South wall
#
# Player spawns at (8, 2) just inside the north door.
# ItemSpawns in the Kitchen provide starter alchemy apparatus and materials.
#
# Exits:
#   North (20,0)+(21,0) → lapidus_wiltoll_lane (3,12)+(4,12)

_HOME_ROOM_ROW = (
    "#" + "." * 10 + "#" + "." * 14 + "#" + "." * 12 + "#"
)  # 40 chars: Bedroom(1-10) | Kitchen(12-25) | Meditation(27-38)

_HOME_MAP = [
    #          1111111111222222222233333333334
    # 0123456789012345678901234567890123456789
    "#" * 20 + "++" + "#" * 18,          # row  0: N wall, door at cols 20-21
    "#" + "." * 38 + "#",                 # row  1: foyer
    "#" + "." * 7 + "@" + "." * 6 + "N" + "." * 23 + "#",  # row  2: @(8,2), N(15,2)
    "#" + "." * 38 + "#",                 # row  3: foyer
    "#####.#####" + "#" + "#######.######" + "#" + "######.#####" + "#",  # row  4: inner wall
    _HOME_ROOM_ROW,                       # row  5
    _HOME_ROOM_ROW,                       # row  6
    _HOME_ROOM_ROW,                       # row  7
    _HOME_ROOM_ROW,                       # row  8
    _HOME_ROOM_ROW,                       # row  9
    _HOME_ROOM_ROW,                       # row 10
    _HOME_ROOM_ROW,                       # row 11
    "#" * 40,                             # row 12: S wall
]

_HOME_EXITS = [
    ZoneExit(x=20, y=0, direction="north",
             target_zone="lapidus_wiltoll_lane", target_x=3, target_y=12),
    ZoneExit(x=21, y=0, direction="north",
             target_zone="lapidus_wiltoll_lane", target_x=4, target_y=12),
]

_HOME_NPC_IDS = ["0005_TOWN"]   # home apothecary vendor

# Kitchen apparatus and starter materials (all within Kitchen cols 12-25, rows 5-11)
_HOME_ITEM_SPAWNS = [
    ItemSpawn(x=13, y=5,  item_id="0001_KLOB", qty=1),   # Mortar
    ItemSpawn(x=14, y=5,  item_id="0002_KLOB", qty=1),   # Pestle
    ItemSpawn(x=13, y=6,  item_id="0004_KLOB", qty=1),   # Retort Stand
    ItemSpawn(x=14, y=6,  item_id="0005_KLOB", qty=1),   # Retort
    ItemSpawn(x=13, y=7,  item_id="0007_KLOB", qty=1),   # Reagent Bottle
    ItemSpawn(x=16, y=5,  item_id="0010_KLOB", qty=1),   # Furnace
    ItemSpawn(x=17, y=5,  item_id="0017_KLOB", qty=1),   # Crucible
    ItemSpawn(x=18, y=5,  item_id="0019_KLOB", qty=1),   # Jar
    ItemSpawn(x=20, y=5,  item_id="0073_KLOB", qty=3),   # Herb (Common) ×3
    ItemSpawn(x=20, y=6,  item_id="0074_KLOB", qty=2),   # Herb (Restorative) ×2
    ItemSpawn(x=21, y=5,  item_id="0040_KLOB", qty=2),   # Water Flask ×2
    ItemSpawn(x=3,  y=2,  item_id="0016_KLIT", qty=50),  # Coins ×50 (in foyer chest)
]


def build_wiltoll_home() -> Zone:
    return build_zone_from_ascii(
        zone_id     = "lapidus_wiltoll_home",
        realm       = Realm.LAPIDUS,
        name        = "Wiltoll Home — Interior",
        rows        = _HOME_MAP,
        exits       = _HOME_EXITS,
        npc_ids     = _HOME_NPC_IDS,
        item_spawns = _HOME_ITEM_SPAWNS,
    )


# ── Litleaf Thoroughfare ──────────────────────────────────────────────────────
#
# 20 wide × 20 tall.  North–South road connecting Wiltoll Lane to Hopefare St.
# The road (cols 0–1) runs the full height.
# Player arrives from Wiltoll at (0,18)+(1,18) and walks North.
#
# Exits:
#   South (0,19)+(1,19) → lapidus_wiltoll_lane (11,1)+(12,1)
#   North (0,0)+(1,0)   → lapidus_slum_interior (stub)

_LITLEAF_MAP = [
    "==" + "," * 18,  # row  0  N exit (stub to slum interior)
    "==" + "," * 18,  # row  1
    "==" + "," * 18,  # row  2
    "==" + "," * 18,  # row  3
    "==" + "," * 18,  # row  4
    "==" + "," * 18,  # row  5
    "==" + "," * 18,  # row  6
    "==" + "," * 18,  # row  7
    "==" + "," * 18,  # row  8
    "==" + "," * 18,  # row  9
    "==" + "," * 18,  # row 10
    "==" + "," * 18,  # row 11
    "==" + "," * 18,  # row 12
    "==" + "," * 18,  # row 13
    "==" + "," * 18,  # row 14
    "==" + "," * 18,  # row 15
    "==" + "," * 18,  # row 16
    "==" + "," * 18,  # row 17
    "==" + "," * 18,  # row 18  player arrives from Wiltoll
    "==" + "," * 18,  # row 19  S exit → Wiltoll
]

_LITLEAF_EXITS = [
    ZoneExit(x=0, y=19, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=11, target_y=1),
    ZoneExit(x=1, y=19, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=12, target_y=1),
    ZoneExit(x=0, y=0, direction="north",
             target_zone="lapidus_slum_interior", target_x=10, target_y=18),
    ZoneExit(x=1, y=0, direction="north",
             target_zone="lapidus_slum_interior", target_x=11, target_y=18),
]


def build_litleaf_thoroughfare() -> Zone:
    return build_zone_from_ascii(
        zone_id = "lapidus_litleaf_thoroughfare",
        realm   = Realm.LAPIDUS,
        name    = "Litleaf Thoroughfare",
        rows    = _LITLEAF_MAP,
        exits   = _LITLEAF_EXITS,
    )


# ── Azonithia Avenue sections ─────────────────────────────────────────────────
#
# Each section is 48 wide × 16 tall with a common structure:
#
#   rows 0–4   North side — city district access, inlet street tiles
#   rows 5–6   Azonithia Avenue main road (ROAD = `=`, 48 tiles wide)
#   row  7     Southern grass verge
#   row  8     Sparse tree scattering (South)
#   rows 9–15  Dense forest wall (South) — woodland constant along full avenue
#
# Each section has a side-street inlet at cols 22–23, rows 0–4, using the
# paving material that marks that district's character.
#
# East→West paving hierarchy visible to the player who reads the ground:
#   Hopefare (yellow brick) → June (ceramic) → Goldshoot (slate) →
#   Youthspring (silica) → Azoth Sprint (marble) → dirt trail (ocean-bound)


def _avenue_forest_rows() -> list[str]:
    """Six rows of dense woodland South of the road."""
    sparse = ",,,,T,,,,,T,,,,,T,,,,,T,,,,,T,,,,,T,,,,,T,,,,,T"
    solid  = "T" * 48
    return [
        "," * 48,   # row  7  S verge
        sparse,     # row  8  sparse trees
        solid,      # row  9
        solid,      # row 10
        solid,      # row 11
        solid,      # row 12
        solid,      # row 13
        solid,      # row 14
        solid,      # row 15
    ]


def _avenue_zone(
    zone_id:    str,
    name:       str,
    inlet_char: str,       # single-char paving material for the side street
    inlet_npc:  str = "",  # optional NPC character_id at row 2, col 20
    east_zone:  str = "",
    west_zone:  str = "",
    north_zone: str = "",
) -> Zone:
    """
    Build a standard Azonithia Avenue section.

    inlet_char: ASCII tile character for the side-street inlet (cols 22–23).
    """
    ic = inlet_char   # shorthand
    # North side rows 0–4: inlet at cols 22–23
    def _north(npc_row: bool = False) -> str:
        left  = "," * 22
        right = "," * 24
        if npc_row:
            left = "," * 20 + "N," + ","  # NPC at col 20, then comma, then inlet starts at 22
            # Actually: cols 0-19=comma, col 20=N, col 21=comma, col 22-23=inlet, col 24-47=comma
            return "," * 20 + "N" + "," + ic + ic + "," * 24
        return left + ic + ic + right

    rows = [
        "," * 22 + ic + ic + "," * 24,       # row 0  N exit
        "," * 22 + ic + ic + "," * 24,       # row 1
        "," * 20 + "N," + ic + ic + "," * 24 if inlet_npc else "," * 22 + ic + ic + "," * 24,  # row 2
        "," * 22 + ic + ic + "," * 24,       # row 3
        "," * 22 + ic + ic + "," * 24,       # row 4
        "=" * 48,                             # row 5  main road (W/E exits)
        "=" * 48,                             # row 6
    ] + _avenue_forest_rows()

    exits: list[ZoneExit] = []
    if east_zone:
        exits += [
            ZoneExit(x=47, y=5, direction="east", target_zone=east_zone, target_x=1, target_y=5),
            ZoneExit(x=47, y=6, direction="east", target_zone=east_zone, target_x=1, target_y=6),
        ]
    if west_zone:
        exits += [
            ZoneExit(x=0, y=5, direction="west", target_zone=west_zone, target_x=46, target_y=5),
            ZoneExit(x=0, y=6, direction="west", target_zone=west_zone, target_x=46, target_y=6),
        ]
    if north_zone:
        exits += [
            ZoneExit(x=22, y=0, direction="north", target_zone=north_zone, target_x=10, target_y=18),
            ZoneExit(x=23, y=0, direction="north", target_zone=north_zone, target_x=11, target_y=18),
        ]

    npc_ids = [inlet_npc] if inlet_npc else []

    return build_zone_from_ascii(
        zone_id  = zone_id,
        realm    = Realm.LAPIDUS,
        name     = name,
        rows     = rows,
        exits    = exits,
        npc_ids  = npc_ids,
    )


# ── Azonithia: Slum section (Hopefare Street / yellow brick) ─────────────────
#
# East-most avenue section.  Yellow brick marks honest poverty — no pretence.
# Hopefare Street runs North into the 9-warren inner city.
# Sidhal (0004_TOWN) is met here managing the forest outskirts.
#
# Exits:
#   East  (47,5)+(47,6)  → lapidus_wiltoll_lane (1,10)+(1,11)
#   West  (0,5)+(0,6)    → lapidus_azonithia_market (46,5)+(46,6)
#   North (22,0)+(23,0)  → lapidus_slum_interior (stub)

def build_azonithia_slum() -> Zone:
    return _avenue_zone(
        zone_id    = "lapidus_azonithia_slum",
        name       = "Azonithia Avenue — Hopefare Street",
        inlet_char = "Y",
        inlet_npc  = "0004_TOWN",   # Sidhal: farmer/forester, quest 0003_KLST guide
        east_zone  = "lapidus_wiltoll_lane",
        west_zone  = "lapidus_azonithia_market",
        north_zone = "lapidus_slum_interior",
    )


# ── Azonithia: Market section (June Street / ceramic) ────────────────────────
#
# Ceramic tile — decorative, commercial, wanting to be noticed.
# June Street leads North to the market district.
#
# Exits:
#   East  (47,5)+(47,6) → lapidus_azonithia_slum (1,5)+(1,6)
#   West  (0,5)+(0,6)   → lapidus_azonithia_temple (46,5)+(46,6)
#   North (22,0)+(23,0) → lapidus_market_interior (stub)

def build_azonithia_market() -> Zone:
    return _avenue_zone(
        zone_id    = "lapidus_azonithia_market",
        name       = "Azonithia Avenue — June Street",
        inlet_char = "C",
        east_zone  = "lapidus_azonithia_slum",
        west_zone  = "lapidus_azonithia_temple",
        north_zone = "lapidus_market_interior",
    )


# ── Azonithia: Temple section (Goldshoot Street / slate) ─────────────────────
#
# Slate — serious, ancient-presenting, institutional weight.
# Goldshoot Street leads North to the Temple of the Gods.
#
# Exits:
#   East  (47,5)+(47,6) → lapidus_azonithia_market (1,5)+(1,6)
#   West  (0,5)+(0,6)   → lapidus_azonithia_heartvein (46,5)+(46,6)
#   North (22,0)+(23,0) → lapidus_temple_interior (stub)

def build_azonithia_temple() -> Zone:
    return _avenue_zone(
        zone_id    = "lapidus_azonithia_temple",
        name       = "Azonithia Avenue — Goldshoot Street",
        inlet_char = "L",
        east_zone  = "lapidus_azonithia_market",
        west_zone  = "lapidus_azonithia_heartvein",
        north_zone = "lapidus_temple_interior",
    )


# ── Azonithia: Heartvein Heights section (Youthspring Road / silica) ─────────
#
# Silica — extravagant, processed; the labor of making something impractical
# underfoot on display.  Youthspring Road leads North to Heartvein Heights
# (ROYL nobles).
#
# Exits:
#   East  (47,5)+(47,6) → lapidus_azonithia_temple (1,5)+(1,6)
#   West  (0,5)+(0,6)   → lapidus_azoth_approach (46,11)+(46,12)
#   North (22,0)+(23,0) → lapidus_heartvein_interior (stub)

def build_azonithia_heartvein() -> Zone:
    return _avenue_zone(
        zone_id    = "lapidus_azonithia_heartvein",
        name       = "Azonithia Avenue — Youthspring Road",
        inlet_char = "X",
        east_zone  = "lapidus_azonithia_temple",
        west_zone  = "lapidus_azoth_approach",
        north_zone = "lapidus_heartvein_interior",
    )


# ── Azoth Approach (Orchard + Azoth Sprint) ───────────────────────────────────
#
# 48 wide × 22 tall.
#
# The orchard of cultivated old-Earth fruit trees (cherry, apple, pomegranate,
# barley, pine needle, acorn, pine nut) flanks the marble approach road.
# The Azoth Sprint: hard marble, short, deadly quiet.  Connects Azonithia
# Avenue to the Castle gate.
#
# Layout:
#   rows  0–10  Marble sprint (cols 22–23) through the orchard
#   rows 11–12  Azonithia Avenue main road (ROAD, E–W)
#   rows 13–21  Southern woodland
#
# Exits:
#   East  (47,11)+(47,12) → lapidus_azonithia_heartvein (1,5)+(1,6)
#   West  (0,11)+(0,12)   → lapidus_dirt_trail (stub — ocean-bound)
#   North (22,0)+(23,0)   → lapidus_castle_azoth (18,19)+(19,19)

_ORCHARD_ROW = "," * 4 + "T" * 17 + "," + "MM" + "," + "T" * 17 + "," * 6  # 48 chars

_APPROACH_MAP = [
    "," * 22 + "MM" + "," * 24,   # row  0  N exit → Castle Azoth
    _ORCHARD_ROW,                  # row  1  orchard + marble sprint
    _ORCHARD_ROW,                  # row  2
    _ORCHARD_ROW,                  # row  3
    _ORCHARD_ROW,                  # row  4
    _ORCHARD_ROW,                  # row  5
    _ORCHARD_ROW,                  # row  6
    _ORCHARD_ROW,                  # row  7
    _ORCHARD_ROW,                  # row  8
    _ORCHARD_ROW,                  # row  9
    _ORCHARD_ROW,                  # row 10
    "=" * 48,                      # row 11  Azonithia Avenue (W/E exits)
    "=" * 48,                      # row 12
    "," * 48,                      # row 13  S verge
    ",,,,T,,,,,T,,,,,T,,,,,T,,,,,T,,,,,T,,,,,T,,,,,T",  # row 14  sparse trees
    "T" * 48,                      # row 15
    "T" * 48,                      # row 16
    "T" * 48,                      # row 17
    "T" * 48,                      # row 18
    "T" * 48,                      # row 19
    "T" * 48,                      # row 20
    "T" * 48,                      # row 21
]

_APPROACH_EXITS = [
    # East → Heartvein Heights section (note: approach road at rows 11-12, heartvein at rows 5-6)
    ZoneExit(x=47, y=11, direction="east",
             target_zone="lapidus_azonithia_heartvein", target_x=1, target_y=5),
    ZoneExit(x=47, y=12, direction="east",
             target_zone="lapidus_azonithia_heartvein", target_x=1, target_y=6),
    # West → ocean-bound dirt trail (stub)
    ZoneExit(x=0, y=11, direction="west",
             target_zone="lapidus_dirt_trail", target_x=18, target_y=5),
    ZoneExit(x=0, y=12, direction="west",
             target_zone="lapidus_dirt_trail", target_x=18, target_y=6),
    # North → Castle Azoth (marble sprint)
    ZoneExit(x=22, y=0, direction="north",
             target_zone="lapidus_castle_azoth", target_x=18, target_y=19),
    ZoneExit(x=23, y=0, direction="north",
             target_zone="lapidus_castle_azoth", target_x=19, target_y=19),
]


def build_azoth_approach() -> Zone:
    return build_zone_from_ascii(
        zone_id = "lapidus_azoth_approach",
        realm   = Realm.LAPIDUS,
        name    = "Azoth Approach — The Orchard",
        rows    = _APPROACH_MAP,
        exits   = _APPROACH_EXITS,
    )


# ── Castle Azoth ──────────────────────────────────────────────────────────────
#
# 40 wide × 20 tall.
# Home of the Stelladeva Dynastic Family, seat of the Royal Lottery system.
# Alfir (0006_WTCH) works here — teaches Infernal Meditation (quest 0009_KLST).
#
# The zodiac fountain at center-courtyard: a ring of stone around a water basin.
# Ceremonial — runs only on the four astronomical anchors (solstices/equinoxes).
# "These people have a thing about water."
#
# Named for Azoth — the alchemical prima materia and the BreathOfKo save-state
# parameter.
#
# Announces itself with grandiosity on the curve where Azonithia Avenue bends
# away from the Southern woodland.  No gradual reveal.
#
# Layout (North → South):
#   rows  0–16  Castle interior and courtyard (fountain at rows 5–9, col 10–19)
#   row  17     South inner wall with gates
#   rows 18–19  Stone courtyard + marble approach base
#
# Exits:
#   South (18,19)+(19,19) → lapidus_azoth_approach (22,1)+(23,1)

_CASTLE_MAP = [
    "########################################",  # row  0  (40 chars) N wall
    "#.N....................................#",  # row  1  Alfir NPC at col 3
    "#......................................#",  # row  2
    "#......................................#",  # row  3
    "#......................................#",  # row  4
    "#.........SSSSSSSSS....................#",  # row  5  fountain outer stone ring
    "#.........S~~~~~~~S....................#",  # row  6  water basin
    "#.........S~~SSS~~S....................#",  # row  7  zodiac center (stone ring in water)
    "#.........S~~~~~~~S....................#",  # row  8  water basin
    "#.........SSSSSSSSS....................#",  # row  9  fountain closes
    "#......................................#",  # row 10
    "#......................................#",  # row 11
    "#......................................#",  # row 12
    "#......................................#",  # row 13
    "#......................................#",  # row 14
    "#......................................#",  # row 15
    "#......................................#",  # row 16
    "#################++####################",  # row 17  S wall — double gate
    "SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS",  # row 18  stone courtyard plaza
    "MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM",  # row 19  marble sprint base (S exit)
]

_CASTLE_EXITS = [
    ZoneExit(x=18, y=19, direction="south",
             target_zone="lapidus_azoth_approach", target_x=22, target_y=1),
    ZoneExit(x=19, y=19, direction="south",
             target_zone="lapidus_azoth_approach", target_x=23, target_y=1),
]

_CASTLE_NPCS = ["0006_WTCH"]   # Alfir: former priest, Infernal Meditation teacher


def build_castle_azoth() -> Zone:
    return build_zone_from_ascii(
        zone_id = "lapidus_castle_azoth",
        realm   = Realm.LAPIDUS,
        name    = "Castle Azoth",
        rows    = _CASTLE_MAP,
        exits   = _CASTLE_EXITS,
        npc_ids = _CASTLE_NPCS,
    )


# ── Mt. Elaene Trail ──────────────────────────────────────────────────────────
#
# 20 wide × 14 tall.
# A small trail through the forest edge at the East end of Wiltoll Lane,
# leading toward Mt. Elaene.  Available at any time — no quest gate, no unlock.
# A pressure valve: always accessible when the city's weight gets heavy.
# Gateway to the Elaene desert — the Alzedroswune's actual home, visible from
# the player's own lane.
#
# Player enters from Wiltoll Lane at (1,6)+(1,7).  Trail corridor is cols 1–2.
# Exit North → Mt. Elaene summit (stub — mountaineering zone, not yet built).
#
# Exits:
#   West  (0,6)+(0,7)   → lapidus_wiltoll_lane (58,10)+(58,11)
#   North (1,0)+(2,0)   → lapidus_mt_elaene_summit (stub)

_ELAENE_MAP = [
    "T" + ",," + "T" * 17,   # row  0  N exit at 1-2
    "T" + ",," + "T" * 17,   # row  1
    "T" + ",," + "T" * 17,   # row  2
    "T" + ",," + "T" * 17,   # row  3
    "T" + ",," + "T" * 17,   # row  4
    "T" + ",," + "T" * 17,   # row  5
    "," + ",," + "T" * 17,   # row  6  player enters from Wiltoll here
    "," + ",," + "T" * 17,   # row  7
    "T" + ",," + "T" * 17,   # row  8
    "T" + ",," + "T" * 17,   # row  9
    "T" * 20,                 # row 10
    "T" * 20,                 # row 11
    "T" * 20,                 # row 12
    "T" * 20,                 # row 13
]

_ELAENE_EXITS = [
    ZoneExit(x=0, y=6, direction="west",
             target_zone="lapidus_wiltoll_lane", target_x=58, target_y=10),
    ZoneExit(x=0, y=7, direction="west",
             target_zone="lapidus_wiltoll_lane", target_x=58, target_y=11),
    ZoneExit(x=1, y=0, direction="north",
             target_zone="lapidus_mt_elaene_summit", target_x=9, target_y=12),
    ZoneExit(x=2, y=0, direction="north",
             target_zone="lapidus_mt_elaene_summit", target_x=10, target_y=12),
]


def build_mt_elaene_trail() -> Zone:
    return build_zone_from_ascii(
        zone_id = "lapidus_mt_elaene_trail",
        realm   = Realm.LAPIDUS,
        name    = "Mt. Elaene Trail",
        rows    = _ELAENE_MAP,
        exits   = _ELAENE_EXITS,
    )


# ── Market Interior (June Street) ─────────────────────────────────────────────
#
# 48 wide × 20 tall.
# Accessed from Azonithia Avenue — June Street (ceramic paving).
# Player arrives at (10,18)+(11,18) from the avenue and walks north into the market.
#
# Two vendor NPCs:
#   0006_TOWN — general vendor (west stall, col 8)
#   0007_TOWN — herb specialist (east stall, col 28)
#
# Exits:
#   South (10,19)+(11,19) → lapidus_azonithia_market (22,4)+(23,4)

_MARKET_STALL = (
    "#" + "." * 7 + "S" * 6 + "." * 14 + "S" * 6 + "." * 13 + "#"
)  # 48 chars: stone counters at cols 8-13 and cols 28-33

_MARKET_MAP = [
    "#" * 48,                                         # row  0: N wall
    "#" + "." * 46 + "#",                             # row  1
    "#" + "." * 46 + "#",                             # row  2
    "#" + "." * 7 + "N" + "." * 19 + "N" + "." * 18 + "#",  # row  3: vendors at 8, 28
    _MARKET_STALL,                                    # row  4: stone stall counters
    "#" + "." * 46 + "#",                             # row  5
    "#" + "." * 46 + "#",                             # row  6
    "#" + "." * 46 + "#",                             # row  7
    "#" + "." * 46 + "#",                             # row  8
    "#" + "." * 46 + "#",                             # row  9
    "#" + "." * 46 + "#",                             # row 10
    "#" + "." * 46 + "#",                             # row 11
    "#" + "." * 46 + "#",                             # row 12
    "#" + "." * 46 + "#",                             # row 13
    "#" + "." * 46 + "#",                             # row 14
    "#" + "." * 46 + "#",                             # row 15
    "#" + "." * 46 + "#",                             # row 16
    "#" * 20 + "++" + "#" * 26,                       # row 17: S wall with door at 20-21
    "," * 10 + "CC" + "," * 36,                       # row 18: arrival tiles (ceramic)
    "C" * 10 + "CC" + "C" * 36,                       # row 19: S exit strip (ceramic)
]

_MARKET_NPC_IDS = ["0006_TOWN", "0007_TOWN"]

_MARKET_EXITS = [
    ZoneExit(x=10, y=19, direction="south",
             target_zone="lapidus_azonithia_market", target_x=22, target_y=4),
    ZoneExit(x=11, y=19, direction="south",
             target_zone="lapidus_azonithia_market", target_x=23, target_y=4),
]


def build_market_interior() -> Zone:
    return build_zone_from_ascii(
        zone_id = "lapidus_market_interior",
        realm   = Realm.LAPIDUS,
        name    = "June Street Market",
        rows    = _MARKET_MAP,
        exits   = _MARKET_EXITS,
        npc_ids = _MARKET_NPC_IDS,
    )