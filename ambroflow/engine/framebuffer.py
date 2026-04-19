"""
Framebuffer
===========
FBO with colour + depth attachments for post-processing passes.

Pattern
-------
  1. Render world + sprites into fbo (not the screen).
  2. DoF pass reads fbo.color_texture + fbo.depth_texture.
  3. Color grade pass reads DoF output.
  4. Final pass blits to screen (default FBO 0).

Usage
-----
    fbo = Framebuffer(1280, 800)

    fbo.bind()
    # ... render scene into fbo ...
    fbo.unbind()

    # Now fbo.color_texture and fbo.depth_texture are ready for post shaders.
"""

from __future__ import annotations

from OpenGL import GL


class Framebuffer:
    """RGBA colour + depth FBO for off-screen rendering."""

    def __init__(self, width: int, height: int) -> None:
        self._width  = width
        self._height = height
        self._fbo    = 0
        self._color  = 0
        self._depth  = 0
        self._build(width, height)

    # ── Resize ────────────────────────────────────────────────────────────────

    def resize(self, width: int, height: int) -> None:
        self._delete_attachments()
        self._build(width, height)

    # ── Bind / unbind ─────────────────────────────────────────────────────────

    def bind(self) -> None:
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._fbo)
        GL.glViewport(0, 0, self._width, self._height)

    def unbind(self) -> None:
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)

    # ── Texture handles ───────────────────────────────────────────────────────

    @property
    def color_texture(self) -> int:
        """GL texture ID for the colour attachment."""
        return self._color

    @property
    def depth_texture(self) -> int:
        """GL texture ID for the depth attachment."""
        return self._depth

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def delete(self) -> None:
        self._delete_attachments()
        GL.glDeleteFramebuffers(1, [self._fbo])

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build(self, width: int, height: int) -> None:
        self._width  = width
        self._height = height

        self._fbo = GL.glGenFramebuffers(1)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._fbo)

        # Colour attachment
        self._color = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._color)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA16F,
                        width, height, 0, GL.GL_RGBA, GL.GL_FLOAT, None)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0,
                                  GL.GL_TEXTURE_2D, self._color, 0)

        # Depth attachment
        self._depth = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._depth)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_DEPTH_COMPONENT24,
                        width, height, 0, GL.GL_DEPTH_COMPONENT, GL.GL_FLOAT, None)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_DEPTH_ATTACHMENT,
                                  GL.GL_TEXTURE_2D, self._depth, 0)

        status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)

        if status != GL.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"Framebuffer incomplete: status={hex(status)}")

    def _delete_attachments(self) -> None:
        if self._color:
            GL.glDeleteTextures(1, [self._color])
            self._color = 0
        if self._depth:
            GL.glDeleteTextures(1, [self._depth])
            self._depth = 0