"""
Camera
======
Octopath HD-2D style perspective camera.

Characteristics
---------------
  - Fixed pitch (~35° down from horizontal) — never rotates on yaw axis
  - Tight FOV (~35° vertical) — slightly flattens perceived depth
  - Smooth player-follow via exponential lerp (configurable speed)
  - Z-up world convention: X = east, Y = up, Z = south

Coordinate system
-----------------
  Tile grid: (col, row) → world (col * SCALE, 0, row * SCALE)
  SCALE = 1.0 by default — one world unit per tile

Usage
-----
    cam = Camera(aspect=width/height)
    cam.target = glm.vec3(player_x, 0, player_z)   # set each frame

    # In render loop:
    cam.update(dt)
    shader["u_view"] = cam.view
    shader["u_proj"] = cam.proj
    shader["u_cam_pos"] = cam.position
"""

from __future__ import annotations

import math
import glm


class Camera:
    """
    Octopath-style fixed-pitch perspective camera.

    Parameters
    ----------
    aspect:      Viewport width / height ratio.
    fov_deg:     Vertical field of view in degrees.  Default 35 (tight/Octopath).
    pitch_deg:   Downward tilt from horizontal in degrees.  Default 35.
    distance:    Camera-to-target distance in world units.  Default 18.
    follow_speed:Exponential lerp coefficient for camera follow.  Default 8.0.
    near / far:  Clip planes.
    """

    def __init__(
        self,
        aspect:       float = 16 / 9,
        fov_deg:      float = 35.0,
        pitch_deg:    float = 35.0,
        distance:     float = 18.0,
        follow_speed: float = 8.0,
        near:         float = 0.1,
        far:          float = 500.0,
    ) -> None:
        self._aspect       = aspect
        self._fov          = glm.radians(fov_deg)
        self._pitch        = glm.radians(pitch_deg)
        self._distance     = distance
        self._follow_speed = follow_speed
        self._near         = near
        self._far          = far

        # Current camera position (smoothed)
        self._pos    = glm.vec3(0.0, distance * math.sin(self._pitch),
                                     distance * math.cos(self._pitch))
        # Look-at target (set externally each frame)
        self.target  = glm.vec3(0.0, 0.0, 0.0)

        self._view   = glm.mat4(1.0)
        self._proj   = glm.perspective(self._fov, aspect, near, far)
        self._dirty  = True

    # ── Per-frame update ──────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        """Smooth-follow target and recompute matrices."""
        desired_pos = self.target + glm.vec3(
            0.0,
            self._distance * math.sin(self._pitch),
            self._distance * math.cos(self._pitch),
        )
        # Exponential lerp — framerate-independent
        t = 1.0 - math.exp(-self._follow_speed * dt)
        self._pos = glm.mix(self._pos, desired_pos, t)

        self._view = glm.lookAt(self._pos, self.target, glm.vec3(0.0, 1.0, 0.0))
        self._dirty = False

    def resize(self, aspect: float) -> None:
        """Call when the window resizes."""
        self._aspect = aspect
        self._proj   = glm.perspective(self._fov, aspect, self._near, self._far)

    # ── Matrix accessors ──────────────────────────────────────────────────────

    @property
    def view(self) -> glm.mat4:
        return self._view

    @property
    def proj(self) -> glm.mat4:
        return self._proj

    @property
    def position(self) -> glm.vec3:
        return self._pos

    @property
    def view_proj(self) -> glm.mat4:
        return self._proj * self._view