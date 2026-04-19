"""
UIRenderer
==========
Screen-space quads for PIL-rendered action layer content:
  - Dialogue panels
  - Character portraits
  - Dream sequence overlays
  - HUD elements

Each panel is a Texture (updated from PIL each frame if dynamic) rendered
onto a screen-space quad defined in NDC ([-1,1] × [-1,1]).

Usage
-----
    ui = UIRenderer()

    # Static portrait:
    portrait = Texture.from_pil(pil_image)
    ui.add(portrait, ndc_rect=(-1.0, -1.0, -0.35, 0.45), opacity=1.0)

    # Dynamic dialogue box (updated each frame):
    dbox = Texture.empty(800, 200)
    dbox.update_pil(rendered_pil_image)
    ui.add(dbox, ndc_rect=(-0.75, -1.0, 0.75, -0.45), opacity=0.95)

    ui.draw()   # renders all queued panels
    ui.clear()  # call each frame after draw
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from OpenGL import GL

from ..engine.shader import Shader
from ..engine.buffer import Buffer, VertexArray
from ..engine.texture import Texture


_SHADERS_DIR = Path(__file__).parent.parent / "engine" / "shaders"

_STRIDE_QUAD = 4 * 4   # 4 floats (pos2 + uv2) × 4 bytes


@dataclass
class UIPanel:
    texture: Texture
    ndc_rect: tuple[float, float, float, float]   # (x0, y0, x1, y1) in NDC
    opacity: float = 1.0


class UIRenderer:
    """
    Immediate-mode UI overlay renderer.

    Call add() to queue panels, draw() to render, clear() to reset.
    """

    def __init__(self) -> None:
        self._shader = Shader(
            (_SHADERS_DIR / "ui.vert").read_text(encoding="utf-8"),
            (_SHADERS_DIR / "ui.frag").read_text(encoding="utf-8"),
        )
        self._vbo = Buffer(np.zeros(16, dtype=np.float32), GL.GL_STREAM_DRAW)
        self._ebo = Buffer(
            np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32),
            GL.GL_STATIC_DRAW,
            target=GL.GL_ELEMENT_ARRAY_BUFFER,
        )
        self._vao = VertexArray()
        self._setup_vao()
        self._queue: list[UIPanel] = []

    # ── Queue management ──────────────────────────────────────────────────────

    def add(
        self,
        texture:  Texture,
        ndc_rect: tuple[float, float, float, float],
        opacity:  float = 1.0,
    ) -> None:
        self._queue.append(UIPanel(texture, ndc_rect, opacity))

    def clear(self) -> None:
        self._queue.clear()

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self) -> None:
        if not self._queue:
            return

        # UI always draws on top — disable depth test, enable alpha blend
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

        self._shader.use()
        self._shader["u_ui_tex"] = 0

        for panel in self._queue:
            self._upload_quad(panel.ndc_rect)
            panel.texture.bind(unit=0)
            self._shader["u_opacity"] = panel.opacity
            self._vao.bind()
            GL.glDrawElements(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT, None)
            self._vao.unbind()
            panel.texture.unbind(unit=0)

        GL.glEnable(GL.GL_DEPTH_TEST)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def delete(self) -> None:
        self._shader.delete()
        self._vbo.delete()
        self._ebo.delete()
        self._vao.delete()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _setup_vao(self) -> None:
        self._vao.bind()
        self._vbo.bind()
        self._ebo.bind()
        s = _STRIDE_QUAD
        self._vao.attrib(0, size=2, stride=s, offset=0)   # a_pos  (NDC)
        self._vao.attrib(1, size=2, stride=s, offset=8)   # a_uv
        self._vao.unbind()
        self._vbo.unbind()

    def _upload_quad(self, rect: tuple[float, float, float, float]) -> None:
        x0, y0, x1, y1 = rect
        # pos(2) + uv(2) per vertex, CCW winding
        verts = np.array([
            x0, y0,  0.0, 1.0,
            x1, y0,  1.0, 1.0,
            x1, y1,  1.0, 0.0,
            x0, y1,  0.0, 0.0,
        ], dtype=np.float32)
        self._vbo.bind()
        GL.glBufferSubData(GL.GL_ARRAY_BUFFER, 0, verts.nbytes, verts)
        self._vbo.unbind()