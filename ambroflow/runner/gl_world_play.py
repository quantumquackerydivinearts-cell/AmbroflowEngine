"""
GLWorldPlay — strictly OpenGL world play controller
====================================================
Wraps WorldPlay game logic; renders entirely via PIL → Texture → UIRenderer.
No pygame surfaces anywhere in the rendering path.

The tile grid, NPC/player tokens, and HUD are painted to a PIL Image each
frame using the same colour tables as WorldRenderer.  Overlay screens
(alchemy, vendor, dialogue, combat, map) come from WorldPlay's existing
_*_bytes attributes, which are already PIL-PNG bytes.
"""

from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False


# ── Minimal overlay screen generators (Gap 9) ─────────────────────────────

def _make_overlay_screen(W: int, H: int, title: str, body_lines: list[str],
                          bg: tuple = (8, 5, 14),
                          accent: tuple = (185, 145, 55)) -> bytes:
    """Generic PIL overlay: dark panel + title + body lines."""
    if not _PIL:
        return b""
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    drw  = ImageDraw.Draw(img)
    pw, ph = int(W * 0.72), int(H * 0.78)
    ox, oy = (W - pw) // 2, (H - ph) // 2
    drw.rectangle([ox, oy, ox+pw, oy+ph], fill=(*bg, 235))
    drw.rectangle([ox, oy, ox+pw, oy+2], fill=(*accent, 255))
    try:
        from .screens.common import _load_font
        fnt_h = _load_font(16)
        fnt_b = _load_font(12)
    except Exception:
        fnt_h = fnt_b = None
    drw.text((ox+18, oy+14), title, fill=(*accent, 255), font=fnt_h)
    drw.line([(ox+16, oy+36), (ox+pw-16, oy+36)], fill=(*accent, 120), width=1)
    ty = oy + 50
    for ln in body_lines:
        drw.text((ox+18, ty), ln, fill=(200, 195, 215, 255), font=fnt_b)
        ty += 20
    hint = "[Esc]  Close"
    drw.text((ox+pw-80, oy+ph-22), hint, fill=(130, 120, 100, 180), font=fnt_b)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _shop_screen_bytes(W: int, H: int) -> bytes:
    return _make_overlay_screen(W, H, "Apothecary Shop",
        ["Your shop is open for trade.",
         "",
         "Stock your counter with crafted goods.",
         "Customers arrive during market hours.",
         "",
         "[Alchemy]  Craft stock",
         "[Space]    Browse inventory"],
        bg=(18, 10, 8), accent=(185, 120, 45))


def _smelt_screen_bytes(W: int, H: int) -> bytes:
    return _make_overlay_screen(W, H, "Furnace",
        ["The furnace is hot.",
         "",
         "Smelt ores into ingots.",
         "Alloy metals at higher temperatures.",
         "",
         "[Alchemy]  Open smelting recipes"],
        bg=(22, 8, 4), accent=(230, 100, 30))

from ..engine.texture import Texture
from ..render.ui      import UIRenderer
from ..world.map      import WorldTileKind, Realm
from ..world.player   import Direction
from ..world.action_handlers import dispatch, ActionContext, ActionResult
from ..world.world_graph      import WorldGraph
from .renderer_bridge import load_renderer_bridge, TILE_SIZE

if TYPE_CHECKING:
    from ..world.play import WorldPlay

log = logging.getLogger(__name__)


# ── InputEvent string → WorldPlay._handle_key() int ──────────────────────────

_EV_TO_KEY: dict[str, int] = {
    "move_north": 1073741906,   # _K_UP
    "move_south": 1073741905,   # _K_DOWN
    "move_east":  1073741903,   # _K_RIGHT
    "move_west":  1073741904,   # _K_LEFT
    "interact":   13,           # _K_RETURN
    "cancel":     27,           # _K_ESCAPE
    "fight":      ord("f"),     # 102
    "alchemy":    ord("z"),     # 122
    "journal":    ord("j"),     # 106
    "menu":       27,           # treat menu as cancel
}


# ── Tile colour tables (mirrors world/renderer.py) ────────────────────────────

_C = WorldTileKind

_LAP_FILL: dict = {
    _C.VOID: (0,0,0), _C.WALL: (82,70,54), _C.FLOOR: (68,60,48),
    _C.DOOR: (112,78,42), _C.GRASS: (50,88,38), _C.ROAD: (112,96,70),
    _C.DIRT: (95,74,48), _C.STONE: (88,82,72), _C.WATER: (28,56,98),
    _C.BRIDGE: (100,80,50), _C.STAIRS_UP: (95,85,65), _C.STAIRS_DOWN: (60,52,40),
    _C.PORTAL: (160,100,180), _C.DUNGEON_ENTRANCE: (35,25,52),
    _C.TREE: (18,55,18), _C.MARBLE: (220,215,200), _C.YELLOW_BRICK: (185,145,55),
    _C.CERAMIC: (88,128,155), _C.SLATE: (72,78,88), _C.SILICA: (195,185,165),
}
_LAP_EDGE: dict = {
    _C.GRASS: (38,70,28), _C.ROAD: (92,78,54), _C.WALL: (60,50,36),
    _C.FLOOR: (52,46,36), _C.DOOR: (140,100,55), _C.WATER: (18,42,78),
    _C.DUNGEON_ENTRANCE: (55,40,80), _C.TREE: (10,40,10),
    _C.MARBLE: (180,175,162), _C.YELLOW_BRICK: (155,118,38),
    _C.CERAMIC: (68,105,130), _C.SLATE: (54,60,70), _C.SILICA: (165,155,138),
}
_MER_FILL: dict = {
    _C.VOID: (0,0,0), _C.WALL: (42,38,78), _C.FLOOR: (35,32,66),
    _C.DOOR: (80,52,108), _C.GRASS: (22,74,65), _C.ROAD: (58,48,86),
    _C.DIRT: (48,40,78), _C.STONE: (52,48,88), _C.WATER: (12,68,90),
    _C.BRIDGE: (55,45,82), _C.STAIRS_UP: (62,56,95), _C.STAIRS_DOWN: (38,34,72),
    _C.PORTAL: (130,100,180), _C.DUNGEON_ENTRANCE: (28,20,52),
    _C.TREE: (12,52,48), _C.MARBLE: (195,195,215), _C.YELLOW_BRICK: (155,138,85),
    _C.CERAMIC: (45,98,118), _C.SLATE: (52,60,82), _C.SILICA: (175,168,192),
}
_MER_EDGE: dict = {
    _C.GRASS: (15,58,52), _C.ROAD: (45,36,70), _C.WALL: (30,26,60),
    _C.FLOOR: (25,22,52), _C.DOOR: (100,68,130), _C.WATER: (8,52,72),
    _C.DUNGEON_ENTRANCE: (45,30,80), _C.TREE: (8,40,36),
    _C.MARBLE: (165,165,182), _C.YELLOW_BRICK: (128,112,65),
    _C.CERAMIC: (30,78,96), _C.SLATE: (38,46,65), _C.SILICA: (148,140,165),
}
_SUL_FILL: dict = {
    _C.VOID: (0,0,0), _C.WALL: (48,12,6), _C.FLOOR: (40,10,5),
    _C.DOOR: (90,35,12), _C.GRASS: (52,18,8), _C.ROAD: (62,28,12),
    _C.DIRT: (58,22,10), _C.STONE: (55,20,8), _C.WATER: (88,32,5),
    _C.BRIDGE: (70,25,10), _C.STAIRS_UP: (75,30,12), _C.STAIRS_DOWN: (42,12,5),
    _C.PORTAL: (140,60,20), _C.DUNGEON_ENTRANCE: (30,8,4),
    _C.TREE: (30,8,2), _C.MARBLE: (165,90,50), _C.YELLOW_BRICK: (145,65,20),
    _C.CERAMIC: (65,30,10), _C.SLATE: (50,18,8), _C.SILICA: (145,80,45),
}
_SUL_EDGE: dict = {
    _C.GRASS: (40,12,5), _C.ROAD: (50,20,8), _C.WALL: (35,8,3),
    _C.FLOOR: (30,7,3), _C.DOOR: (110,45,15), _C.WATER: (65,20,3),
    _C.DUNGEON_ENTRANCE: (60,18,8), _C.TREE: (20,5,1),
    _C.MARBLE: (135,70,35), _C.YELLOW_BRICK: (118,50,12),
    _C.CERAMIC: (48,20,6), _C.SLATE: (35,12,4), _C.SILICA: (118,60,30),
}

_REALM_FILL = {Realm.LAPIDUS: _LAP_FILL, Realm.MERCURIE: _MER_FILL, Realm.SULPHERA: _SUL_FILL}
_REALM_EDGE = {Realm.LAPIDUS: _LAP_EDGE, Realm.MERCURIE: _MER_EDGE, Realm.SULPHERA: _SUL_EDGE}

# Interior atlas for home zones — tile_id 0-15 matching fate_knocks_gl._ATLAS_COLORS
_INTERIOR_ATLAS_COLORS = [
    ( 72,  62,  50),   #  0  FLOOR
    ( 55,  90,  42),   #  1  GRASS (unused inside)
    (100,  78,  52),   #  2  ROAD/DIRT (unused inside)
    ( 86,  74,  58),   #  3  WALL
    ( 32,  58, 100),   #  4  WATER (unused inside)
    ( 90,  84,  74),   #  5  STONE (unused inside)
    (  8,   6,  12),   #  6  VOID
    (110,  65,  38),   #  7  BED
    ( 88,  56,  28),   #  8  TABLE
    (185, 160, 105),   #  9  JOURNAL
    ( 90,  42,  28),   # 10  FURNACE
    ( 62,  64,  68),   # 11  ANVIL
    ( 78,  66,  50),   # 12  COUNTER
    ( 48,  52,  60),   # 13  REGISTER
    ( 72,  56,  94),   # 14  ALTAR
    ( 58,  42,  24),   # 15  BOOKSHELF
    ( 98,  78,  50),   # 16  DESK (lighter oak — also used for stair step visual)
]

def _make_interior_atlas() -> "Image.Image":
    """16×1 RGBA interior atlas — mirrors fate_knocks_gl._ATLAS_COLORS."""
    cell = 32
    cols = len(_INTERIOR_ATLAS_COLORS)
    img  = Image.new("RGBA", (cols * cell, cell), (0, 0, 0, 0))
    pix  = img.load()
    for idx, (r, g, b) in enumerate(_INTERIOR_ATLAS_COLORS):
        ox = idx * cell
        for py in range(cell):
            for px in range(cell):
                border = px == 0 or py == 0 or px == cell - 1 or py == cell - 1
                col = (r // 2, g // 2, b // 2, 255) if border else (r, g, b, 255)
                pix[ox + px, py] = col
    return img

# kind_to_atlas override for home zone (interior atlas cell indices)
_HOME_KIND_ATLAS: dict = {
    _C.VOID:        6,
    _C.WALL:        3,
    _C.WALL_FACE:   3,   # same atlas cell as WALL; distinct colour added via override below
    _C.FLOOR:       0,
    _C.DOOR:        0,
    _C.GRASS:       1,
    _C.ROAD:        2,
    _C.STAIRS_UP:   0,
    _C.STAIRS_DOWN: 0,
    _C.PORTAL:      0,
}

# Zones that use the interior atlas palette
_INTERIOR_ZONE_IDS = frozenset({"lapidus_wiltoll_home", "player_home_upper"})

# Entity and HUD colours sourced from renderer_bridge.py (LoKiel pre-decode).
# Do not edit here — edit renderer_bridge.py; both renderers share the same values.
from .renderer_bridge import (
    PLAYER_FILL   as _PLAYER_FILL,
    PLAYER_SHADOW as _PLAYER_SHADOW,
    NPC_FILL      as _NPC_FILL,
    NPC_SHADOW    as _NPC_SHADOW,
    NPC_OUTLINE   as _NPC_OUTLINE,
    HUD_TEXT      as _HUD_TEXT,
    HUD_ACCENT    as _HUD_ACCENT,
)

# Tile size sourced from renderer_bridge.ko Cannabis mode A (×2 for 2× display scale).
# When the Kobra VM is available TILE_SIZE will be derived directly from the parsed .ko.
TILE_SIZE = TILE_SIZE  # re-exported from renderer_bridge

# Atlas cell ordering — must match _default_atlas indices in render/world.py.
# Cells 0-15: base types; 16-18: specialty road/paving surfaces.
_ATLAS_ORDER = [
    _C.FLOOR, _C.GRASS, _C.ROAD, _C.WALL, _C.WATER, _C.STONE, _C.VOID,
    _C.DOOR, _C.BRIDGE, _C.YELLOW_BRICK, _C.MARBLE, _C.PORTAL,
    _C.DUNGEON_ENTRANCE, _C.TREE, _C.STAIRS_UP, _C.STAIRS_DOWN,
    _C.CERAMIC, _C.SLATE, _C.SILICA,
]

def _make_realm_atlas(fill_map: dict) -> "Image.Image":
    """Build a 16×1 cell RGBA atlas from a realm fill-colour dict."""
    cols = len(_ATLAS_ORDER)
    cell = 32
    img  = Image.new("RGBA", (cols * cell, cell), (0, 0, 0, 0))
    pix  = img.load()
    for idx, kind in enumerate(_ATLAS_ORDER):
        r, g, b = fill_map.get(kind, (20, 20, 20))
        ox = idx * cell
        for py in range(cell):
            for px in range(cell):
                border = px == 0 or py == 0 or px == cell-1 or py == cell-1
                col = (r//2, g//2, b//2, 255) if border else (r, g, b, 255)
                pix[ox+px, py] = col
    return img


# ── PIL world tile renderer (kept for NPC/player overlay only) ────────────────

def _render_world_pil(wp: "WorldPlay", W: int, H: int) -> "Image.Image":
    """Paint tile grid + entities + HUD into a PIL RGBA image."""
    T      = TILE_SIZE
    img    = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    drw    = ImageDraw.Draw(img)
    zone   = wp._zone
    player = wp._player
    hint   = wp._hint

    vw    = W // T
    vh    = H // T
    cam_x = player.x - vw // 2
    cam_y = player.y - vh // 2

    fill_map = _REALM_FILL.get(zone.realm, _LAP_FILL)
    edge_map = _REALM_EDGE.get(zone.realm, _LAP_EDGE)

    for ty in range(cam_y - 1, cam_y + vh + 2):
        for tx in range(cam_x - 1, cam_x + vw + 2):
            sx = (tx - cam_x) * T
            sy = (ty - cam_y) * T
            tile = zone.tile_at(tx, ty)
            fill = fill_map.get(tile, (20, 20, 20))
            drw.rectangle([sx, sy, sx + T - 1, sy + T - 1], fill=fill)
            edge = edge_map.get(tile)
            if edge:
                drw.rectangle([sx + 1, sy + 1, sx + T - 2, sy + T - 2], outline=edge)
            if tile == WorldTileKind.DOOR:
                dc = (min(255, fill[0]+55), min(255, fill[1]+35), max(0, fill[2]-10))
                mid = T // 2
                drw.rectangle([sx + mid - 3, sy + 2, sx + mid + 3, sy + T - 2], fill=dc)
            elif tile == WorldTileKind.PORTAL:
                cx, cy = sx + T // 2, sy + T // 2
                rc = (min(255, fill[0]+40), min(255, fill[1]+30), min(255, fill[2]+50))
                for r in (T // 4, T // 3):
                    drw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=rc)

    # NPCs
    for npc in zone.npc_spawns:
        sx = (npc.x - cam_x) * T
        sy = (npc.y - cam_y) * T
        cx = sx + T // 2
        cy = sy + T // 2
        r  = T // 2 - 6
        drw.ellipse([cx-r, cy+2-r, cx+r, cy+2+r], fill=_NPC_SHADOW)
        drw.ellipse([cx-r, cy-r,   cx+r, cy+r  ], fill=_NPC_FILL)
        drw.ellipse([cx-r, cy-r,   cx+r, cy+r  ], outline=_NPC_OUTLINE)

    # Player diamond
    px = (player.x - cam_x) * T
    py = (player.y - cam_y) * T
    cx = px + T // 2
    cy = py + T // 2
    r  = T // 2 - 5
    drw.polygon([(cx, cy-r+2), (cx+r, cy+2), (cx, cy+r+2), (cx-r, cy+2)],
                fill=_PLAYER_SHADOW)
    drw.polygon([(cx, cy-r), (cx+r, cy), (cx, cy+r), (cx-r, cy)],
                fill=_PLAYER_FILL, outline=_PLAYER_SHADOW)
    pip = {
        Direction.NORTH: (cx, cy-r+3), Direction.SOUTH: (cx, cy+r-3),
        Direction.EAST:  (cx+r-3, cy), Direction.WEST:  (cx-r+3, cy),
    }.get(player.facing, (cx, cy))
    drw.ellipse([pip[0]-2, pip[1]-2, pip[0]+2, pip[1]+2], fill=(30, 20, 5))

    # HUD — top bar
    bar_top = Image.new("RGBA", (W, 24), (0, 0, 0, 145))
    img.alpha_composite(bar_top, (0, 0))
    drw2 = ImageDraw.Draw(img)
    realm_v = zone.realm.value if hasattr(zone.realm, "value") else str(zone.realm)
    drw2.text((8, 4), f"{zone.name}  [ {realm_v.capitalize()} ]", fill=_HUD_ACCENT)

    # HUD — bottom bar
    bar_bot = Image.new("RGBA", (W, 28), (0, 0, 0, 155))
    img.alpha_composite(bar_bot, (0, H - 28))
    drw3 = ImageDraw.Draw(img)
    drw3.text((W - len(player.name) * 7 - 10, H - 21), player.name, fill=_HUD_TEXT)
    if hint:
        drw3.text(((W - len(hint) * 7) // 2, H - 21), hint, fill=_HUD_TEXT)

    return img


# ── GLWorldPlay ───────────────────────────────────────────────────────────────

class GLWorldPlay:
    """
    Strictly-GL world play layer.

    Takes an already-constructed WorldPlay instance and drives it via
    InputEvent strings (no pygame events).  Every frame is painted to a
    persistent Texture via PIL, then blitted as a fullscreen NDC quad.

    Parameters
    ----------
    world_play : the WorldPlay game-logic instance
    ui         : shared UIRenderer (owned externally; not deleted here)
    width      : initial framebuffer width
    height     : initial framebuffer height
    """

    def __init__(
        self,
        world_play:           "WorldPlay",
        ui:                   UIRenderer,
        width:                int,
        height:               int,
        world_graph:          Optional[WorldGraph] = None,
        interaction_entities: Optional[List[Dict[str, Any]]] = None,
        game_state:           Any = None,
        systems:              Optional[Dict[str, Any]] = None,
    ) -> None:
        self._wp          = world_play
        self._ui          = ui
        self._W           = width
        self._H           = height
        self._graph       = world_graph or WorldGraph.load()
        self._entities    = interaction_entities or []
        self._game_state  = game_state
        self._systems     = systems or {}
        self._pending_transition: Optional[ActionResult] = None
        self._t           = 0.0
        self._zone_id_cached: int = -1  # id() of loaded zone — detects transitions

        # ── WorldRenderer + Camera (same pipeline as FateKnocksGLPlay) ────────
        from ..render.world import WorldRenderer
        from ..engine.camera import Camera

        zone    = self._wp._zone
        zone_id = getattr(zone, "zone_id", "")

        # Static furniture persists across _reload_entities calls
        self._static_furniture: list = []

        if zone_id in _INTERIOR_ZONE_IDS:
            atlas_img = _make_interior_atlas()
            atlas_tex = Texture.from_pil(atlas_img)
            self._wr  = WorldRenderer.for_lapidus(
                atlas_tex, atlas_cols=len(_INTERIOR_ATLAS_COLORS), atlas_rows=1)
            self._wr.load_zone(zone, kind_to_atlas=_HOME_KIND_ATLAS)
            try:
                from ..scenes.player_home import (
                    get_player_home_furniture, get_player_home_interactions,
                )
                self._static_furniture = get_player_home_furniture(zone_id)
                # Prefer .ko scene interactions if passed in (loaded from file),
                # fall back to Python-defined list when no scene file exists.
                if interaction_entities:
                    self._entities = list(interaction_entities)
                else:
                    self._entities = get_player_home_interactions(zone_id)
            except Exception:
                pass
        else:
            realm     = getattr(zone, "realm", None)
            fill      = _REALM_FILL.get(realm, _LAP_FILL)
            atlas_img = _make_realm_atlas(fill)
            atlas_tex = Texture.from_pil(atlas_img)
            self._wr  = WorldRenderer.for_lapidus(
                atlas_tex, atlas_cols=len(_ATLAS_ORDER), atlas_rows=1)
            self._wr.load_zone(zone)

        self._zone_id_cached = id(zone)

        self._cam = Camera(
            aspect       = width / max(1, height),
            fov_deg      = 35.0,
            pitch_deg    = 40.0,
            distance     = 14.0,
            follow_speed = 6.0,
        )

        # Movement throttle state
        self._mov_last:  dict[str, float] = {}
        self._mov_start: dict[str, float] = {}

        # PIL texture kept only for overlay-mode screens (ALCHEMY, SHOP, etc.)
        self._tex = Texture.empty(width, height)

    # ── Public API ────────────────────────────────────────────────────────────

    def is_done(self) -> bool:
        return self._wp.is_done()

    # ── Scene graph integration ───────────────────────────────────────────────

    def pending_transition(self) -> Optional[ActionResult]:
        """Return and clear any pending scene transition result."""
        t = self._pending_transition
        self._pending_transition = None
        return t

    def load_scene(self, scene_id: str, spawn_id: str = "spawn_point") -> bool:
        """
        Load a new scene by scene_id.  Updates WorldPlay zone if possible.
        Returns True on success.
        """
        from ..world.ko_scene_reader import load_ko_scene
        from ..world.kobra_zone_loader import load_zone_from_kobra
        import json
        from pathlib import Path

        # Discover the scene file (prefer .scene.ko, fall back to .scene.json)
        candidates = [
            Path("C:/DjinnOS/productions/kos-labyrnth/scenes") / scene_id.replace("/", "/") ,
        ]
        candidates_ko   = [c.with_suffix("").with_suffix(".scene.ko")   for c in candidates]
        candidates_json = [c.with_suffix("").with_suffix(".scene.json") for c in candidates]
        all_candidates  = candidates_ko + candidates_json

        scene_data = None
        for p in all_candidates:
            if p.exists():
                try:
                    scene_data = load_ko_scene(p) if p.suffix == ".ko" else json.loads(p.read_text())
                    break
                except Exception as exc:
                    log.warning("scene load error %s: %s", p, exc)

        if scene_data is None:
            log.info("scene transition stub: %s → %s (scene file not yet authored)", scene_id, spawn_id)
            self._pending_transition = ActionResult.transition(scene_id, spawn_id)
            return False

        # Rebuild interaction entities for the new scene
        self._entities = [n for n in scene_data.get("nodes", []) if n.get("kind") == "interaction"]
        log.info("loaded scene %s — %d interactions", scene_id, len(self._entities))
        self._pending_transition = ActionResult.transition(scene_id, spawn_id)
        return True

    def _find_interaction_at(self, x: float, y: float) -> Optional[Dict[str, Any]]:
        """Return the nearest interaction entity within 1.5 tiles, or None."""
        best, best_dist = None, 1.5 * 1.5
        for ent in self._entities:
            dx = float(ent.get("x", 0)) - x
            dy = float(ent.get("y", 0)) - y
            d2 = dx * dx + dy * dy
            if d2 < best_dist:
                best, best_dist = ent, d2
        return best

    def _dispatch_interaction(self) -> None:
        player = self._wp._player
        ent = self._find_interaction_at(player.x, player.y)
        if ent is None:
            return
        meta   = ent.get("metadata") or ent.get("meta") or {}
        action = meta.get("action") or meta.get("action_mavo", "").replace("Mavo", "").lower()
        if not action:
            return
        # Convert MavoName to snake_case action_id
        import re as _re
        action_id = _re.sub(r"(?<=[a-z])(?=[A-Z])", "_", action).lower()
        zone   = self._wp._zone if hasattr(self._wp, "_zone") else None
        ctx = ActionContext(
            action_id   = action_id,
            entity_id   = str(ent.get("node_id", "")),
            player_x    = float(player.x),
            player_y    = float(player.y),
            player_z    = 0.0,
            scene_id    = str(zone.zone_id if zone and hasattr(zone, "zone_id") else ""),
            realm_id    = str(zone.realm.value if zone and hasattr(zone, "realm") else "lapidus"),
            world_graph = self._graph,
            game_state  = self._game_state,
            systems     = self._systems,
        )
        result = dispatch(action_id, ctx)

        if result.kind == "scene_transition" and result.scene_id:
            # Direct zone transition: resolve in WorldPlay's zone registry first.
            # spawn_id may encode "x,y" for precise placement.
            target_zone = self._wp._world.zones.get(result.scene_id)
            if target_zone is not None:
                tx, ty = target_zone.player_spawn
                if result.spawn_id and "," in (result.spawn_id or ""):
                    try:
                        px, py = result.spawn_id.split(",", 1)
                        tx, ty = int(px), int(py)
                    except Exception:
                        pass
                self._wp._player.zone_id = result.scene_id
                self._wp._player.x       = tx
                self._wp._player.y       = ty
                self._wp._zone           = target_zone
            else:
                self.load_scene(result.scene_id, result.spawn_id or "spawn_point")

        elif result.kind == "ui_open":
            from ..world.play import WorldMode
            _UI_BEGIN = {
                "alchemy":    "_begin_alchemy",
                "journal":    "_begin_journal",
                "lore_books": "_begin_journal",   # use journal as lore viewer
                "meditation": "_begin_alchemy",   # alchemy overlay until MEDITATION mode
                "smelt":      None,
                "shop":       None,
            }
            _UI_MODE = {
                "smelt": WorldMode.SMELT,
                "shop":  WorldMode.SHOP,
            }
            method_name = _UI_BEGIN.get(result.ui)
            if method_name:
                fn = getattr(self._wp, method_name, None)
                if fn:
                    fn()
            else:
                mode = _UI_MODE.get(result.ui)
                if mode is not None:
                    self._wp._mode = mode

        elif result.kind == "save":
            self._wp._hint = "Rested."

            # Akashic: flush save record into BreathOfKo
            br = getattr(self._wp, "_breath", None)
            if br is not None:
                ar = getattr(br, "akashic_record", None)
                if ar is not None:
                    try:
                        game_day = 0
                        if self._wp._clock is not None:
                            game_day = getattr(
                                getattr(self._wp._clock, "date", None), "day", 0)
                        ar.flush_save(
                            zone_id  = self._wp._player.zone_id,
                            game_day = game_day,
                        )
                    except Exception:
                        pass

            if self._wp._journal is not None:
                try:
                    from ..journal.journal import EntryKind
                    self._wp._journal.write(
                        EntryKind.OBSERVATION,
                        "Rest at Home",
                        "A moment of stillness in the apprentice's quarters.",
                    )
                except Exception:
                    pass

        elif not result.ok:
            log.debug("action %r: %s", action_id, result.message)

    # ── Public API ────────────────────────────────────────────────────────────

    # Movement throttle constants
    _WALK_DELAY = 0.18   # s/tile — initial hold speed
    _RUN_DELAY  = 0.08   # s/tile — sustained run speed
    _RUN_THRESH = 0.35   # s of continuous hold before run speed
    _FRESH_GAP  = 0.55   # gap > this = treat as new keypress

    _MOVE_EVS = frozenset({"move_north", "move_south", "move_east", "move_west"})

    def handle_event(self, ev: str) -> None:
        import time as _ti

        # Throttled movement
        if ev in self._MOVE_EVS:
            now  = _ti.monotonic()
            last = self._mov_last.get(ev, 0.0)
            gap  = now - last
            if gap > self._FRESH_GAP:
                # Fresh press — always move, reset hold timer
                self._mov_start[ev] = now
                self._mov_last[ev]  = now
                self._wp._handle_key(_EV_TO_KEY[ev])
            else:
                hold  = now - self._mov_start.get(ev, now)
                delay = self._RUN_DELAY if hold > self._RUN_THRESH else self._WALK_DELAY
                if gap >= delay:
                    self._mov_last[ev] = now
                    self._wp._handle_key(_EV_TO_KEY[ev])
            return

        if ev == "interact":
            self._dispatch_interaction()
        key = _EV_TO_KEY.get(ev, 0)
        if key:
            self._wp._handle_key(key)

    def resize(self, w: int, h: int) -> None:
        self._W, self._H = w, h
        self._wp.width   = w
        self._wp.height  = h
        self._cam.resize(w / max(1, h))
        if self._tex is not None:
            self._tex.delete()
        self._tex = Texture.empty(w, h)

    def tick(self, dt: float) -> None:
        self._t += dt
        self._wp.tick(dt, [])

        # Follow player
        import glm
        player = self._wp._player
        self._cam.target = glm.vec3(float(player.x), 0.0, float(player.y))
        self._cam.update(dt)

        # Reload WorldRenderer when zone changes (exits, dungeon transitions)
        zone = self._wp._zone
        if id(zone) != self._zone_id_cached:
            from ..render.world import WorldRenderer
            zone_id = getattr(zone, "zone_id", "")
            self._wr.delete()
            if zone_id in _INTERIOR_ZONE_IDS:
                atlas_img = _make_interior_atlas()
                atlas_tex = Texture.from_pil(atlas_img)
                self._wr  = WorldRenderer.for_lapidus(
                    atlas_tex, atlas_cols=len(_INTERIOR_ATLAS_COLORS), atlas_rows=1)
                self._wr.load_zone(zone, kind_to_atlas=_HOME_KIND_ATLAS)
                try:
                    from ..scenes.player_home import (
                        get_player_home_furniture, get_player_home_interactions,
                    )
                    self._static_furniture = get_player_home_furniture(zone_id)
                    self._entities         = get_player_home_interactions(zone_id)
                except Exception:
                    self._static_furniture = []
                    self._entities         = []
            else:
                realm     = getattr(zone, "realm", None)
                fill      = _REALM_FILL.get(realm, _LAP_FILL)
                atlas_img = _make_realm_atlas(fill)
                atlas_tex = Texture.from_pil(atlas_img)
                self._wr  = WorldRenderer.for_lapidus(
                    atlas_tex, atlas_cols=len(_ATLAS_ORDER), atlas_rows=1)
                self._wr.load_zone(zone)
                self._static_furniture = []
                self._entities         = []
            self._zone_id_cached = id(zone)

        # Refresh player + NPC furniture instances each frame
        self._reload_entities()

    def _reload_entities(self) -> None:
        """Upload static furniture + dynamic entity positions each frame."""
        class _P:
            __slots__ = ("x","y","z","tile_id","height")
            def __init__(self,x,y,z,t,h): self.x=x;self.y=y;self.z=z;self.tile_id=t;self.height=h

        player     = self._wp._player
        placements = list(self._static_furniture)  # zone furniture first
        placements.append(_P(float(player.x), 0.12, float(player.y), 9, 0.45))  # player (amber)
        for npc in getattr(self._wp._zone, "npc_spawns", []):
            placements.append(_P(float(npc.x), 0.08, float(npc.y), 2, 0.35))   # NPC (grey)
        self._wr.load_furniture(placements)

    def draw(self) -> None:
        """Render using WorldRenderer (GL) for world modes; PIL overlay for UI screens."""
        from ..world.play import WorldMode
        from OpenGL import GL

        mode = self._wp._mode

        if mode in (WorldMode.WORLD, WorldMode.DUNGEON, WorldMode.DEAD, WorldMode.DIALOGUE):
            # ── 3D world render — same path as FateKnocksGLPlay ──────────────
            GL.glClearColor(0.04, 0.03, 0.08, 1.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
            self._wr.draw(self._cam, time=self._t)

            # Dialogue overlay on top
            if mode == WorldMode.DIALOGUE:
                data = getattr(self._wp, "_dialogue_bytes", None)
                if data and _PIL:
                    try:
                        img  = Image.open(io.BytesIO(data)).convert("RGBA")
                        dh   = int(self._H * 0.38)
                        img  = img.resize((self._W, dh), Image.LANCZOS)
                        base = Image.new("RGBA", (self._W, self._H), (0,0,0,0))
                        base.alpha_composite(img, (0, self._H - dh))
                        self._tex.update_pil(base)
                        self._ui.add(self._tex, (-1.0,-1.0,1.0,1.0), opacity=0.96)
                        self._ui.draw()
                        self._ui.clear()
                    except Exception:
                        pass
            return

        # ── Overlay modes (ALCHEMY, SHOP, SMELT, VENDOR …) — PIL bytes ───────
        if not _PIL:
            return
        img = self._render_pil()
        self._tex.update_pil(img)
        self._ui.add(self._tex, (-1.0, -1.0, 1.0, 1.0), opacity=1.0)
        self._ui.draw()
        self._ui.clear()

    def delete(self) -> None:
        if hasattr(self, "_wr"):
            try:
                self._wr.delete()
            except Exception:
                pass
        if self._tex is not None:
            self._tex.delete()
            self._tex = None

    # ── Frame composition ─────────────────────────────────────────────────────

    def _render_pil(self) -> "Image.Image":
        from ..world.play import WorldMode
        wp   = self._wp
        mode = wp._mode

        # World view + optional dialogue overlay
        if mode in (WorldMode.WORLD, WorldMode.DIALOGUE,
                    WorldMode.DUNGEON, WorldMode.DEAD):
            img = _render_world_pil(wp, self._W, self._H)
            if mode == WorldMode.DIALOGUE:
                data = getattr(wp, "_dialogue_bytes", None)
                if data:
                    try:
                        overlay = Image.open(io.BytesIO(data)).convert("RGBA")
                        dh  = int(self._H * 0.38)
                        ow  = self._W
                        overlay = overlay.resize((ow, dh), Image.LANCZOS)
                        img.alpha_composite(overlay, (0, self._H - dh))
                    except Exception:
                        pass
            elif mode == WorldMode.DEAD:
                # Dark veil over the world
                veil = Image.new("RGBA", (self._W, self._H), (0, 0, 0, 180))
                img.alpha_composite(veil)
                drw = ImageDraw.Draw(img)
                msg = "You have fallen.  [space]  Return to the world."
                drw.text(((self._W - len(msg) * 7) // 2, self._H // 2 - 8),
                         msg, fill=(200, 80, 80))
            return img

        # Overlay-only modes — full-screen PIL bytes from WorldPlay
        _BYTES_ATTR = {
            WorldMode.ALCHEMY:       "_alchemy_bytes",
            WorldMode.VENDOR:        "_vendor_bytes",
            WorldMode.SHOP:          "_shop_bytes",
            WorldMode.SMELT:         "_smelt_bytes",
            WorldMode.COMBAT:        "_combat_bytes",
            WorldMode.MAP_DISCOVERY: "_map_bytes",
            WorldMode.JOURNAL:       "_journal_bytes",
        }
        attr = _BYTES_ATTR.get(mode)
        if attr:
            data = getattr(wp, attr, None)
            # Generate missing shop/smelt bytes on demand
            if data is None and mode == WorldMode.SHOP:
                data = _shop_screen_bytes(self._W, self._H)
                wp._shop_bytes = data
            elif data is None and mode == WorldMode.SMELT:
                data = _smelt_screen_bytes(self._W, self._H)
                wp._smelt_bytes = data
            if data:
                try:
                    return Image.open(io.BytesIO(data)).convert("RGBA").resize(
                        (self._W, self._H), Image.LANCZOS)
                except Exception:
                    pass

        # Fallback: void
        return Image.new("RGBA", (self._W, self._H), (4, 3, 8, 255))