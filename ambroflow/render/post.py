"""
PostProcessor
=============
DoF + color grade pipeline.

Pass order
----------
  1. DoF horizontal (FBO scene → fbo_h)
  2. DoF vertical   (fbo_h → fbo_v)
  3. Color grade    (fbo_v → screen / next FBO)

Usage
-----
    pp = PostProcessor(width, height, realm="lapidus")
    pp.resize(w, h)   # on window resize

    # After scene is in scene_fbo:
    pp.process(scene_fbo, time=elapsed)

    # Blit result to screen:
    pp.blit_to_screen()
"""

from __future__ import annotations

from pathlib import Path

from OpenGL import GL

from ..engine.shader import Shader
from ..engine.framebuffer import Framebuffer
from ..engine.buffer import VertexArray


_SHADERS_DIR = Path(__file__).parent.parent / "engine" / "shaders"

_FULLSCREEN_VERT = (_SHADERS_DIR / "fullscreen.vert").read_text(encoding="utf-8")

_PASSTHROUGH_FRAG = """
#version 410 core
in vec2 v_uv;
uniform sampler2D u_color;
layout(location = 0) out vec4 frag_color;
void main() { frag_color = texture(u_color, v_uv); }
"""


def _load_grade_shader(realm: str) -> Shader:
    frag_path = _SHADERS_DIR / f"post_grade_{realm}.frag"
    if not frag_path.exists():
        frag_path = _SHADERS_DIR / "post_grade_lapidus.frag"
    return Shader(
        _FULLSCREEN_VERT,
        frag_path.read_text(encoding="utf-8"),
    )


class PostProcessor:
    """
    Two-pass DoF + color grade.

    Parameters
    ----------
    width, height : Initial viewport size.
    realm         : Shader variant ("lapidus", "mercurie", "sulphera").
    focus_dist    : World-space focus plane depth.
    focus_range   : Half-width of sharp band.
    max_blur      : Maximum CoC pixel radius.
    near / far    : Camera clip planes (for depth linearisation).
    """

    def __init__(
        self,
        width:       int,
        height:      int,
        realm:       str   = "lapidus",
        focus_dist:  float = 14.0,
        focus_range: float = 4.0,
        max_blur:    float = 12.0,
        near:        float = 0.1,
        far:         float = 500.0,
    ) -> None:
        self._width       = width
        self._height      = height
        self._focus_dist  = focus_dist
        self._focus_range = focus_range
        self._max_blur    = max_blur
        self._near        = near
        self._far         = far

        dof_frag = (_SHADERS_DIR / "post_dof.frag").read_text(encoding="utf-8")

        self._sh_dof_h  = Shader(_FULLSCREEN_VERT, dof_frag)
        self._sh_dof_v  = Shader(_FULLSCREEN_VERT, dof_frag)
        self._sh_grade  = _load_grade_shader(realm)
        self._sh_out    = Shader(_FULLSCREEN_VERT, _PASSTHROUGH_FRAG)

        self._fbo_h     = Framebuffer(width, height)
        self._fbo_v     = Framebuffer(width, height)
        self._fbo_out   = Framebuffer(width, height)

        self._empty_vao = VertexArray()

    # ── Resize ────────────────────────────────────────────────────────────────

    def resize(self, width: int, height: int) -> None:
        self._width  = width
        self._height = height
        self._fbo_h.resize(width, height)
        self._fbo_v.resize(width, height)
        self._fbo_out.resize(width, height)

    # ── Process ───────────────────────────────────────────────────────────────

    def process(self, scene_fbo: Framebuffer, time: float = 0.0) -> None:
        """Run full post pipeline.  scene_fbo must already be unbound."""
        GL.glDisable(GL.GL_DEPTH_TEST)   # fullscreen passes don't need depth
        w, h = float(self._width), float(self._height)
        res  = (w, h)

        # ── Pass 1: DoF horizontal ──────────────────────────────────────
        self._fbo_h.bind()
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        self._sh_dof_h.use()
        self._sh_dof_h["u_color"]       = 0
        self._sh_dof_h["u_depth"]       = 1
        self._sh_dof_h["u_resolution"]  = res
        self._sh_dof_h["u_direction"]   = (1.0, 0.0)
        self._sh_dof_h["u_near"]        = self._near
        self._sh_dof_h["u_far"]         = self._far
        self._sh_dof_h["u_focus_dist"]  = self._focus_dist
        self._sh_dof_h["u_focus_range"] = self._focus_range
        self._sh_dof_h["u_max_blur"]    = self._max_blur
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, scene_fbo.color_texture)
        GL.glActiveTexture(GL.GL_TEXTURE1)
        self._bind_depth(scene_fbo.depth_texture)
        self._fullscreen_draw()
        self._fbo_h.unbind()

        # ── Pass 2: DoF vertical ────────────────────────────────────────
        self._fbo_v.bind()
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        self._sh_dof_v.use()
        self._sh_dof_v["u_color"]       = 0
        self._sh_dof_v["u_depth"]       = 1
        self._sh_dof_v["u_resolution"]  = res
        self._sh_dof_v["u_direction"]   = (0.0, 1.0)
        self._sh_dof_v["u_near"]        = self._near
        self._sh_dof_v["u_far"]         = self._far
        self._sh_dof_v["u_focus_dist"]  = self._focus_dist
        self._sh_dof_v["u_focus_range"] = self._focus_range
        self._sh_dof_v["u_max_blur"]    = self._max_blur
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._fbo_h.color_texture)
        GL.glActiveTexture(GL.GL_TEXTURE1)
        self._bind_depth(scene_fbo.depth_texture)
        self._fullscreen_draw()
        self._fbo_v.unbind()

        # ── Pass 3: Color grade ─────────────────────────────────────────
        self._fbo_out.bind()
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        self._sh_grade.use()
        self._sh_grade["u_color"]             = 0
        self._sh_grade["u_time"]              = time
        self._sh_grade["u_vignette_strength"] = 0.45
        self._sh_grade["u_saturation"]        = 0.88
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._fbo_v.color_texture)
        self._fullscreen_draw()
        self._fbo_out.unbind()

    def blit_to_screen(self) -> None:
        """Draw grade output to default FBO 0 (screen) via fullscreen pass.

        Using a draw rather than glBlitFramebuffer avoids format-compatibility
        issues when blitting RGBA16F to an RGBA8 default framebuffer.
        """
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glViewport(0, 0, self._width, self._height)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        self._sh_out.use()
        self._sh_out["u_color"] = 0
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._fbo_out.color_texture)
        self._fullscreen_draw()

    @property
    def output_fbo(self) -> Framebuffer:
        return self._fbo_out

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def delete(self) -> None:
        self._sh_dof_h.delete()
        self._sh_dof_v.delete()
        self._sh_grade.delete()
        self._sh_out.delete()
        self._fbo_h.delete()
        self._fbo_v.delete()
        self._fbo_out.delete()
        self._empty_vao.delete()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fullscreen_draw(self) -> None:
        self._empty_vao.bind()
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        self._empty_vao.unbind()

    @staticmethod
    def _bind_depth(depth_tex_id: int) -> None:
        """Bind a depth attachment texture for shader sampling.

        Depth textures need GL_TEXTURE_COMPARE_MODE = GL_NONE to be read
        as raw floats (sampler2D) rather than comparison samplers.
        """
        GL.glBindTexture(GL.GL_TEXTURE_2D, depth_tex_id)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_COMPARE_MODE,
                           GL.GL_NONE)