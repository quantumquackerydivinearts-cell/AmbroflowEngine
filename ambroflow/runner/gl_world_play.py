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
from typing import Optional, TYPE_CHECKING

try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False

from ..engine.texture import Texture
from ..render.ui      import UIRenderer
from ..world.map      import WorldTileKind, Realm
from ..world.player   import Direction

if TYPE_CHECKING:
    from ..world.play import WorldPlay


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

_PLAYER_FILL   = (220, 190, 100)
_PLAYER_SHADOW = ( 80,  60,  20)
_NPC_FILL      = (160, 160, 180)
_NPC_SHADOW    = ( 60,  60,  70)
_NPC_OUTLINE   = (100, 100, 120)
_HUD_TEXT      = (200, 180, 130)
_HUD_ACCENT    = (200, 155,  50)

TILE_SIZE = 32


# ── PIL world tile renderer ───────────────────────────────────────────────────

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
        world_play: "WorldPlay",
        ui:         UIRenderer,
        width:      int,
        height:     int,
    ) -> None:
        self._wp  = world_play
        self._ui  = ui
        self._W   = width
        self._H   = height
        self._tex = Texture.empty(width, height)

    # ── Public API ────────────────────────────────────────────────────────────

    def is_done(self) -> bool:
        return self._wp.is_done()

    def handle_event(self, ev: str) -> None:
        key = _EV_TO_KEY.get(ev, 0)
        if key:
            self._wp._handle_key(key)

    def resize(self, w: int, h: int) -> None:
        self._W, self._H = w, h
        self._wp.width   = w
        self._wp.height  = h
        if self._tex is not None:
            self._tex.delete()
        self._tex = Texture.empty(w, h)

    def tick(self, dt: float) -> None:
        """Update hint text (no pygame events needed)."""
        self._wp.tick(dt, [])

    def draw(self) -> None:
        """Render current game state to a PIL image, upload, blit as fullscreen quad."""
        if not _PIL:
            return
        img = self._render_pil()
        self._tex.update_pil(img)
        self._ui.add(self._tex, (-1.0, -1.0, 1.0, 1.0), opacity=1.0)
        self._ui.draw()
        self._ui.clear()

    def delete(self) -> None:
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
            WorldMode.COMBAT:        "_combat_bytes",
            WorldMode.MAP_DISCOVERY: "_map_bytes",
        }
        attr = _BYTES_ATTR.get(mode)
        if attr:
            data = getattr(wp, attr, None)
            if data:
                try:
                    return Image.open(io.BytesIO(data)).convert("RGBA").resize(
                        (self._W, self._H), Image.LANCZOS)
                except Exception:
                    pass

        # Fallback: void
        return Image.new("RGBA", (self._W, self._H), (4, 3, 8, 255))