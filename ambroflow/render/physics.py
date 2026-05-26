"""
ambroflow/render/physics.py
===========================
PhysicsRenderer — live physics body visualiser.

Draws each active (non-static) body in a PhysicsWorld as a camera-facing
glowing disc.  Colour encodes the element or compound involved; radius and
pulse rate encode kinetic energy.

Usage in a GL render loop
-------------------------
    from ambroflow.render.physics import PhysicsRenderer
    from ambroflow.physics.backend import get_backend

    world = get_backend()
    phys_r = PhysicsRenderer.for_treatment(element_forces=(ADDR_ZOT, ADDR_SHAK))

    # each frame during alchemy animation:
    phys_r.update(world)
    phys_r.draw(camera, time=elapsed)

    # when the treatment is done:
    phys_r.clear()

Element / compound colour palette
----------------------------------
  SHAK (104) Fire    — hot orange     (1.00, 0.38, 0.08)
  PUF  (105) Air     — pale sky       (0.78, 0.92, 1.00)
  MEL  (106) Water   — deep blue      (0.18, 0.52, 1.00)
  ZOT  (107) Earth   — forest green   (0.42, 0.68, 0.18)
  WU   ( 45) Process — lavender       (0.88, 0.72, 1.00)
  Compounds 108–123 blend between their two reactant colours.
"""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np
from OpenGL import GL

from ..engine.shader import Shader
from ..engine.buffer import Buffer, VertexArray
from ..engine.camera import Camera

if TYPE_CHECKING:
    from ..physics.world import PhysicsWorld


_SHADERS_DIR = Path(__file__).parent.parent / "engine" / "shaders"


# ── Element / compound colour table ───────────────────────────────────────────

_T = tuple[float, float, float]

_ELEMENT_COLORS: dict[int, _T] = {
     45: (0.88, 0.72, 1.00),   # WU  — Process: lavender
    104: (1.00, 0.38, 0.08),   # SHAK — Fire: hot orange
    105: (0.78, 0.92, 1.00),   # PUF  — Air: pale sky
    106: (0.18, 0.52, 1.00),   # MEL  — Water: deep blue
    107: (0.42, 0.68, 0.18),   # ZOT  — Earth: forest green
}

# Compounds 108–123 — blended + shifted to suggest the reaction character
_COMPOUND_COLORS: dict[int, _T] = {
    108: (1.00, 0.18, 0.00),   # Shak×Shak = Combustion  — pure white-hot red
    109: (1.00, 0.55, 0.90),   # Shak×Puf  = Plasma      — electric pink
    110: (0.62, 0.42, 0.95),   # Shak×Mel  = Alkahest    — dissolving violet
    111: (0.92, 0.22, 0.08),   # Shak×Zot  = Magma       — deep lava
    112: (0.95, 0.98, 0.45),   # Puf×Shak  = Lightning   — sharp yellow
    113: (0.85, 0.96, 1.00),   # Puf×Puf   = Resonance   — pure white-air
    114: (0.70, 0.88, 0.95),   # Puf×Mel   = Vapor       — misty cyan
    115: (0.78, 0.72, 0.52),   # Puf×Zot   = Dust        — warm ochre
    116: (0.88, 0.92, 0.98),   # Mel×Shak  = Steam       — white-grey steam
    117: (0.58, 0.80, 0.92),   # Mel×Puf   = Mist        — diffuse haze
    118: (0.15, 0.38, 0.88),   # Mel×Mel   = Brine       — deep ocean
    119: (0.42, 0.62, 0.72),   # Mel×Zot   = Erosion     — slate grey-blue
    120: (0.52, 1.00, 0.28),   # Zot×Shak  = Radiation   — sickly lime
    121: (0.60, 0.78, 0.32),   # Zot×Puf   = Spore       — biological green
    122: (0.62, 0.82, 0.98),   # Zot×Mel   = Crystal     — ice blue
    123: (0.55, 0.54, 0.50),   # Zot×Zot   = Stone       — neutral grey
}

_FALLBACK_COLOR: _T = (0.80, 0.80, 0.80)


def body_color(addr: int) -> _T:
    """Return the RGB colour for an element or compound byte address."""
    if addr in _ELEMENT_COLORS:
        return _ELEMENT_COLORS[addr]
    if addr in _COMPOUND_COLORS:
        return _COMPOUND_COLORS[addr]
    return _FALLBACK_COLOR


def treatment_color(element_forces: tuple[int, ...]) -> _T:
    """
    Derive the display colour for a treatment from its element_forces.

    If two elements react to a compound, return the compound colour.
    If a single element, return its colour.  Otherwise blend.
    """
    if not element_forces:
        return _FALLBACK_COLOR
    if len(element_forces) >= 2:
        try:
            from ..physics.elements import react
            compound = react(element_forces[0], element_forces[1])
            if compound is not None and compound in _COMPOUND_COLORS:
                return _COMPOUND_COLORS[compound]
        except Exception:
            pass
        # Blend the two element colours
        c1 = _ELEMENT_COLORS.get(element_forces[0], _FALLBACK_COLOR)
        c2 = _ELEMENT_COLORS.get(element_forces[1], _FALLBACK_COLOR)
        return (
            (c1[0] + c2[0]) * 0.5,
            (c1[1] + c2[1]) * 0.5,
            (c1[2] + c2[2]) * 0.5,
        )
    return _ELEMENT_COLORS.get(element_forces[0], _FALLBACK_COLOR)


# ── Billboard quad geometry ────────────────────────────────────────────────────
# Per-vertex: corner(2) + uv(2) = 4 floats, 16 bytes

_QUAD_VERTS = np.array([
    # corner (x,y)   uv (u,v)
    -0.5, -0.5,      0.0, 0.0,
     0.5, -0.5,      1.0, 0.0,
     0.5,  0.5,      1.0, 1.0,
    -0.5,  0.5,      0.0, 1.0,
], dtype=np.float32)

_QUAD_INDICES = np.array([0, 1, 2,  0, 2, 3], dtype=np.uint32)

_STRIDE_QUAD = 4 * 4   # 4 floats × 4 bytes

# Per-instance: world_pos(3) + color(3) + ke_norm(1) + radius(1) = 8 floats, 32 bytes
_STRIDE_INST = 8 * 4


# ── PhysicsRenderer ───────────────────────────────────────────────────────────

class PhysicsRenderer:
    """
    Instanced billboard renderer for physics bodies.

    Parameters
    ----------
    shader:
        Compiled physics_body.vert + physics_body.frag shader.
    body_colors:
        Optional per-body-index colour override list.  Index = body ID in
        the PhysicsWorld.  Bodies with no entry in this list use
        _FALLBACK_COLOR.  Statics are always skipped.
    body_radius:
        Visual radius in world units for all bodies (default 0.35).
    fog_near / fog_far:
        Should match the world renderer's fog range so bodies fade with the
        tile geometry.
    """

    def __init__(
        self,
        shader:       Shader,
        body_colors:  Optional[list[_T]] = None,
        body_radius:  float = 0.35,
        fog_near:     float = 18.0,
        fog_far:      float = 60.0,
    ) -> None:
        self._shader      = shader
        self._body_colors = body_colors or []
        self._body_radius = body_radius
        self._fog_near    = fog_near
        self._fog_far     = fog_far

        # Static billboard quad
        self._vbo_quad = Buffer(_QUAD_VERTS, GL.GL_STATIC_DRAW)
        self._ebo      = Buffer(_QUAD_INDICES, GL.GL_STATIC_DRAW,
                                target=GL.GL_ELEMENT_ARRAY_BUFFER)
        # Dynamic instance buffer — reallocated when body count changes
        self._vbo_inst:      Optional[Buffer] = None
        self._instance_count: int             = 0

        self._vao = VertexArray()
        self._setup_vao()

    # ── VAO wiring ────────────────────────────────────────────────────────────

    def _setup_vao(self) -> None:
        self._vao.bind()

        # Static quad vertex attributes
        self._vbo_quad.bind()
        self._ebo.bind()
        s = _STRIDE_QUAD
        self._vao.attrib(0, size=2, stride=s, offset=0)    # a_corner
        self._vao.attrib(1, size=2, stride=s, offset=8)    # a_uv

        self._vao.unbind()
        self._vbo_quad.unbind()

    def _rewire_instance_attribs(self) -> None:
        """Re-bind instance attributes after uploading a new instance buffer."""
        self._vao.bind()
        self._vbo_inst.bind()
        s = _STRIDE_INST
        self._vao.attrib(2, size=3, stride=s, offset=0)    # i_world_pos
        self._vao.attrib(3, size=3, stride=s, offset=12)   # i_color
        self._vao.attrib(4, size=1, stride=s, offset=24)   # i_ke_norm
        self._vao.attrib(5, size=1, stride=s, offset=28)   # i_radius
        self._vao.attrib_divisor(2, 1)
        self._vao.attrib_divisor(3, 1)
        self._vao.attrib_divisor(4, 1)
        self._vao.attrib_divisor(5, 1)
        self._vao.unbind()
        self._vbo_inst.unbind()

    # ── Per-frame update ──────────────────────────────────────────────────────

    def update(self, world: "PhysicsWorld") -> None:
        """
        Read current body state from world and upload to the instance buffer.

        Call once per frame before draw().  Static bodies (floor, walls) are
        skipped automatically.
        """
        rows: list[float] = []

        for i in range(world.body_count):
            b = world.get_body(i)
            if b is None or not b.active or b.is_static:
                continue

            x, y, z   = world.pos(i)
            vx, vy, vz = world.vel_tuple(i)
            ke_norm   = min(1.0, (vx*vx + vy*vy + vz*vz) / 10.0)

            color = (
                self._body_colors[i]
                if i < len(self._body_colors)
                else _FALLBACK_COLOR
            )

            rows.extend([
                x, y + b.half_ext.y,   # lift to top of body AABB
                z,
                color[0], color[1], color[2],
                ke_norm,
                self._body_radius,
            ])

        self._instance_count = len(rows) // 8
        if self._instance_count == 0:
            return

        data = np.array(rows, dtype=np.float32)
        if self._vbo_inst is None:
            self._vbo_inst = Buffer(data, GL.GL_DYNAMIC_DRAW)
            self._rewire_instance_attribs()
        else:
            self._vbo_inst.upload(data, GL.GL_DYNAMIC_DRAW)

    def clear(self) -> None:
        """Remove all instances (call when the treatment animation ends)."""
        self._instance_count = 0

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, camera: Camera, time: float = 0.0) -> None:
        """Draw all active bodies.  Call after update() in the render loop."""
        if self._instance_count == 0:
            return

        self._shader.use()
        self._shader["u_view"]     = camera.view
        self._shader["u_proj"]     = camera.proj
        self._shader["u_time"]     = time
        self._shader["u_fog_near"] = self._fog_near
        self._shader["u_fog_far"]  = self._fog_far

        # Additive-ish blend: bodies glow over the world without muddying it
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glDepthMask(GL.GL_FALSE)   # bodies don't write depth — they float above

        self._vao.bind()
        GL.glDrawElementsInstanced(
            GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
            ctypes.c_void_p(0), self._instance_count,
        )
        self._vao.unbind()

        GL.glDepthMask(GL.GL_TRUE)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def delete(self) -> None:
        self._vbo_quad.delete()
        self._ebo.delete()
        if self._vbo_inst:
            self._vbo_inst.delete()
        self._vao.delete()

    # ── Factories ─────────────────────────────────────────────────────────────

    @classmethod
    def build_shader(cls) -> Shader:
        """Compile the physics body shader from the bundled GLSL sources."""
        return Shader(
            (_SHADERS_DIR / "physics_body.vert").read_text(encoding="utf-8"),
            (_SHADERS_DIR / "physics_body.frag").read_text(encoding="utf-8"),
        )

    @classmethod
    def for_treatment(
        cls,
        element_forces: tuple[int, ...],
        max_bodies:     int   = 16,
        body_radius:    float = 0.35,
        fog_near:       float = 18.0,
        fog_far:        float = 60.0,
    ) -> "PhysicsRenderer":
        """
        Create a PhysicsRenderer pre-coloured for a specific element treatment.

        All dynamic bodies receive the compound colour derived from
        element_forces (or the blended element colour if no compound forms).
        Static bodies (floor) are skipped automatically during update().
        """
        shader = cls.build_shader()
        color  = treatment_color(element_forces)
        # Body 0 is typically the static floor — give it the same colour anyway
        # (it will be skipped in update() since is_static=True)
        colors = [color] * max_bodies
        return cls(
            shader      = shader,
            body_colors = colors,
            body_radius = body_radius,
            fog_near    = fog_near,
            fog_far     = fog_far,
        )

    @classmethod
    def for_world(
        cls,
        body_colors:  Optional[list[_T]] = None,
        body_radius:  float = 0.30,
        fog_near:     float = 18.0,
        fog_far:      float = 60.0,
    ) -> "PhysicsRenderer":
        """
        Create a PhysicsRenderer for ambient world physics bodies.

        body_colors: one entry per body index.  Bodies beyond the list
        length render in neutral grey.
        """
        shader = cls.build_shader()
        return cls(
            shader      = shader,
            body_colors = body_colors or [],
            body_radius = body_radius,
            fog_near    = fog_near,
            fog_far     = fog_far,
        )
