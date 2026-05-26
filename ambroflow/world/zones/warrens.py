"""
warrens.py — Zone builders for the Azonithia Slum warrens (7_KLGS).

9 warren zones + Cestii Alley passage + Serpent's Pass exit plaza.

Zone topology (quest 0003_KLST route):
  lapidus_azonithia_slum
    ──Lovecraft Lane──►  lapidus_warren_faithsalt        (60×10, enclosed)
    ──Breakheart Blvd──► lapidus_warren_gethsemane       (40×30, open)
    ──Lockstep Lane──►   lapidus_warren_lithos           (50×40, enclosed labyrinth)
    ──Whistletoe Walk──► lapidus_warren_manchester       (40×25, open)
    ──Dervish Ave──►     lapidus_warren_samwise          (40×40, enclosed ring)
    ──Cestii Alley──►    lapidus_cestii_alley            (8×20, narrow)
    ──────────────────►  lapidus_warren_rhododendron     (55×12, enclosed)
    ──Heartache Alley──► lapidus_warren_aetherfield      (65×45, open, largest)
    ──Sundershoot St──►  lapidus_warren_kidney           (45×35, open)
    ──July/Aug/Dec──►    lapidus_warren_grimes           (50×35, mixed industrial)
    ──Georgia St──►      lapidus_serpents_pass           (40×25, narrows to plaza)
    ──Orebustle Rd──►    exterior (lapidus_orebustle_road)

Material: Aeralune soapstone — enclosed zones feel underground even when they aren't.
Open zones: garden / grass floor. The Grimes: dirt.
"""

from __future__ import annotations

from ..kobra_zone_loader import load_zone_from_kobra
from ..map import Realm, Zone


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _wall(x: int, y: int, layer: str = "g") -> str:
    return f"{layer}|{x},{y} : [Vo Ka]"

def _floor(x: int, y: int, layer: str = "g", color: str = "Ha") -> str:
    return f"{layer}|{x},{y} : [Va {color}]"

def _spawn(x: int, y: int, layer: str = "g") -> str:
    return f"{layer}|{x},{y} : [Va Ha St]"

def _npc(x: int, y: int, npc_id: str, layer: str = "g") -> str:
    return f"{layer}|{x},{y} : [Va Ha Lo {npc_id}]"

def _exit(x: int, y: int, direction: str, target: str, tx: int, ty: int,
          label: str = "", layer: str = "g") -> str:
    lex = f"{direction} {target} {tx} {ty}"
    if label:
        lex += f" {label}"
    return f"{layer}|{x},{y} : [Va Ha Ne {lex}]"

def _build(lines: list[str], zone_id: str, name: str,
           spawn: tuple[int, int] = (1, 1)) -> Zone:
    return load_zone_from_kobra(
        source       = "\n".join(lines),
        zone_id      = zone_id,
        name         = name,
        realm        = Realm.LAPIDUS,
        player_spawn = spawn,
    )

def _perimeter(W: int, H: int, lines: list[str],
               passable: set[tuple[int,int]] | None = None) -> None:
    """Add perimeter walls, skipping any positions in `passable`."""
    skip = passable or set()
    for x in range(W):
        if (x, 0) not in skip:     lines.append(_wall(x, 0))
        if (x, H-1) not in skip:   lines.append(_wall(x, H-1))
    for y in range(1, H-1):
        if (0, y) not in skip:     lines.append(_wall(0, y))
        if (W-1, y) not in skip:   lines.append(_wall(W-1, y))

def _fill_floor(W: int, H: int, lines: list[str],
                walls: set[tuple[int,int]],
                color: str = "Ha") -> None:
    """Fill every non-wall interior position with floor tiles."""
    for y in range(1, H-1):
        for x in range(1, W-1):
            if (x, y) not in walls:
                lines.append(_floor(x, y, color=color))


# ─────────────────────────────────────────────────────────────────────────────
# 1. Faithsalt Corridor  (60 × 10, enclosed)
#    Long soapstone artery — the entry passage of the warren district.
#    Joshua (0014_TOWN) lives here, works in Lithos Alleys.
# ─────────────────────────────────────────────────────────────────────────────

def build_faithsalt() -> Zone:
    W, H = 60, 10
    SPAWN = (3, 5)
    ENTRY = (0, 5)    # from lapidus_azonithia_slum via Lovecraft Lane
    EXIT  = (59, 5)   # to Gethsemane via Breakheart Boulevard

    lines: list[str] = []
    passable = {ENTRY, EXIT}
    _perimeter(W, H, lines, passable)

    # Interior floor
    for y in range(1, H-1):
        for x in range(1, W-1):
            lines.append(_floor(x, y))

    # Structural pillars breaking the monotony (impassable)
    for px in (15, 30, 45):
        lines.append(_wall(px, 2))
        lines.append(_wall(px, 7))

    lines.append(_spawn(*SPAWN))
    lines.append(_npc(10, 5, "0014_TOWN"))   # Joshua lives here
    lines.append(_exit(*ENTRY, "west",  "lapidus_slum_interior",    38, 10, "Lovecraft_Lane"))
    lines.append(_exit(*EXIT,  "east",  "lapidus_warren_gethsemane", 2, 15, "Breakheart_Boulevard"))

    return _build(lines, "lapidus_warren_faithsalt", "Faithsalt Corridor", SPAWN)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Gethsemane Gardens  (40 × 30, open sky)
#    Burial garden. Sidhal + Marcia live here.
#    Lyra (0016_TOWN) and Vaxian (0017_TOWN) Graves work here.
# ─────────────────────────────────────────────────────────────────────────────

def build_gethsemane() -> Zone:
    W, H = 40, 30
    SPAWN = (20, 15)
    ENTRY = (20, 0)    # from Faithsalt via Breakheart Boulevard
    EXIT  = (20, 29)   # to Lithos via Lockstep Lane

    lines: list[str] = []
    passable = {ENTRY, EXIT}
    _perimeter(W, H, lines, passable)

    # Grave garden area — grass tiles in the burial section (south half)
    burial_grass = {(x, y) for x in range(8, 32) for y in range(16, 26)}
    # Stone path through the garden
    path_tiles   = {(20, y) for y in range(1, 29)} | {(x, 10) for x in range(1, 39)}

    for y in range(1, H-1):
        for x in range(1, W-1):
            if (x, y) in burial_grass and (x, y) not in path_tiles:
                lines.append(_floor(x, y, color="Ki"))   # grass
            else:
                lines.append(_floor(x, y, color="Ha"))   # stone path

    lines.append(_spawn(*SPAWN))
    lines.append(_npc( 8, 8,  "0004_TOWN"))   # Sidhal (home)
    lines.append(_npc(12, 8,  "0010_TOWN"))   # Marcia (home)
    lines.append(_npc(15, 20, "0016_TOWN"))   # Lyra Graves (works here)
    lines.append(_npc(20, 20, "0017_TOWN"))   # Vaxian Graves (works here)
    lines.append(_exit(*ENTRY, "north", "lapidus_warren_faithsalt",   57, 5,  "Breakheart_Boulevard"))
    lines.append(_exit(*EXIT,  "south", "lapidus_warren_lithos",      25, 2,  "Lockstep_Lane"))

    return _build(lines, "lapidus_warren_gethsemane", "Gethsemane Gardens", SPAWN)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Lithos Alleys  (50 × 40, enclosed labyrinth)
#    Soapstone maze with two shops.
#    Joshua's radio shop (0014_TOWN) — Nexiott-aligned.
#    Slag's metallurgy (0015_TOWN) — Fae-aligned.
#
#    Maze path (zigzag):
#      Enter (25,0) → left=Joshua's room | right=main path
#      y=10 wall (gap x=25-48) → zigzag east past wall
#      y=20 wall (gap x=1-23)  → cross west
#      y=30 wall (gap x=36-48) → cross east → Slag accessible by going N from gap
#      Exit (25,39)
# ─────────────────────────────────────────────────────────────────────────────

def build_lithos() -> Zone:
    W, H = 50, 40
    SPAWN = (25, 1)    # junction tile — player arrives and can go left (Joshua) or right (main path)
    ENTRY = (25, 0)    # from Gethsemane via Lockstep Lane
    EXIT  = (25, 39)   # to Manchester via Whistletoe Walkway

    # Internal wall positions
    internal: set[tuple[int,int]] = set()
    # Horizontal wall 1: y=10, x=1-24  (gap x=25-48)
    for x in range(1, 25):  internal.add((x, 10))
    # Horizontal wall 2: y=20, x=24-48 (gap x=1-23)
    for x in range(24, 49): internal.add((x, 20))
    # Horizontal wall 3: y=30, x=1-35  (gap x=36-48)
    for x in range(1, 36):  internal.add((x, 30))
    # Vertical wall A: x=25, y=2-9  (divides top chamber; y=1 left open as junction)
    for y in range(2, 10):  internal.add((25, y))
    # Vertical wall B: x=24, y=11-18 (y=19 left open so player can cross west to use Wall 2 gap)
    for y in range(11, 19): internal.add((24, y))
    # Vertical wall C: x=36, y=21-28 (y=29 left open so player can cross east to use Wall 3 gap)
    for y in range(21, 29): internal.add((36, y))

    lines: list[str] = []
    passable = {ENTRY, EXIT}
    _perimeter(W, H, lines, passable)

    for pos in internal:
        lines.append(_wall(*pos))

    _fill_floor(W, H, lines, internal)

    # Shop interaction nodes
    lines.append(f"g|8,5 : [Va Ha To joshua_radio_shop open_alchemy_ui]")
    lines.append(f"g|42,25 : [Va Ha To slag_metallurgy open_smelt_ui]")

    lines.append(_spawn(*SPAWN))
    lines.append(_exit(*ENTRY, "north", "lapidus_warren_gethsemane", 20, 27, "Lockstep_Lane"))
    lines.append(_exit(*EXIT,  "south", "lapidus_warren_manchester",  20, 2,  "Whistletoe_Walkway"))

    return _build(lines, "lapidus_warren_lithos", "Lithos Alleys", SPAWN)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Manchester Garden  (40 × 25, open sky)
#    Labour gathering space. Lavelle (0003_TOWN) + 2 kids live here.
# ─────────────────────────────────────────────────────────────────────────────

def build_manchester() -> Zone:
    W, H = 40, 25
    SPAWN = (20, 12)
    ENTRY = (20, 0)    # from Lithos via Whistletoe Walkway
    EXIT  = (20, 24)   # to Samwise via Dervish Avenue

    lines: list[str] = []
    passable = {ENTRY, EXIT}
    _perimeter(W, H, lines, passable)

    # Grass garden with stone paths
    for y in range(1, H-1):
        for x in range(1, W-1):
            on_path = (x == 20) or (y in (6, 18))
            lines.append(_floor(x, y, color="Ha" if on_path else "Ki"))

    lines.append(_spawn(*SPAWN))
    lines.append(_npc(15, 12, "0003_TOWN"))   # Lavelle (home)
    lines.append(_exit(*ENTRY, "north", "lapidus_warren_lithos",  25, 37, "Whistletoe_Walkway"))
    lines.append(_exit(*EXIT,  "south", "lapidus_warren_samwise", 20, 2,  "Dervish_Avenue"))

    return _build(lines, "lapidus_warren_manchester", "Manchester Garden", SPAWN)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Samwise Circuit  (40 × 40, enclosed ring)
#    A loop — walkable ring around a hollow central structure.
#    Wells (0002_TOWN) + Janine (0007_TOWN) live here.
# ─────────────────────────────────────────────────────────────────────────────

def build_samwise() -> Zone:
    W, H = 40, 40
    SPAWN = (20, 5)
    ENTRY = (20, 0)    # from Manchester via Dervish Avenue
    EXIT  = (20, 39)   # to Cestii Alley

    # Inner block (impassable central structure x=10-29, y=10-29)
    inner: set[tuple[int,int]] = set()
    for y in range(10, 30):
        for x in range(10, 30):
            inner.add((x, y))

    lines: list[str] = []
    passable = {ENTRY, EXIT}
    _perimeter(W, H, lines, passable)

    for pos in inner:
        lines.append(_wall(*pos))

    # Ring floor (between outer wall and inner block)
    for y in range(1, H-1):
        for x in range(1, W-1):
            if (x, y) not in inner:
                lines.append(_floor(x, y))

    lines.append(_spawn(*SPAWN))
    lines.append(_npc(5, 20,  "0002_TOWN"))   # Wells (home)
    lines.append(_npc(8, 20,  "0007_TOWN"))   # Janine (home)
    lines.append(_exit(*ENTRY, "north", "lapidus_warren_manchester", 20, 22, "Dervish_Avenue"))
    lines.append(_exit(*EXIT,  "south", "lapidus_cestii_alley",      4,  2,  "Cestii_Alley"))

    return _build(lines, "lapidus_warren_samwise", "Samwise Circuit", SPAWN)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Cestii Alley  (8 × 20, enclosed narrow passage)
#    Genovise's occult shop / black market access point.
#    Connects Samwise Circuit to Rhododendron Corridor.
# ─────────────────────────────────────────────────────────────────────────────

def build_cestii_alley() -> Zone:
    W, H = 8, 20
    SPAWN = (4, 10)
    ENTRY = (4, 0)     # from Samwise Circuit
    EXIT  = (4, 19)    # to Rhododendron

    lines: list[str] = []
    passable = {ENTRY, EXIT}
    _perimeter(W, H, lines, passable)

    for y in range(1, H-1):
        for x in range(1, W-1):
            lines.append(_floor(x, y))

    # Genovise's shop interaction node (mid-alley)
    lines.append(f"g|4,10 : [Va Ka To genovise_shop open_shop_ui]")

    lines.append(_spawn(*SPAWN))
    lines.append(_exit(*ENTRY, "north", "lapidus_warren_samwise",      20, 37, ""))
    lines.append(_exit(*EXIT,  "south", "lapidus_warren_rhododendron", 2,  6,  ""))

    return _build(lines, "lapidus_cestii_alley", "Cestii Alley", SPAWN)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Rhododendron Corridor  (55 × 12, enclosed)
#    Narrow covered corridor, flowering plants overhanging soapstone.
#    Genovise (0011_TOWN) lives at the west end.
# ─────────────────────────────────────────────────────────────────────────────

def build_rhododendron() -> Zone:
    W, H = 55, 12
    SPAWN = (10, 6)
    ENTRY = (0, 6)     # from Cestii Alley
    EXIT  = (54, 6)    # to Aetherfield via Heartache Alley

    lines: list[str] = []
    passable = {ENTRY, EXIT}
    _perimeter(W, H, lines, passable)

    # Interior: stone floor with grass tiles suggesting flowering plants at walls
    for y in range(1, H-1):
        for x in range(1, W-1):
            # Flowers overhang from the walls (top and bottom edge rows are grass)
            if y in (1, H-2) and x % 3 != 0:
                lines.append(_floor(x, y, color="Ki"))
            else:
                lines.append(_floor(x, y, color="Ha"))

    # Structural pillars
    for px in (18, 36):
        lines.append(_wall(px, 3))
        lines.append(_wall(px, 8))

    lines.append(_spawn(*SPAWN))
    lines.append(_npc(8, 6, "0011_TOWN"))    # Genovise (home)
    lines.append(_exit(*ENTRY, "west",  "lapidus_cestii_alley",       4,  17, ""))
    lines.append(_exit(*EXIT,  "east",  "lapidus_warren_aetherfield", 2,  22, "Heartache_Alley"))

    return _build(lines, "lapidus_warren_rhododendron", "Rhododendron Corridor", SPAWN)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Aetherfield  (65 × 45, open sky — largest zone)
#    The only truly roofless warren. Aqueduct visible overhead.
#    James (0005_TOWN) + Tyrone (0006_TOWN) live here.
# ─────────────────────────────────────────────────────────────────────────────

def build_aetherfield() -> Zone:
    W, H = 65, 45
    SPAWN = (32, 22)
    ENTRY = (0, 22)    # from Rhododendron via Heartache Alley
    EXIT  = (64, 22)   # to Kidney Park via Sundershoot Street

    lines: list[str] = []
    passable = {ENTRY, EXIT}
    _perimeter(W, H, lines, passable)

    # Open field: mostly grass, stone path through centre
    centre_path = {(x, 22) for x in range(1, W-1)} | {(32, y) for y in range(1, H-1)}
    # Aqueduct supports: stone pillars at regular intervals (suggest overhead structure)
    aqueduct = {(x, y) for x in range(10, W-5, 15) for y in (10, 34)}

    for y in range(1, H-1):
        for x in range(1, W-1):
            if (x, y) in aqueduct:
                lines.append(_wall(x, y))
            elif (x, y) in centre_path:
                lines.append(_floor(x, y, color="Ha"))
            else:
                lines.append(_floor(x, y, color="Ki"))

    lines.append(_spawn(*SPAWN))
    lines.append(_npc(28, 18, "0005_TOWN"))   # James (home)
    lines.append(_npc(36, 18, "0006_TOWN"))   # Tyrone (home)
    lines.append(_exit(*ENTRY, "west",  "lapidus_warren_rhododendron", 52, 6,  "Heartache_Alley"))
    lines.append(_exit(*EXIT,  "east",  "lapidus_warren_kidney",        2, 17, "Sundershoot_Street"))

    return _build(lines, "lapidus_warren_aetherfield", "Aetherfield", SPAWN)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Kidney Park  (45 × 35, open sky)
#    Organic curved park. Bar, carpenter, undertakers' home.
#    Jackie (0012_TOWN) + Gwev (0013_TOWN) live here.
#    Lyra (0016_TOWN) + Vaxian (0017_TOWN) Graves live here.
# ─────────────────────────────────────────────────────────────────────────────

def build_kidney() -> Zone:
    W, H = 45, 35
    SPAWN = (22, 17)
    ENTRY = (0, 17)    # from Aetherfield via Sundershoot Street
    EXIT  = (44, 17)   # to The Grimes via July/August/December passage

    # Organic "kidney" shape: curved walls cutting the northeast and southwest corners
    corner_walls: set[tuple[int,int]] = set()
    # Northeast curved corner (x=32-43, y=1-8)
    for y in range(1, 9):
        for x in range(32 + (8 - y), W-1):
            corner_walls.add((x, y))
    # Southwest curved corner (x=1-12, y=26-33)
    for y in range(26, H-1):
        for x in range(1, 13 - (y - 26)):
            corner_walls.add((x, y))

    lines: list[str] = []
    passable = {ENTRY, EXIT}
    _perimeter(W, H, lines, passable)

    for pos in corner_walls:
        lines.append(_wall(*pos))

    for y in range(1, H-1):
        for x in range(1, W-1):
            if (x, y) in corner_walls:
                continue
            on_path = (y == 17) or (x == 22)
            lines.append(_floor(x, y, color="Ha" if on_path else "Ki"))

    # Bar structure (small enclosed area for Gwev's bar — open front)
    for bx in range(28, 38):
        lines.append(_wall(bx, 8))    # back wall
    for by in range(9, 14):
        lines.append(_wall(28, by))   # left wall
        lines.append(_wall(37, by))   # right wall
    # Bar interior floor (overwrite the grass we just wrote)
    for by in range(9, 14):
        for bx in range(29, 37):
            lines.append(_floor(bx, by, color="Ha"))

    lines.append(_spawn(*SPAWN))
    lines.append(_npc(22, 12, "0012_TOWN"))   # Jackie (carpenter, home)
    lines.append(_npc(32, 11, "0013_TOWN"))   # Gwev  (bar, home)
    lines.append(_npc(14, 25, "0016_TOWN"))   # Lyra Graves (home)
    lines.append(_npc(20, 25, "0017_TOWN"))   # Vaxian Graves (home)
    lines.append(_exit(*ENTRY, "west",  "lapidus_warren_aetherfield", 62, 22, "Sundershoot_Street"))
    lines.append(_exit(*EXIT,  "east",  "lapidus_warren_grimes",       2, 17, "July_August_December"))

    return _build(lines, "lapidus_warren_kidney", "Kidney Park", SPAWN)


# ─────────────────────────────────────────────────────────────────────────────
# 10. The Grimes  (50 × 35, mixed — heaviest warren)
#     Industrial, mine-adjacent, partially enclosed.
#     Kaelith (0009_TOWN) + Joannah (0001_TOWN) + Hartwell (0008_TOWN).
# ─────────────────────────────────────────────────────────────────────────────

def build_grimes() -> Zone:
    W, H = 50, 35
    SPAWN = (8, 17)
    ENTRY = (0, 17)    # from Kidney Park via December Boulevard
    EXIT  = (49, 17)   # to Serpent's Pass via Georgia Street

    # Industrial structures (partial roofs / enclosed rooms)
    structures: set[tuple[int,int]] = set()
    # Structure A — northwest block (storage/housing)
    for y in range(3, 12):
        structures.add((5, y)); structures.add((18, y))
    for x in range(5, 19):
        structures.add((x, 3)); structures.add((x, 11))
    # Structure B — southeast block (forge/industrial)
    for y in range(20, 32):
        structures.add((28, y)); structures.add((44, y))
    for x in range(28, 45):
        structures.add((x, 20)); structures.add((x, 31))

    lines: list[str] = []
    passable = {ENTRY, EXIT}
    _perimeter(W, H, lines, passable)

    for pos in structures:
        lines.append(_wall(*pos))

    # Interior of structures becomes floor (rooms inside the structures)
    struct_interiors: set[tuple[int,int]] = set()
    for y in range(4, 11):
        for x in range(6, 18):
            struct_interiors.add((x, y))
    for y in range(21, 31):
        for x in range(29, 44):
            struct_interiors.add((x, y))

    for y in range(1, H-1):
        for x in range(1, W-1):
            if (x, y) in structures:
                continue
            if (x, y) in struct_interiors:
                lines.append(_floor(x, y, color="Ha"))
            else:
                lines.append(_floor(x, y, color="Ung"))   # dirt

    lines.append(_spawn(*SPAWN))
    lines.append(_npc(10, 7,  "0009_TOWN"))   # Kaelith (home)
    lines.append(_npc(14, 7,  "0001_TOWN"))   # Joannah (home)
    lines.append(_npc(35, 25, "0008_TOWN"))   # Hartwell (home)
    lines.append(_exit(*ENTRY, "west",  "lapidus_warren_kidney",  42, 17, "December_Boulevard"))
    lines.append(_exit(*EXIT,  "east",  "lapidus_warren_serpents_pass",   2, 22, "Georgia_Street"))

    return _build(lines, "lapidus_warren_grimes", "The Grimes", SPAWN)


# ─────────────────────────────────────────────────────────────────────────────
# 11. Serpent's Pass  (40 × 25)
#     Narrow soapstone canyon that widens into a plaza.
#     Wells (0002_TOWN) + Lavelle (0003_TOWN) are met here in 0003_KLST.
# ─────────────────────────────────────────────────────────────────────────────

def build_serpents_pass() -> Zone:
    W, H = 40, 25
    SPAWN = (20, 20)
    ENTRY = (0, 12)    # from The Grimes via Georgia Street (canyon entry)
    EXIT  = (20, 24)   # to Orebustle Road exterior

    # Canyon walls — narrow at north, widen toward south
    # Passable width per row:
    canyon_pass = {
        0:  range(18, 22),   # 4 wide at entry
        1:  range(17, 23),
        2:  range(16, 24),
        3:  range(15, 25),
        4:  range(14, 26),
        5:  range(12, 28),
        6:  range(10, 30),
        7:  range(8,  32),
        8:  range(6,  34),
        9:  range(4,  36),
        10: range(2,  38),
        11: range(1,  39),   # nearly full width
    }

    lines: list[str] = []

    # North wall (canyon entry row)
    for x in range(W):
        if x not in canyon_pass.get(0, range(0)):
            if (x, 0) != ENTRY:
                lines.append(_wall(x, 0))
        else:
            lines.append(_floor(x, 0))
    # ENTRY point
    lines.append(_exit(*ENTRY, "west", "lapidus_warren_grimes", 47, 17, "Georgia_Street"))

    # Canyon body rows 1-11
    for y in range(1, 12):
        passable_xs = canyon_pass.get(y, range(1, W-1))
        for x in range(W):
            if x == 0 or x == W-1:
                lines.append(_wall(x, y))
            elif x in passable_xs:
                lines.append(_floor(x, y))
            else:
                lines.append(_wall(x, y))

    # Plaza rows 12-23 (full width, open)
    for y in range(12, H-1):
        lines.append(_wall(0, y))
        lines.append(_wall(W-1, y))
        for x in range(1, W-1):
            lines.append(_floor(x, y, color="Ha"))

    # South wall
    for x in range(W):
        if (x, H-1) == EXIT:
            lines.append(_exit(*EXIT, "south", "lapidus_orebustle_road", 5, 5, "Orebustle_Road"))
        else:
            lines.append(_wall(x, H-1))

    lines.append(_spawn(*SPAWN))
    # Wells and Lavelle are here only during quest 0003_KLST — static spawns for ambient presence
    lines.append(_npc(15, 20, "0002_TOWN"))   # Wells
    lines.append(_npc(25, 20, "0003_TOWN"))   # Lavelle

    return _build(lines, "lapidus_warren_serpents_pass", "Serpent's Pass", SPAWN)


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

def build_all_warren_zones() -> list[Zone]:
    """Build and return all warren zones for inclusion in the game world."""
    return [
        build_faithsalt(),
        build_gethsemane(),
        build_lithos(),
        build_manchester(),
        build_samwise(),
        build_cestii_alley(),
        build_rhododendron(),
        build_aetherfield(),
        build_kidney(),
        build_grimes(),
        build_serpents_pass(),
    ]
