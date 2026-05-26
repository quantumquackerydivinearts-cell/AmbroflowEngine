"""
Mercurie Zones -- Ko's Labyrinth (7_KLGS)
==========================================
The Faewilds. Gated by the hypnotic_meditation perk (quest 0007_KLST).

Two entry points from Lapidus:
  - Ocean shore at low tide  (lapidus_ocean_shore → mercurie_threshold)
  - Lapidus mines deepest level (not yet built — stub exit)

Zone topology:
  mercurie_threshold   ← liminal crossing point
      ↓ South  → lapidus_ocean_shore
      ↓ North  → tideglass / rootbloom
  tideglass            ← still water, glass light, water-Fae refracted
  cindergrove          ← warm-barked ash trees, ember Fae zone
  rootbloom            ← inhabited Fae settlement (most approachable)
  thornveil            ← shrouded, hostile-leaning Fae zone
  dewspire             ← Fae Queen Amelia's domain (temple-like)
"""
from __future__ import annotations
from ..map import Realm, Zone, ZoneExit
from ..kobra_zone_loader import load_zone_from_kobra


# ── Tile emitters ─────────────────────────────────────────────────────────────

def _tree(x, y):             return f"g|{x},{y} : [Vo Ki tree]"
def _grass(x, y):            return f"g|{x},{y} : [Va Ki grass]"
def _water(x, y):            return f"g|{x},{y} : [Va Fu water]"
def _thorn(x, y):            return f"g|{x},{y} : [Vo Ka thorn]"
def _faelight(x, y):         return f"g|{x},{y} : [Va AE faelight]"
def _spawn(x, y):            return f"g|{x},{y} : [Va Ki St]"
def _npc(x, y, nid):         return f"g|{x},{y} : [Va Ki Lo {nid}]"
def _portal(x, y, dungeon_id): return f"g|{x},{y} : [Va AE Ro {dungeon_id}]"


def _build(lines: list[str], zone_id: str, name: str,
           spawn: tuple[int, int], exits: list[ZoneExit]) -> Zone:
    return load_zone_from_kobra(
        source="\n".join(lines),
        zone_id=zone_id, name=name, realm=Realm.MERCURIE,
        player_spawn=spawn, exits=exits,
    )


# ── Mercurie Threshold ────────────────────────────────────────────────────────
#
# 52 wide × 14 tall. Liminal space — the light bends here.
# Entry from south (ocean shore). Exits north to tideglass and rootbloom.
# Three faelight paths mark the crossing. Tide-water below.
#
# Exits:
#   South (25,13)+(26,13) → lapidus_ocean_shore
#   NW    (1,0)+(2,0)     → mercurie_tideglass
#   NE    (49,0)+(50,0)   → mercurie_rootbloom

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
    W, H = 52, 14
    lines: list[str] = []

    # Row 0: tree canopy with grass openings at the two exit pairs
    for x in range(W):
        if x in (1, 2, 49, 50):
            lines.append(_grass(x, 0))
        else:
            lines.append(_tree(x, 0))

    # Rows 1-2: open grassland
    for y in range(1, 3):
        for x in range(W):
            lines.append(_grass(x, y))

    # Rows 3, 5, 8: faelight paths at odd columns 1..47
    for y in (3, 5, 8):
        for x in range(W):
            if x % 2 == 1 and 1 <= x <= 47:
                lines.append(_faelight(x, y))
            else:
                lines.append(_grass(x, y))

    # Rows 4, 6, 7: open grassland
    for y in (4, 6, 7):
        for x in range(W):
            lines.append(_grass(x, y))

    # Rows 9-10: grassland above the tide line
    for y in (9, 10):
        for x in range(W):
            lines.append(_grass(x, y))

    # Rows 11-12: tide-water
    for y in (11, 12):
        for x in range(W):
            lines.append(_water(x, y))

    # Row 13: tide-water with grass exit gap at cols 25-26
    for x in range(W):
        if x in (25, 26):
            lines.append(_grass(x, 13))
        else:
            lines.append(_water(x, 13))

    lines.append(_spawn(25, 9))
    return _build(lines, "mercurie_threshold", "Mercurie Threshold", (25, 9), _THRESHOLD_EXITS)


# ── Tideglass ─────────────────────────────────────────────────────────────────
#
# 40 wide × 16 tall. Still water, glass light, water-Fae refracted.
# A tidal pool ringed with grass. Faelight path runs east-west.
# Exits: South → threshold, East → cindergrove, West → rootbloom

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
    W, H = 40, 16
    lines: list[str] = []

    # Rows 0-1: open water
    for y in range(2):
        for x in range(W):
            lines.append(_water(x, y))

    # Rows 2-4: tidal pool — water frame with grass interior
    for y in range(2, 5):
        for x in range(W):
            if x == 0 or x == W - 1:
                lines.append(_water(x, y))
            else:
                lines.append(_grass(x, y))

    # Row 5: water closing the pool
    for x in range(W):
        lines.append(_water(x, 5))

    # Rows 6-7: open grassland (W/E exits)
    for y in (6, 7):
        for x in range(W):
            lines.append(_grass(x, y))

    # Row 8: faelight path at positions 1, 4, 7, ... (every 3rd col from 1)
    for x in range(W):
        if x % 3 == 1:
            lines.append(_faelight(x, 8))
        else:
            lines.append(_grass(x, 8))

    # Row 9: open grass
    for x in range(W):
        lines.append(_grass(x, 9))

    # Rows 10-12: woodland belt
    for y in range(10, 13):
        for x in range(W):
            lines.append(_tree(x, y))

    # Rows 13-15: open grassland (south exits)
    for y in range(13, H):
        for x in range(W):
            lines.append(_grass(x, y))

    lines.append(_portal(20, 3, "fae_undine_deep"))   # pool depths — water Fae
    lines.append(_spawn(20, 7))
    return _build(lines, "mercurie_tideglass", "Tideglass", (20, 7), _TG_EXITS)


# ── Cindergrove ───────────────────────────────────────────────────────────────
#
# 40 wide × 16 tall. Warm-barked ash trees, drifting embers.
# Exits: West → tideglass, East → thornveil, South → rootbloom

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
    W, H = 40, 16
    lines: list[str] = []

    # Rows 0-1: dense woodland canopy
    for y in range(2):
        for x in range(W):
            lines.append(_tree(x, y))

    # Row 2: dappled canopy edge — alternating tree and grass
    for x in range(W):
        if x % 2 == 0:
            lines.append(_tree(x, 2))
        else:
            lines.append(_grass(x, 2))

    # Rows 3-5: tree border + grass clearing interior
    for y in range(3, 6):
        for x in range(W):
            if x == 0 or x == W - 1:
                lines.append(_tree(x, y))
            else:
                lines.append(_grass(x, y))

    # Rows 6-7: open grassland (W/E exits)
    for y in (6, 7):
        for x in range(W):
            lines.append(_grass(x, y))

    # Rows 8-9: tree border + grass interior
    for y in (8, 9):
        for x in range(W):
            if x == 0 or x == W - 1:
                lines.append(_tree(x, y))
            else:
                lines.append(_grass(x, y))

    # Rows 10-11: woodland belt
    for y in (10, 11):
        for x in range(W):
            lines.append(_tree(x, y))

    # Rows 12-15: open grassland (south exits)
    for y in range(12, H):
        for x in range(W):
            lines.append(_grass(x, y))

    lines.append(_portal(20, 4, "fae_salamander_forge"))   # forge ember — fire Fae
    lines.append(_spawn(20, 7))
    return _build(lines, "mercurie_cindergrove", "Cindergrove", (20, 7), _CG_EXITS)


# ── Rootbloom ─────────────────────────────────────────────────────────────────
#
# 48 wide × 18 tall. Fae settlement woven between tree roots. Most approachable.
# Fae children, bioluminescent lanterns, genuine hospitality (if Fae relations allow).
# Five tree-root huts at y=3-8. Faelight ring frames the settlement at y=1.
#
# Exits:
#   North (12,0)+(13,0)   → mercurie_cindergrove
#   West  (0,14)+(0,15)   → mercurie_tideglass
#   South (23,17)+(24,17) → mercurie_threshold
#   East  (47,14)+(47,15) → mercurie_thornveil

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


def _fae_hut(lines: list[str], x0: int, y0: int) -> None:
    """5×6 tree-root hut: top/bottom walls at y0 and y0+5, left/right at x0 and x0+4."""
    for x in range(x0, x0 + 5):
        lines.append(f"g|{x},{y0} : [Vo Ki tree]")      # top wall
        lines.append(f"g|{x},{y0+5} : [Vo Ki tree]")    # bottom wall
    for y in range(y0 + 1, y0 + 5):
        lines.append(f"g|{x0},{y} : [Vo Ki tree]")        # left wall
        lines.append(f"g|{x0+4},{y} : [Vo Ki tree]")      # right wall
        for x in range(x0 + 1, x0 + 4):
            lines.append(f"g|{x},{y} : [Va Ha floor]")    # interior


def build_rootbloom() -> Zone:
    W, H = 48, 18
    lines: list[str] = []

    # Row 0: tree canopy with grass exits at cols 12-13 (north to cindergrove)
    for x in range(W):
        if x in (12, 13):
            lines.append(_grass(x, 0))
        else:
            lines.append(_tree(x, 0))

    # Row 1: faelight ring marking the settlement boundary
    lines.append(_tree(0, 1))
    for x in range(1, W - 1):
        lines.append(_faelight(x, 1))
    lines.append(_tree(W - 1, 1))

    # Row 2: tree border, grass interior
    lines.append(_tree(0, 2))
    for x in range(1, W - 1):
        lines.append(_grass(x, 2))
    lines.append(_tree(W - 1, 2))

    # Rows 3-11: tree border + grass interior (huts will overwrite rows 3-8)
    for y in range(3, 12):
        lines.append(_tree(0, y))
        for x in range(1, W - 1):
            lines.append(_grass(x, y))
        lines.append(_tree(W - 1, y))

    # Five Fae huts at y0=3, evenly spaced across the settlement
    for hut_x0 in (1, 9, 17, 25, 33):
        _fae_hut(lines, hut_x0, 3)

    # Player spawn
    lines.append(_spawn(1, 10))

    # Rows 12-13: dense woodland belt
    for y in (12, 13):
        for x in range(W):
            lines.append(_tree(x, y))

    # Rows 14-17: open grassland — all four edge exits are passable here
    for y in range(14, H):
        for x in range(W):
            lines.append(_grass(x, y))

    lines.append(_portal(24, 9, "fae_dryad_grove"))    # root-tree shrine — wood Fae
    lines.append(_portal(40, 9, "fae_gnome_warren"))   # burrow mouth — earth Fae
    return _build(lines, "mercurie_rootbloom", "Rootbloom", (1, 10), _RB_EXITS)


# ── Thornveil ─────────────────────────────────────────────────────────────────
#
# 40 wide × 14 tall. Deliberate thorned bramble — Fae warning-and-wall.
# Hostile-leaning if Fae relations are poor; navigable if Rootbloom quest active.
# Thorn walls form a corridor with two inner gaps for the vertical exits.
# Exits: West → cindergrove, South → rootbloom, North → dewspire

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
    W, H = 40, 14
    lines: list[str] = []

    # Row 0: full thorn wall (impassable until Rootbloom quest clears it)
    for x in range(W):
        lines.append(_thorn(x, 0))

    # Rows 1-5: thorn border + grass interior
    for y in range(1, 6):
        for x in range(W):
            if x == 0 or x == W - 1:
                lines.append(_thorn(x, y))
            else:
                lines.append(_grass(x, y))

    # Rows 6-7: open grassland (west exit to cindergrove)
    for y in (6, 7):
        for x in range(W):
            lines.append(_grass(x, y))

    # Rows 8-9: thorn border + grass interior
    for y in (8, 9):
        for x in range(W):
            if x == 0 or x == W - 1:
                lines.append(_thorn(x, y))
            else:
                lines.append(_grass(x, y))

    # Row 10: thorn wall with gap at cols 18-19 (south exit to rootbloom)
    for x in range(W):
        if x in (18, 19):
            lines.append(_grass(x, 10))
        else:
            lines.append(_thorn(x, 10))

    # Row 11: open grass (south exit passable row)
    for x in range(W):
        lines.append(_grass(x, 11))

    # Row 12: thorn wall with gap at cols 18-19 (north exit to dewspire)
    for x in range(W):
        if x in (18, 19):
            lines.append(_grass(x, 12))
        else:
            lines.append(_thorn(x, 12))

    # Row 13: open grass (north exit passable row)
    for x in range(W):
        lines.append(_grass(x, 13))

    lines.append(_spawn(20, 7))
    return _build(lines, "mercurie_thornveil", "Thornveil", (20, 7), _TV_EXITS)


# ── Dewspire ──────────────────────────────────────────────────────────────────
#
# 40 wide × 14 tall. Sacred Fae spire — Fae Queen Amelia's domain.
# At the crown of the oldest tree, dewdrops held in permanent suspension.
# Amelia (1004_NYMP) is present here — key NPC for quest 0013_KLST.
# Faelight forms a diamond: widest at rows 3-5, narrowing to a point.
# Exit: South → thornveil

_DS_EXITS = [
    ZoneExit(x=19, y=11, direction="south",
             target_zone="mercurie_thornveil", target_x=18, target_y=12),
    ZoneExit(x=20, y=11, direction="south",
             target_zone="mercurie_thornveil", target_x=19, target_y=12),
]

# Faelight column ranges for each row of the diamond (rows 0-8)
_DS_FAELIGHT = [
    (16, 24),  # row 0 — narrow peak
    (14, 26),  # row 1
    (12, 28),  # row 2
    (10, 30),  # row 3
    (10, 30),  # row 4 — widest (Amelia at col 17)
    (10, 30),  # row 5
    (12, 28),  # row 6
    (14, 26),  # row 7
    (16, 24),  # row 8 — narrow base
]


def build_dewspire() -> Zone:
    W, H = 40, 14
    lines: list[str] = []

    # Faelight diamond (rows 0-8)
    for y, (fl_lo, fl_hi) in enumerate(_DS_FAELIGHT):
        for x in range(W):
            if fl_lo <= x < fl_hi:
                lines.append(_faelight(x, y))
            else:
                lines.append(_grass(x, y))

    # Amelia — Fae Queen, quest 0013_KLST fulcrum
    lines.append(_npc(17, 4, "1004_NYMP"))

    # Rows 9-13: open grassland below the spire crown
    for y in range(9, H):
        for x in range(W):
            lines.append(_grass(x, y))

    lines.append(_portal(20, 6, "fae_faerie_court"))   # crown gate — Fae Court
    lines.append(_spawn(20, 9))
    return _build(lines, "mercurie_dewspire", "Dewspire", (20, 9), _DS_EXITS)
