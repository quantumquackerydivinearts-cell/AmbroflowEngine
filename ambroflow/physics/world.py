"""
world.py — Python mirror of the Kobra physics engine.

Exact API match to the Rust PhysicsWorld in kobra-core/src/physics.rs.
Same Verlet integration, same AABB collision, same five-element force dispatch.
Same constants, same defaults, same behaviour.

A Kobra physics script (.kobra) runs identically whether executing in the
DjinnOS kernel (Rust) or through Ambroflow (this module).  The script is
the asset; the engine is the runtime.

When running on DjinnOS natively, backend.py will swap this implementation
for a thin ctypes shim calling into the live kernel physics world.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .elements import ADDR_SHAK, ADDR_PUF, ADDR_MEL, ADDR_ZOT, ADDR_WU

MAX_BODIES = 16


# ── Vec3 ──────────────────────────────────────────────────────────────────────

@dataclass
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @classmethod
    def zero(cls) -> "Vec3":
        return cls(0.0, 0.0, 0.0)

    def add(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def sub(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def scale(self, s: float) -> "Vec3":
        return Vec3(self.x * s, self.y * s, self.z * s)

    def dot(self, o: "Vec3") -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def len_sq(self) -> float:
        return self.dot(self)

    def length(self) -> float:
        return math.sqrt(self.len_sq())

    def kinetic_energy(self, mass: float) -> float:
        """½mv² — kinetic energy of a body with this velocity vector."""
        return 0.5 * mass * self.len_sq()

    def __repr__(self) -> str:
        return f"({self.x:.2f},{self.y:.2f},{self.z:.2f})"


# ── AABB ──────────────────────────────────────────────────────────────────────

@dataclass
class Aabb:
    min: Vec3
    max: Vec3

    def overlaps(self, o: "Aabb") -> bool:
        return (
            self.min.x <= o.max.x and self.max.x >= o.min.x and
            self.min.y <= o.max.y and self.max.y >= o.min.y and
            self.min.z <= o.max.z and self.max.z >= o.min.z
        )

    def penetration(self, o: "Aabb") -> Vec3:
        return Vec3(
            max(0.0, min(self.max.x, o.max.x) - max(self.min.x, o.min.x)),
            max(0.0, min(self.max.y, o.max.y) - max(self.min.y, o.min.y)),
            max(0.0, min(self.max.z, o.max.z) - max(self.min.z, o.min.z)),
        )


# ── Body ──────────────────────────────────────────────────────────────────────

@dataclass
class Body:
    id:          int  = 0
    pos:         Vec3 = field(default_factory=Vec3.zero)
    prev_pos:    Vec3 = field(default_factory=Vec3.zero)
    acc:         Vec3 = field(default_factory=Vec3.zero)
    mass:        float = 1.0
    restitution: float = 0.5
    half_ext:    Vec3 = field(default_factory=lambda: Vec3(0.5, 0.5, 0.5))
    is_static:   bool = False
    active:      bool = False
    # Collision tracking (not in Rust version — Python extension for Bridge)
    collisions:  int  = 0

    def aabb(self) -> Aabb:
        return Aabb(
            min=self.pos.sub(self.half_ext),
            max=self.pos.add(self.half_ext),
        )

    def vel(self, dt: float) -> Vec3:
        """Velocity derived from Verlet positions."""
        if dt == 0.0:
            return Vec3.zero()
        return self.pos.sub(self.prev_pos).scale(1.0 / dt)

    def kinetic_energy(self, dt: float) -> float:
        return self.vel(dt).kinetic_energy(self.mass)

    def apply_acc(self, a: Vec3) -> None:
        if self.active and not self.is_static:
            self.acc = self.acc.add(a)


# ── PhysicsWorld ──────────────────────────────────────────────────────────────

class PhysicsWorld:
    """
    Python mirror of kobra-core PhysicsWorld.
    Identical API, identical integration scheme, identical defaults.
    """

    def __init__(self) -> None:
        self.bodies:         list[Body] = [Body() for _ in range(MAX_BODIES)]
        self.body_count:     int        = 0
        self.gravity:        Vec3       = Vec3(0.0, -9.8, 0.0)
        self.dt:             float      = 0.016
        self.time:           float      = 0.0
        self.linear_damping: float      = 0.02
        self.drag_coeff:     float      = 0.001
        self.steps:          int        = 0
        self._kael_seed:     int        = 0xDEAD_BEEF
        # Python-only: collision count and energy history for the Bridge
        self.total_collisions: int      = 0
        self._energy_history:  list[float] = []

    # ── Body management ───────────────────────────────────────────────────────

    def add_body(self, mass: float, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Optional[int]:
        if self.body_count >= MAX_BODIES:
            return None
        idx = self.body_count
        pos = Vec3(x, y, z)
        b = self.bodies[idx]
        b.id          = idx
        b.pos         = pos
        b.prev_pos    = Vec3(x, y, z)
        b.acc         = Vec3.zero()
        b.mass        = mass
        b.restitution = 0.5
        b.half_ext    = Vec3(0.5, 0.5, 0.5)
        b.is_static   = False
        b.active      = True
        b.collisions  = 0
        self.body_count += 1
        return idx

    def add_static(self, x: float, y: float, z: float,
                   hx: float = 50.0, hy: float = 0.5, hz: float = 50.0) -> Optional[int]:
        idx = self.add_body(0.0, x, y, z)
        if idx is None:
            return None
        self.bodies[idx].half_ext = Vec3(hx, hy, hz)
        self.bodies[idx].is_static = True
        return idx

    def reset(self) -> None:
        for b in self.bodies:
            b.active = False
        self.body_count     = 0
        self.time           = 0.0
        self.steps          = 0
        self.total_collisions = 0
        self._energy_history.clear()

    def get_body(self, idx: int) -> Optional[Body]:
        if 0 <= idx < self.body_count:
            return self.bodies[idx]
        return None

    def pos(self, idx: int) -> tuple[float, float, float]:
        b = self.get_body(idx)
        return (b.pos.x, b.pos.y, b.pos.z) if b else (0.0, 0.0, 0.0)

    def vel_tuple(self, idx: int) -> tuple[float, float, float]:
        b = self.get_body(idx)
        if b is None:
            return (0.0, 0.0, 0.0)
        v = b.vel(self.dt)
        return (v.x, v.y, v.z)

    # ── Element force dispatch (matches Kobra addresses) ─────────────────────

    def apply_zot(self, scale: float = 1.0) -> None:
        """Zot (107) Earth — gravity."""
        g = self.gravity.scale(scale)
        for i in range(self.body_count):
            self.bodies[i].apply_acc(g)

    def apply_mel(self, coeff: float | None = None) -> None:
        """Mel (106) Water — linear velocity damping via Verlet prev_pos."""
        c = 1.0 - min(1.0, max(0.0, coeff if coeff is not None else self.linear_damping))
        for i in range(self.body_count):
            b = self.bodies[i]
            if not b.active or b.is_static:
                continue
            disp = b.pos.sub(b.prev_pos).scale(c)
            b.prev_pos = b.pos.sub(disp)

    def apply_puf(self, coeff: float | None = None) -> None:
        """Puf (105) Air — quadratic drag."""
        c = coeff if coeff is not None else self.drag_coeff
        for i in range(self.body_count):
            b = self.bodies[i]
            if not b.active or b.is_static:
                continue
            v = b.vel(self.dt)
            v2 = v.len_sq()
            if v2 > 0.0001:
                b.apply_acc(v.scale(-c * v2))

    def apply_shak(self, body_id: int, fx: float, fy: float, fz: float) -> None:
        """Shak (104) Fire — apply impulse to a specific body."""
        b = self.get_body(body_id)
        if b is None or not b.active or b.is_static or b.mass == 0.0:
            return
        b.apply_acc(Vec3(fx / b.mass, fy / b.mass, fz / b.mass))

    def apply_kael(self, magnitude: float = 0.5) -> None:
        """Kael — Chaos — deterministic noise perturbation (LCG, same seed as Rust)."""
        for i in range(self.body_count):
            b = self.bodies[i]
            if not b.active or b.is_static:
                continue
            nx = self._kael_noise() * magnitude
            ny = self._kael_noise() * magnitude
            nz = self._kael_noise() * magnitude
            b.apply_acc(Vec3(nx, ny, nz))

    def _kael_noise(self) -> float:
        """LCG matching the Rust implementation exactly."""
        self._kael_seed = (self._kael_seed * 1_664_525 + 1_013_904_223) & 0xFFFF_FFFF
        return ((self._kael_seed >> 16) / 32767.5) - 1.0

    # ── Dispatch by byte address ──────────────────────────────────────────────

    def dispatch(self, addr: int, scale: float = 1.0, body_id: int = 0) -> None:
        """
        Dispatch a physics operation by Shygazun byte address.
        Mirrors the Kobra eval dispatch: same address → same operation.
        """
        if addr == ADDR_ZOT:
            self.apply_zot(scale)
        elif addr == ADDR_MEL:
            self.apply_mel(scale)
        elif addr == ADDR_PUF:
            self.apply_puf(scale)
        elif addr == ADDR_SHAK:
            self.apply_shak(body_id, 0.0, scale * 10.0, 0.0)
        elif addr == ADDR_WU:
            self.wu_tick()

    # ── Integration (Wu — tick) ───────────────────────────────────────────────

    def wu_tick(self) -> None:
        """Full step: Zot → Mel → Puf → Verlet → collisions."""
        self.apply_zot(1.0)
        self.apply_mel(self.linear_damping)
        self.apply_puf(self.drag_coeff)
        self._verlet_integrate()
        self._resolve_collisions()
        self.time  += self.dt
        self.steps += 1
        # Track energy for Bridge
        e = self.total_kinetic_energy()
        if len(self._energy_history) >= 256:
            self._energy_history.pop(0)
        self._energy_history.append(e)

    def wu_tick_flags(self, zot: bool = True, mel: bool = True, puf: bool = True) -> None:
        """Tick with explicit force selection."""
        if zot: self.apply_zot(1.0)
        if mel: self.apply_mel(self.linear_damping)
        if puf: self.apply_puf(self.drag_coeff)
        self._verlet_integrate()
        self._resolve_collisions()
        self.time  += self.dt
        self.steps += 1
        # Track energy (same as wu_tick) so is_settled() works
        e = self.total_kinetic_energy()
        if len(self._energy_history) >= 256:
            self._energy_history.pop(0)
        self._energy_history.append(e)

    def _verlet_integrate(self) -> None:
        dt2 = self.dt * self.dt
        for i in range(self.body_count):
            b = self.bodies[i]
            if not b.active or b.is_static:
                continue
            new_pos = Vec3(
                2.0 * b.pos.x - b.prev_pos.x + b.acc.x * dt2,
                2.0 * b.pos.y - b.prev_pos.y + b.acc.y * dt2,
                2.0 * b.pos.z - b.prev_pos.z + b.acc.z * dt2,
            )
            b.prev_pos = b.pos
            b.pos      = new_pos
            b.acc      = Vec3.zero()

    def _resolve_collisions(self) -> None:
        for i in range(self.body_count):
            for j in range(i + 1, self.body_count):
                bi = self.bodies[i]
                bj = self.bodies[j]
                if not bi.active or not bj.active:
                    continue
                if bi.is_static and bj.is_static:
                    continue
                ai = bi.aabb()
                aj = bj.aabb()
                if not ai.overlaps(aj):
                    continue
                pen = ai.penetration(aj)
                # Minimum penetration axis
                if pen.x <= pen.y and pen.x <= pen.z:
                    axis, depth = 0, pen.x
                elif pen.y <= pen.z:
                    axis, depth = 1, pen.y
                else:
                    axis, depth = 2, pen.z
                r           = (bi.restitution + bj.restitution) * 0.5
                correction  = depth * 0.5
                self._separate(bi, bj, axis, correction, r)
                bi.collisions += 1
                bj.collisions += 1
                self.total_collisions += 1

    def _separate(self, bi: Body, bj: Body, axis: int, correction: float, r: float) -> None:
        attrs = ("x", "y", "z")
        ax = attrs[axis]
        pi = getattr(bi.pos, ax) < getattr(bj.pos, ax)
        for b, sign in ((bi, -1.0 if pi else 1.0), (bj, 1.0 if pi else -1.0)):
            if b.is_static:
                continue
            # Positional correction
            setattr(b.pos, ax, getattr(b.pos, ax) + sign * correction)
            # Velocity reflection via Verlet prev_pos
            disp = getattr(b.pos, ax) - getattr(b.prev_pos, ax)
            setattr(b.prev_pos, ax, getattr(b.pos, ax) - disp * r)

    # ── Energy and state summary (Python extension for Bridge) ───────────────

    def total_kinetic_energy(self) -> float:
        return sum(
            self.bodies[i].kinetic_energy(self.dt)
            for i in range(self.body_count)
            if self.bodies[i].active and not self.bodies[i].is_static
        )

    def energy_delta(self) -> float:
        """Energy change over the last two steps (positive = gaining energy)."""
        if len(self._energy_history) < 2:
            return 0.0
        return self._energy_history[-1] - self._energy_history[-2]

    def is_settled(self, threshold: float = 0.01) -> bool:
        """True when kinetic energy has stabilised (physics at rest)."""
        if len(self._energy_history) < 16:
            return False
        recent = self._energy_history[-16:]
        return max(recent) - min(recent) < threshold

    def fingerprint(self) -> dict:
        """
        Compact state summary for the BreathOfKo Bridge.
        Encodes the physical state without exposing raw positions.
        """
        return {
            "steps":             self.steps,
            "time":              round(self.time, 4),
            "total_ke":          round(self.total_kinetic_energy(), 6),
            "total_collisions":  self.total_collisions,
            "body_count":        self.body_count,
            "settled":           self.is_settled(),
            "energy_trend":      round(self.energy_delta(), 6),
        }

    def status(self) -> str:
        lines = [f"PhysicsWorld: {self.body_count} bodies  {self.steps} steps  t={self.time:.3f}s"]
        for i in range(self.body_count):
            b = self.bodies[i]
            if not b.active:
                continue
            tag = "STATIC" if b.is_static else f"m={b.mass}"
            lines.append(f"  b{i} [{tag}] pos={b.pos}  collisions={b.collisions}")
        return "\n".join(lines)
