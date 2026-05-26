"""
Sulphera Zones -- Ko's Labyrinth (7_KLGS)
==========================================
The Underworld. Gated by the infernal_meditation perk (quest 0010_KLST).

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
  royal_ring            Accessible after Asmodeus's blessing (quest 0037_KLST)

Individual dungeon areas within each ring are handled by the dungeon generator.
These zone definitions are the navigable overworld layer of each ring.
"""
from __future__ import annotations
from ..map import Realm, Zone, ZoneExit
from ..kobra_zone_loader import load_zone_from_kobra


# ── Tile emitters ─────────────────────────────────────────────────────────────

def _dark(x, y):               return f"g|{x},{y} : [Vo Ga dark_stone]"
def _floor(x, y):              return f"g|{x},{y} : [Va Ha floor]"
def _sulphur(x, y):            return f"g|{x},{y} : [Va Na sulphur_stone]"
def _glow(x, y):               return f"g|{x},{y} : [Va AE infernal_glow]"
def _water(x, y):              return f"g|{x},{y} : [Va Fu water]"
def _spawn(x, y):              return f"g|{x},{y} : [Va Ha St]"
def _npc(x, y, nid):           return f"g|{x},{y} : [Va Ha Lo {nid}]"
def _portal(x, y, dungeon_id): return f"g|{x},{y} : [Va AE Ro {dungeon_id}]"


def _build(lines: list[str], zone_id: str, name: str,
           spawn: tuple[int, int], exits: list[ZoneExit]) -> Zone:
    return load_zone_from_kobra(
        source="\n".join(lines),
        zone_id=zone_id, name=name, realm=Realm.SULPHERA,
        player_spawn=spawn, exits=exits,
    )


# ── Visitor Ring exit coordinates ─────────────────────────────────────────────

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

_VR_EXITS: list[ZoneExit] = []
for _col, _target in zip(_RING_EXIT_COLS, _RING_TARGET_ZONES):
    _VR_EXITS += [
        ZoneExit(x=_col,   y=17, direction="south", target_zone=_target, target_x=5, target_y=0),
        ZoneExit(x=_col+1, y=17, direction="south", target_zone=_target, target_x=6, target_y=0),
    ]


# ── Visitor Ring ──────────────────────────────────────────────────────────────
#
# 60 wide × 20 tall.
# Entry ring — safe rest zone, demon-run market stalls, waypoint stones.
# Seven radial exits lead to the sin rings.
# No surface exit: meditation return only (handled by BreathOfKo system).

def build_visitor_ring() -> Zone:
    W, H = 60, 20
    lines: list[str] = []

    # Base fill: all dark stone
    for y in range(H):
        for x in range(W):
            lines.append(_dark(x, y))

    # Open interior between outer wall and sulphur ring
    for y in list(range(1, 5)) + list(range(14, 17)) + [18]:
        for x in range(1, W - 1):
            lines.append(_floor(x, y))

    # Sulphur ring outer band (rows 5 and 13)
    for y in (5, 13):
        for x in range(1, 5):
            lines.append(_floor(x, y))
        for x in range(5, 55):
            lines.append(_sulphur(x, y))
        for x in range(55, W - 1):
            lines.append(_floor(x, y))

    # Sulphur ring sides (rows 6-12): sulphur pillars at cols 5 and 54
    for y in range(6, 13):
        for x in range(1, 5):
            lines.append(_floor(x, y))
        lines.append(_sulphur(5, y))
        for x in range(6, 54):
            lines.append(_floor(x, y))
        lines.append(_sulphur(54, y))
        for x in range(55, W - 1):
            lines.append(_floor(x, y))

    # Infernal glow at row 8: 7 beacons marking the axis of each sin ring
    for x in (6, 14, 22, 29, 37, 45, 53):
        lines.append(_glow(x, 8))

    # Player spawn: centre of the waypoint ring interior
    lines.append(_spawn(25, 10))

    # Dungeon portal — the deep floors of the Visitor Ring itself
    lines.append(_portal(40, 10, "sulphera_ring_visitor"))

    # Exit floor pairs on row 17 (seven ring gates)
    for col in _RING_EXIT_COLS:
        lines.append(_floor(col,     17))
        lines.append(_floor(col + 1, 17))

    return _build(lines, "sulphera_visitor_ring", "The Visitor Ring", (25, 10), _VR_EXITS)


# ── Ring entry zones ──────────────────────────────────────────────────────────
#
# Each sin ring gets a 20 wide × 10 tall threshold space.
# Dark stone ambient, floor interior, atmospheric row 4, spawn at row 5.
# North exit pair (row 0, cols 1-2) returns to the Visitor Ring.

def _ring_entry_zone(zone_id: str, name: str, vr_col: int,
                     style: str = "plain", npc: str = "",
                     dungeon_id: str = "") -> Zone:
    W, H = 20, 10
    lines: list[str] = []

    # Base: all dark stone
    for y in range(H):
        for x in range(W):
            lines.append(_dark(x, y))

    # Open interior floor (rows 1-8, cols 1-18)
    for y in range(1, 9):
        for x in range(1, W - 1):
            lines.append(_floor(x, y))

    # North exit tiles at row 0
    lines.append(_floor(1, 0))
    lines.append(_floor(2, 0))

    # Row 4: atmospheric overlay per ring character
    if style in ("pride", "lust"):
        for x in range(2, 19, 2):          # alternating infernal glow
            lines.append(_glow(x, 4))
    elif style == "greed":
        for x in range(2, 19, 2):          # alternating sulphur stones
            lines.append(_sulphur(x, 4))
    elif style == "sloth":
        for x in (2, 5, 8, 11, 14, 17):   # sparse, restful glow
            lines.append(_glow(x, 4))
    elif style == "wrath":
        for x in range(1, W - 1):          # brimstone channel across the row
            lines.append(_water(x, 4))

    # Player spawn
    lines.append(_spawn(7, 5))

    # Optional NPC (used for quest-gated ring bosses)
    if npc:
        lines.append(_npc(2, 7, npc))

    # Dungeon portal into this ring's generated floors
    if dungeon_id:
        lines.append(_portal(16, 5, dungeon_id))

    exits = [
        ZoneExit(x=1, y=0, direction="north",
                 target_zone="sulphera_visitor_ring", target_x=vr_col,     target_y=16),
        ZoneExit(x=2, y=0, direction="north",
                 target_zone="sulphera_visitor_ring", target_x=vr_col + 1, target_y=16),
    ]
    return _build(lines, zone_id, name, (7, 5), exits)


def build_sulphera_ring_entries() -> list[Zone]:
    """Return entry zones for the seven sin rings plus the Royal Ring."""
    _SPECS = [
        ("sulphera_pride_entry",    "Pride Ring — Promenade",              _RING_EXIT_COLS[0], "pride", "", "sulphera_ring_pride"),
        ("sulphera_greed_entry",    "Greed Ring — Counting House Foyer",   _RING_EXIT_COLS[1], "greed", "", "sulphera_ring_greed"),
        ("sulphera_envy_entry",     "Envy Ring — Approach",                _RING_EXIT_COLS[2], "plain", "", "sulphera_ring_envy"),
        ("sulphera_gluttony_entry", "Gluttony Ring — Banquet Approach",    _RING_EXIT_COLS[3], "plain", "", "sulphera_ring_gluttony"),
        ("sulphera_sloth_entry",    "The Sitting Place",                   _RING_EXIT_COLS[4], "sloth", "", "sulphera_ring_sloth"),
        ("sulphera_wrath_entry",    "Wrath Ring — Threshold",              _RING_EXIT_COLS[5], "wrath", "", "sulphera_ring_wrath"),
        ("sulphera_lust_entry",     "Lust Ring — Outer Approach",          _RING_EXIT_COLS[6], "lust",  "", "sulphera_ring_lust"),
    ]
    zones = [_ring_entry_zone(zid, nm, col, style, npc, did)
             for zid, nm, col, style, npc, did in _SPECS]

    # ── Royal Ring ────────────────────────────────────────────────────────────
    # Accessible after Asmodeus's blessing (quest 0037_KLST).
    # No exit back to the Visitor Ring — entered via quest event only.
    # Hypatia is present in demoness form; Drovitth stands at the Orrery.
    W, H = 20, 10
    rr: list[str] = []
    for y in range(H):
        for x in range(W):
            rr.append(_dark(x, y))
    for y in range(1, 9):
        for x in range(1, W - 1):
            rr.append(_floor(x, y))
    rr.append(_floor(1, 0))
    rr.append(_floor(2, 0))
    for x in (2, 4, 6, 8, 10, 12, 14, 16):   # faelight strip marking the royal presence
        rr.append(_glow(x, 2))
    rr.append(_spawn(7, 5))
    rr.append(_npc(2,  7, "0000_0451"))        # Hypatia (demoness form)
    rr.append(_npc(16, 7, "1018_DJNN"))        # Drovitth at the Orrery
    rr.append(_portal(16, 5, "sulphera_ring_royal"))  # Royal Ring dungeon floors

    zones.append(_build(rr, "sulphera_royal_ring", "The Royal Ring", (7, 5), []))
    return zones
