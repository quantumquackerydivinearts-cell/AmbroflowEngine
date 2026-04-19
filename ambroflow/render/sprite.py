"""
SpriteRenderer (GL)
===================
Billboard sprites in 3-D world space.

Each sprite is a Y-locked camera-facing quad.  Sprites are batched into
a single instanced draw call per atlas page.

Usage
-----
    sr = SpriteRenderer(shader, atlas_texture)

    # Each frame, rebuild instance list from entity positions:
    sr.begin()
    sr.add(world_pos=(x, y, z), size=(1.0, 2.0),
           frame_u=0.0, frame_v=0.0, frame_w=0.0625, frame_h=0.125)
    sr.end()    # uploads to GPU

    sr.draw(camera)
"""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Optional

import numpy as np
from OpenGL import GL

from ..engine.shader import Shader
from ..engine.buffer import Buffer, VertexArray
from ..engine.texture import Texture
from ..engine.camera import Camera


_SHADERS_DIR = Path(__file__).parent.parent / "engine" / "shaders"

# Unit quad anchored at feet: x∈[-0.5,0.5], y∈[0,1]
# Interleaved: a_quad(2) + a_uv(2) = 4 floats
_QUAD_VERTS = np.array([
    -0.5, 0.0,  0.0, 1.0,
     0.5, 0.0,  1.0, 1.0,
     0.5, 1.0,  1.0, 0.0,
    -0.5, 1.0,  0.0, 0.0,
], dtype=np.float32)

_QUAD_INDICES = np.array([0, 1, 2,  0, 2, 3], dtype=np.uint32)

_STRIDE_QUAD = 4 * 4    # 4 floats × 4 bytes

# Per-instance: world_pos(3) + size(2) + frame(4) = 9 floats
_STRIDE_INST = 9 * 4
_MAX_SPRITES = 4096


class SpriteRenderer:
    """
    Batched billboard sprite renderer.

    Parameters
    ----------
    shader : Compiled sprite.vert + sprite.frag.
    atlas  : Sprite atlas Texture.
    """

    def __init__(self, shader: Shader, atlas: Texture) -> None:
        self._shader = shader
        self._atlas  = atlas

        self._vbo_quad  = Buffer(_QUAD_VERTS, GL.GL_STATIC_DRAW)
        self._ebo       = Buffer(_QUAD_INDICES, GL.GL_STATIC_DRAW,
                                 target=GL.GL_ELEMENT_ARRAY_BUFFER)

        # Pre-allocate instance buffer for _MAX_SPRITES
        dummy = np.zeros(_MAX_SPRITES * 9, dtype=np.float32)
        self._vbo_inst  = Buffer(dummy, GL.GL_STREAM_DRAW)
        self._count     = 0
        self._instances: list[float] = []

        self._vao = VertexArray()
        self._setup_vao()

    # ── Build batch ───────────────────────────────────────────────────────────

    def begin(self) -> None:
        self._instances = []
        self._count = 0

    def add(
        self,
        world_pos: tuple[float, float, float],
        size:      tuple[float, float],
        frame_u:   float,
        frame_v:   float,
        frame_w:   float,
        frame_h:   float,
    ) -> None:
        if self._count >= _MAX_SPRITES:
            return
        self._instances.extend([
            world_pos[0], world_pos[1], world_pos[2],
            size[0], size[1],
            frame_u, frame_v, frame_w, frame_h,
        ])
        self._count += 1

    def end(self) -> None:
        """Upload current batch to GPU."""
        if not self._instances:
            return
        data = np.array(self._instances, dtype=np.float32)
        self._vbo_inst.bind()
        GL.glBufferSubData(GL.GL_ARRAY_BUFFER, 0, data.nbytes, data)
        self._vbo_inst.unbind()

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, camera: Camera, ambient: tuple = (0.14, 0.12, 0.22),
             sun_color: tuple = (1.0, 0.92, 0.70)) -> None:
        if self._count == 0:
            return

        self._shader.use()
        self._shader["u_view"]       = camera.view
        self._shader["u_proj"]       = camera.proj

        # Extract right vector from view matrix row 0
        import glm
        view_row0 = glm.vec3(camera.view[0][0], camera.view[1][0], camera.view[2][0])
        self._shader["u_cam_right"]  = view_row0
        self._shader["u_ambient"]    = ambient
        self._shader["u_sun_color"]  = sun_color
        self._shader["u_alpha_cutoff"] = 0.5

        self._atlas.bind(unit=0)
        self._shader["u_sprite_atlas"] = 0

        GL.glDisable(GL.GL_CULL_FACE)
        self._vao.bind()
        GL.glDrawElementsInstanced(
            GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
            ctypes.c_void_p(0), self._count,
        )
        self._vao.unbind()
        self._atlas.unbind(unit=0)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def delete(self) -> None:
        self._vbo_quad.delete()
        self._ebo.delete()
        self._vbo_inst.delete()
        self._vao.delete()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _setup_vao(self) -> None:
        self._vao.bind()
        self._vbo_quad.bind()
        self._ebo.bind()
        s = _STRIDE_QUAD
        self._vao.attrib(0, size=2, stride=s, offset=0)   # a_quad
        self._vao.attrib(1, size=2, stride=s, offset=8)   # a_uv

        self._vbo_inst.bind()
        si = _STRIDE_INST
        self._vao.attrib(2, size=3, stride=si, offset=0)    # i_world_pos
        self._vao.attrib(3, size=2, stride=si, offset=12)   # i_size
        self._vao.attrib(4, size=1, stride=si, offset=20)   # i_frame_u
        self._vao.attrib(5, size=1, stride=si, offset=24)   # i_frame_v
        self._vao.attrib(6, size=1, stride=si, offset=28)   # i_frame_w
        self._vao.attrib(7, size=1, stride=si, offset=32)   # i_frame_h
        for i in range(2, 8):
            self._vao.attrib_divisor(i, 1)

        self._vao.unbind()
        self._vbo_quad.unbind()
        self._vbo_inst.unbind()

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def default(cls, atlas: Texture) -> "SpriteRenderer":
        shader = Shader(
            (_SHADERS_DIR / "sprite.vert").read_text(encoding="utf-8"),
            (_SHADERS_DIR / "sprite.frag").read_text(encoding="utf-8"),
        )
        return cls(shader, atlas)