"""
WorldRenderer (GL)
==================
Draws the 3D tile geometry for one zone.

Architecture
------------
  - One VAO + instanced draw for the tile layer.
  - Tile quad: unit XZ plane (1×1), Y=0 — one per tile.
  - Per-instance buffer: (offset_x, offset_y, offset_z, tile_id, height).
  - Separate Buffer object updated each frame if the zone scrolls.

Usage
-----
    from ambroflow.render.world import WorldRenderer
    from ambroflow.engine import Camera, Shader, Framebuffer

    wr = WorldRenderer(shader, atlas_texture, atlas_cols=16, atlas_rows=16)
    wr.load_zone(zone)      # uploads instance buffer

    fbo.bind()
    wr.draw(camera)
    fbo.unbind()
"""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np
from OpenGL import GL

from ..engine.shader import Shader
from ..engine.buffer import Buffer, VertexArray
from ..engine.texture import Texture
from ..engine.camera import Camera

if TYPE_CHECKING:
    from ..world.map import WorldMap, Zone


# ── Tile quad geometry (XZ plane, unit size) ───────────────────────────────────
# Interleaved: pos(3) + uv(2) + normal(3)  = 8 floats per vertex
_TILE_VERTS = np.array([
    # pos (x,y,z)    uv (u,v)   normal (0,1,0)
    -0.5, 0.0, -0.5,   0.0, 0.0,   0.0, 1.0, 0.0,
     0.5, 0.0, -0.5,   1.0, 0.0,   0.0, 1.0, 0.0,
     0.5, 0.0,  0.5,   1.0, 1.0,   0.0, 1.0, 0.0,
    -0.5, 0.0,  0.5,   0.0, 1.0,   0.0, 1.0, 0.0,
], dtype=np.float32).reshape(-1, 8)

_TILE_INDICES = np.array([0, 1, 2,  0, 2, 3], dtype=np.uint32)

_STRIDE_TILE  = 8 * 4   # 8 floats × 4 bytes

# Per-instance layout: offset(3) + tile_id(1) + height(1) = 5 floats
_STRIDE_INST  = 5 * 4

_SHADERS_DIR = Path(__file__).parent.parent / "engine" / "shaders"


# ── Realm lighting presets ─────────────────────────────────────────────────────

LAPIDUS_LIGHTING = {
    "u_sun_dir"       : (0.6,  1.0, -0.4),
    "u_sun_color"     : (1.00, 0.92, 0.70),
    "u_ambient"       : (0.14, 0.12, 0.22),
    "u_rim_color"     : (0.55, 0.60, 0.75),
    "u_fog_near"      : 18.0,
    "u_fog_far"       : 60.0,
    "u_fog_color"     : (0.36, 0.33, 0.44),
    "u_seam_width"    : 0.14,   # wider band = more gradual, organic edge
    "u_seam_strength" : 0.22,   # lower strength = softer, less harsh
}


class WorldRenderer:
    """
    Instanced tile-layer renderer.

    Parameters
    ----------
    shader       : Compiled world.vert + lapidus_world.frag (or realm variant).
    atlas        : Tile atlas Texture.
    atlas_cols   : Number of tile columns in the atlas.
    atlas_rows   : Number of tile rows in the atlas.
    lighting     : Dict of uniform name → value.  Defaults to LAPIDUS_LIGHTING.
    """

    def __init__(
        self,
        shader:     Shader,
        atlas:      Texture,
        atlas_cols: int = 16,
        atlas_rows: int = 16,
        lighting:   Optional[dict] = None,
    ) -> None:
        self._shader     = shader
        self._atlas      = atlas
        self._atlas_cols = atlas_cols
        self._atlas_rows = atlas_rows
        self._lighting   = lighting or LAPIDUS_LIGHTING.copy()

        # Static tile quad geometry
        self._vbo_tile = Buffer(_TILE_VERTS.flatten(), GL.GL_STATIC_DRAW)
        self._ebo      = Buffer(_TILE_INDICES, GL.GL_STATIC_DRAW,
                                target=GL.GL_ELEMENT_ARRAY_BUFFER)

        # Instance buffer — allocated on load_zone
        self._vbo_inst: Optional[Buffer] = None
        self._instance_count = 0

        # Furniture instance buffer — allocated on load_furniture
        self._vbo_furn: Optional[Buffer] = None
        self._furn_count = 0
        self._vao_furn = VertexArray()

        self._vao = VertexArray()
        self._setup_vao()

    # ── Zone loading ───────────────────────────────────────────────────────────

    def load_zone(self, zone: "Zone",
                  kind_to_atlas: "dict | None" = None) -> None:
        """Upload tile instances from a Zone."""
        instances = self._build_instances(zone, kind_to_atlas)
        self._instance_count = len(instances) // 5

        if self._instance_count == 0:
            return

        data = instances.astype(np.float32)
        if self._vbo_inst is None:
            self._vbo_inst = Buffer(data, GL.GL_DYNAMIC_DRAW)
        else:
            self._vbo_inst.upload(data, GL.GL_DYNAMIC_DRAW)

        # Re-wire instance attribs into VAO
        self._vao.bind()
        self._vbo_inst.bind()
        stride = _STRIDE_INST
        self._vao.attrib(3, size=3, stride=stride, offset=0)         # i_offset
        self._vao.attrib(4, size=1, stride=stride, offset=12)        # i_tile_id
        self._vao.attrib(5, size=1, stride=stride, offset=16)        # i_height
        self._vao.attrib_divisor(3, 1)
        self._vao.attrib_divisor(4, 1)
        self._vao.attrib_divisor(5, 1)
        self._vao.unbind()
        self._vbo_inst.unbind()

    # ── Ko scene loading (.scene.ko / .scene.json → direct instance buffer) ──

    # Interaction node action_id → (atlas tile_id, height) — used by load_scene_ko
    _KO_ACTION_FURN: "dict[str, tuple[int, float]]" = {
        "open_alchemy_ui":     (8,  0.8),   # TABLE workbench
        "open_smelt_ui":       (10, 1.0),   # FURNACE
        "open_shop_ui":        (12, 0.9),   # COUNTER
        "shop_counter":        (12, 0.9),
        "meditation_tutorial": (14, 0.4),   # ALTAR
        "meditate":            (14, 0.4),
        "lore_books":          (15, 1.8),   # BOOKSHELF
        "read":                (15, 1.8),
        "save_and_heal":       (7,  0.5),   # BED
        "open_chest":          (8,  0.6),   # TABLE (chest height)
    }

    # Kobra color token → atlas tile ID (maps to _ATLAS_COLORS in fate_knocks_gl)
    _KO_TOKEN_ATLAS: "dict[str, int]" = {
        "Ot":  0,   # warm flagstone / wood floor
        "El":  3,   # stone wall
        "Ru": 10,   # furnace / door (ember-dark)
        "Fu":  4,   # water / glass (blue)
        "Ka": 14,   # cloth / altar (violet-indigo)
        "AE": 14,   # cushion (violet)
        "Ki":  1,   # nature / spirit (forest green)
        "Na":  5,   # silver / stone
        "Ha":  9,   # white / parchment
        "Ga":  6,   # void / black
        "Ung": 15,  # dark wood / thatch
        "Wu":  6,   # deep black
    }
    _KO_TOKEN_ATLAS_DEFAULT = 0

    def load_scene_ko(self, path: "Path | str") -> int:
        """
        Load a .scene.ko (or compiled .scene.json) directly into the renderer.

        Maps Kobra color tokens → atlas tile IDs using _KO_TOKEN_ATLAS,
        bypassing the Zone tile-kind system entirely so per-material colors
        are preserved.

        Returns the number of voxels loaded.
        """
        from ..world.ko_scene_reader import load_ko_scene

        try:
            scene = load_ko_scene(Path(path))
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("load_scene_ko failed: %s", exc)
            return 0

        voxels = scene.get("renderer", {}).get("scene", {}).get("voxels", [])
        if not voxels:
            return 0

        rows: list[float] = []
        for v in voxels:
            tok  = v.get("color_token", "")
            tid  = float(self._KO_TOKEN_ATLAS.get(tok, self._KO_TOKEN_ATLAS_DEFAULT))
            # scene coords: x=column, y=row, z=elevation
            # world coords: X=column, Y=elevation, Z=row
            rows.extend([
                float(v.get("x", 0)),   # world X
                float(v.get("z", 0)),   # world Y (elevation)
                float(v.get("y", 0)),   # world Z (row / depth)
                tid,
                1.0,                    # unit height
            ])

        if not rows:
            return 0

        import numpy as _np
        data = _np.array(rows, dtype=_np.float32)
        n    = len(voxels)

        if self._vbo_inst is None:
            self._vbo_inst = Buffer(data, GL.GL_DYNAMIC_DRAW)
        else:
            self._vbo_inst.upload(data, GL.GL_DYNAMIC_DRAW)
        self._instance_count = n

        self._vao.bind()
        self._vbo_inst.bind()
        stride = _STRIDE_INST
        self._vao.attrib(3, size=3, stride=stride, offset=0)
        self._vao.attrib(4, size=1, stride=stride, offset=12)
        self._vao.attrib(5, size=1, stride=stride, offset=16)
        self._vao.attrib_divisor(3, 1)
        self._vao.attrib_divisor(4, 1)
        self._vao.attrib_divisor(5, 1)
        self._vao.unbind()
        self._vbo_inst.unbind()

        # ── Furniture: interaction nodes → FurniturePlacement-like objects ────
        class _P:
            __slots__ = ("x", "y", "z", "tile_id", "height")
            def __init__(self, x, y, z, tile_id, height):
                self.x=x; self.y=y; self.z=z; self.tile_id=tile_id; self.height=height

        placements = []
        for node in scene.get("nodes", []):
            if node.get("kind") != "interaction":
                continue
            meta   = node.get("metadata") or {}
            action = meta.get("action", "")
            entry  = self._KO_ACTION_FURN.get(action)
            if entry is None:
                continue
            tile_id, height = entry
            # scene coords → world: x=col, z=elevation(meta.z), y=row→world Z
            placements.append(_P(
                x       = float(node.get("x", 0)),
                y       = float(meta.get("z", 0)),      # elevation → world Y
                z       = float(node.get("y", 0)),      # row       → world Z
                tile_id = tile_id,
                height  = height,
            ))

        if placements:
            self.load_furniture(placements)

        return n

    # ── Furniture loading ──────────────────────────────────────────────────────

    def load_furniture(self, placements: "list") -> None:
        """
        Upload furniture instances.

        placements — list of FurniturePlacement objects.  Each placement
        contributes one instance at (x, y_elevation, z, tile_id, height).
        The furniture VAO shares the same static tile quad as the zone VAO.
        """
        if not placements:
            self._furn_count = 0
            return

        rows: list[float] = []
        for p in placements:
            rows.extend([
                float(p.x),
                float(p.y),      # elevation (not always 0)
                float(p.z),
                float(p.tile_id),
                float(p.height),
            ])

        data = np.array(rows, dtype=np.float32)
        self._furn_count = len(placements)

        if self._vbo_furn is None:
            self._vbo_furn = Buffer(data, GL.GL_DYNAMIC_DRAW)
        else:
            self._vbo_furn.upload(data, GL.GL_DYNAMIC_DRAW)

        self._vao_furn.bind()
        self._vbo_tile.bind()
        self._ebo.bind()
        s = _STRIDE_TILE
        self._vao_furn.attrib(0, size=3, stride=s, offset=0)   # a_pos
        self._vao_furn.attrib(1, size=2, stride=s, offset=12)  # a_uv
        self._vao_furn.attrib(2, size=3, stride=s, offset=20)  # a_normal
        self._vbo_furn.bind()
        stride = _STRIDE_INST
        self._vao_furn.attrib(3, size=3, stride=stride, offset=0)
        self._vao_furn.attrib(4, size=1, stride=stride, offset=12)
        self._vao_furn.attrib(5, size=1, stride=stride, offset=16)
        self._vao_furn.attrib_divisor(3, 1)
        self._vao_furn.attrib_divisor(4, 1)
        self._vao_furn.attrib_divisor(5, 1)
        self._vao_furn.unbind()
        self._vbo_furn.unbind()

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, camera: Camera, time: float = 0.0) -> None:
        if self._instance_count == 0:
            return

        self._shader.use()
        self._shader["u_view"]       = camera.view
        self._shader["u_proj"]       = camera.proj
        self._shader["u_atlas_size"] = (float(self._atlas_cols),
                                        float(self._atlas_rows))
        self._shader["u_time"]       = time

        for name, val in self._lighting.items():
            self._shader[name] = val

        self._atlas.bind(unit=0)
        self._shader["u_atlas"] = 0

        GL.glDisable(GL.GL_CULL_FACE)
        self._vao.bind()
        GL.glDrawElementsInstanced(
            GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
            ctypes.c_void_p(0), self._instance_count,
        )
        self._vao.unbind()

        # Draw furniture layer on top
        if self._furn_count > 0:
            self._vao_furn.bind()
            GL.glDrawElementsInstanced(
                GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
                ctypes.c_void_p(0), self._furn_count,
            )
            self._vao_furn.unbind()

        self._atlas.unbind(unit=0)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def update_lighting(self, updates: dict) -> None:
        """Merge lighting uniform overrides into the current lighting dict."""
        self._lighting.update(updates)

    def delete(self) -> None:
        self._vbo_tile.delete()
        self._ebo.delete()
        if self._vbo_inst:
            self._vbo_inst.delete()
        if self._vbo_furn:
            self._vbo_furn.delete()
        self._vao.delete()
        self._vao_furn.delete()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _setup_vao(self) -> None:
        self._vao.bind()
        self._vbo_tile.bind()
        self._ebo.bind()
        s = _STRIDE_TILE
        self._vao.attrib(0, size=3, stride=s, offset=0)   # a_pos
        self._vao.attrib(1, size=2, stride=s, offset=12)  # a_uv
        self._vao.attrib(2, size=3, stride=s, offset=20)  # a_normal
        self._vao.unbind()
        self._vbo_tile.unbind()

    @staticmethod
    def _build_instances(zone: "Zone",
                         kind_to_atlas: "dict | None" = None) -> np.ndarray:
        """Convert Zone.voxels into flat (offset_x, offset_y, offset_z, tile_id, height) array."""
        from ..world.map import WorldTileKind
        _default_atlas: dict[WorldTileKind, int] = {
            WorldTileKind.VOID:             6,
            WorldTileKind.WALL:             3,
            WorldTileKind.FLOOR:            0,
            WorldTileKind.DOOR:             7,
            WorldTileKind.GRASS:            1,
            WorldTileKind.ROAD:             2,
            WorldTileKind.DIRT:             2,
            WorldTileKind.STONE:            5,
            WorldTileKind.WATER:            4,
            WorldTileKind.BRIDGE:           8,
            WorldTileKind.STAIRS_UP:        14,
            WorldTileKind.STAIRS_DOWN:      15,
            WorldTileKind.PORTAL:           11,
            WorldTileKind.DUNGEON_ENTRANCE: 12,
            WorldTileKind.TREE:             13,
            WorldTileKind.MARBLE:           10,
            WorldTileKind.YELLOW_BRICK:     9,
            WorldTileKind.CERAMIC:          16,
            WorldTileKind.SLATE:            17,
            WorldTileKind.SILICA:           18,
        }
        atlas_map = kind_to_atlas or _default_atlas
        rows: list[float] = []
        for (x, y), kind in zone.voxels.items():
            tile_id = atlas_map.get(kind, 0)
            rows.extend([
                float(x),    # X east
                0.0,         # Y ground
                float(y),    # Z south
                float(tile_id),
                0.0,         # height
            ])
        return np.array(rows, dtype=np.float32)

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def for_lapidus(cls, atlas: Texture,
                    atlas_cols: int = 16, atlas_rows: int = 16) -> "WorldRenderer":
        """Build a WorldRenderer pre-loaded with Lapidus shaders and lighting."""
        shader = Shader(
            (_SHADERS_DIR / "world.vert").read_text(encoding="utf-8"),
            (_SHADERS_DIR / "lapidus_world.frag").read_text(encoding="utf-8"),
        )
        return cls(shader, atlas, atlas_cols, atlas_rows, LAPIDUS_LIGHTING.copy())