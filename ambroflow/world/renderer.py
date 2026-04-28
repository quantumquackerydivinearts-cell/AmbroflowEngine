"""
World Renderer
==============
Renders the navigable world directly to a pygame Surface.

No PIL intermediate for the tile layer — everything is pygame.draw primitives.
PIL is only re-introduced for dialogue overlays (existing dialogue frames are
composited over the frozen world background).

Two render modes
----------------
  live      Full tile render + NPCs + player token + HUD.
            Called every frame during world navigation.

  dialogue  Blit frozen background snapshot + PIL dialogue panel.
            World tile cost is zero during conversation scenes.
            Capture the snapshot with snapshot() before entering dialogue.

Tile colour tables
------------------
Each Realm has its own colour table.  A subtle 1px edge line gives tiles
definition without harsh grid lines (PMD-style soft rendering).
"""

from __future__ import annotations

import io
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .map import Zone, Realm as RealmT
    from .player import WorldPlayer, Direction as DirectionT

try:
    import pygame
    _PG = True
except ImportError:
    _PG = False

from .map import WorldTileKind, Realm
from .player import Direction


# ── Colour tables ─────────────────────────────────────────────────────────────

_C = WorldTileKind  # alias

# Lapidus — warm overworld: earth, stone, green fields
_LAP_FILL: dict[WorldTileKind, tuple] = {
    _C.VOID:             (  0,   0,   0),
    _C.WALL:             ( 82,  70,  54),
    _C.FLOOR:            ( 68,  60,  48),
    _C.DOOR:             (112,  78,  42),
    _C.GRASS:            ( 50,  88,  38),
    _C.ROAD:             (112,  96,  70),
    _C.DIRT:             ( 95,  74,  48),
    _C.STONE:            ( 88,  82,  72),
    _C.WATER:            ( 28,  56,  98),
    _C.BRIDGE:           (100,  80,  50),
    _C.STAIRS_UP:        ( 95,  85,  65),
    _C.STAIRS_DOWN:      ( 60,  52,  40),
    _C.PORTAL:           (160, 100, 180),
    _C.DUNGEON_ENTRANCE: ( 35,  25,  52),
    # Surface materials
    _C.TREE:             ( 18,  55,  18),   # deep forest green — impassable
    _C.MARBLE:           (220, 215, 200),   # pale cream — Azoth Sprint
    _C.YELLOW_BRICK:     (185, 145,  55),   # warm yellow — Hopefare St / slum
    _C.CERAMIC:          ( 88, 128, 155),   # cool blue tile — June St / market
    _C.SLATE:            ( 72,  78,  88),   # dark gray-blue — Goldshoot St / temple
    _C.SILICA:           (195, 185, 165),   # pale extravagant — Youthspring Rd / nobles
}
_LAP_EDGE: dict[WorldTileKind, tuple] = {
    _C.GRASS:            ( 38,  70,  28),
    _C.ROAD:             ( 92,  78,  54),
    _C.WALL:             ( 60,  50,  36),
    _C.FLOOR:            ( 52,  46,  36),
    _C.DOOR:             (140, 100,  55),
    _C.WATER:            ( 18,  42,  78),
    _C.DUNGEON_ENTRANCE: ( 55,  40,  80),
    _C.TREE:             ( 10,  40,  10),
    _C.MARBLE:           (180, 175, 162),
    _C.YELLOW_BRICK:     (155, 118,  38),
    _C.CERAMIC:          ( 68, 105, 130),
    _C.SLATE:            ( 54,  60,  70),
    _C.SILICA:           (165, 155, 138),
}

# Mercurie — cool faewilds: teal, silver, deep purple
_MER_FILL: dict[WorldTileKind, tuple] = {
    _C.VOID:             (  0,   0,   0),
    _C.WALL:             ( 42,  38,  78),
    _C.FLOOR:            ( 35,  32,  66),
    _C.DOOR:             ( 80,  52, 108),
    _C.GRASS:            ( 22,  74,  65),
    _C.ROAD:             ( 58,  48,  86),
    _C.DIRT:             ( 48,  40,  78),
    _C.STONE:            ( 52,  48,  88),
    _C.WATER:            ( 12,  68,  90),
    _C.BRIDGE:           ( 55,  45,  82),
    _C.STAIRS_UP:        ( 62,  56,  95),
    _C.STAIRS_DOWN:      ( 38,  34,  72),
    _C.PORTAL:           (130, 100, 180),
    _C.DUNGEON_ENTRANCE: ( 28,  20,  52),
    _C.TREE:             ( 12,  52,  48),
    _C.MARBLE:           (195, 195, 215),
    _C.YELLOW_BRICK:     (155, 138,  85),
    _C.CERAMIC:          ( 45,  98, 118),
    _C.SLATE:            ( 52,  60,  82),
    _C.SILICA:           (175, 168, 192),
}
_MER_EDGE: dict[WorldTileKind, tuple] = {
    _C.GRASS:            ( 15,  58,  52),
    _C.ROAD:             ( 45,  36,  70),
    _C.WALL:             ( 30,  26,  60),
    _C.FLOOR:            ( 25,  22,  52),
    _C.DOOR:             (100,  68, 130),
    _C.WATER:            (  8,  52,  72),
    _C.DUNGEON_ENTRANCE: ( 45,  30,  80),
    _C.TREE:             (  8,  40,  36),
    _C.MARBLE:           (165, 165, 182),
    _C.YELLOW_BRICK:     (128, 112,  65),
    _C.CERAMIC:          ( 30,  78,  96),
    _C.SLATE:            ( 38,  46,  65),
    _C.SILICA:           (148, 140, 165),
}

# Sulphera — hot underworld: ember, dark stone, lava
_SUL_FILL: dict[WorldTileKind, tuple] = {
    _C.VOID:             (  0,   0,   0),
    _C.WALL:             ( 48,  12,   6),
    _C.FLOOR:            ( 40,  10,   5),
    _C.DOOR:             ( 90,  35,  12),
    _C.GRASS:            ( 52,  18,   8),   # scorched earth
    _C.ROAD:             ( 62,  28,  12),
    _C.DIRT:             ( 58,  22,  10),
    _C.STONE:            ( 55,  20,   8),
    _C.WATER:            ( 88,  32,   5),   # lava
    _C.BRIDGE:           ( 70,  25,  10),
    _C.STAIRS_UP:        ( 75,  30,  12),
    _C.STAIRS_DOWN:      ( 42,  12,   5),
    _C.PORTAL:           (140,  60,  20),
    _C.DUNGEON_ENTRANCE: ( 30,   8,   4),
    _C.TREE:             ( 30,   8,   2),   # charred
    _C.MARBLE:           (165,  90,  50),   # stained cream
    _C.YELLOW_BRICK:     (145,  65,  20),
    _C.CERAMIC:          ( 65,  30,  10),
    _C.SLATE:            ( 50,  18,   8),
    _C.SILICA:           (145,  80,  45),
}
_SUL_EDGE: dict[WorldTileKind, tuple] = {
    _C.GRASS:            ( 40,  12,   5),
    _C.ROAD:             ( 50,  20,   8),
    _C.WALL:             ( 35,   8,   3),
    _C.FLOOR:            ( 30,   7,   3),
    _C.DOOR:             (110,  45,  15),
    _C.WATER:            ( 65,  20,   3),
    _C.DUNGEON_ENTRANCE: ( 60,  18,   8),
    _C.TREE:             ( 20,   5,   1),
    _C.MARBLE:           (135,  70,  35),
    _C.YELLOW_BRICK:     (118,  50,  12),
    _C.CERAMIC:          ( 48,  20,   6),
    _C.SLATE:            ( 35,  12,   4),
    _C.SILICA:           (118,  60,  30),
}

_REALM_FILL: dict[Realm, dict] = {
    Realm.LAPIDUS:  _LAP_FILL,
    Realm.MERCURIE: _MER_FILL,
    Realm.SULPHERA: _SUL_FILL,
}
_REALM_EDGE: dict[Realm, dict] = {
    Realm.LAPIDUS:  _LAP_EDGE,
    Realm.MERCURIE: _MER_EDGE,
    Realm.SULPHERA: _SUL_EDGE,
}

# Entity colours
_PLAYER_FILL   = (220, 190, 100)
_PLAYER_SHADOW = ( 80,  60,  20)
_NPC_FILL      = (160, 160, 180)
_NPC_SHADOW    = ( 60,  60,  70)
_NPC_OUTLINE   = (100, 100, 120)

# HUD
_HUD_TEXT   = (200, 180, 130)
_HUD_ACCENT = (200, 155,  50)


class WorldRenderer:
    """
    Renders the navigable world directly to a pygame Surface.

    TILE_SIZE  — pixels per tile.  32 gives PMD-style density at 1280×800
                 (40 × 25 visible tiles, comfortably more than any authored zone).
    """

    TILE_SIZE = 32

    def __init__(self, width: int, height: int) -> None:
        self.width  = width
        self.height = height
        self._font_hud:  object = None
        self._font_tiny: object = None
        if _PG:
            self._init_fonts()

    def _init_fonts(self) -> None:
        try:
            pygame.font.init()
            self._font_hud  = pygame.font.SysFont(None, 18)
            self._font_tiny = pygame.font.SysFont(None, 14)
        except Exception:
            pass

    # ── Camera ────────────────────────────────────────────────────────────────

    def _cam(self, px: int, py: int) -> tuple[int, int]:
        """Tile-space camera origin so the player appears centred."""
        vw = self.width  // self.TILE_SIZE
        vh = self.height // self.TILE_SIZE
        return px - vw // 2, py - vh // 2

    # ── Tile ─────────────────────────────────────────────────────────────────

    def _draw_tile(
        self,
        screen: object,
        sx: int, sy: int,
        tile: WorldTileKind,
        realm: Realm,
    ) -> None:
        T    = self.TILE_SIZE
        fill = _REALM_FILL.get(realm, _LAP_FILL).get(tile, (20, 20, 20))
        edge = _REALM_EDGE.get(realm, _LAP_EDGE).get(tile)

        pygame.draw.rect(screen, fill, (sx, sy, T, T))
        if edge:
            pygame.draw.rect(screen, edge, (sx + 1, sy + 1, T - 2, T - 2), 1)

        # Door: vertical beam suggesting a frame
        if tile == WorldTileKind.DOOR:
            door_col = (
                min(255, fill[0] + 55),
                min(255, fill[1] + 35),
                max(0,   fill[2] - 10),
            )
            mid = T // 2
            pygame.draw.rect(screen, door_col,
                             (sx + mid - 3, sy + 2, 6, T - 2))
            pygame.draw.rect(screen, edge or fill,
                             (sx + mid - 4, sy + 1, 8, T), 1)

        # Dungeon entrance: dark recess with faint glow hint
        elif tile == WorldTileKind.DUNGEON_ENTRANCE:
            glow = (70, 45, 100)
            pygame.draw.rect(screen, glow,
                             (sx + 4, sy + 4, T - 8, T - 8), 2)

        # Portal: concentric rings
        elif tile == WorldTileKind.PORTAL:
            cx, cy = sx + T // 2, sy + T // 2
            ring_col = (min(255, fill[0] + 40),
                        min(255, fill[1] + 30),
                        min(255, fill[2] + 50))
            for r in (T // 4, T // 3):
                pygame.draw.circle(screen, ring_col, (cx, cy), r, 1)

    # ── Player token ──────────────────────────────────────────────────────────

    def _draw_player(
        self,
        screen: object,
        sx: int, sy: int,
        facing: Direction,
    ) -> None:
        T  = self.TILE_SIZE
        cx = sx + T // 2
        cy = sy + T // 2
        r  = T // 2 - 5

        # Drop shadow
        shadow_pts = [
            (cx,     cy - r + 2),
            (cx + r, cy     + 2),
            (cx,     cy + r + 2),
            (cx - r, cy     + 2),
        ]
        pygame.draw.polygon(screen, _PLAYER_SHADOW, shadow_pts)

        # Diamond body
        body_pts = [
            (cx,     cy - r),
            (cx + r, cy    ),
            (cx,     cy + r),
            (cx - r, cy    ),
        ]
        pygame.draw.polygon(screen, _PLAYER_FILL, body_pts)
        pygame.draw.polygon(screen, _PLAYER_SHADOW, body_pts, 1)

        # Facing pip
        pip = {
            Direction.NORTH: (cx,         cy - r + 3),
            Direction.SOUTH: (cx,         cy + r - 3),
            Direction.EAST:  (cx + r - 3, cy        ),
            Direction.WEST:  (cx - r + 3, cy        ),
        }.get(facing, (cx, cy))
        pygame.draw.circle(screen, (30, 20, 5), pip, 2)

    # ── NPC token ─────────────────────────────────────────────────────────────

    def _draw_npc(self, screen: object, sx: int, sy: int) -> None:
        T  = self.TILE_SIZE
        cx = sx + T // 2
        cy = sy + T // 2
        r  = T // 2 - 6
        pygame.draw.circle(screen, _NPC_SHADOW,  (cx, cy + 2), r)
        pygame.draw.circle(screen, _NPC_FILL,    (cx, cy),     r)
        pygame.draw.circle(screen, _NPC_OUTLINE, (cx, cy),     r, 1)

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hud(
        self,
        screen:      object,
        zone_name:   str,
        realm:       Realm,
        player_name: str,
        hint:        str = "",
    ) -> None:
        W, H = self.width, self.height

        # Top bar — zone / realm name
        top_bar = pygame.Surface((W, 24), pygame.SRCALPHA)
        top_bar.fill((0, 0, 0, 145))
        screen.blit(top_bar, (0, 0))

        if self._font_hud:
            label = f"{zone_name}  [ {realm.value.capitalize()} ]"
            txt = self._font_hud.render(label, True, _HUD_ACCENT)
            screen.blit(txt, (8, 4))

        # Bottom bar — player name + interaction hint
        bot_bar = pygame.Surface((W, 28), pygame.SRCALPHA)
        bot_bar.fill((0, 0, 0, 155))
        screen.blit(bot_bar, (0, H - 28))

        if self._font_hud:
            nm = self._font_hud.render(player_name, True, _HUD_TEXT)
            screen.blit(nm, (W - nm.get_width() - 10, H - 22))

        if hint and self._font_tiny:
            h_txt = self._font_tiny.render(hint, True, _HUD_TEXT)
            screen.blit(h_txt, ((W - h_txt.get_width()) // 2, H - 21))

    # ── Full live render ──────────────────────────────────────────────────────

    def render(
        self,
        screen: object,
        zone:   object,   # Zone
        player: object,   # WorldPlayer
        hint:   str = "",
    ) -> None:
        """Render the full world view to screen — tile grid, entities, HUD."""
        if not _PG:
            return
        T = self.TILE_SIZE
        cam_x, cam_y = self._cam(player.x, player.y)

        # Tile columns/rows to draw (one extra on each side to avoid pop-in)
        vw = self.width  // T + 2
        vh = self.height // T + 2

        screen.fill((0, 0, 0))

        for ty in range(cam_y - 1, cam_y + vh + 1):
            for tx in range(cam_x - 1, cam_x + vw + 1):
                sx = (tx - cam_x) * T
                sy = (ty - cam_y) * T
                tile = zone.tile_at(tx, ty)
                self._draw_tile(screen, sx, sy, tile, zone.realm)

        # NPC tokens
        for npc in zone.npc_spawns:
            sx = (npc.x - cam_x) * T
            sy = (npc.y - cam_y) * T
            self._draw_npc(screen, sx, sy)

        # Player token
        px = (player.x - cam_x) * T
        py = (player.y - cam_y) * T
        self._draw_player(screen, px, py, player.facing)

        # HUD overlay
        self._draw_hud(screen, zone.name, zone.realm, player.name, hint)

    # ── Frozen background (dialogue optimisation) ─────────────────────────────

    def snapshot(self, screen: object) -> object:
        """Capture the current screen as a frozen Surface for dialogue mode."""
        return screen.copy()

    def render_with_dialogue(
        self,
        screen:         object,
        frozen_bg:      object,
        dialogue_bytes: Optional[bytes],
    ) -> None:
        """
        Blit the frozen world background + a PIL dialogue panel.

        The dialogue panel occupies the bottom 38 % of the screen.
        World tile render cost is zero — the background is a pre-captured copy.
        """
        if not _PG:
            return
        screen.blit(frozen_bg, (0, 0))
        if dialogue_bytes:
            try:
                dial_surf = pygame.image.load(io.BytesIO(dialogue_bytes))
                dw = self.width
                dh = int(self.height * 0.38)
                scaled = pygame.transform.scale(dial_surf, (dw, dh))
                screen.blit(scaled, (0, self.height - dh))
            except Exception:
                pass