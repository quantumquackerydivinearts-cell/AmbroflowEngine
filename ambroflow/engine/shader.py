"""
Shader
======
GLSL shader program compilation and uniform binding.

Usage
-----
    shader = Shader(vert_src, frag_src)
    shader.use()
    shader["u_mvp"] = mvp_matrix          # glm.mat4
    shader["u_color"] = (1.0, 0.5, 0.2)  # tuple → vec3
    shader["u_time"] = 1.23               # float
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import glm
import numpy as np
from OpenGL import GL


_GLUniform = Union[int, float, tuple, glm.mat4, glm.mat3, glm.vec4, glm.vec3, glm.vec2]


class Shader:
    """Compiled GLSL program with a dict-style uniform interface."""

    def __init__(self, vert_src: str, frag_src: str) -> None:
        self._id = _link(
            _compile(GL.GL_VERTEX_SHADER,   vert_src),
            _compile(GL.GL_FRAGMENT_SHADER, frag_src),
        )
        self._locs: dict[str, int] = {}

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_files(cls, vert_path: Union[str, Path], frag_path: Union[str, Path]) -> "Shader":
        return cls(
            Path(vert_path).read_text(encoding="utf-8"),
            Path(frag_path).read_text(encoding="utf-8"),
        )

    # ── Use ───────────────────────────────────────────────────────────────────

    def use(self) -> None:
        GL.glUseProgram(self._id)

    # ── Uniforms ──────────────────────────────────────────────────────────────

    def __setitem__(self, name: str, value: _GLUniform) -> None:
        loc = self._loc(name)
        if loc == -1:
            return   # uniform optimised away — silently skip

        if isinstance(value, glm.mat4):
            GL.glUniformMatrix4fv(loc, 1, GL.GL_TRUE,
                                  np.array(value, dtype=np.float32).flatten())
        elif isinstance(value, glm.mat3):
            GL.glUniformMatrix3fv(loc, 1, GL.GL_TRUE,
                                  np.array(value, dtype=np.float32).flatten())
        elif isinstance(value, (glm.vec4, glm.vec3, glm.vec2)):
            data = list(value)
            {2: GL.glUniform2f, 3: GL.glUniform3f, 4: GL.glUniform4f}[len(data)](loc, *data)
        elif isinstance(value, (list, tuple)):
            n = len(value)
            {1: GL.glUniform1f, 2: GL.glUniform2f,
             3: GL.glUniform3f, 4: GL.glUniform4f}[n](loc, *value)
        elif isinstance(value, float):
            GL.glUniform1f(loc, value)
        elif isinstance(value, int):
            GL.glUniform1i(loc, value)
        elif isinstance(value, np.ndarray) and value.shape == (4, 4):
            GL.glUniformMatrix4fv(loc, 1, GL.GL_FALSE, value.flatten().astype(np.float32))

    def _loc(self, name: str) -> int:
        if name not in self._locs:
            self._locs[name] = GL.glGetUniformLocation(self._id, name)
        return self._locs[name]

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def delete(self) -> None:
        GL.glDeleteProgram(self._id)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _compile(shader_type: int, src: str) -> int:
    sid = GL.glCreateShader(shader_type)
    GL.glShaderSource(sid, src)
    GL.glCompileShader(sid)
    if not GL.glGetShaderiv(sid, GL.GL_COMPILE_STATUS):
        log = GL.glGetShaderInfoLog(sid).decode()
        GL.glDeleteShader(sid)
        label = "vertex" if shader_type == GL.GL_VERTEX_SHADER else "fragment"
        raise RuntimeError(f"GLSL {label} compile error:\n{log}")
    return sid


def _link(vert_id: int, frag_id: int) -> int:
    pid = GL.glCreateProgram()
    GL.glAttachShader(pid, vert_id)
    GL.glAttachShader(pid, frag_id)
    GL.glLinkProgram(pid)
    GL.glDeleteShader(vert_id)
    GL.glDeleteShader(frag_id)
    if not GL.glGetProgramiv(pid, GL.GL_LINK_STATUS):
        log = GL.glGetProgramInfoLog(pid).decode()
        GL.glDeleteProgram(pid)
        raise RuntimeError(f"GLSL link error:\n{log}")
    return pid