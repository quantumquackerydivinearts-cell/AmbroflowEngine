"""
Buffer / VertexArray
====================
VBO and VAO abstractions over raw PyOpenGL calls.

Usage
-----
    # Interleaved position + UV buffer
    verts = np.array([...], dtype=np.float32)
    vbo   = Buffer(verts, GL.GL_STATIC_DRAW)
    vao   = VertexArray()
    vao.bind()
    vbo.bind()
    # attrib 0 = position (3 floats), attrib 1 = UV (2 floats)
    vao.attrib(0, size=3, stride=20, offset=0)
    vao.attrib(1, size=2, stride=20, offset=12)
    vao.unbind()

    # Later, in draw call:
    vao.bind()
    GL.glDrawArrays(GL.GL_TRIANGLES, 0, vertex_count)
    vao.unbind()
"""

from __future__ import annotations

import numpy as np
from OpenGL import GL


class Buffer:
    """OpenGL VBO (or EBO if target=GL_ELEMENT_ARRAY_BUFFER)."""

    def __init__(
        self,
        data:   np.ndarray,
        usage:  int = GL.GL_STATIC_DRAW,
        target: int = GL.GL_ARRAY_BUFFER,
    ) -> None:
        self._id     = GL.glGenBuffers(1)
        self._target = target
        self.upload(data, usage)

    def upload(self, data: np.ndarray, usage: int = GL.GL_STATIC_DRAW) -> None:
        self.bind()
        GL.glBufferData(self._target, data.nbytes, data, usage)
        self.unbind()

    def bind(self) -> None:
        GL.glBindBuffer(self._target, self._id)

    def unbind(self) -> None:
        GL.glBindBuffer(self._target, 0)

    def delete(self) -> None:
        GL.glDeleteBuffers(1, [self._id])


class VertexArray:
    """OpenGL VAO — records vertex attribute layout."""

    def __init__(self) -> None:
        self._id = GL.glGenVertexArrays(1)

    def bind(self) -> None:
        GL.glBindVertexArray(self._id)

    def unbind(self) -> None:
        GL.glBindVertexArray(0)

    def attrib(
        self,
        index:      int,
        size:       int,          # components (1–4)
        stride:     int,          # bytes between consecutive vertices
        offset:     int,          # byte offset within vertex
        gl_type:    int = GL.GL_FLOAT,
        normalized: bool = False,
    ) -> None:
        """Define a vertex attribute pointer (VAO must be bound first)."""
        GL.glEnableVertexAttribArray(index)
        GL.glVertexAttribPointer(
            index, size, gl_type,
            GL.GL_TRUE if normalized else GL.GL_FALSE,
            stride,
            GL.ctypes.c_void_p(offset),
        )

    def attrib_divisor(self, index: int, divisor: int) -> None:
        """Set instance divisor (for instanced rendering)."""
        GL.glVertexAttribDivisor(index, divisor)

    def delete(self) -> None:
        GL.glDeleteVertexArrays(1, [self._id])