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
  W  WALL_FACE (impassable — decorative back wall, pixel art wallpaper substrate)
  @  player spawn (→ FLOOR)
  N  NPC spawn    (→ FLOOR, matched to npc_ids in order)
"""

from __future__ import annotations

from ..map import Realm, Zone, ZoneExit, ItemSpawn, build_zone_from_ascii
from ..kobra_zone_loader import load_zone_from_kobra


# ── Vendor catalogs ───────────────────────────────────────────────────────────
#
# Maps character_id → {item_id: coin_price}.
# Referenced by WorldPlay to open vendor mode on NPC interaction.

VENDOR_CATALOGS: dict[str, dict[str, int]] = {
    # 0005_TOWN removed — player is the shopkeeper; player stock is in PlayerState
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
# Sparse, lush green avenue — player home at the quiet West end of the city.
# Mt. Elaene is the constant background presence at the East.
#
# Road rows 10–11 (East–West, Azonithia axis).
# Litleaf Thoroughfare fork: cols 11–12, rows 0–9 (perpendicular road going North).
# Player home: cols 1–9, rows 2–7 (North of road, door in S wall at cols 3–4).
# Player spawns at (3,8) on the north verge, facing the home entrance.
# Sparse trees: rows 13–14 (South of road).  Dense woodland: rows 19–21 (South).
#
# Exits:
#   West  (0,10)+(0,11)   → lapidus_azonithia_slum      (46,5)+(46,6)
#   East  (59,10)+(59,11) → lapidus_mt_elaene_trail      (1,6)+(1,7)
#   North (11,0)+(12,0)   → lapidus_litleaf_thoroughfare (0,18)+(1,18)
#   North (3,8)+(4,8)     → player_home_ground            (23,11)

_WILTOLL_MAP = [
    #          1111111111222222222233333333334444444444555555555566
    # 0123456789012345678901234567890123456789012345678901234567890
    ",,,,,,,,,,,==,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  0  N exit Litleaf 11-12
    ",,,,,,,,,,,==,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  1
    # row 2–7: player home (cols 1–9) | Elsa's house (cols 15–23) | Hypatia's house (cols 44–55)
    ",#########,==,," + "#########" + "," * 20 + "############" + "," * 4,  # row  2  back walls
    ",#.......#,==,," + "#.......#" + "," * 20 + "#..........#" + "," * 4,  # row  3  interiors
    ",#.......#,==,," + "#.......#" + "," * 20 + "#..........#" + "," * 4,  # row  4
    ",#.......#,==,," + "#.......#" + "," * 20 + "#..........#" + "," * 4,  # row  5
    ",#.......#,==,," + "#.......#" + "," * 20 + "#..........#" + "," * 4,  # row  6
    ",##++#####,==,," + "#####++##" + "," * 20 + "####++######" + "," * 4,  # row  7  doors: player(3-4) Elsa(20-21) Hypatia(48-49)
    # row 8: player spawn @(3,8) | Elsa N(20) — Hypatia works at the castle, not here
    ",,,@,,,,,,,==,,,,,,," + "N" + "," * 39,                                 # row  8
    ",,,,,,,,,,,==,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",           # row  9
    "============================================================",  # row 10  main road W/E exits
    "============================================================",  # row 11
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 12  S verge
    ",,T,,,,,,,,,,,,,,T,,,,,T,,,,,,T,,,,,T,,,,,,,,T,,,,,,T,,,,,,,",  # row 13  sparse trees S (was N)
    ",,T,,,,,,,,,,,,,,T,,,,,T,,,,,,T,,,,,T,,,,,,,,T,,,,,,T,,,,,,,",  # row 14
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 15  clearing
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 16
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 17
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row 18
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
    # North fork exits → Litleaf Thoroughfare (cols 11-12)
    ZoneExit(x=11, y=0, direction="north",
             target_zone="lapidus_litleaf_thoroughfare", target_x=0, target_y=18),
    ZoneExit(x=12, y=0, direction="north",
             target_zone="lapidus_litleaf_thoroughfare", target_x=1, target_y=18),
    # Player home door at cols 3-4, row 8 → canonical 48-wide home zone
    ZoneExit(x=3, y=8, direction="north",
             target_zone="player_home_ground", target_x=23, target_y=11),
    ZoneExit(x=4, y=8, direction="north",
             target_zone="player_home_ground", target_x=23, target_y=11),
    # Elsa's house door at cols 20-21, row 8
    ZoneExit(x=20, y=8, direction="north",
             target_zone="lapidus_elsa_house", target_x=13, target_y=8),
    ZoneExit(x=21, y=8, direction="north",
             target_zone="lapidus_elsa_house", target_x=14, target_y=8),
    # Hypatia's house door at cols 48-49, row 8
    # Quest-gated in game logic: not accessible after 0002_KLST accepted.
    ZoneExit(x=48, y=8, direction="north",
             target_zone="lapidus_hypatia_house", target_x=19, target_y=11),
    ZoneExit(x=49, y=8, direction="north",
             target_zone="lapidus_hypatia_house", target_x=20, target_y=11),
]

_HOME_STAIR_EXIT = ZoneExit(
    x=9, y=2, direction="north",
    target_zone="player_home_upper", target_x=24, target_y=7,
)


def build_wiltoll_lane() -> Zone:
    return build_zone_from_ascii(
        zone_id = "lapidus_wiltoll_lane",
        realm   = Realm.LAPIDUS,
        name    = "Wiltoll Lane",
        rows    = _WILTOLL_MAP,
        exits   = _WILTOLL_EXITS,
        # Elsa (0024_TOWN) at col 20 row 8.
        # Hypatia works at Castle Azoth to the west — she is not on the lane.
        npc_ids = ["0024_TOWN"],
    )


# ── Player Home Interior (Wiltoll Lane) ───────────────────────────────────────
#
# 40 wide × 13 tall.
# Entered from the south facade door of the home on Wiltoll Lane
# (home is North of the road; player approaches from north verge, walks north into door).
# Three back rooms (Bedroom / Kitchen / Meditation) accessed via the Foyer.
#
# Layout (N→S, top→bottom):
#   row  0    North wall (solid — back of house)
#   rows 1–7  Three rooms: Bedroom (cols 1–10), Kitchen (cols 12–25),
#             Meditation (cols 27–38)
#   row  8    Inner dividing wall with room openings at cols 5, 19, 33
#   rows 9–11 Foyer — entrance hall, vendor NPC (0005_TOWN)
#   row 12    South wall — door at cols 20–21 (faces road)
#
# Player spawns at (8, 10) just inside the south door.
# ItemSpawns in the Kitchen provide starter alchemy apparatus and materials.
#
# Exits:
#   South (20,12)+(21,12) → lapidus_wiltoll_lane (3,8)+(4,8)

_HOME_ROOM_ROW = (
    "#" + "." * 10 + "#" + "." * 14 + "#" + "." * 12 + "#"
)  # 40 chars: Bedroom(1-10) | Kitchen(12-25) | Meditation(27-38)

# Row 1 — decorative back wall face: WALL_FACE tiles inside each room,
# structural WALL at the column dividers.  Pixel art wallpaper goes here.
_HOME_WALL_ROW = (
    "#" + "W" * 10 + "#" + "W" * 14 + "#" + "W" * 12 + "#"
)  # 40 chars

_HOME_MAP = [
    #          1111111111222222222233333333334
    # 0123456789012345678901234567890123456789
    "#" * 40,                             # row  0: N wall (back of house)
    _HOME_WALL_ROW,                       # row  1: decorative back wall face
    "#" + "." * 8 + "^." + "#" + "." * 14 + "#" + "." * 12 + "#",  # row  2: ^ stair (9,2)
    "#" + "." * 10 + "#" + ".." + "F" + "." * 6 + "F" + "...." + "#" + "." * 12 + "#",  # row  3: F=alchemy bench(14,3) F=anvil(21,3)
    "#" + "..." + "F" + "." * 6 + "#" + "." * 14 + "#" + "." * 6 + "F" + "." * 5 + "#",  # row  4: F=bed(4,4) F=meditation mat(33,4)
    _HOME_ROOM_ROW,                       # row  5
    _HOME_ROOM_ROW,                       # row  6
    _HOME_ROOM_ROW,                       # row  7: item spawns (mortar/pestle/furnace etc.)
    "#####.#####" + "#" + "#######.######" + "#" + "######.#####" + "#",  # row  8: inner wall
    "#" + "." * 18 + "F" + "." * 19 + "#",  # row  9: F=shop counter(19,9)
    "#" + ".." + "F" + "...." + "@" + "." * 30 + "#",  # row 10: F=chest(3,10) @=player spawn(8,10)
    "#" + "." * 38 + "#",                 # row 11: shop floor
    "#" * 20 + "++" + "#" * 18,          # row 12: S wall, door at cols 20-21
]

_HOME_EXITS = [
    ZoneExit(x=20, y=12, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=3, target_y=8),
    ZoneExit(x=21, y=12, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=4, target_y=8),
]

_HOME_NPC_IDS: list = []   # no vendor NPCs — player IS the shopkeeper

# Kitchen apparatus and starter materials (all within Kitchen cols 12-25, rows 5-11)
_HOME_ITEM_SPAWNS = [
    # y-coordinates mirror the N/S flip: new_y = 12 - old_y
    ItemSpawn(x=13, y=7,  item_id="0001_KLOB", qty=1),   # Mortar
    ItemSpawn(x=14, y=7,  item_id="0002_KLOB", qty=1),   # Pestle
    ItemSpawn(x=13, y=6,  item_id="0004_KLOB", qty=1),   # Retort Stand
    ItemSpawn(x=14, y=6,  item_id="0005_KLOB", qty=1),   # Retort
    ItemSpawn(x=13, y=5,  item_id="0007_KLOB", qty=1),   # Reagent Bottle
    ItemSpawn(x=16, y=7,  item_id="0010_KLOB", qty=1),   # Furnace
    ItemSpawn(x=17, y=7,  item_id="0017_KLOB", qty=1),   # Crucible
    ItemSpawn(x=18, y=7,  item_id="0019_KLOB", qty=1),   # Jar
    ItemSpawn(x=20, y=7,  item_id="0073_KLOB", qty=3),   # Herb (Common) ×3
    ItemSpawn(x=20, y=6,  item_id="0074_KLOB", qty=2),   # Herb (Restorative) ×2
    ItemSpawn(x=21, y=7,  item_id="0040_KLOB", qty=2),   # Water Flask ×2
    ItemSpawn(x=3,  y=10, item_id="0016_KLIT", qty=50),  # Coins ×50 (in foyer chest)
]


def build_wiltoll_home() -> Zone:
    return build_zone_from_ascii(
        zone_id     = "lapidus_wiltoll_home",
        realm       = Realm.LAPIDUS,
        name        = "Wiltoll Home — Interior",
        rows        = _HOME_MAP,
        exits       = _HOME_EXITS + [_HOME_STAIR_EXIT],
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
# Nexiott (0023_TOWN) is found here — the information broker who runs the
# district radio network.
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
        east_zone  = "lapidus_wiltoll_lane",
        west_zone  = "lapidus_azonithia_market",
        north_zone = "lapidus_slum_interior",   # → Hopefare Junction
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
        north_zone = "lapidus_june_quarter",   # → June Quarter (proper)
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
        north_zone = "lapidus_goldshoot_street",   # → Goldshoot Street (proper)
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
        north_zone = "lapidus_youthspring_road",   # → Youthspring Road (proper)
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
# Alfir (0006_WTCH) works here — teaches Infernal Meditation in quest 0010_KLST
# (Perfect Circles), unlocked after 0009_KLST (Demons and Diamonds) completes.
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
    "###################++##################",  # row  0  N wall — double gate to main hall
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
    "#...........................N..........#",  # row 14  Hypatia: lab area (col 28) — she was here all night
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
    ZoneExit(x=19, y=0,  direction="north",
             target_zone="lapidus_castle_main_hall", target_x=27, target_y=28),
    ZoneExit(x=20, y=0,  direction="north",
             target_zone="lapidus_castle_main_hall", target_x=28, target_y=28),
]

_CASTLE_NPCS = ["0006_WTCH", "0000_0451"]
# Alfir: former priest, Infernal Meditation teacher (row 1 col 2)
# Hypatia: alchemist, beats everyone out of bed because she was here all night (row 14 col 28)
# Hypatia's spawn is removed from world state after 0002_KLST is accepted.


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
# A small trail through the forest edge at the East end of Wiltoll Lane.
# The Forest Witch (0007_WTCH) lives in the clearing at rows 3-4.
# He carries the folded Mercurie map and offers quest 0007_KLST (Dream of Glass).
# No quest gate to reach him — he is available any time.
#
# Trail continues East along the mountain base to Serpent's Pass.
#
# Exits:
#   West  (0,6)+(0,7)   → lapidus_wiltoll_lane (58,10)+(58,11)
#   North (1,0)+(2,0)   → lapidus_mt_elaene_summit (stub)
#   East  (19,6)+(19,7) → lapidus_serpents_pass (1,6)+(1,7)

_ELAENE_MAP = [
    "T" + ",," + "T" * 17,   # row  0  N exit at 1-2
    "T" + ",," + "T" * 17,   # row  1
    "T" + ",," + "T" * 17,   # row  2
    "T" + ",N," + "T" * 16,  # row  3  Forest Witch at col 2
    "T" + ",," + "T" * 17,   # row  4
    "T" + ",," + "T" * 17,   # row  5
    "," + ",," + "T" * 14 + ",,",  # row  6  W enter + E exit at 19
    "," + ",," + "T" * 14 + ",,",  # row  7
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
    ZoneExit(x=19, y=6, direction="east",
             target_zone="lapidus_serpents_pass", target_x=1, target_y=6),
    ZoneExit(x=19, y=7, direction="east",
             target_zone="lapidus_serpents_pass", target_x=1, target_y=7),
]

_ELAENE_NPCS = ["0007_WTCH"]   # Forest Witch: Mercurie map, quest 0007_KLST


def build_mt_elaene_trail() -> Zone:
    return build_zone_from_ascii(
        zone_id = "lapidus_mt_elaene_trail",
        realm   = Realm.LAPIDUS,
        name    = "Mt. Elaene Trail",
        rows    = _ELAENE_MAP,
        exits   = _ELAENE_EXITS,
        npc_ids = _ELAENE_NPCS,
    )


# ── Serpent's Pass ────────────────────────────────────────────────────────────
#
# 40 wide × 14 tall.
# A narrow defile between old stone walls, mountain base to the North,
# city outskirts to the South.  Wells and Lavelle have their camp at the East
# end where the aqueduct stone is laid (0003_KLST endpoint).
#
# Exits:
#   West  (0,6)+(0,7)   → lapidus_mt_elaene_trail (18,6)+(18,7)
#   East  (39,6)+(39,7) → lapidus_ocean_shore (1,6)+(1,7)

_PASS_MAP = [
    "S" * 40,                      # row  0  mountain stone wall (North)
    "S,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,S",  # row  1  narrow pass
    "S,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,S",  # row  2
    "S,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,S",  # row  3
    "S,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,S",  # row  4
    "S,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,NS",  # row  5  Wells NPC near East
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,N,",  # row  6  W/E exits + Lavelle NPC
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  7
    "S,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,S",  # row  8
    "S,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,S",  # row  9
    "S" * 40,                      # row 10  South wall
    "," * 40,                      # row 11
    "," * 40,                      # row 12
    "," * 40,                      # row 13
]

_PASS_EXITS = [
    ZoneExit(x=0, y=6, direction="west",
             target_zone="lapidus_mt_elaene_trail", target_x=18, target_y=6),
    ZoneExit(x=0, y=7, direction="west",
             target_zone="lapidus_mt_elaene_trail", target_x=18, target_y=7),
    ZoneExit(x=39, y=6, direction="east",
             target_zone="lapidus_ocean_shore", target_x=1, target_y=6),
    ZoneExit(x=39, y=7, direction="east",
             target_zone="lapidus_ocean_shore", target_x=1, target_y=7),
]

_PASS_NPCS = ["0021_TOWN", "0022_TOWN"]   # Wells, Lavelle (0003_KLST endpoint)


def build_serpents_pass() -> Zone:
    return build_zone_from_ascii(
        zone_id = "lapidus_serpents_pass",
        realm   = Realm.LAPIDUS,
        name    = "Serpent's Pass",
        rows    = _PASS_MAP,
        exits   = _PASS_EXITS,
        npc_ids = _PASS_NPCS,
    )


# ── Ocean Shore ───────────────────────────────────────────────────────────────
#
# 50 wide × 12 tall.
# Open coastline past Serpent's Pass.  Dark water, salt wind.
# The Mercurie threshold is accessible here at low tide (quest 0007_KLST gate).
#
# Exits:
#   West  (0,6)+(0,7)    → lapidus_serpents_pass (38,6)+(38,7)
#   North (24,0)+(25,0)  → mercurie_threshold (25,11)+(26,11)

_SHORE_MAP = [
    "~" * 25 + ",," + "~" * 23,   # row  0  N exit at 24-25 (mercurie)
    "~" * 50,                      # row  1  open water
    "~" * 50,                      # row  2
    "~" * 50,                      # row  3
    "," * 10 + "~" * 30 + "," * 10,   # row  4  shoreline
    "," * 50,                      # row  5  sandy shore
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  6  W/E exits
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",  # row  7
    "," * 50,                      # row  8
    "D" * 50,                      # row  9  dirt track (inland path)
    "D" * 50,                      # row 10
    "," * 50,                      # row 11
]

_SHORE_EXITS = [
    ZoneExit(x=0, y=6, direction="west",
             target_zone="lapidus_serpents_pass", target_x=38, target_y=6),
    ZoneExit(x=0, y=7, direction="west",
             target_zone="lapidus_serpents_pass", target_x=38, target_y=7),
    # Mercurie threshold — gated by 0007_KLST in dialogue/selector.py
    ZoneExit(x=24, y=0, direction="north",
             target_zone="mercurie_threshold", target_x=25, target_y=11),
    ZoneExit(x=25, y=0, direction="north",
             target_zone="mercurie_threshold", target_x=26, target_y=11),
]


def build_ocean_shore() -> Zone:
    return build_zone_from_ascii(
        zone_id = "lapidus_ocean_shore",
        realm   = Realm.LAPIDUS,
        name    = "Ocean Shore",
        rows    = _SHORE_MAP,
        exits   = _SHORE_EXITS,
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


# ── Elsa's House ──────────────────────────────────────────────────────────────
#
# 28 wide × 10 tall.
# Three doors east of the player home on Wiltoll Lane.
# Elsa (0024_TOWN) — neighbour, 50s, has lived on the lane thirty years.
# Warm, working-class interior. A chair by the window. A clean kitchen corner.
# She is met outside on the lane (quest 0001 scene); this interior is for
# subsequent visits and deeper conversation.
#
# Exits:
#   South (13,9)+(14,9) → lapidus_wiltoll_lane (20,8)+(21,8)

_ELSA_MAP = [
    "#" * 28,                              # row 0  N wall
    "#" + "W" * 26 + "#",                 # row 1  wall face (back-wall wallpaper register)
    "#" + "." * 26 + "#",                 # row 2
    "#" + "." * 5 + "F" + "." * 20 + "#", # row 3  F = table (col 6)
    "#" + "." * 26 + "#",                 # row 4
    "#" + "." * 10 + "@" + "." * 15 + "#", # row 5  player spawn
    "#" + "." * 26 + "#",                 # row 6
    "#" + "." * 26 + "#",                 # row 7
    "#" + "." * 26 + "#",                 # row 8
    "#" * 13 + "++" + "#" * 13,           # row 9  S wall door at 13-14
]

_ELSA_EXITS = [
    ZoneExit(x=13, y=9, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=20, target_y=8),
    ZoneExit(x=14, y=9, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=21, target_y=8),
]

_ELSA_ITEMS = [
    ItemSpawn(x=6, y=3, item_id="0073_KLOB", qty=1),   # Herb (Common) on table
]


def build_elsa_house() -> Zone:
    return build_zone_from_ascii(
        zone_id     = "lapidus_elsa_house",
        realm       = Realm.LAPIDUS,
        name        = "Elsa's House",
        rows        = _ELSA_MAP,
        exits       = _ELSA_EXITS,
        item_spawns = _ELSA_ITEMS,
    )


# ── Hypatia's House ───────────────────────────────────────────────────────────
#
# 40 wide × 13 tall.
# At the quiet east end of Wiltoll Lane — the house with the light on at
# strange hours.  Hypatia (0000_0451) works here in the early game (quests
# 0001–0002). After 0002_KLST is accepted she is absent; the house stays open
# but she is not here. The alchemy apparatus is hers — the player may take
# consumables but apparatus is fixed.
#
# Layout (N→S, top→bottom):
#   rows 0–6   Workshop (left) + living space (right) separated by interior wall
#   row  7     Open passage — the wall has no door; it just stops
#   rows 8–11  Combined lower space — foyer, bench, open floor
#   row  12    South wall — door at cols 19-20
#
# Exits:
#   South (19,12)+(20,12) → lapidus_wiltoll_lane (48,8)+(49,8)

_HYPATIA_HOUSE_MAP = [
    "#" * 40,                              # row  0  N wall
    "#" + "W" * 38 + "#",                 # row  1  wall face
    "#" + "." * 17 + "#" + "." * 20 + "#",  # row  2  interior divider col 18
    "#" + "F" + "." * 6 + "F" + "." * 9 + "#" + "." * 20 + "#",  # row  3  alchemy benches (2,8)
    "#" + "." * 16 + "#" + "." * 20 + "#",  # row  4
    "#" + "." * 16 + "#" + "." * 20 + "#",  # row  5  (Hypatia not here — she's at the castle)
    "#" + "." * 16 + "#" + "." * 20 + "#",  # row  6
    "#" + "." * 38 + "#",                 # row  7  divider ends — open
    "#" + "." * 38 + "#",                 # row  8
    "#" + "." * 38 + "#",                 # row  9
    "#" + "." * 17 + "@" + "." * 20 + "#",  # row 10  player spawn
    "#" + "." * 38 + "#",                 # row 11
    "#" * 19 + "++" + "#" * 19,           # row 12  S wall door at 19-20
]

_HYPATIA_HOUSE_EXITS = [
    ZoneExit(x=19, y=12, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=48, target_y=8),
    ZoneExit(x=20, y=12, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=49, target_y=8),
]

_HYPATIA_HOUSE_NPCS: list[str] = []
# Hypatia works at Castle Azoth. Her house is here — the lab materials, the dagger —
# but she is not. The player finds her at the castle, not at home.

_HYPATIA_HOUSE_ITEMS = [
    # Workshop consumables — player may take freely in early game.
    ItemSpawn(x=2,  y=3, item_id="0001_KLOB", qty=1),   # Mortar
    ItemSpawn(x=8,  y=3, item_id="0005_KLOB", qty=1),   # Retort
    ItemSpawn(x=3,  y=3, item_id="0007_KLOB", qty=2),   # Reagent Bottles
    ItemSpawn(x=12, y=3, item_id="0073_KLOB", qty=2),   # Herb (Common)
    ItemSpawn(x=13, y=3, item_id="0017_KLOB", qty=1),   # Crucible
    # Alzedroswune materials — present quietly on the bench.
    # Not explained. The player who does quest 0038 will recognize them.
    ItemSpawn(x=16, y=3, item_id="0041_KLOB", qty=1),   # Moldavite (sky-born, Alzedroswune-adjacent)
    ItemSpawn(x=15, y=3, item_id="0042_KLOB", qty=1),   # Desert Glass (lightning formation)
    # Quest item: dagger — placed here as fallback if player misses 0002 scene.
    # Game logic removes it once 0002_KLST is accepted (Hypatia gives it in dialogue).
    ItemSpawn(x=20, y=5, item_id="0001_KLIT", qty=1),   # The dagger (Hypatia's teacher's)
]


def build_hypatia_house() -> Zone:
    return build_zone_from_ascii(
        zone_id     = "lapidus_hypatia_house",
        realm       = Realm.LAPIDUS,
        name        = "Hypatia's House",
        rows        = _HYPATIA_HOUSE_MAP,
        exits       = _HYPATIA_HOUSE_EXITS,
        npc_ids     = _HYPATIA_HOUSE_NPCS,
        item_spawns = _HYPATIA_HOUSE_ITEMS,
    )


# ── Kobra zone helpers (lapidus material palette) ─────────────────────────────
#
# Colors encode material character via Shygazun byte table:
#   El  (byte 26, Rose, Vector Yellow)  — yellow brick: honest, working
#   Ka  (byte 29, Rose, Vector Indigo)  — slate: institutional, ancient-weight
#   Ha  (byte 43, Rose, Absolute Pos.)  — ceramic / general warm floor
#   Ga  (byte 44, Rose, Absolute Neg.)  — silica: extravagant, processed cold
#   Vo  (wall presence)                 — all wall tiles

def _kw(x: int, y: int) -> str:
    return f"g|{x},{y} : [Vo Ka]"

def _kf(x: int, y: int, color: str = "Ha") -> str:
    return f"g|{x},{y} : [Va {color}]"

def _ks(x: int, y: int) -> str:
    return f"g|{x},{y} : [Va Ha St]"

def _kn(x: int, y: int, npc_id: str) -> str:
    return f"g|{x},{y} : [Va Ha Lo {npc_id}]"

def _ke(x: int, y: int, direction: str, target: str,
        tx: int, ty: int, label: str = "") -> str:
    lex = f"{direction} {target} {tx} {ty}"
    if label:
        lex += f" {label}"
    return f"g|{x},{y} : [Va Ha Ne {lex}]"

def _kperim(W: int, H: int, lines: list[str],
            passable: set[tuple[int, int]] | None = None) -> None:
    skip = passable or set()
    for x in range(W):
        if (x, 0)   not in skip: lines.append(_kw(x, 0))
        if (x, H-1) not in skip: lines.append(_kw(x, H-1))
    for y in range(1, H-1):
        if (0, y)   not in skip: lines.append(_kw(0, y))
        if (W-1, y) not in skip: lines.append(_kw(W-1, y))

def _kfill(W: int, H: int, lines: list[str],
           walls: set[tuple[int, int]], color: str = "Ha") -> None:
    for y in range(1, H-1):
        for x in range(1, W-1):
            if (x, y) not in walls:
                lines.append(_kf(x, y, color=color))

def _kbuild(lines: list[str], zone_id: str, name: str,
            spawn: tuple[int, int] = (2, 2)) -> Zone:
    return load_zone_from_kobra(
        source       = "\n".join(lines),
        zone_id      = zone_id,
        name         = name,
        realm        = Realm.LAPIDUS,
        player_spawn = spawn,
    )


# ── Hopefare Inner Junction  (40 × 22) ───────────────────────────────────────
#
# The crossroads where Hopefare Street opens into the warren network.
# Yellow brick throughout — Hopefare's honest material continues inside.
# The warren district proper begins here; the nine warrens branch from
# passages visible as openings in the walls.
#
# Exits:
#   South  (19,21)+(20,21) → lapidus_azonithia_slum (22,1)+(23,1)
#   East   (39,10)+(39,11) → lapidus_warren_faithsalt (1,5)+(1,6)  [Lovecraft Lane]
#   West   (0,10)+(0,11)   → stub (deeper inner passages, future)
#
# Note: lapidus_warren_faithsalt's west exit must be updated to point here.

def build_hopefare_junction() -> Zone:
    W, H = 40, 22
    SPAWN = (4, 10)

    SOUTH_EXITS = {(19, H-1), (20, H-1)}
    EAST_EXITS  = {(W-1, 10), (W-1, 11)}
    WEST_EXITS  = {(0, 10), (0, 11)}
    passable    = SOUTH_EXITS | EAST_EXITS | WEST_EXITS

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    _kperim(W, H, lines, passable)
    walls.update({(x, 0) for x in range(W)} | {(x, H-1) for x in range(W)})
    walls.update({(0, y) for y in range(H)} | {(W-1, y) for y in range(H)})
    walls -= passable

    # Central junction markers — low stone dividers suggesting alleys
    for x in (10, 20, 30):
        for y in (5, 16):
            lines.append(_kw(x, y))
            walls.add((x, y))

    _kfill(W, H, lines, walls, color="El")   # yellow brick

    lines.append(_ks(*SPAWN))

    # Exits
    for (x, y) in SOUTH_EXITS:
        lines.append(_ke(x, y, "south", "lapidus_azonithia_slum", 22, 1))
    for (x, y) in EAST_EXITS:
        lines.append(_ke(x, y, "east", "lapidus_warren_faithsalt", 1, 5,
                        "Lovecraft_Lane"))
    for (x, y) in WEST_EXITS:
        lines.append(_ke(x, y, "west", "lapidus_slum_west_stub", 1, 5))

    return _kbuild(lines, "lapidus_slum_interior", "Hopefare Junction", SPAWN)


# ── June Quarter  (80 × 12) ───────────────────────────────────────────────────
#
# Long market corridor — more long than wide.
# Ceramic tile throughout: decorative, commercial, wanting to be noticed.
# Stall counters line both sides of a central walkway.
# Four vendor positions; two are populated (0006_TOWN, 0007_TOWN),
# two are open stalls for quest-gated merchants.
#
# Layout:
#   rows 0, 11     N/S walls
#   rows 1–3       North stalls (stone counters + vendor NPCs)
#   rows 4–7       Central walkway
#   rows 8–10      South stalls (stone counters + open positions)
#
# Exits:
#   South (39,11)+(40,11) → lapidus_azonithia_market (22,1)+(23,1)
#   East  (79,5)+(79,6)   → stub (east market extension, future)

def build_june_quarter() -> Zone:
    W, H = 80, 12
    SPAWN = (40, 6)

    SOUTH_EXITS = {(39, H-1), (40, H-1)}
    EAST_EXITS  = {(W-1, 5), (W-1, 6)}
    passable    = SOUTH_EXITS | EAST_EXITS

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    _kperim(W, H, lines, passable)
    walls.update({(x, 0) for x in range(W)} | {(x, H-1) for x in range(W)})
    walls.update({(0, y) for y in range(H)} | {(W-1, y) for y in range(H)})
    walls -= passable

    # North stall counters (row 2, cols 2–19, 22–39, 42–59, 62–77)
    for seg_start in (2, 22, 42, 62):
        for x in range(seg_start, seg_start + 16):
            lines.append(_kw(x, 2))
            walls.add((x, 2))

    # South stall counters (row 9)
    for seg_start in (2, 22, 42, 62):
        for x in range(seg_start, seg_start + 16):
            lines.append(_kw(x, 9))
            walls.add((x, 9))

    _kfill(W, H, lines, walls, color="Ha")   # ceramic — warm commercial

    lines.append(_ks(*SPAWN))

    # Vendor NPCs (north stalls, behind counters at row 1)
    lines.append(_kn(10, 1, "0006_TOWN"))   # general vendor
    lines.append(_kn(30, 1, "0007_TOWN"))   # herb specialist

    # Exits
    for (x, y) in SOUTH_EXITS:
        lines.append(_ke(x, y, "south", "lapidus_azonithia_market", 22, 1))
    for (x, y) in EAST_EXITS:
        lines.append(_ke(x, y, "east", "lapidus_june_east_stub", 1, 5))

    return _kbuild(lines, "lapidus_june_quarter", "June Quarter", SPAWN)


# ── Goldshoot Street  (16 × 36) ──────────────────────────────────────────────
#
# Slate-paved approach to the Temple of the Gods.
# Narrow, deep — the length gives the approach its institutional gravity.
# Serious, ancient-presenting. Progressive weight as the player moves north.
# Sidhal (0020_TOWN) is the temple custodian; met here on the way up.
#
# Exits:
#   South (7,35)+(8,35)  → lapidus_azonithia_temple (22,1)+(23,1)
#   North (7,0)+(8,0)    → lapidus_temple_interior (stub)

def build_goldshoot_street() -> Zone:
    W, H = 16, 36
    SPAWN = (8, 30)

    SOUTH_EXITS = {(7, H-1), (8, H-1)}
    NORTH_EXITS = {(7, 0),   (8, 0)}
    passable    = SOUTH_EXITS | NORTH_EXITS

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    _kperim(W, H, lines, passable)
    walls.update({(x, 0) for x in range(W)} | {(x, H-1) for x in range(W)})
    walls.update({(0, y) for y in range(H)} | {(W-1, y) for y in range(H)})
    walls -= passable

    # Architectural markers — columns suggesting temple approach formality
    for col_x in (3, 12):
        for row_y in (8, 16, 24):
            lines.append(_kw(col_x, row_y))
            walls.add((col_x, row_y))

    _kfill(W, H, lines, walls, color="Ka")   # slate — Vector Indigo, institutional

    lines.append(_ks(*SPAWN))
    lines.append(_kn(8, 20, "0020_TOWN"))    # Sidhal: temple custodian

    for (x, y) in SOUTH_EXITS:
        lines.append(_ke(x, y, "south", "lapidus_azonithia_temple", 22, 1))
    for (x, y) in NORTH_EXITS:
        lines.append(_ke(x, y, "north", "lapidus_temple_interior", 7, 34))

    return _kbuild(lines, "lapidus_goldshoot_street", "Goldshoot Street", SPAWN)


# ── Youthspring Road  (22 × 28) ──────────────────────────────────────────────
#
# Melted silica approach to Heartvein Heights.
# Wider than Goldshoot — wealth demands space underfoot.
# Extravagant, processed; the labor of making something impractical on display.
# Nexiott (0017_ROYL) is encountered here — caravan boss, radio network owner.
#
# Exits:
#   South (10,27)+(11,27) → lapidus_azonithia_heartvein (22,1)+(23,1)
#   North (10,0)+(11,0)   → lapidus_heartvein_interior (stub)

def build_youthspring_road() -> Zone:
    W, H = 22, 28
    SPAWN = (11, 22)

    SOUTH_EXITS = {(10, H-1), (11, H-1)}
    NORTH_EXITS = {(10, 0),   (11, 0)}
    passable    = SOUTH_EXITS | NORTH_EXITS

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    _kperim(W, H, lines, passable)
    walls.update({(x, 0) for x in range(W)} | {(x, H-1) for x in range(W)})
    walls.update({(0, y) for y in range(H)} | {(W-1, y) for y in range(H)})
    walls -= passable

    # Noble district character — wide verge walls suggesting estate boundaries
    for vx in (5, 16):
        for vy in range(4, 24, 4):
            lines.append(_kw(vx, vy))
            walls.add((vx, vy))

    _kfill(W, H, lines, walls, color="Ga")   # silica — Absolute Negative, cold extravagance

    lines.append(_ks(*SPAWN))
    lines.append(_kn(11, 14, "0017_ROYL"))   # Nexiott on Youthspring Road

    for (x, y) in SOUTH_EXITS:
        lines.append(_ke(x, y, "south", "lapidus_azonithia_heartvein", 22, 1))
    for (x, y) in NORTH_EXITS:
        lines.append(_ke(x, y, "north", "lapidus_heartvein_interior", 10, 26))

    return _kbuild(lines, "lapidus_youthspring_road", "Youthspring Road", SPAWN)


# ── Castle Azoth — Main Hall / Lottery Chamber  (56 × 30) ────────────────────
#
# Ground floor. The Lottery is drawn here. The room is designed to make people
# feel small — wide formal hall, central aisle, raised dais at the north end
# where Bombastus presides. Columns create lanes. Stone throughout.
#
# NPCs:
#   Bombastus (ROYL, King) — on the dais, north center
#
# Exits:
#   South (27,29)+(28,29) → lapidus_castle_azoth courtyard (19,1)+(20,1)
#   West  (0,14)+(0,15)   → lapidus_castle_west_wing (stub)
#   North (27,0)+(28,0)   → lapidus_castle_first_floor (27,28)+(28,28)
#   Down  (2,2)+(3,2)     → lapidus_castle_basement (stub — locked Game 7)

def build_castle_main_hall() -> Zone:
    W, H = 56, 30
    SPAWN = (28, 24)

    SOUTH = {(27, H-1), (28, H-1)}
    NORTH = {(27, 0),   (28, 0)}
    WEST  = {(0, 14),   (0, 15)}
    passable = SOUTH | NORTH | WEST

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    _kperim(W, H, lines, passable)
    for x in range(W):
        walls.add((x, 0)); walls.add((x, H-1))
    for y in range(H):
        walls.add((0, y)); walls.add((W-1, y))
    walls -= passable

    # Dais — raised stone platform at north center (rows 3-6, cols 18-37)
    for x in range(18, 38):
        for y in (3, 6):
            lines.append(_kw(x, y)); walls.add((x, y))
    for y in range(4, 6):
        lines.append(_kw(18, y)); walls.add((18, y))
        lines.append(_kw(37, y)); walls.add((37, y))

    # Formal columns lining the central aisle (rows 8,12,16,20 — cols 8 and 47)
    for ry in (8, 12, 16, 20):
        for cx in (8, 47):
            lines.append(_kw(cx, ry)); walls.add((cx, ry))

    # Basement stairs marker (locked — west corner, rows 2-3)
    for x in (2, 3):
        for y in (2, 3):
            lines.append(_kw(x, y)); walls.add((x, y))

    _kfill(W, H, lines, walls, color="Ha")

    lines.append(_ks(*SPAWN))

    # Bombastus on the dais
    lines.append(_kn(27, 4, "ROYL_BOMBASTUS"))

    # Exits
    for (x, y) in SOUTH:
        lines.append(_ke(x, y, "south", "lapidus_castle_azoth", 19, 1))
    for (x, y) in NORTH:
        lines.append(_ke(x, y, "north", "lapidus_castle_first_floor", 27, 28))
    for (x, y) in WEST:
        lines.append(_ke(x, y, "west", "lapidus_castle_west_stub", 1, 5))

    return _kbuild(lines, "lapidus_castle_main_hall", "Castle Azoth — Lottery Hall", SPAWN)


# ── Castle Azoth — First Floor  (48 × 24) ─────────────────────────────────────
#
# Administrative wing. Alfir's workshop occupies the northwest.
# Bombastus's private study is northeast.
# Central corridor connects stair landings.
#
# NPCs:
#   Alfir (0006_WTCH) — northwest workshop (quest 0010_KLST gate)
#
# Exits:
#   South (23,23)+(24,23) → lapidus_castle_main_hall (27,1)+(28,1)
#   North (23,0)+(24,0)   → lapidus_castle_second_floor (23,22)+(24,22)

def build_castle_first_floor() -> Zone:
    W, H = 48, 24
    SPAWN = (24, 18)

    SOUTH = {(23, H-1), (24, H-1)}
    NORTH = {(23, 0),   (24, 0)}
    passable = SOUTH | NORTH

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    _kperim(W, H, lines, passable)
    for x in range(W):
        walls.add((x, 0)); walls.add((x, H-1))
    for y in range(H):
        walls.add((0, y)); walls.add((W-1, y))
    walls -= passable

    # Northwest workshop walls — Alfir's space (cols 1-14, rows 1-10)
    for x in range(1, 15):
        lines.append(_kw(x, 10)); walls.add((x, 10))
    for y in range(1, 10):
        lines.append(_kw(14, y)); walls.add((14, y))
    # Workshop door at (14, 7)+(14, 8)
    walls.discard((14, 7)); walls.discard((14, 8))

    # Northeast study walls — Bombastus's private room (cols 33-46, rows 1-10)
    for x in range(33, 47):
        lines.append(_kw(x, 10)); walls.add((x, 10))
    for y in range(1, 10):
        lines.append(_kw(33, y)); walls.add((33, y))
    # Study door at (33, 7)+(33, 8)
    walls.discard((33, 7)); walls.discard((33, 8))

    # Alchemy bench markers in workshop (rows 3-5, cols 3-8)
    for x in range(3, 9):
        lines.append(_kw(x, 5)); walls.add((x, 5))

    _kfill(W, H, lines, walls, color="Ha")

    lines.append(_ks(*SPAWN))

    # Alfir in his workshop
    lines.append(_kn(7, 3, "0006_WTCH"))

    for (x, y) in SOUTH:
        lines.append(_ke(x, y, "south", "lapidus_castle_main_hall", 27, 1))
    for (x, y) in NORTH:
        lines.append(_ke(x, y, "north", "lapidus_castle_second_floor", 23, 22))

    return _kbuild(lines, "lapidus_castle_first_floor",
                   "Castle Azoth — First Floor", SPAWN)


# ── Castle Azoth — Second Floor / Royal Chambers  (40 × 20) ──────────────────
#
# Private residential floor. Luminyx's chambers occupy the east wing.
# West wing: family library and private sitting room.
# Quieter, more intimate than the floors below.
# The stair north leads to Hypatia's tower study.
#
# NPCs:
#   Luminyx (0019_ROYL) — east wing (early game, before quest 0052_KLST)
#
# Exits:
#   South (19,19)+(20,19) → lapidus_castle_first_floor (23,1)+(24,1)
#   North (19,0)+(20,0)   → lapidus_castle_hypatia_tower (7,28)+(8,28)

def build_castle_second_floor() -> Zone:
    W, H = 40, 20
    SPAWN = (20, 14)

    SOUTH = {(19, H-1), (20, H-1)}
    NORTH = {(19, 0),   (20, 0)}
    passable = SOUTH | NORTH

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    _kperim(W, H, lines, passable)
    for x in range(W):
        walls.add((x, 0)); walls.add((x, H-1))
    for y in range(H):
        walls.add((0, y)); walls.add((W-1, y))
    walls -= passable

    # East wing divider — Luminyx's chambers (cols 22-38, rows 1-14)
    for y in range(1, 15):
        lines.append(_kw(22, y)); walls.add((22, y))
    # Chamber door at (22, 8)+(22, 9)
    walls.discard((22, 8)); walls.discard((22, 9))

    # West wing — library shelves (rows 2-4, cols 2-10)
    for x in range(2, 11):
        lines.append(_kw(x, 4)); walls.add((x, 4))

    _kfill(W, H, lines, walls, color="Ha")

    lines.append(_ks(*SPAWN))

    # Luminyx in her chambers
    lines.append(_kn(32, 8, "0019_ROYL"))

    for (x, y) in SOUTH:
        lines.append(_ke(x, y, "south", "lapidus_castle_first_floor", 23, 1))
    for (x, y) in NORTH:
        lines.append(_ke(x, y, "north", "lapidus_castle_hypatia_tower", 7, 28))

    return _kbuild(lines, "lapidus_castle_second_floor",
                   "Castle Azoth — Royal Chambers", SPAWN)


# ── Castle Azoth — Basement  (64 × 20)  [LOCKED Game 7] ─────────────────────
#
# The founding crime. The Stelladeva Arkship sank into a sinkhole here in the
# founding year 50 (~3677 AD); the castle was built on top of the burial.
# In Game 7 the basement is inaccessible — the locked door in the main hall
# stair corner registers as impassable. In Game 8 the grandchildren excavate.
#
# Zone exists but has no navigable exits in Game 7.
# The Arkship location is suggested by unusual floor geometry (a depression).

def build_castle_basement() -> Zone:
    W, H = 64, 20
    SPAWN = (32, 10)

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    # Fully enclosed — no exits in Game 7
    _kperim(W, H, lines, set())
    for x in range(W):
        walls.add((x, 0)); walls.add((x, H-1))
    for y in range(H):
        walls.add((0, y)); walls.add((W-1, y))

    # The Arkship depression — a rectangular void in the floor center
    # (rows 6-13, cols 20-43) — darker floor tiles marking the burial site
    for x in range(20, 44):
        for y in (6, 13):
            lines.append(_kw(x, y)); walls.add((x, y))
    for y in range(7, 13):
        lines.append(_kw(20, y)); walls.add((20, y))
        lines.append(_kw(43, y)); walls.add((43, y))

    _kfill(W, H, lines, walls, color="Ga")   # cold dark stone — Absolute Negative

    lines.append(_ks(*SPAWN))

    return _kbuild(lines, "lapidus_castle_basement",
                   "Castle Azoth — Basement", SPAWN)


# ── Castle Azoth — Hypatia's Tower  (16 × 30) ────────────────────────────────
#
# The tower study above the Royal Chambers — a narrow stone spire.
# Instrument tables, reference texts, worked alchemy residue on the sills.
# First accessible in 0010_KLST (Alfir's apprenticeship quest chain).
# The highest enclosed floor; the canopy lies one stair above.
#
# NPCs:
#   Hypatia (0000_0451) — at her instrument table, center north
#
# Exits:
#   South (7,29)+(8,29) → lapidus_castle_second_floor (19,18)+(20,18)
#   North (7,0)+(8,0)   → lapidus_castle_canopy (15,16)+(16,16)

def build_castle_hypatia_tower() -> Zone:
    W, H = 16, 30
    SPAWN = (8, 22)

    SOUTH = {(7, H-1), (8, H-1)}
    NORTH = {(7, 0),   (8, 0)}
    passable = SOUTH | NORTH

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    _kperim(W, H, lines, passable)
    for x in range(W):
        walls.add((x, 0)); walls.add((x, H-1))
    for y in range(H):
        walls.add((0, y)); walls.add((W-1, y))
    walls -= passable

    # Instrument table — long bench across north section (rows 4-5, cols 2-13)
    for x in range(2, 14):
        lines.append(_kw(x, 5)); walls.add((x, 5))

    # Bookshelf alcoves on west wall (rows 8,12,16,20 — single-tile depth)
    for sy in (8, 12, 16, 20):
        lines.append(_kw(1, sy)); walls.add((1, sy))

    # Observation nook — narrow ledge east wall (rows 10-14)
    for ny in range(10, 15):
        lines.append(_kw(W-2, ny)); walls.add((W-2, ny))

    _kfill(W, H, lines, walls, color="Ha")   # warm — scholarly warmth

    lines.append(_ks(*SPAWN))

    # Hypatia at her instrument table (one row above bench)
    lines.append(_kn(8, 3, "0000_0451"))

    for (x, y) in SOUTH:
        lines.append(_ke(x, y, "south", "lapidus_castle_second_floor", 19, 18))
    for (x, y) in NORTH:
        lines.append(_ke(x, y, "north", "lapidus_castle_canopy", 15, 16))

    return _kbuild(lines, "lapidus_castle_hypatia_tower",
                   "Hypatia's Tower", SPAWN)


# ── Castle Azoth — Canopy  (32 × 18) ─────────────────────────────────────────
#
# The fifth floor: an open canopy level where the castle's ancient trees
# break through the roof line. No ceiling. Mt. Elaene visible to the East.
# The highest accessible point in Castle Azoth in Game 7.
# Battlements form the perimeter; trees crowd the interior.
#
# Exits:
#   South (15,17)+(16,17) → lapidus_castle_hypatia_tower (7,28)+(8,28)

def build_castle_canopy() -> Zone:
    W, H = 32, 18
    SPAWN = (16, 10)

    SOUTH = {(15, H-1), (16, H-1)}
    passable = SOUTH

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    _kperim(W, H, lines, passable)
    for x in range(W):
        walls.add((x, 0)); walls.add((x, H-1))
    for y in range(H):
        walls.add((0, y)); walls.add((W-1, y))
    walls -= passable

    # Ancient trees growing through the floor (impassable trunks)
    # Irregular placement suggesting genuine growth, not design
    for (tx, ty) in [(4, 3), (5, 3), (4, 4),      # NW cluster
                     (26, 3), (27, 3), (27, 4),    # NE cluster
                     (9, 8), (10, 8),               # center-west
                     (21, 9), (22, 9),              # center-east
                     (6, 13), (7, 13),              # SW canopy
                     (24, 12), (25, 12)]:           # SE canopy
        lines.append(_kw(tx, ty)); walls.add((tx, ty))

    # Battlement crenellations — gaps in north wall
    for bx in (4, 8, 12, 16, 20, 24, 28):
        walls.discard((bx, 0))    # leave perimeter gap (decorative — not traversable)

    _kfill(W, H, lines, walls, color="El")   # El = Vector Yellow — sunlight, open sky

    lines.append(_ks(*SPAWN))

    for (x, y) in SOUTH:
        lines.append(_ke(x, y, "south", "lapidus_castle_hypatia_tower", 7, 28))

    return _kbuild(lines, "lapidus_castle_canopy",
                   "Castle Azoth — Canopy", SPAWN)