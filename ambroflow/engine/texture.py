"""
Texture
=======
PIL → OpenGL texture pipeline.

Handles both static textures (portraits, atlases) and dynamic textures
(PIL-rendered dialogue frames, dream sequences updated each frame).

Usage
-----
    # From a PIL Image
    tex = Texture.from_pil(img)
    tex.bind(unit=0)           # binds to GL_TEXTURE0

    # From raw bytes (e.g. to_png() output from screens.py)
    tex = Texture.from_bytes(png_bytes)

    # Dynamic: update every frame with a new PIL image
    tex = Texture.empty(width, height)
    tex.update_pil(new_img)
"""

from __future__ import annotations

import io
from typing import Optional

import numpy as np
from OpenGL import GL

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False


class Texture:
    """2D OpenGL texture."""

    def __init__(self, width: int, height: int, gl_id: int) -> None:
        self._id     = gl_id
        self._width  = width
        self._height = height

    # ── Factories ─────────────────────────────────────────────────────────────

    @classmethod
    def from_pil(cls, img: "Image.Image") -> "Texture":
        img  = img.convert("RGBA")
        data = np.asarray(img, dtype=np.uint8)
        return cls._upload(img.width, img.height, data)

    @classmethod
    def from_bytes(cls, data: bytes) -> "Texture":
        if not _PIL:
            raise RuntimeError("PIL is required for Texture.from_bytes")
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        return cls.from_pil(img)

    @classmethod
    def empty(cls, width: int, height: int) -> "Texture":
        """Create an empty RGBA texture for dynamic updates."""
        data = np.zeros((height, width, 4), dtype=np.uint8)
        return cls._upload(width, height, data)

    # ── Update ────────────────────────────────────────────────────────────────

    def update_pil(self, img: "Image.Image") -> None:
        """Upload a new PIL image into this texture (same dimensions expected)."""
        img  = img.convert("RGBA")
        data = np.asarray(img, dtype=np.uint8)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._id)
        GL.glTexSubImage2D(
            GL.GL_TEXTURE_2D, 0, 0, 0,
            img.width, img.height,
            GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, data,
        )
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    def update_bytes(self, data: bytes) -> None:
        if not _PIL:
            return
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        self.update_pil(img)

    # ── Bind ──────────────────────────────────────────────────────────────────

    def bind(self, unit: int = 0) -> None:
        GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._id)

    def unbind(self, unit: int = 0) -> None:
        GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def gl_id(self) -> int:
        return self._id

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def delete(self) -> None:
        GL.glDeleteTextures(1, [self._id])

    # ── Internal ──────────────────────────────────────────────────────────────

    @classmethod
    def _upload(cls, width: int, height: int, data: np.ndarray) -> "Texture":
        gl_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, gl_id)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D, 0, GL.GL_RGBA,
            width, height, 0,
            GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, data,
        )
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        return cls(width, height, gl_id)