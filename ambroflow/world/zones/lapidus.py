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
         ↕ East
  lapidus_serpents_pass         Mountain defile.  East exit → Elaene desert (summit stub).

West of Castle Azoth:
  lapidus_dirt_trail            Caravan trail — plateau stone, wide dirt road.
         ↕ West
  lapidus_the_rocks             Hieronymus Coast enclave (assassins).
         ↕ West
  lapidus_ocean_shore           The Hieronymus Coast — open ocean to the west.

South of Youthspring Road (N/S only):
  lapidus_witch_forest          Forest commune.  One entrance: Youthspring Road south.

Unimplemented targets (show "(nothing that way yet)" in-game):
  lapidus_slum_interior         Azonithia Slum (9 warrens / 13 passages).
  lapidus_temple_interior       Temple of the Gods interior.
  lapidus_heartvein_interior    Heartvein Heights residential district.
  lapidus_mt_elaene_summit      Mt. Elaene summit / Elaene desert gateway (East terminus).
"""

from __future__ import annotations

from dataclasses import replace as _dc_replace

from ..map import (
    Realm, Zone, ZoneExit, ItemSpawn,
    NPCSchedule, NPCScheduleEntry, ZoneCondition,
)
from ..kobra_zone_loader import load_zone_from_kobra


# ── Vendor catalogs ───────────────────────────────────────────────────────────
#
# Maps character_id → {item_id: coin_price}.
# Referenced by WorldPlay to open vendor mode on NPC interaction.

VENDOR_CATALOGS: dict[str, dict[str, int]] = {
    "0018_TOWN": {   # Howard Stone — general market (June Street)
        "0073_KLOB": 5,
        "0074_KLOB": 8,
        "0040_KLOB": 3,
        "0075_KLOB": 12,
    },
    "0019_TOWN": {   # Lucy Clement — herbs and foraging (June Street)
        "0073_KLOB": 4,
        "0074_KLOB": 6,
        "0075_KLOB": 10,
    },
}


# ── Exit lists ────────────────────────────────────────────────────────────────

_WILTOLL_EXITS = [
    ZoneExit(x= 0, y=10, direction="west",
             target_zone="lapidus_azonithia_slum",       target_x=46, target_y=5),
    ZoneExit(x= 0, y=11, direction="west",
             target_zone="lapidus_azonithia_slum",       target_x=46, target_y=6),
    ZoneExit(x=59, y=10, direction="east",
             target_zone="lapidus_mt_elaene_trail",      target_x=1,  target_y=6),
    ZoneExit(x=59, y=11, direction="east",
             target_zone="lapidus_mt_elaene_trail",      target_x=1,  target_y=7),
    ZoneExit(x=11, y= 0, direction="north",
             target_zone="lapidus_litleaf_thoroughfare", target_x=0,  target_y=18),
    ZoneExit(x=12, y= 0, direction="north",
             target_zone="lapidus_litleaf_thoroughfare", target_x=1,  target_y=18),
    ZoneExit(x= 3, y= 8, direction="north",
             target_zone="player_home_ground",           target_x=23, target_y=11),
    ZoneExit(x= 4, y= 8, direction="north",
             target_zone="player_home_ground",           target_x=23, target_y=11),
    ZoneExit(x=20, y= 8, direction="north",
             target_zone="lapidus_elsa_house",           target_x=13, target_y=8),
    ZoneExit(x=21, y= 8, direction="north",
             target_zone="lapidus_elsa_house",           target_x=14, target_y=8),
    ZoneExit(x=48, y= 8, direction="north",
             target_zone="lapidus_hypatia_house",        target_x=19, target_y=11),
    ZoneExit(x=49, y= 8, direction="north",
             target_zone="lapidus_hypatia_house",        target_x=20, target_y=11),
]

_HOME_STAIR_EXIT = ZoneExit(
    x=9, y=2, direction="north",
    target_zone="player_home_upper", target_x=24, target_y=7,
)

_HOME_EXITS = [
    ZoneExit(x=20, y=12, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=3, target_y=8),
    ZoneExit(x=21, y=12, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=4, target_y=8),
]

_HOME_ITEM_SPAWNS = [
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
    ItemSpawn(x=3,  y=10, item_id="0016_KLIT", qty=50),  # Coins ×50 (foyer chest)
]

_LITLEAF_EXITS = [
    ZoneExit(x=0, y=19, direction="south",
             target_zone="lapidus_wiltoll_lane",  target_x=11, target_y=1),
    ZoneExit(x=1, y=19, direction="south",
             target_zone="lapidus_wiltoll_lane",  target_x=12, target_y=1),
    ZoneExit(x=0, y= 0, direction="north",
             target_zone="lapidus_slum_interior", target_x=10, target_y=18),
    ZoneExit(x=1, y= 0, direction="north",
             target_zone="lapidus_slum_interior", target_x=11, target_y=18),
]

_APPROACH_EXITS = [
    ZoneExit(x=47, y=11, direction="east",
             target_zone="lapidus_azonithia_heartvein", target_x=1,  target_y=5),
    ZoneExit(x=47, y=12, direction="east",
             target_zone="lapidus_azonithia_heartvein", target_x=1,  target_y=6),
    ZoneExit(x= 0, y=11, direction="west",
             target_zone="lapidus_dirt_trail",          target_x=18, target_y=5),
    ZoneExit(x= 0, y=12, direction="west",
             target_zone="lapidus_dirt_trail",          target_x=18, target_y=6),
    ZoneExit(x=22, y= 0, direction="north",
             target_zone="lapidus_castle_azoth",        target_x=18, target_y=19),
    ZoneExit(x=23, y= 0, direction="north",
             target_zone="lapidus_castle_azoth",        target_x=19, target_y=19),
]

_CASTLE_EXITS = [
    ZoneExit(x=18, y=19, direction="south",
             target_zone="lapidus_azoth_approach",   target_x=22, target_y=1),
    ZoneExit(x=19, y=19, direction="south",
             target_zone="lapidus_azoth_approach",   target_x=23, target_y=1),
    ZoneExit(x=19, y= 0, direction="north",
             target_zone="lapidus_castle_main_hall", target_x=27, target_y=28),
    ZoneExit(x=20, y= 0, direction="north",
             target_zone="lapidus_castle_main_hall", target_x=28, target_y=28),
]

# Alfir's daily schedule in the courtyard.
# Night: home with the witch community in the forest south of Azonithia.
_ALFIR_COURTYARD_SCHEDULE = NPCSchedule(
    character_id = "0006_WTCH",
    entries      = [
        NPCScheduleEntry("dawn",           x= 5, y= 7, activity="ritual"),
        NPCScheduleEntry("morning",        x= 3, y= 3, activity="work"),
        NPCScheduleEntry("afternoon",      x=25, y= 7, activity="patrol"),
        NPCScheduleEntry("late_afternoon", x= 5, y= 5, activity="ritual"),
        NPCScheduleEntry("dusk",           x= 5, y= 6, activity="ritual"),
        NPCScheduleEntry("night",          x= 5, y= 5, activity="sleep"),
    ],
)

_ELAENE_EXITS = [
    ZoneExit(x= 0, y=6, direction="west",
             target_zone="lapidus_wiltoll_lane",     target_x=58, target_y=10),
    ZoneExit(x= 0, y=7, direction="west",
             target_zone="lapidus_wiltoll_lane",     target_x=58, target_y=11),
    ZoneExit(x= 1, y=0, direction="north",
             target_zone="lapidus_mt_elaene_summit", target_x=9,  target_y=12),
    ZoneExit(x= 2, y=0, direction="north",
             target_zone="lapidus_mt_elaene_summit", target_x=10, target_y=12),
    ZoneExit(x=19, y=6, direction="east",
             target_zone="lapidus_serpents_pass",    target_x=1,  target_y=6),
    ZoneExit(x=19, y=7, direction="east",
             target_zone="lapidus_serpents_pass",    target_x=1,  target_y=7),
]

_PASS_EXITS = [
    ZoneExit(x= 0, y=6, direction="west",
             target_zone="lapidus_mt_elaene_trail",   target_x=18, target_y=6),
    ZoneExit(x= 0, y=7, direction="west",
             target_zone="lapidus_mt_elaene_trail",   target_x=18, target_y=7),
    ZoneExit(x=39, y=6, direction="east",
             target_zone="lapidus_mt_elaene_summit",  target_x=1,  target_y=6),
    ZoneExit(x=39, y=7, direction="east",
             target_zone="lapidus_mt_elaene_summit",  target_x=1,  target_y=7),
]

_DIRT_TRAIL_EXITS = [
    ZoneExit(x=29, y=5, direction="east",
             target_zone="lapidus_azoth_approach", target_x=1,  target_y=11),
    ZoneExit(x=29, y=6, direction="east",
             target_zone="lapidus_azoth_approach", target_x=1,  target_y=12),
    ZoneExit(x= 0, y=5, direction="west",
             target_zone="lapidus_the_rocks",      target_x=38, target_y=5),
    ZoneExit(x= 0, y=6, direction="west",
             target_zone="lapidus_the_rocks",      target_x=38, target_y=6),
]

_THE_ROCKS_EXITS = [
    ZoneExit(x=39, y=5, direction="east",
             target_zone="lapidus_dirt_trail",   target_x=1,  target_y=5),
    ZoneExit(x=39, y=6, direction="east",
             target_zone="lapidus_dirt_trail",   target_x=1,  target_y=6),
    ZoneExit(x= 0, y=5, direction="west",
             target_zone="lapidus_ocean_shore",  target_x=48, target_y=5),
    ZoneExit(x= 0, y=6, direction="west",
             target_zone="lapidus_ocean_shore",  target_x=48, target_y=6),
]

_WITCH_FOREST_EXITS = [
    ZoneExit(x=17, y=0, direction="north",
             target_zone="lapidus_youthspring_road", target_x=2, target_y=26),
    ZoneExit(x=18, y=0, direction="north",
             target_zone="lapidus_youthspring_road", target_x=3, target_y=26),
]

_OCEAN_SHORE_EXITS = [
    ZoneExit(x=49, y=5, direction="east",
             target_zone="lapidus_the_rocks", target_x=1, target_y=5),
    ZoneExit(x=49, y=6, direction="east",
             target_zone="lapidus_the_rocks", target_x=1, target_y=6),
]

# lapidus_warren_serpents_pass is the warren-chain zone (distinct from lapidus_serpents_pass
# which is the mountain pass east of Wiltoll). Zone-ID collision is a known TODO.
_OREBUSTLE_EXITS = [
    ZoneExit(x=5, y=0, direction="north",
             target_zone="lapidus_warren_serpents_pass", target_x=20, target_y=23),
    ZoneExit(x=6, y=0, direction="north",
             target_zone="lapidus_warren_serpents_pass", target_x=21, target_y=23),
    ZoneExit(x=39, y=5, direction="east",
             target_zone="lapidus_mine_entrance", target_x=1, target_y=5),
    ZoneExit(x=39, y=6, direction="east",
             target_zone="lapidus_mine_entrance", target_x=1, target_y=6),
]

_MINE_ENTRANCE_EXITS = [
    ZoneExit(x=0, y=5, direction="west",
             target_zone="lapidus_orebustle_road", target_x=38, target_y=5),
    ZoneExit(x=0, y=6, direction="west",
             target_zone="lapidus_orebustle_road", target_x=38, target_y=6),
]

_MARKET_EXITS = [
    ZoneExit(x=10, y=19, direction="south",
             target_zone="lapidus_azonithia_market", target_x=22, target_y=4),
    ZoneExit(x=11, y=19, direction="south",
             target_zone="lapidus_azonithia_market", target_x=23, target_y=4),
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

_HYPATIA_HOUSE_EXITS = [
    ZoneExit(x=19, y=12, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=48, target_y=8),
    ZoneExit(x=20, y=12, direction="south",
             target_zone="lapidus_wiltoll_lane", target_x=49, target_y=8),
]

_HYPATIA_HOUSE_ITEMS = [
    ItemSpawn(x=2,  y=3, item_id="0001_KLOB", qty=1),   # Mortar
    ItemSpawn(x=8,  y=3, item_id="0005_KLOB", qty=1),   # Retort
    ItemSpawn(x=3,  y=3, item_id="0007_KLOB", qty=2),   # Reagent Bottles
    ItemSpawn(x=12, y=3, item_id="0073_KLOB", qty=2),   # Herb (Common)
    ItemSpawn(x=13, y=3, item_id="0017_KLOB", qty=1),   # Crucible
    ItemSpawn(x=16, y=3, item_id="0041_KLOB", qty=1),   # Moldavite
    ItemSpawn(x=15, y=3, item_id="0042_KLOB", qty=1),   # Desert Glass
    ItemSpawn(x=20, y=5, item_id="0001_KLIT", qty=1),   # The dagger (fallback)
]


# ── Low-level tile emitters ───────────────────────────────────────────────────
#
# Each function returns one line of Kobra placement notation.
# The kobra loader resolves these to WorldTileKind values.

def _wall(x: int, y: int) -> str:
    return f"g|{x},{y} : [Vo Ka]"

def _floor(x: int, y: int, mat: str = "floor") -> str:
    return f"g|{x},{y} : [Va Ha {mat}]"

def _grass(x: int, y: int) -> str:
    return f"g|{x},{y} : [Va Ki grass]"

def _road(x: int, y: int) -> str:
    return f"g|{x},{y} : [Va Ru road]"

def _tree(x: int, y: int) -> str:
    return f"g|{x},{y} : [Vo Ki tree]"

def _water(x: int, y: int) -> str:
    return f"g|{x},{y} : [Va Fu water]"

def _stone(x: int, y: int) -> str:
    return f"g|{x},{y} : [Va Na stone]"

def _dirt(x: int, y: int) -> str:
    return f"g|{x},{y} : [Va Ung dirt]"

def _mat(x: int, y: int, name: str) -> str:
    return f"g|{x},{y} : [Va Ha {name}]"

def _spawn_tile(x: int, y: int) -> str:
    return f"g|{x},{y} : [Va Ha St]"

def _npc_tile(x: int, y: int, npc_id: str) -> str:
    return f"g|{x},{y} : [Va Ha Lo {npc_id}]"

def _portal(x: int, y: int, dungeon_id: str, mat: str = "Ung") -> str:
    return f"g|{x},{y} : [Va {mat} Ro {dungeon_id}]"

def _build(lines: list[str], zone_id: str, name: str, realm: Realm,
           spawn: tuple[int, int], exits: list) -> Zone:
    return load_zone_from_kobra(
        source       = "\n".join(lines),
        zone_id      = zone_id,
        name         = name,
        realm        = realm,
        player_spawn = spawn,
        exits        = exits,
    )


# ── House footprint helper ────────────────────────────────────────────────────

def _house(lines: list[str], x0: int, x1: int, y0: int, y1: int,
           door_cols: tuple[int, int]) -> None:
    """Rectangular house footprint: perimeter walls, floor inside, doors on south wall."""
    dc0, dc1 = door_cols
    for x in range(x0, x1 + 1):
        lines.append(_wall(x, y0))
        if x in (dc0, dc1):
            lines.append(_floor(x, y1, "door"))
        else:
            lines.append(_wall(x, y1))
    for y in range(y0 + 1, y1):
        lines.append(_wall(x0, y))
        lines.append(_wall(x1, y))
        for x in range(x0 + 1, x1):
            lines.append(_floor(x, y))


# ── Wiltoll Lane ──────────────────────────────────────────────────────────────
#
# 60 wide × 22 tall.
# Three houses on the North verge: player home (cols 1–9), Elsa's (cols 15–23),
# Hypatia's (cols 44–55).  Road rows 10–11 (East–West).  Litleaf fork at cols
# 11–12 running North.  Sparse tree scattering South of road; dense woodland
# at far South (rows 20–21).
#
# Exits:
#   West  (0,10)+(0,11)   → lapidus_azonithia_slum
#   East  (59,10)+(59,11) → lapidus_mt_elaene_trail
#   North (11,0)+(12,0)   → lapidus_litleaf_thoroughfare
#   North (3,8)+(4,8)     → player_home_ground
#   North (20,8)+(21,8)   → lapidus_elsa_house
#   North (48,8)+(49,8)   → lapidus_hypatia_house

_WILTOLL_SPARSE_13 = (2, 17, 23, 30, 36, 43, 50)
_WILTOLL_SPARSE_19 = (3, 4, 5, 6, 14, 15, 16, 21, 22, 23,
                      30, 31, 32, 33, 34, 41, 42, 43, 50, 51, 52)


def build_wiltoll_lane() -> Zone:
    W, H = 60, 22
    lines: list[str] = []

    for y in range(H):
        for x in range(W):
            lines.append(_grass(x, y))

    # Litleaf fork road: cols 11-12, rows 0-9
    for y in range(10):
        lines.append(_road(11, y))
        lines.append(_road(12, y))

    # Main road rows 10-11
    for y in (10, 11):
        for x in range(W):
            lines.append(_road(x, y))

    # Three houses
    _house(lines, 1, 9, 2, 7, (3, 4))       # player home
    _house(lines, 15, 23, 2, 7, (20, 21))   # Elsa
    _house(lines, 44, 55, 2, 7, (48, 49))   # Hypatia

    # Sparse trees rows 13-14
    for x in _WILTOLL_SPARSE_13:
        lines.append(_tree(x, 13))
        lines.append(_tree(x, 14))

    # Sparse trees row 19
    for x in _WILTOLL_SPARSE_19:
        lines.append(_tree(x, 19))

    # Dense woodland rows 20-21
    for y in (20, 21):
        for x in range(W):
            lines.append(_tree(x, y))

    lines.append(_spawn_tile(3, 8))
    lines.append(_npc_tile(20, 8, "0024_TOWN"))   # Elsa

    return _build(lines, "lapidus_wiltoll_lane", "Wiltoll Lane",
                  Realm.LAPIDUS, (3, 8), _WILTOLL_EXITS)


# ── Player Home Interior (Wiltoll Lane) ───────────────────────────────────────
#
# 40 wide × 13 tall.
# Three rooms: Bedroom (cols 1–10), Kitchen (cols 12–25), Meditation (cols 27–38).
# Vertical dividers at cols 0, 11, 26, 39.
# Row 8: inner wall with room doors at cols 5, 19, 33.
# Rows 9–11: Foyer.  Row 12: south wall, door at cols 20–21.
#
# Exits:
#   North (9,2)           → player_home_upper (staircase)
#   South (20,12)+(21,12) → lapidus_wiltoll_lane

def build_wiltoll_home() -> Zone:
    W, H = 40, 13
    lines: list[str] = []

    # North wall
    for x in range(W):
        lines.append(_wall(x, 0))

    # Row 1: decorative back wall (impassable throughout)
    for x in range(W):
        lines.append(_wall(x, 1))

    # Rows 2-7: three rooms with dividers
    for y in range(2, 8):
        for div in (0, 11, 26, W - 1):
            lines.append(_wall(div, y))
        for x in range(1, 11):          # Bedroom
            lines.append(_floor(x, y))
        for x in range(12, 26):         # Kitchen
            lines.append(_floor(x, y))
        for x in range(27, 39):         # Meditation
            lines.append(_floor(x, y))

    # Staircase at (9,2) — north-east corner of Bedroom
    lines.append(_floor(9, 2, "stairs_up"))

    # Inner wall row 8, doors at 5, 19, 33
    for x in range(W):
        if x in (5, 19, 33):
            lines.append(_floor(x, 8, "door"))
        else:
            lines.append(_wall(x, 8))

    # Foyer rows 9-11
    for y in range(9, 12):
        lines.append(_wall(0, y))
        lines.append(_wall(W - 1, y))
        for x in range(1, W - 1):
            lines.append(_floor(x, y))

    # South wall, door at 20-21
    for x in range(W):
        if x in (20, 21):
            lines.append(_floor(x, 12, "door"))
        else:
            lines.append(_wall(x, 12))

    lines.append(_spawn_tile(8, 10))

    zone = _build(lines, "lapidus_wiltoll_home", "Wiltoll Home — Interior",
                  Realm.LAPIDUS, (8, 10), _HOME_EXITS + [_HOME_STAIR_EXIT])
    zone.item_spawns = list(_HOME_ITEM_SPAWNS)
    return zone


# ── Litleaf Thoroughfare ──────────────────────────────────────────────────────
#
# 20 wide × 20 tall.  N–S road (cols 0–1) connecting Wiltoll Lane to Hopefare St.

def build_litleaf_thoroughfare() -> Zone:
    W, H = 20, 20
    lines: list[str] = []
    for y in range(H):
        for x in range(W):
            if x < 2:
                lines.append(_road(x, y))
            else:
                lines.append(_grass(x, y))
    return _build(lines, "lapidus_litleaf_thoroughfare", "Litleaf Thoroughfare",
                  Realm.LAPIDUS, (0, 18), _LITLEAF_EXITS)


# ── Azonithia Avenue sections ─────────────────────────────────────────────────
#
# 48 wide × 16 tall.  Common structure:
#   rows 0–4   North side — district inlet at cols 22–23 (paving material).
#   rows 5–6   Main road (East–West).
#   row  7     Southern grass verge.
#   row  8     Sparse trees (cols 4,10,16,22,28,34,40,46).
#   rows 9–15  Dense woodland.
#
# The inlet material identifies the district character:
#   yellow_brick (Y) — Hopefare / honest poverty
#   ceramic      (C) — June Quarter / commercial warmth
#   slate        (L) — Goldshoot / institutional gravity
#   silica       (X) — Youthspring / extravagant expense

_AVENUE_SPARSE = (4, 10, 16, 22, 28, 34, 40, 46)

_INLET_MATERIAL: dict[str, str] = {
    "Y": "yellow_brick",
    "C": "ceramic",
    "L": "slate",
    "X": "silica",
    "M": "marble",
}


def _avenue_zone(
    zone_id:    str,
    name:       str,
    inlet_char: str,
    east_zone:  str = "",
    west_zone:  str = "",
    north_zone: str = "",
) -> Zone:
    W, H = 48, 16
    mat   = _INLET_MATERIAL.get(inlet_char, "floor")
    lines: list[str] = []

    for y in range(5):
        for x in range(W):
            if x in (22, 23):
                lines.append(_mat(x, y, mat))
            else:
                lines.append(_grass(x, y))

    for y in (5, 6):
        for x in range(W):
            lines.append(_road(x, y))

    for x in range(W):
        lines.append(_grass(x, 7))

    for x in range(W):
        if x in _AVENUE_SPARSE:
            lines.append(_tree(x, 8))
        else:
            lines.append(_grass(x, 8))

    for y in range(9, H):
        for x in range(W):
            lines.append(_tree(x, y))

    exits: list[ZoneExit] = []
    if east_zone:
        exits += [ZoneExit(x=47, y=5, direction="east",
                           target_zone=east_zone, target_x=1,  target_y=5),
                  ZoneExit(x=47, y=6, direction="east",
                           target_zone=east_zone, target_x=1,  target_y=6)]
    if west_zone:
        exits += [ZoneExit(x=0,  y=5, direction="west",
                           target_zone=west_zone, target_x=46, target_y=5),
                  ZoneExit(x=0,  y=6, direction="west",
                           target_zone=west_zone, target_x=46, target_y=6)]
    if north_zone:
        exits += [ZoneExit(x=22, y=0, direction="north",
                           target_zone=north_zone, target_x=10, target_y=18),
                  ZoneExit(x=23, y=0, direction="north",
                           target_zone=north_zone, target_x=11, target_y=18)]

    return _build(lines, zone_id, name, Realm.LAPIDUS, (24, 5), exits)


def build_azonithia_slum() -> Zone:
    return _avenue_zone(
        zone_id    = "lapidus_azonithia_slum",
        name       = "Azonithia Avenue — Hopefare Street",
        inlet_char = "Y",
        east_zone  = "lapidus_wiltoll_lane",
        west_zone  = "lapidus_azonithia_market",
        north_zone = "lapidus_slum_interior",
    )


def build_azonithia_market() -> Zone:
    return _avenue_zone(
        zone_id    = "lapidus_azonithia_market",
        name       = "Azonithia Avenue — June Street",
        inlet_char = "C",
        east_zone  = "lapidus_azonithia_slum",
        west_zone  = "lapidus_azonithia_temple",
        north_zone = "lapidus_june_quarter",
    )


def build_azonithia_temple() -> Zone:
    return _avenue_zone(
        zone_id    = "lapidus_azonithia_temple",
        name       = "Azonithia Avenue — Goldshoot Street",
        inlet_char = "L",
        east_zone  = "lapidus_azonithia_market",
        west_zone  = "lapidus_azonithia_heartvein",
        north_zone = "lapidus_goldshoot_street",
    )


def build_azonithia_heartvein() -> Zone:
    return _avenue_zone(
        zone_id    = "lapidus_azonithia_heartvein",
        name       = "Azonithia Avenue — Youthspring Road",
        inlet_char = "X",
        east_zone  = "lapidus_azonithia_temple",
        west_zone  = "lapidus_azoth_approach",
        north_zone = "lapidus_youthspring_road",
    )


# ── Azoth Approach (Orchard + Azoth Sprint) ───────────────────────────────────
#
# 48 wide × 22 tall.
# Old-Earth orchard trees flank the marble sprint (cols 22–23) for rows 1–10.
# Left orchard: cols 4–20.  Right orchard: cols 25–41.
# Road rows 11–12 (Azonithia Avenue W/E exits).
# Dense woodland South (rows 15–21).
#
# Exits:
#   East  (47,11)+(47,12) → lapidus_azonithia_heartvein
#   West  (0,11)+(0,12)   → lapidus_dirt_trail
#   North (22,0)+(23,0)   → lapidus_castle_azoth

def build_azoth_approach() -> Zone:
    W, H = 48, 22
    lines: list[str] = []

    # Row 0: marble sprint start, grass elsewhere
    for x in range(W):
        if x in (22, 23):
            lines.append(_mat(x, 0, "marble"))
        else:
            lines.append(_grass(x, 0))

    # Rows 1-10: orchard flanking the marble sprint
    for y in range(1, 11):
        for x in range(W):
            if x in (22, 23):
                lines.append(_mat(x, y, "marble"))
            elif 4 <= x <= 20 or 25 <= x <= 41:
                lines.append(_tree(x, y))
            else:
                lines.append(_grass(x, y))

    # Rows 11-12: road
    for y in (11, 12):
        for x in range(W):
            lines.append(_road(x, y))

    # Row 13: grass verge
    for x in range(W):
        lines.append(_grass(x, 13))

    # Row 14: sparse trees
    for x in range(W):
        if x in _AVENUE_SPARSE:
            lines.append(_tree(x, 14))
        else:
            lines.append(_grass(x, 14))

    # Rows 15-21: dense woodland
    for y in range(15, H):
        for x in range(W):
            lines.append(_tree(x, y))

    return _build(lines, "lapidus_azoth_approach",
                  "Azoth Approach — The Orchard",
                  Realm.LAPIDUS, (22, 11), _APPROACH_EXITS)


# ── Castle Azoth ──────────────────────────────────────────────────────────────
#
# 40 wide × 20 tall.
# Interior courtyard rows 0–16.  Zodiac fountain rows 5–9, cols 10–18:
#   stone outer ring, water basin, stone zodiac markers at center (row 7, cols 13–15).
# South inner wall row 17 with gate at cols 17–18.
# Stone plaza row 18.  Marble sprint base row 19 (S exits).
#
# NPCs:
#   Alfir (0006_WTCH) — col 2, row 1.  Cosmic Witch, Daemonologist, 50s.
#   Hypatia (0000_0451) — col 28, row 14.  Present all night; beats everyone out of bed.
#
# Exits:
#   South (18,19)+(19,19) → lapidus_azoth_approach
#   North (19,0)+(20,0)   → lapidus_castle_main_hall

def build_castle_azoth() -> Zone:
    W, H = 40, 20
    lines: list[str] = []

    # North wall, gate at cols 19-20
    for x in range(W):
        if x in (19, 20):
            lines.append(_floor(x, 0, "door"))
        else:
            lines.append(_wall(x, 0))

    # Interior rows 1-16: side walls + floor
    for y in range(1, 17):
        lines.append(_wall(0, y))
        lines.append(_wall(W - 1, y))
        for x in range(1, W - 1):
            lines.append(_floor(x, y))

    # Fountain stone ring: perimeter of rows 5-9, cols 10-18
    for x in range(10, 19):
        lines.append(_stone(x, 5))
        lines.append(_stone(x, 9))
    for y in range(6, 9):
        lines.append(_stone(10, y))
        lines.append(_stone(18, y))

    # Water basin: rows 6-8, cols 11-17
    for y in range(6, 9):
        for x in range(11, 18):
            lines.append(_water(x, y))

    # Zodiac markers: row 7, cols 13-15 (stone islands in the water)
    for x in (13, 14, 15):
        lines.append(_stone(x, 7))

    # South inner wall row 17, gate at cols 17-18
    for x in range(W):
        if x in (17, 18):
            lines.append(_floor(x, 17, "door"))
        else:
            lines.append(_wall(x, 17))

    # Stone plaza row 18, marble sprint row 19
    for x in range(W):
        lines.append(_stone(x, 18))
        lines.append(_mat(x, 19, "marble"))

    lines.append(_npc_tile(2, 1, "0006_WTCH"))     # Alfir
    lines.append(_npc_tile(28, 14, "0000_0451"))   # Hypatia
    lines.append(_spawn_tile(10, 10))

    zone = _build(lines, "lapidus_castle_azoth", "Castle Azoth",
                  Realm.LAPIDUS, (10, 10), _CASTLE_EXITS)
    zone.npc_schedules = [_ALFIR_COURTYARD_SCHEDULE]
    zone.npc_spawns = [
        _dc_replace(npc, condition=ZoneCondition("0009_KLST", "pending"))
        if npc.character_id == "0006_WTCH"
        else _dc_replace(npc, condition=ZoneCondition("0002_KLST", "pending"))
        if npc.character_id == "0000_0451"
        else npc
        for npc in zone.npc_spawns
    ]
    return zone


# ── Mt. Elaene Trail ──────────────────────────────────────────────────────────
#
# 20 wide × 14 tall.  Forest edge trail, dense canopy on either side.
# The Forest Witch (0007_WTCH) — gay male witch, folded Mercurie map —
# is in the clearing at (2,3).  Trail corridor: cols 1–2 throughout;
# rows 6–7 open full width (W/E passage and E exit to Serpent's Pass).
#
# Exits:
#   West  (0,6)+(0,7)   → lapidus_wiltoll_lane
#   North (1,0)+(2,0)   → lapidus_mt_elaene_summit
#   East  (19,6)+(19,7) → lapidus_serpents_pass

def build_mt_elaene_trail() -> Zone:
    W, H = 20, 14
    lines: list[str] = []

    # Base: dense forest
    for y in range(H):
        for x in range(W):
            lines.append(_tree(x, y))

    # Trail corridor: cols 1-2 open throughout, path continues south to witch forest
    for y in range(H):
        lines.append(_grass(1, y))
        lines.append(_grass(2, y))

    # Passage rows 6-7: full width open
    for y in (6, 7):
        for x in range(W):
            lines.append(_grass(x, y))

    lines.append(_npc_tile(2, 3, "0007_WTCH"))
    lines.append(_spawn_tile(2, 6))

    return _build(lines, "lapidus_mt_elaene_trail", "Mt. Elaene Trail",
                  Realm.LAPIDUS, (2, 6), _ELAENE_EXITS)


# ── Serpent's Pass ────────────────────────────────────────────────────────────
#
# 40 wide × 14 tall.  Mountain defile — stone walls North (row 0) and
# South (row 10) with stone side walls containing the pass interior.
# Wells (0002_TOWN) and Lavelle (0003_TOWN) camped near the East end
# (rows 5–6, col 38) — the aqueduct work site, quest 0003_KLST endpoint.
# Rows 11–13: open clearing South of the pass.
#
# Exits:
#   West  (0,6)+(0,7)   → lapidus_mt_elaene_trail
#   East  (39,6)+(39,7) → lapidus_mt_elaene_summit (Elaene desert, stub)

def build_serpents_pass() -> Zone:
    W, H = 40, 14
    lines: list[str] = []

    # Base: grass
    for y in range(H):
        for x in range(W):
            lines.append(_grass(x, y))

    # Mountain stone walls: row 0 (north), row 10 (south) — full width
    for x in range(W):
        lines.append(_stone(x, 0))
        lines.append(_stone(x, 10))

    # Stone side walls: col 0 and col 39, rows 1-9
    for y in range(1, 10):
        lines.append(_stone(0, y))
        lines.append(_stone(W - 1, y))

    lines.append(_npc_tile(38, 5, "0002_TOWN"))   # Wells — aqueduct foreman
    lines.append(_npc_tile(38, 6, "0003_TOWN"))   # Lavelle — laundry/explosives
    lines.append(_spawn_tile(5, 6))

    return _build(lines, "lapidus_serpents_pass", "Serpent's Pass",
                  Realm.LAPIDUS, (5, 6), _PASS_EXITS)


# ── Dirt Trail (West Caravan Road) ────────────────────────────────────────────
#
# 30 wide × 12 tall.  Caravan road leading west from Castle Azoth along the
# edge of the Hieronymus Plateau toward The Rocks on the Hieronymus Coast.
# Rocky plateau stone flanks a wide dirt path (rows 4–7).
#
# Exits:
#   East  (29,5)+(29,6) → lapidus_azoth_approach
#   West  (0,5)+(0,6)   → lapidus_the_rocks

def build_dirt_trail() -> Zone:
    W, H = 30, 12
    lines: list[str] = []

    # Base: rocky plateau stone (passable)
    for y in range(H):
        for x in range(W):
            lines.append(_stone(x, y))

    # Caravan road: wide dirt path rows 4-7
    for y in range(4, 8):
        for x in range(W):
            lines.append(_dirt(x, y))

    return _build(lines, "lapidus_dirt_trail", "The Dirt Trail",
                  Realm.LAPIDUS, (18, 5), _DIRT_TRAIL_EXITS)


# ── The Rocks (Assassin Enclave) ──────────────────────────────────────────────
#
# 40 wide × 14 tall.  Rugged Hieronymus Coast enclave west of the Hieronymus
# Plateau.  Home territory of Hue (0011_ASSN) and the assassin community.
# Stone formations, hidden clearings, coastal water at the south edge.
#
# Exits:
#   East  (39,5)+(39,6) → lapidus_dirt_trail

def build_the_rocks() -> Zone:
    W, H = 40, 14
    lines: list[str] = []

    # Base: coastal stone (rocky terrain)
    for y in range(H):
        for x in range(W):
            lines.append(_stone(x, y))

    # Hieronymus Coast — water at south edge
    for x in range(W):
        lines.append(_water(x, 13))
        lines.append(_water(x, 12))

    # Coastal grass strip above the waterline
    for x in range(W):
        lines.append(_grass(x, 11))
        lines.append(_grass(x, 10))

    # Central enclave clearing: cols 8-22, rows 3-9
    for y in range(3, 10):
        for x in range(8, 23):
            lines.append(_grass(x, y))

    # West clearing: cols 2-6, rows 3-8
    for y in range(3, 9):
        for x in range(2, 7):
            lines.append(_grass(x, y))

    # Stone formation between clearings (natural barrier)
    for y in range(2, 10):
        lines.append(_stone(7, y))

    # Hue in the central clearing (grass tile + NPC spawn)
    lines.append(f"g|15,7 : [Va Ki Lo 0011_ASSN]")

    return _build(lines, "lapidus_the_rocks", "The Rocks",
                  Realm.LAPIDUS, (28, 5), _THE_ROCKS_EXITS)


# ── Witch Forest Commune ──────────────────────────────────────────────────────
#
# 36 wide × 26 tall.  Dense forest south of Youthspring Road.
# Home of the Forest Witch (0007_WTCH) — the commune and their private wood.
# The only entrance is north, connecting directly back to Youthspring Road.
# Thick tree canopy on all sides; central clearing with grass and cottage.
# The Forest Witch's journal (found here) contains a folded Mercurie map.
#
# Exits:
#   North (17,0)+(18,0) → lapidus_youthspring_road (2,26)+(3,26)

def build_witch_forest() -> Zone:
    W, H = 36, 26

    # Path corridor from north entrance south to the clearing
    PATH_COLS = {17, 18}
    CLEAR_X0, CLEAR_X1 = 8, 27
    CLEAR_Y0, CLEAR_Y1 = 8, 18

    lines: list[str] = []

    # Base: dense tree canopy everywhere
    for y in range(H):
        for x in range(W):
            lines.append(_tree(x, y))

    # North approach path: cols 17-18, rows 0-7
    for y in range(8):
        for x in PATH_COLS:
            lines.append(_grass(x, y))

    # Widen path into the clearing top: cols 15-20, rows 6-8
    for y in range(6, 9):
        for x in range(15, 21):
            lines.append(_grass(x, y))

    # Commune clearing: grass floor
    for y in range(CLEAR_Y0, CLEAR_Y1 + 1):
        for x in range(CLEAR_X0, CLEAR_X1 + 1):
            lines.append(_grass(x, y))

    # Cottage footprint: stone walls cols 14-22, rows 11-16; floor inside
    for x in range(14, 23):
        lines.append(_stone(x, 11))
        lines.append(_stone(x, 16))
    for y in range(12, 16):
        lines.append(_stone(14, y))
        lines.append(_stone(22, y))
    for y in range(12, 16):
        for x in range(15, 22):
            lines.append(_floor(x, y))
    # Door on south wall
    lines.append(_floor(18, 16, "door"))

    # Forest Witch in the clearing outside the cottage
    lines.append(_npc_tile(11, 13, "0007_WTCH"))

    # Player spawn on the path just inside the tree line
    spawn = (17, 2)

    return _build(lines, "lapidus_witch_forest", "Witch Forest Commune",
                  Realm.LAPIDUS, spawn, _WITCH_FOREST_EXITS)


# ── Ocean Shore (Hieronymus Coast) ────────────────────────────────────────────
#
# 50 wide × 14 tall.  The open western coast of Lapidus.
# Coastal scrub at the top, sandy beach in the middle, ocean water below.
# Entered from The Rocks going west; the rest of the coast stretches away.
#
# Exits:
#   East (49,5)+(49,6) → lapidus_the_rocks (1,5)+(1,6)

def build_ocean_shore() -> Zone:
    W, H = 50, 14

    lines: list[str] = []

    # Base: ocean water (rows 7-13)
    for y in range(7, H):
        for x in range(W):
            lines.append(_water(x, y))

    # Sandy beach (rows 4-6) — passable
    for y in range(4, 7):
        for x in range(W):
            lines.append(_dirt(x, y))

    # Coastal scrub (rows 1-3): alternating grass and sparse trees
    for y in range(1, 4):
        for x in range(W):
            if (x + y) % 5 == 0:
                lines.append(_tree(x, y))
            else:
                lines.append(_grass(x, y))

    # Stone cliff edge (row 0): rocky lip above the scrub
    for x in range(W):
        lines.append(_stone(x, 0))

    # Player spawns on the beach, away from the Rocks exit
    spawn = (20, 5)

    return _build(lines, "lapidus_ocean_shore", "The Hieronymus Coast",
                  Realm.LAPIDUS, spawn, _OCEAN_SHORE_EXITS)


# ── Orebustle Road ────────────────────────────────────────────────────────────
#
# 40 wide × 14 tall.  Exterior road at the foot of Mt. Hieronymus, east of the
# Azonithia Slum warren chain.  Connects from the warrens' Serpent's Pass south
# exit (player arrives at x=5, y=5) and leads east to the mine entrance.
#
# NOTE: The north exits target lapidus_warren_serpents_pass — a distinct zone
# from the lapidus_serpents_pass mountain pass.  Zone-ID collision is a
# pre-existing TODO in the codebase.
#
# Exits:
#   North (5,0)+(6,0)   → lapidus_warren_serpents_pass
#   East  (39,5)+(39,6) → lapidus_mine_entrance

def build_orebustle_road() -> Zone:
    W, H = 40, 14
    lines: list[str] = []

    # Base: rocky plateau stone
    for y in range(H):
        for x in range(W):
            lines.append(_stone(x, y))

    # Dirt road rows 3-8 (east-west caravan road)
    for y in range(3, 9):
        for x in range(W):
            lines.append(_dirt(x, y))

    return _build(lines, "lapidus_orebustle_road", "Orebustle Road",
                  Realm.LAPIDUS, (5, 5), _OREBUSTLE_EXITS)


# ── Mine Entrance — Orebustle Mine Head ──────────────────────────────────────
#
# 40 wide × 16 tall.  The mine head above the three named shafts.
# Single entrance from Orebustle Road (west); three DungeonPortal tiles lead
# down into the Iron Shaft (7 F), Silver Shaft (8 F), and Gold Shaft (9 F).
#
# Portal colors encode shaft character:
#   Iron   (Ru, rust-red)  — shallowest, forge ore
#   Silver (Na, stone-grey) — mid depth, precious metal
#   Gold   (El, warm yellow) — deepest, rarest, desire_crystal_cache
#
# Exits:
#   West (0,5)+(0,6) → lapidus_orebustle_road

def build_mine_entrance() -> Zone:
    W, H = 40, 16
    lines: list[str] = []

    # Base: stone (mine yard)
    for y in range(H):
        for x in range(W):
            lines.append(_stone(x, y))

    # Dirt approach path from west (rows 4-9)
    for y in range(4, 10):
        for x in range(W):
            lines.append(_dirt(x, y))

    # Three shaft clearings (grass) — each one a distinct open area
    for y in range(2, 13):
        for x in range(5, 15):     # Iron shaft area
            lines.append(_grass(x, y))
        for x in range(17, 25):   # Silver shaft area
            lines.append(_grass(x, y))
        for x in range(27, 37):   # Gold shaft area
            lines.append(_grass(x, y))

    # Portal tiles — overwrite one grass cell in each clearing
    lines.append(_portal(10, 7, "mine_iron",   "Ru"))   # iron: rust-red
    lines.append(_portal(21, 7, "mine_silver", "Na"))   # silver: grey stone
    lines.append(_portal(32, 7, "mine_gold",   "El"))   # gold: warm yellow

    return _build(lines, "lapidus_mine_entrance", "Orebustle Mine Head",
                  Realm.LAPIDUS, (2, 6), _MINE_ENTRANCE_EXITS)


# ── Market Interior (June Street) ─────────────────────────────────────────────
#
# 48 wide × 20 tall.  Ceramic paving throughout.
# Stone stall counters (row 4, cols 8–13 and 28–33).
# Howard Stone (0018_TOWN) — stonemason, general market, west stall.
# Lucy Clement (0019_TOWN) — forager, herbs and materials, east stall.
#
# Exits:
#   South (10,19)+(11,19) → lapidus_azonithia_market

def build_market_interior() -> Zone:
    W, H = 48, 20
    lines: list[str] = []

    # North wall row 0
    for x in range(W):
        lines.append(_wall(x, 0))

    # Interior rows 1-16 (ceramic floor, side walls)
    for y in range(1, 17):
        lines.append(_wall(0, y))
        lines.append(_wall(W - 1, y))
        for x in range(1, W - 1):
            lines.append(_mat(x, y, "ceramic"))

    # Stone stall counters row 4
    for seg in ((8, 13), (28, 33)):
        for x in range(seg[0], seg[1] + 1):
            lines.append(_stone(x, 4))

    # Vendor NPCs row 3 (behind counters)
    lines.append(_npc_tile(10, 3, "0018_TOWN"))   # Howard Stone
    lines.append(_npc_tile(30, 3, "0019_TOWN"))   # Lucy Clement

    # South wall row 17, door at 20-21
    for x in range(W):
        if x in (20, 21):
            lines.append(_floor(x, 17, "door"))
        else:
            lines.append(_wall(x, 17))

    # Arrival strip rows 18-19 (ceramic exterior)
    for y in (18, 19):
        for x in range(W):
            lines.append(_mat(x, y, "ceramic"))

    lines.append(_spawn_tile(24, 9))

    return _build(lines, "lapidus_market_interior", "June Street Market",
                  Realm.LAPIDUS, (24, 9), _MARKET_EXITS)


# ── Elsa's House ──────────────────────────────────────────────────────────────
#
# 28 wide × 10 tall.  Warm, working-class interior.
# A chair by the window (col 6, row 3).  A clean kitchen corner.
# Elsa is met outside on the lane; this interior is for deeper conversation.
#
# Exits:
#   South (13,9)+(14,9) → lapidus_wiltoll_lane

def build_elsa_house() -> Zone:
    W, H = 28, 10
    lines: list[str] = []

    # North wall + decorative back wall
    for x in range(W):
        lines.append(_wall(x, 0))
        lines.append(_wall(x, 1))

    # Interior rows 2-8
    for y in range(2, H - 1):
        lines.append(_wall(0, y))
        lines.append(_wall(W - 1, y))
        for x in range(1, W - 1):
            lines.append(_floor(x, y))

    # South wall, door at 13-14
    for x in range(W):
        if x in (13, 14):
            lines.append(_floor(x, H - 1, "door"))
        else:
            lines.append(_wall(x, H - 1))

    lines.append(_spawn_tile(11, 5))

    zone = _build(lines, "lapidus_elsa_house", "Elsa's House",
                  Realm.LAPIDUS, (11, 5), _ELSA_EXITS)
    zone.item_spawns = list(_ELSA_ITEMS)
    return zone


# ── Hypatia's House ───────────────────────────────────────────────────────────
#
# 40 wide × 13 tall.  Workshop (cols 1–17) and living space (cols 19–38)
# divided at col 18 (rows 2–6); wall ends at row 7 — combined space below.
# Hypatia is at Castle Azoth.  The apparatus is hers; the dagger is fallback
# if the player misses the 0002_KLST scene.
#
# Exits:
#   South (19,12)+(20,12) → lapidus_wiltoll_lane

def build_hypatia_house() -> Zone:
    W, H = 40, 13
    lines: list[str] = []

    # North wall + decorative back wall
    for x in range(W):
        lines.append(_wall(x, 0))
        lines.append(_wall(x, 1))

    # Rows 2-6: two rooms with divider at col 18
    for y in range(2, 7):
        lines.append(_wall(0, y))
        lines.append(_wall(W - 1, y))
        lines.append(_wall(18, y))   # interior divider
        for x in range(1, 18):
            lines.append(_floor(x, y))
        for x in range(19, W - 1):
            lines.append(_floor(x, y))

    # Rows 7-11: open combined space
    for y in range(7, H - 1):
        lines.append(_wall(0, y))
        lines.append(_wall(W - 1, y))
        for x in range(1, W - 1):
            lines.append(_floor(x, y))

    # South wall, door at 19-20
    for x in range(W):
        if x in (19, 20):
            lines.append(_floor(x, H - 1, "door"))
        else:
            lines.append(_wall(x, H - 1))

    lines.append(_spawn_tile(18, 10))

    zone = _build(lines, "lapidus_hypatia_house", "Hypatia's House",
                  Realm.LAPIDUS, (18, 10), _HYPATIA_HOUSE_EXITS)
    zone.item_spawns = list(_HYPATIA_HOUSE_ITEMS)
    return zone


# ── Kobra zone helpers (lapidus material palette) ─────────────────────────────
#
# Colors encode material character via Shygazun byte table:
#   El  (byte 26, Rose, Vector Yellow)  — yellow brick: honest, working
#   Ka  (byte 29, Rose, Vector Indigo)  — slate: institutional, ancient-weight
#   Ha  (byte 43, Rose, Absolute Pos.)  — ceramic / general warm floor
#   Ga  (byte 44, Rose, Absolute Neg.)  — silica: extravagant, processed cold

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
#
# Exits:
#   South  (19,21)+(20,21) → lapidus_azonithia_slum (22,1)+(23,1)
#   East   (39,10)+(39,11) → lapidus_warren_faithsalt (1,5)+(1,6)
#   West   (0,10)+(0,11)   → stub

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

    for x in (10, 20, 30):
        for y in (5, 16):
            lines.append(_kw(x, y))
            walls.add((x, y))

    _kfill(W, H, lines, walls, color="El")

    lines.append(_ks(*SPAWN))

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
# Long market corridor.  Ceramic tile throughout.
# Stall counters line both sides of a central walkway.
# Howard Stone (0018_TOWN) and Lucy Clement (0019_TOWN) at north stalls.
#
# Exits:
#   South (39,11)+(40,11) → lapidus_azonithia_market (22,1)+(23,1)
#   East  (79,5)+(79,6)   → stub

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

    for seg_start in (2, 22, 42, 62):
        for x in range(seg_start, seg_start + 16):
            lines.append(_kw(x, 2))
            walls.add((x, 2))

    for seg_start in (2, 22, 42, 62):
        for x in range(seg_start, seg_start + 16):
            lines.append(_kw(x, 9))
            walls.add((x, 9))

    _kfill(W, H, lines, walls, color="Ha")

    lines.append(_ks(*SPAWN))

    lines.append(_kn(10, 1, "0018_TOWN"))   # Howard Stone — general market
    lines.append(_kn(30, 1, "0019_TOWN"))   # Lucy Clement — herb specialist

    for (x, y) in SOUTH_EXITS:
        lines.append(_ke(x, y, "south", "lapidus_azonithia_market", 22, 1))
    for (x, y) in EAST_EXITS:
        lines.append(_ke(x, y, "east", "lapidus_june_east_stub", 1, 5))

    return _kbuild(lines, "lapidus_june_quarter", "June Quarter", SPAWN)


# ── Goldshoot Street  (16 × 36) ──────────────────────────────────────────────
#
# Slate-paved approach to the Temple of the Gods.
# Narrow, deep — the length gives the approach its institutional gravity.
# Sidhal (0004_TOWN) is the temple custodian; met here on the way up.
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

    for col_x in (3, 12):
        for row_y in (8, 16, 24):
            lines.append(_kw(col_x, row_y))
            walls.add((col_x, row_y))

    _kfill(W, H, lines, walls, color="Ka")

    lines.append(_ks(*SPAWN))
    lines.append(_kn(8, 20, "0004_TOWN"))    # Sidhal: temple custodian

    for (x, y) in SOUTH_EXITS:
        lines.append(_ke(x, y, "south", "lapidus_azonithia_temple", 22, 1))
    for (x, y) in NORTH_EXITS:
        lines.append(_ke(x, y, "north", "lapidus_temple_interior", 7, 34))

    return _kbuild(lines, "lapidus_goldshoot_street", "Goldshoot Street", SPAWN)


# ── Youthspring Road  (22 × 28) ──────────────────────────────────────────────
#
# Melted silica approach to Heartvein Heights.
# Wider than Goldshoot — wealth demands space underfoot.
# Nexiott (0017_ROYL) encountered here — caravan boss, radio network owner.
#
# Exits:
#   South (10,27)+(11,27) → lapidus_azonithia_heartvein (22,1)+(23,1)
#   South  (2,27)+ (3,27) → lapidus_witch_forest (17,1)+(18,1)  [west-side forest path]
#   North (10,0)+(11,0)   → lapidus_heartvein_interior (stub)

def build_youthspring_road() -> Zone:
    W, H = 22, 28
    SPAWN = (11, 22)

    SOUTH_EXITS        = {(10, H-1), (11, H-1)}
    SOUTH_FOREST_EXITS = {( 2, H-1), ( 3, H-1)}
    NORTH_EXITS        = {(10, 0),   (11, 0)}
    passable = SOUTH_EXITS | SOUTH_FOREST_EXITS | NORTH_EXITS

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    _kperim(W, H, lines, passable)
    walls.update({(x, 0) for x in range(W)} | {(x, H-1) for x in range(W)})
    walls.update({(0, y) for y in range(H)} | {(W-1, y) for y in range(H)})
    walls -= passable

    for vx in (5, 16):
        for vy in range(4, 24, 4):
            lines.append(_kw(vx, vy))
            walls.add((vx, vy))

    _kfill(W, H, lines, walls, color="Ga")

    lines.append(_ks(*SPAWN))
    lines.append(_kn(11, 14, "0017_ROYL"))   # Nexiott on Youthspring Road

    for (x, y) in SOUTH_EXITS:
        lines.append(_ke(x, y, "south", "lapidus_azonithia_heartvein", 22, 1))
    for (x, y) in SOUTH_FOREST_EXITS:
        lines.append(_ke(x, y, "south", "lapidus_witch_forest", 17, 1))
    for (x, y) in NORTH_EXITS:
        lines.append(_ke(x, y, "north", "lapidus_heartvein_interior", 10, 26))

    return _kbuild(lines, "lapidus_youthspring_road", "Youthspring Road", SPAWN)


# ── Castle Azoth — Main Hall / Lottery Chamber  (56 × 30) ────────────────────
#
# Ground floor. Designed to make people feel small — wide formal hall,
# central aisle, raised dais at the north end where Bombastus presides.
# Columns create lanes.
#
# Exits:
#   South (27,29)+(28,29) → lapidus_castle_azoth courtyard (19,1)+(20,1)
#   West  (0,14)+(0,15)   → lapidus_castle_west_wing (stub)
#   North (27,0)+(28,0)   → lapidus_castle_first_floor (27,28)+(28,28)

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

    for x in range(18, 38):
        for y in (3, 6):
            lines.append(_kw(x, y)); walls.add((x, y))
    for y in range(4, 6):
        lines.append(_kw(18, y)); walls.add((18, y))
        lines.append(_kw(37, y)); walls.add((37, y))

    for ry in (8, 12, 16, 20):
        for cx in (8, 47):
            lines.append(_kw(cx, ry)); walls.add((cx, ry))

    for x in (2, 3):
        for y in (2, 3):
            lines.append(_kw(x, y)); walls.add((x, y))

    _kfill(W, H, lines, walls, color="Ha")

    lines.append(_ks(*SPAWN))
    lines.append(_kn(27, 4, "ROYL_BOMBASTUS"))

    for (x, y) in SOUTH:
        lines.append(_ke(x, y, "south", "lapidus_castle_azoth", 19, 1))
    for (x, y) in NORTH:
        lines.append(_ke(x, y, "north", "lapidus_castle_first_floor", 27, 28))
    for (x, y) in WEST:
        lines.append(_ke(x, y, "west", "lapidus_castle_west_stub", 1, 5))

    return _kbuild(lines, "lapidus_castle_main_hall", "Castle Azoth — Lottery Hall", SPAWN)


# ── Castle Azoth — First Floor  (48 × 24) ─────────────────────────────────────
#
# Administrative wing. Alfir's workshop (northwest). Bombastus's study (northeast).
# Alfir only appears here after 0009_KLST (before that: courtyard below).
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

    for x in range(1, 15):
        lines.append(_kw(x, 10)); walls.add((x, 10))
    for y in range(1, 10):
        lines.append(_kw(14, y)); walls.add((14, y))
    walls.discard((14, 7)); walls.discard((14, 8))

    for x in range(33, 47):
        lines.append(_kw(x, 10)); walls.add((x, 10))
    for y in range(1, 10):
        lines.append(_kw(33, y)); walls.add((33, y))
    walls.discard((33, 7)); walls.discard((33, 8))

    for x in range(3, 9):
        lines.append(_kw(x, 5)); walls.add((x, 5))

    _kfill(W, H, lines, walls, color="Ha")

    lines.append(_ks(*SPAWN))
    lines.append(_kn(7, 3, "0006_WTCH"))

    for (x, y) in SOUTH:
        lines.append(_ke(x, y, "south", "lapidus_castle_main_hall", 27, 1))
    for (x, y) in NORTH:
        lines.append(_ke(x, y, "north", "lapidus_castle_second_floor", 23, 22))

    zone = _kbuild(lines, "lapidus_castle_first_floor",
                   "Castle Azoth — First Floor", SPAWN)
    zone.npc_spawns = [
        _dc_replace(npc, condition=ZoneCondition("0009_KLST", "witnessed"))
        if npc.character_id == "0006_WTCH"
        else npc
        for npc in zone.npc_spawns
    ]
    return zone


# ── Castle Azoth — Second Floor / Royal Chambers  (40 × 20) ──────────────────
#
# Private residential floor. Luminyx's chambers (east wing).
# West wing: family library and sitting room.
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

    for y in range(1, 15):
        lines.append(_kw(22, y)); walls.add((22, y))
    walls.discard((22, 8)); walls.discard((22, 9))

    for x in range(2, 11):
        lines.append(_kw(x, 4)); walls.add((x, 4))

    _kfill(W, H, lines, walls, color="Ha")

    lines.append(_ks(*SPAWN))
    lines.append(_kn(32, 8, "0019_ROYL"))

    for (x, y) in SOUTH:
        lines.append(_ke(x, y, "south", "lapidus_castle_first_floor", 23, 1))
    for (x, y) in NORTH:
        lines.append(_ke(x, y, "north", "lapidus_castle_hypatia_tower", 7, 28))

    return _kbuild(lines, "lapidus_castle_second_floor",
                   "Castle Azoth — Royal Chambers", SPAWN)


# ── Castle Azoth — Basement  (64 × 20)  [LOCKED Game 7] ─────────────────────
#
# The founding crime. The Stelladeva Arkship sank into a sinkhole here in
# founding year 50 (~3677 AD); the castle was built on top.
# Inaccessible in Game 7. The grandchildren excavate in Game 8.

def build_castle_basement() -> Zone:
    W, H = 64, 20
    SPAWN = (32, 10)

    lines: list[str] = []
    walls: set[tuple[int, int]] = set()

    _kperim(W, H, lines, set())
    for x in range(W):
        walls.add((x, 0)); walls.add((x, H-1))
    for y in range(H):
        walls.add((0, y)); walls.add((W-1, y))

    for x in range(20, 44):
        for y in (6, 13):
            lines.append(_kw(x, y)); walls.add((x, y))
    for y in range(7, 13):
        lines.append(_kw(20, y)); walls.add((20, y))
        lines.append(_kw(43, y)); walls.add((43, y))

    _kfill(W, H, lines, walls, color="Ga")

    lines.append(_ks(*SPAWN))

    return _kbuild(lines, "lapidus_castle_basement",
                   "Castle Azoth — Basement", SPAWN)


# ── Castle Azoth — Hypatia's Tower  (16 × 30) ────────────────────────────────
#
# Narrow stone spire above the Royal Chambers.
# Instrument tables, reference texts, worked alchemy residue on the sills.
# First accessible in 0010_KLST.
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

    for x in range(2, 14):
        lines.append(_kw(x, 5)); walls.add((x, 5))

    for sy in (8, 12, 16, 20):
        lines.append(_kw(1, sy)); walls.add((1, sy))

    for ny in range(10, 15):
        lines.append(_kw(W-2, ny)); walls.add((W-2, ny))

    _kfill(W, H, lines, walls, color="Ha")

    lines.append(_ks(*SPAWN))
    lines.append(_kn(8, 3, "0000_0451"))

    for (x, y) in SOUTH:
        lines.append(_ke(x, y, "south", "lapidus_castle_second_floor", 19, 18))
    for (x, y) in NORTH:
        lines.append(_ke(x, y, "north", "lapidus_castle_canopy", 15, 16))

    return _kbuild(lines, "lapidus_castle_hypatia_tower",
                   "Hypatia's Tower", SPAWN)


# ── Castle Azoth — Glass Canopy  (32 × 18) ───────────────────────────────────
#
# Fifth floor: a greenhouse canopy capping Hypatia's tower.
# Iron-framed glass panels — glazing bar intersections at cols 6,12,18,24
# × rows 4,8,12.  El-colored fill: sunlight through glass.
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

    for bx in (6, 12, 18, 24):
        for by in (4, 8, 12):
            lines.append(_kw(bx, by)); walls.add((bx, by))

    _kfill(W, H, lines, walls, color="El")

    lines.append(_ks(*SPAWN))

    for (x, y) in SOUTH:
        lines.append(_ke(x, y, "south", "lapidus_castle_hypatia_tower", 7, 28))

    return _kbuild(lines, "lapidus_castle_canopy",
                   "Castle Azoth — Glass Canopy", SPAWN)
