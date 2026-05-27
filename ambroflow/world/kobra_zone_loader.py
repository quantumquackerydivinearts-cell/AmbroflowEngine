"""
kobra_zone_loader.py
====================
Loads Zone geometry from Kobra placement notation produced by the
Tile Placement Network (TPN) in the Atelier.

Input format (one entity per line):
    id : [presence? x_rose y_rose z_rose? color_token? traversal? daisy_type? lex*]

Where:
    presence     — Ta (present, default) or Zo (absent — skip this tile)
    x_rose       — one or more Rose digit tokens encoding the x coordinate (base-12)
    y_rose       — one or more Rose digit tokens encoding the y coordinate (base-12)
    z_rose       — optional z-level Rose digit tokens
    color_token  — a single whitespace-delimited token that is either a Rose vector,
                   an Aster chiral symbol, or a combined akinenwun of those
                   (e.g. Ru, Ry, Ra, RuOtKi)
    traversal    — Va (walkable / Order) or Vo (visual blocker / Chaos)
    daisy_type   — Lo (NPC) | To (prop/item) | Ne (exit/portal) | Gl (membrane/door)
    lex          — zero or more arbitrary tokens carrying entity-specific meaning
                   (character_id, item_id, direction, target_zone, ...)

Tile key in id field
    The id is the TPN tile key: "layer|x,y" (decimal).
    When present this is the primary source of coordinates; Rose numeral tokens
    serve as a confirmation / fallback.

Token colour system
    Rose vectors (Ru Ot El Ki Fu Ka AE Ha Ga Na Ung Wu)
        — 12 base spectral hues
    Aster right-chiral (Ry Oth Le Gi Fe Ky Alz)
        — corresponding Rose hue shifted +28 % toward white
    Aster left-chiral (Ra Tho Lu Ge Fo Kw Dr)
        — corresponding Rose hue shifted +32 % toward black
    Combined akinenwun (e.g. RuOtKi, KaFuNa)
        — greedy segmentation of the above 26 units, RGBs averaged
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

try:
    from pathlib import Path as _Path
    from ..kobra import get_runtime as _kobra_get_rt
    _kzl_ko = _Path(__file__).parent / "kobra_zone_loader.ko"
    if _kzl_ko.exists():
        _rt = _kobra_get_rt()
        if "KobraZoneLoader" not in _rt.units():
            _rt.load(_kzl_ko)
except ImportError:
    pass

from .map import (
    Zone, Realm, WorldTileKind,
    ZoneExit, DungeonPortal, NPCSpawn, ItemSpawn,
)


# ── Rose numeral system ───────────────────────────────────────────────────────

_ROSE_DIGIT: dict[str, int] = {
    "Gaoh": 0, "Ao": 1, "Ye": 2, "Ui": 3, "Shu": 4, "Kiel": 5,
    "Yeshu": 6, "Lao": 7, "Shushy": 8, "Uinshu": 9, "Kokiel": 10, "Aonkiel": 11,
}

def _eval_rose(digits: list[str]) -> int:
    """Evaluate a list of Rose digit tokens as a base-12 integer."""
    val = 0
    for d in digits:
        val = val * 12 + _ROSE_DIGIT[d]
    return val


# ── Colour token system ───────────────────────────────────────────────────────

_ROSE_HUE: dict[str, tuple[int,int,int]] = {
    "Ru":  (198,  40,  40),
    "Ot":  (239, 108,   0),
    "El":  (249, 168,  37),
    "Ki":  ( 46, 125,  50),
    "Fu":  ( 21, 101, 192),
    "Ka":  ( 40,  53, 147),
    "AE":  (106,  27, 154),
    "Ha":  (255, 255, 255),
    "Ga":  ( 17,  17,  17),
    "Na":  (158, 158, 158),
    "Ung": ( 78,  52,  46),
    "Wu":  (207, 216, 220),
}

_ASTER_RIGHT: dict[str, str] = {
    "Ry": "Ru", "Oth": "Ot", "Le": "El", "Gi": "Ki",
    "Fe": "Fu", "Ky": "Ka", "Alz": "AE",
}
_ASTER_LEFT: dict[str, str] = {
    "Ra": "Ru", "Tho": "Ot", "Lu": "El", "Ge": "Ki",
    "Fo": "Fu", "Kw": "Ka", "Dr": "AE",
}

# Greedy segmentation units — longest first so multi-char tokens win
_COLOR_UNITS: list[str] = sorted(
    list(_ROSE_HUE) + list(_ASTER_RIGHT) + list(_ASTER_LEFT),
    key=len, reverse=True,
)

def _shift(rgb: tuple, target: tuple, factor: float) -> tuple[int,int,int]:
    return (
        round(rgb[0] + (target[0] - rgb[0]) * factor),
        round(rgb[1] + (target[1] - rgb[1]) * factor),
        round(rgb[2] + (target[2] - rgb[2]) * factor),
    )

def _resolve_single_color(tok: str) -> Optional[tuple[int,int,int]]:
    if tok in _ROSE_HUE:
        return _ROSE_HUE[tok]
    if tok in _ASTER_RIGHT:
        return _shift(_ROSE_HUE[_ASTER_RIGHT[tok]], (255, 255, 255), 0.28)
    if tok in _ASTER_LEFT:
        return _shift(_ROSE_HUE[_ASTER_LEFT[tok]], (0, 0, 0), 0.32)
    return None

def resolve_color_token(tok: str) -> Optional[tuple[int,int,int]]:
    """
    Resolve a color token (single or combined akinenwun) to an RGB triple.
    Returns None if the token is not a recognized color expression.
    """
    direct = _resolve_single_color(tok)
    if direct:
        return direct
    # Attempt greedy segmentation of a combined akinenwun
    src = re.sub(r"[^A-Za-z]", "", tok)
    parts: list[str] = []
    offset = 0
    while offset < len(src):
        matched = ""
        for unit in _COLOR_UNITS:
            if src.startswith(unit, offset):
                matched = unit
                break
        if not matched:
            return None  # unrecognised segment
        parts.append(matched)
        offset += len(matched)
    if not parts:
        return None
    rgbs = [_resolve_single_color(p) for p in parts]
    if not all(rgbs):
        return None
    r = round(sum(c[0] for c in rgbs) / len(rgbs))
    g = round(sum(c[1] for c in rgbs) / len(rgbs))
    b = round(sum(c[2] for c in rgbs) / len(rgbs))
    return (r, g, b)

def _is_color_token(tok: str) -> bool:
    return resolve_color_token(tok) is not None

# Dominant hue → WorldTileKind category (used when traversal is walkable_surface)
def _hue_category(tok: str) -> str:
    """Map a color token to a coarse material category name."""
    if not tok:
        return "floor"
    # Resolve to single dominant Rose unit
    src = re.sub(r"[^A-Za-z]", "", tok)
    parts: list[str] = []
    offset = 0
    while offset < len(src):
        matched = ""
        for unit in _COLOR_UNITS:
            if src.startswith(unit, offset):
                matched = unit
                break
        if not matched:
            break
        parts.append(matched)
        offset += len(matched)
    # Normalise chiral to Rose
    def base(p: str) -> str:
        if p in _ASTER_RIGHT:
            return _ASTER_RIGHT[p]
        if p in _ASTER_LEFT:
            return _ASTER_LEFT[p]
        return p
    bases = [base(p) for p in parts] if parts else [tok]
    # Majority vote
    from collections import Counter
    dominant = Counter(bases).most_common(1)[0][0] if bases else "Ha"
    return {
        "Fu": "water",
        "Ki": "grass", "El": "grass",
        "Ru": "road",  "Ot": "road",
        "Ung": "dirt",
        "Ka": "wall",
        "AE": "portal",
        "Ha": "floor", "Na": "floor", "Wu": "floor",
        "Ga": "void",
    }.get(dominant, "floor")


# ── Token classification ──────────────────────────────────────────────────────

_PRESENCE_TOKENS = {"Ta", "Zo"}
_TRAVERSAL_TOKENS = {"Va": "walkable_surface", "Vo": "visual_unwalkable"}
_DAISY_STRUCTURAL = {
    "Lo", "Yei", "Ol", "X", "Yx", "Go", "Foa", "Oy", "W", "Th",
    "Kael", "Ro", "Gl", "To", "Ma", "Ne", "Ym", "Nz", "Sho", "Hi",
    "Mh", "Zhi", "Vr", "St", "Fn", "N",
}

@dataclass
class ParsedPlacement:
    id:            str
    x:             int
    y:             int
    z:             int                  = 0
    layer:         str                  = "base"
    presence:      str                  = "Ta"       # Ta | Zo
    color_token:   str                  = "Ha"
    traversal:     str                  = "walkable_surface"
    daisy_type:    Optional[str]        = None
    lex:           list[str]            = field(default_factory=list)


def _parse_tile_key_id(id_str: str) -> tuple[Optional[str], Optional[int], Optional[int]]:
    """Try to extract (layer, x, y) from a tile key like 'ground|3,12'."""
    if "|" in id_str:
        layer, _, coord = id_str.partition("|")
        parts = coord.split(",")
        if len(parts) >= 2:
            try:
                return layer.strip(), int(parts[0]), int(parts[1])
            except ValueError:
                pass
    return None, None, None


def _parse_placement_line(line: str) -> Optional[ParsedPlacement]:
    """
    Parse one line of the form:
        id : [token token ...]
    Returns None for lines that should be skipped.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if " : " not in line:
        return None

    id_part, _, bracket_part = line.partition(" : ")
    id_str = id_part.strip()

    # Strip brackets
    inner = bracket_part.strip()
    if inner.startswith("["):
        inner = inner[1:]
    if inner.endswith("]"):
        inner = inner[:-1]

    tokens = inner.split()
    if not tokens:
        return None

    # Extract coordinates from tile key id first
    layer, key_x, key_y = _parse_tile_key_id(id_str)

    # Walk tokens
    presence   = "Ta"
    traversal  = "walkable_surface"
    color_tok  = "Ha"
    daisy_type = None
    lex: list[str] = []
    rose_runs: list[list[str]] = []
    current_rose: list[str] = []

    for tok in tokens:
        if tok in _PRESENCE_TOKENS:
            presence = tok
        elif tok in _ROSE_DIGIT:
            current_rose.append(tok)
        else:
            if current_rose:
                rose_runs.append(current_rose)
                current_rose = []
            if tok in _TRAVERSAL_TOKENS:
                traversal = _TRAVERSAL_TOKENS[tok]
            elif tok in _DAISY_STRUCTURAL:
                daisy_type = tok
            elif _is_color_token(tok):
                color_tok = tok
            else:
                lex.append(tok)
    if current_rose:
        rose_runs.append(current_rose)

    # Resolve coordinates: prefer tile key, fall back to Rose runs
    if key_x is not None:
        x, y = key_x, key_y
        z = _eval_rose(rose_runs[2]) if len(rose_runs) >= 3 else 0
    else:
        x = _eval_rose(rose_runs[0]) if len(rose_runs) >= 1 else 0
        y = _eval_rose(rose_runs[1]) if len(rose_runs) >= 2 else 0
        z = _eval_rose(rose_runs[2]) if len(rose_runs) >= 3 else 0

    return ParsedPlacement(
        id         = id_str,
        x          = x,
        y          = y,
        z          = z,
        layer      = layer or "base",
        presence   = presence,
        color_token= color_tok,
        traversal  = traversal,
        daisy_type = daisy_type,
        lex        = lex,
    )


# ── Tile kind resolver ────────────────────────────────────────────────────────

def _tile_kind(p: ParsedPlacement) -> WorldTileKind:
    """Map a parsed placement to the appropriate WorldTileKind."""
    # Explicit lex override (tile type name directly in lex)
    _LEX_OVERRIDE: dict[str, WorldTileKind] = {
        "door":             WorldTileKind.DOOR,
        "stairs_up":        WorldTileKind.STAIRS_UP,
        "stairs_down":      WorldTileKind.STAIRS_DOWN,
        "portal":           WorldTileKind.PORTAL,
        "dungeon":          WorldTileKind.DUNGEON_ENTRANCE,
        "bridge":           WorldTileKind.BRIDGE,
        "water":            WorldTileKind.WATER,
        "tree":             WorldTileKind.TREE,
        "marble":           WorldTileKind.MARBLE,
        "yellow_brick":     WorldTileKind.YELLOW_BRICK,
        "ceramic":          WorldTileKind.CERAMIC,
        "slate":            WorldTileKind.SLATE,
        "silica":           WorldTileKind.SILICA,
        "stone":            WorldTileKind.STONE,
        "grass":            WorldTileKind.GRASS,
        "road":             WorldTileKind.ROAD,
        "dirt":             WorldTileKind.DIRT,
        "floor":            WorldTileKind.FLOOR,
        "wall":             WorldTileKind.WALL,
        "bed":              WorldTileKind.BED,
    }
    for tok in p.lex:
        if tok.lower() in _LEX_OVERRIDE:
            return _LEX_OVERRIDE[tok.lower()]

    trav = p.traversal

    if trav == "visual_unwalkable":
        cat = _hue_category(p.color_token)
        if cat == "grass":
            return WorldTileKind.TREE
        return WorldTileKind.WALL

    if trav != "walkable_surface":
        return WorldTileKind.VOID

    # Walkable — colour determines material
    cat = _hue_category(p.color_token)
    return {
        "floor":  WorldTileKind.FLOOR,
        "grass":  WorldTileKind.GRASS,
        "road":   WorldTileKind.ROAD,
        "dirt":   WorldTileKind.DIRT,
        "water":  WorldTileKind.WATER,
        "portal": WorldTileKind.PORTAL,
        "void":   WorldTileKind.VOID,
        "wall":   WorldTileKind.WALL,
    }.get(cat, WorldTileKind.FLOOR)


# ── Main loader ───────────────────────────────────────────────────────────────

def load_zone_from_kobra(
    source:       str,
    zone_id:      str,
    name:         str,
    realm:        Realm               = Realm.LAPIDUS,
    player_spawn: tuple[int, int]     = (1, 1),
    exits:        list[ZoneExit]      = (),
) -> Zone:
    """
    Parse Kobra placement notation and return a fully constructed Zone.

    Parameters
    ----------
    source       : multiline string of entity placement specs
    zone_id      : stable identifier for this zone
    name         : display name
    realm        : which realm this zone belongs to
    player_spawn : default spawn if not declared in source
    exits        : additional exits to merge in (e.g. hand-authored transitions)
    """
    voxels:      dict[tuple[int,int], WorldTileKind] = {}
    npc_spawns:  list[NPCSpawn]      = []
    item_spawns: list[ItemSpawn]     = []
    portals:     list[DungeonPortal] = []
    zone_exits:  list[ZoneExit]      = list(exits)
    spawn:       tuple[int,int]      = player_spawn

    for line in source.splitlines():
        p = _parse_placement_line(line)
        if p is None:
            continue
        if p.presence == "Zo":
            continue  # explicit void — don't instantiate

        x, y = p.x, p.y

        # Structural entities by Daisy type
        if p.daisy_type == "Lo":
            # NPC spawn — lex[0] is character_id if present
            char_id = p.lex[0] if p.lex else f"npc_{x}_{y}"
            npc_spawns.append(NPCSpawn(x=x, y=y, character_id=char_id))
            voxels[(x, y)] = WorldTileKind.FLOOR

        elif p.daisy_type == "To":
            # Item spawn — lex[0] is item_id, lex[1] is qty if present
            item_id = p.lex[0] if p.lex else f"item_{x}_{y}"
            try:
                qty = int(p.lex[1]) if len(p.lex) >= 2 else 1
            except ValueError:
                qty = 1
            item_spawns.append(ItemSpawn(x=x, y=y, item_id=item_id, qty=qty))
            voxels[(x, y)] = WorldTileKind.FLOOR

        elif p.daisy_type == "Ne":
            # Zone exit — lex: direction target_zone target_x target_y
            if len(p.lex) >= 4:
                try:
                    zone_exits.append(ZoneExit(
                        x=x, y=y,
                        direction  = p.lex[0],
                        target_zone= p.lex[1],
                        target_x   = int(p.lex[2]),
                        target_y   = int(p.lex[3]),
                    ))
                except (ValueError, IndexError):
                    pass
            voxels[(x, y)] = WorldTileKind.DOOR

        elif p.daisy_type == "Ro":
            # Dungeon portal — lex[0] is dungeon_id
            dungeon_id = p.lex[0] if p.lex else f"dungeon_{x}_{y}"
            portals.append(DungeonPortal(x=x, y=y, dungeon_id=dungeon_id))
            voxels[(x, y)] = WorldTileKind.DUNGEON_ENTRANCE

        elif p.daisy_type == "Gl":
            # Door / membrane
            voxels[(x, y)] = WorldTileKind.DOOR

        elif p.daisy_type == "St":
            # Surface marker — player spawn
            spawn = (x, y)
            voxels[(x, y)] = WorldTileKind.FLOOR

        else:
            # Ordinary tile
            voxels[(x, y)] = _tile_kind(p)

    if not voxels:
        return Zone(
            zone_id=zone_id, realm=realm, name=name,
            width=1, height=1, voxels={(0,0): WorldTileKind.VOID},
            player_spawn=spawn,
        )

    xs = [k[0] for k in voxels]
    ys = [k[1] for k in voxels]
    width  = max(xs) + 1
    height = max(ys) + 1

    return Zone(
        zone_id      = zone_id,
        realm        = realm,
        name         = name,
        width        = width,
        height       = height,
        voxels       = voxels,
        player_spawn = spawn,
        exits        = zone_exits,
        npc_spawns   = npc_spawns,
        portals      = portals,
        item_spawns  = item_spawns,
    )