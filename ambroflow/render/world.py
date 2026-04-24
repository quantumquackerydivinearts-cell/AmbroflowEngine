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
    "u_sun_dir"   : (0.6,  1.0, -0.4),
    "u_sun_color" : (1.00, 0.92, 0.70),
    "u_ambient"   : (0.14, 0.12, 0.22),
    "u_rim_color" : (0.55, 0.60, 0.75),
    "u_fog_near"  : 18.0,
    "u_fog_far"   : 60.0,
    "u_fog_color" : (0.36, 0.33, 0.44),
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
            WorldTileKind.DOOR:             0,
            WorldTileKind.GRASS:            1,
            WorldTileKind.ROAD:             2,
            WorldTileKind.DIRT:             2,
            WorldTileKind.STONE:            5,
            WorldTileKind.WATER:            4,
            WorldTileKind.BRIDGE:           7,
            WorldTileKind.STAIRS_UP:        0,
            WorldTileKind.STAIRS_DOWN:      0,
            WorldTileKind.PORTAL:           0,
            WorldTileKind.DUNGEON_ENTRANCE: 0,
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