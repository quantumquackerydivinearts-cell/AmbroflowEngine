"""
Ambroflow Engine — GL Core
==========================
OpenGL 4.1 rendering engine built on PyOpenGL + glfw + PyGLM.

Replaces the pygame prototype renderer.

Public surface
--------------
  Window      — glfw window, event loop, input normalization
  Shader      — GLSL shader program compilation and uniform binding
  Buffer      — VBO / VAO management
  Texture     — PIL → GL texture pipeline
  Camera      — Octopath-style perspective camera, player-follow
  Framebuffer — FBO for post-processing passes
"""

from .window  import Window
from .shader  import Shader
from .buffer  import Buffer, VertexArray
from .texture import Texture
from .camera  import Camera
from .framebuffer import Framebuffer

__all__ = [
    "Window",
    "Shader",
    "Buffer",
    "VertexArray",
    "Texture",
    "Camera",
    "Framebuffer",
]