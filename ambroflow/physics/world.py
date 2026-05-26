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
class VacuumState:
    """
    The void's energy level is nonzero (byte 245).
    Parameters the zero-point energy floor and electromagnetic reference state.
    kael_amplitude: vacuum fluctuation level (Kaelzo, byte 1636)
    freq_ref:       reference frequency for Y/U coherence window
    phase_ref:      global vacuum phase reference
    """
    kael_amplitude: float = 0.001
    freq_ref:       float = 1.0
    phase_ref:      float = 0.0


# Rose spectral bin boundaries (frequency → byte address of Rose vector 24-30)
def rose_bin(frequency: float) -> int:
    """Map body frequency to Rose spectral bin byte address (24=Ru through 30=AE)."""
    f = max(0.0, frequency)
    if   f < 0.5:  return 24  # Ru — red
    elif f < 1.0:  return 25  # Ot — orange
    elif f < 1.5:  return 26  # El — yellow
    elif f < 2.0:  return 27  # Ki — green
    elif f < 2.5:  return 28  # Fu — blue
    elif f < 3.0:  return 29  # Ka — indigo
    else:          return 30  # AE — violet


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
    # Collision tracking (Python extension for Bridge)
    collisions:  int  = 0
    # ── Electromagnetic / chiral state (Mel + Puf extended) ───────────────────
    # phase:     electromagnetic phase [0, 2π] — A/O Mind+/− (bytes 98/99)
    # frequency: angular frequency — Y/U Time+/− (bytes 102/103); rose_bin maps to Rose 24-30
    # spin:      circular polarization +1/-1/0 — I/E Space+/− (bytes 100/101); Pauli byte 246
    phase:       float = 0.0
    frequency:   float = 0.0
    spin:        int   = 0    # +1, 0, or -1

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
        self.total_collisions: int        = 0
        self._energy_history:  list[float] = []
        # ── Electromagnetic / chiral world state ──────────────────────────────
        # vacuum:     zero-point energy floor and reference state (byte 245)
        # eigenstate: 79-dimensional vector — the atomically golden network (Au, Z=79).
        #   [0]     = Kael void (vacuum floor — zero-point before any tongue)
        #   [1–24]  = YeGaoh Group (24 tongues: Lotus–Djinn)       COMPLETE
        #   [25–50] = YeYe Group   (26 tongues: Fold–Blade)         COMPLETE
        #   [51–78] = YeShu Group  (28 tongues: pending)            PENDING → 0.0
        #   24 + 26 + 28 + 1 void = 79.  Groups encode their own sizes.
        self.vacuum:     VacuumState = VacuumState()
        self.eigenstate: list[float] = [0.0] * 79

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
        # Initial phase: vacuum-seeded via Kael noise — nonzero, body-unique
        b.phase       = (self._kael_noise() + 1.0) * math.pi   # [0, 2π]
        b.frequency   = self.vacuum.freq_ref                    # coherent with vacuum
        b.spin        = 0                                        # unaligned
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
        self.body_count       = 0
        self.time             = 0.0
        self.steps            = 0
        self.total_collisions = 0
        self._energy_history.clear()
        self.eigenstate       = [0.0] * 51

    def reset_session(self) -> None:
        """
        Clear player bodies only — preserve world history.

        Bodies are specific to a character/player (mass, count, initial pos vary
        between games).  World state (steps, time, kael_seed, collision count,
        energy history) persists because the world was already affected by prior
        characters and sessions.  Call this at game boundaries, not reset().
        """
        for b in self.bodies:
            b.active = False
        self.body_count = 0

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

    # ── Electromagnetic force (Mel extended) ─────────────────────────────────

    def apply_mel_photonic(self, coeff: Optional[float] = None) -> None:
        """
        Mel (106) Electromagnetic — photonic extension.

        Phase coupling: A-mode (in-phase < π/4) attracts; O-mode (antiphase
        > 3π/4) repels.  Maps A/O ontic vowels (bytes 98/99) to live physics.

        Frequency coherence: body pairs within ±10% of vacuum freq_ref
        synchronize (Y-mode, Time+).  Bodies outside that window diverge.

        Phase advances by frequency × dt each call.
        """
        c = coeff if coeff is not None else self.linear_damping * 0.5
        TAU = 2.0 * math.pi
        freq_window = self.vacuum.freq_ref * 0.1

        for i in range(self.body_count):
            bi = self.bodies[i]
            if not bi.active or bi.is_static:
                continue
            for j in range(i + 1, self.body_count):
                bj = self.bodies[j]
                if not bj.active or bj.is_static:
                    continue

                # Phase coupling mode
                diff = abs(bi.phase - bj.phase) % TAU
                if diff > math.pi:
                    diff = TAU - diff
                if diff < math.pi * 0.25:
                    mode = 1.0   # A-mode: constructive
                elif diff > math.pi * 0.75:
                    mode = -1.0  # O-mode: destructive
                else:
                    mode = 0.0
                if mode == 0.0:
                    continue

                dx = bj.pos.x - bi.pos.x
                dy = bj.pos.y - bi.pos.y
                dz = bj.pos.z - bi.pos.z
                r2 = max(0.01, dx*dx + dy*dy + dz*dz)
                f  = c * mode / r2
                mi = max(0.001, bi.mass)
                mj = max(0.001, bj.mass)

                bi.apply_acc(Vec3( dx * f / mi,  dy * f / mi,  dz * f / mi))
                bj.apply_acc(Vec3(-dx * f / mj, -dy * f / mj, -dz * f / mj))

                # Frequency synchronization (Y-mode)
                if abs(bi.frequency - bj.frequency) < freq_window:
                    sync = (bj.frequency - bi.frequency) * c * 0.1
                    bi.frequency += sync
                    bj.frequency -= sync

        # Phase advance: oscillate at body frequency
        for i in range(self.body_count):
            b = self.bodies[i]
            if b.active and not b.is_static:
                b.phase = (b.phase + b.frequency * self.dt) % TAU

    # ── Chiral force (Puf extended) ───────────────────────────────────────────

    def apply_puf_chiral(self, coeff: Optional[float] = None) -> None:
        """
        Puf (105) Weak Nuclear — chiral extension.

        Pauli exclusion (byte 246): same-spin bodies in contact repel extra.
        Opposite-spin: reduced repulsion, slight attractive bias.
        Maps I/E ontic vowels (bytes 100/101) to live physics via spin ±1.
        """
        c = coeff if coeff is not None else self.drag_coeff * 0.5
        for i in range(self.body_count):
            bi = self.bodies[i]
            if not bi.active or bi.is_static or bi.spin == 0:
                continue
            for j in range(i + 1, self.body_count):
                bj = self.bodies[j]
                if not bj.active or bj.is_static or bj.spin == 0:
                    continue
                ai, aj = bi.aabb(), bj.aabb()
                if not ai.overlaps(aj):
                    continue
                pen = ai.penetration(aj)
                depth = min(pen.x, pen.y, pen.z)
                if depth < 0.001:
                    continue
                spin_factor = 1.5 * c if bi.spin == bj.spin else -0.3 * c
                if pen.x <= pen.y and pen.x <= pen.z:
                    axis = 0
                elif pen.y <= pen.z:
                    axis = 1
                else:
                    axis = 2
                attrs = ("x", "y", "z")
                ax = attrs[axis]
                sign = -1.0 if getattr(bi.pos, ax) < getattr(bj.pos, ax) else 1.0
                delta = depth * spin_factor
                if not bi.is_static:
                    setattr(bi.pos, ax, getattr(bi.pos, ax) + sign * delta)
                if not bj.is_static:
                    setattr(bj.pos, ax, getattr(bj.pos, ax) - sign * delta)

    # ── Extended tick ─────────────────────────────────────────────────────────

    def wu_tick_extended(
        self,
        zot:    bool = True,
        mel:    bool = True,
        puf:    bool = True,
        photon: bool = False,
        chiral: bool = False,
    ) -> None:
        """
        Full tick with optional photonic (Mel phase coupling) and
        chiral (Puf spin exclusion) forces.  Updates the 24-eigenstate vector.
        """
        if zot:    self.apply_zot(1.0)
        if mel:    self.apply_mel(self.linear_damping)
        if puf:    self.apply_puf(self.drag_coeff)
        if photon: self.apply_mel_photonic()
        if chiral: self.apply_puf_chiral()
        self._verlet_integrate()
        self._resolve_collisions()
        self.time  += self.dt
        self.steps += 1
        e = self.total_kinetic_energy()
        if len(self._energy_history) >= 256:
            self._energy_history.pop(0)
        self._energy_history.append(e)
        self._update_eigenstate()

    # ── Full eigenstate update (50 tongues) ───────────────────────────────────

    def _update_eigenstate(self) -> None:
        """
        Compute all 50 eigenstate weights from live physics observables.
        One weight per tongue (Tongues 1-50, indexed 0-49).

        Three passes:
          Pass 1 — single body stats (O(n))
          Pass 2 — pair stats (O(n²), n ≤ 16 = 120 pairs max)
          Pass 3 — energy history stats

        Every position is physically grounded in its tongue's semantic domain.
        Positions 8-23 (Dragon–Djinn) and 24-41 (Fold–Janus) use the best
        available classical observables; the Hopfield semantic layer will
        deepen these when tongue weights are integrated.
        """
        n    = self.body_count
        TAU  = 2.0 * math.pi
        PI   = math.pi
        eps  = 1e-6

        if n == 0:
            self.eigenstate = [0.0] * 79
            return

        dyn = [b for b in self.bodies[:n] if b.active and not b.is_static]
        nd  = float(len(dyn)) or 1.0
        fr  = self.vacuum.freq_ref or 1.0

        # ── Pass 1: single-body statistics ────────────────────────────────────
        ke_vals      = []
        y_vals       = []
        x_vals       = []
        z_vals       = []
        mass_vals    = []
        rest_vals    = []
        freq_vals    = []
        phase_vals   = []
        spin_vals    = []
        vel_sq_vals  = []
        vel_vecs     = []
        dist_sq_vals = []
        rose_counts  = [0] * 7
        pos_sum      = Vec3.zero()
        pos_sq_sum   = 0.0
        spin_sum     = 0
        spin_count   = 0
        momentum_sum = 0.0
        elevated     = 0   # y > 0.5
        in_motion    = 0   # vel² > 0.001
        low_mass     = 0   # mass < 0.5
        freq_above   = 0   # frequency > freq_ref
        liminal      = 0   # phase in (π/4, 3π/4) ∪ (5π/4, 7π/4) — neutral zone
        janus_ct     = 0   # phase near 0, π, or 2π — transition points
        settled      = 0   # vel² < 1e-4 (register-file still)

        for b in dyn:
            ke = b.kinetic_energy(self.dt)
            ke_vals.append(ke)
            y_vals.append(b.pos.y)
            x_vals.append(b.pos.x)
            z_vals.append(b.pos.z)
            dist_sq_vals.append(b.pos.len_sq())
            mass_vals.append(b.mass)
            rest_vals.append(b.restitution)
            freq_vals.append(b.frequency)
            phase_vals.append(b.phase)
            spin_vals.append(b.spin)
            v = b.vel(self.dt)
            vsq = v.len_sq()
            vel_sq_vals.append(vsq)
            vel_vecs.append(v)
            momentum_sum += b.mass * math.sqrt(vsq)
            if vsq < 1e-4: settled += 1
            bin_idx = rose_bin(b.frequency) - 24
            if 0 <= bin_idx < 7:
                rose_counts[bin_idx] += 1
            pos_sum    = pos_sum.add(b.pos)
            pos_sq_sum += b.pos.len_sq()
            if b.spin != 0:
                spin_sum   += b.spin
                spin_count += 1
            if b.pos.y > 0.5:   elevated  += 1
            if vsq > 0.001:     in_motion += 1
            if b.mass < 0.5:    low_mass  += 1
            if b.frequency > fr: freq_above += 1
            # liminal: phase in (π/4,3π/4) or (5π/4,7π/4)
            pm = b.phase % PI
            if PI * 0.25 < pm < PI * 0.75:   liminal += 1
            # janus: near 0, π, or 2π
            if pm < PI * 0.1 or pm > PI * 0.9: janus_ct += 1

        ke_sum  = sum(ke_vals)
        ke_max  = max(ke_vals) if ke_vals else eps
        n_spin  = max(spin_count, 1)

        mean_pos  = pos_sum.scale(1.0 / nd)
        spread_sq = max(0.0, pos_sq_sum / nd - mean_pos.len_sq())

        mass_mean = sum(mass_vals) / nd
        mass_var  = sum((m - mass_mean) ** 2 for m in mass_vals) / nd
        rest_mean = sum(rest_vals) / nd
        rest_var  = sum((r - rest_mean) ** 2 for r in rest_vals) / nd
        vel_mean  = sum(vel_sq_vals) / nd
        vel_var   = sum((v - vel_mean) ** 2 for v in vel_sq_vals) / nd
        freq_dev  = sum(abs(f - fr) / fr for f in freq_vals) / nd
        freq_std  = (sum((f - (sum(freq_vals)/nd))**2 for f in freq_vals) / nd) ** 0.5
        max_ke    = max(ke_vals) if ke_vals else eps
        min_y     = min(y_vals) if y_vals else 0.0
        neg_spin  = sum(1 for s in spin_vals if s < 0)

        unique_bins = len(set(rose_bin(f) for f in freq_vals))

        # ── Pass 2: pair statistics ───────────────────────────────────────────
        constructive   = 0
        destructive    = 0
        neutral_pairs  = 0
        total_pairs    = 0
        overlapping    = 0
        deep_overlap   = 0   # penetration depth > 0.1
        max_overlap    = 0.0
        coupling_sum   = 0.0  # sum of |coupling mode| / r²

        for i, bi in enumerate(dyn):
            for bj in dyn[i+1:]:
                total_pairs += 1
                diff = abs(bi.phase - bj.phase) % TAU
                if diff > PI: diff = TAU - diff
                if   diff < PI * 0.25: constructive  += 1
                elif diff > PI * 0.75: destructive   += 1
                else:                  neutral_pairs += 1

                dx = bj.pos.x - bi.pos.x
                dy = bj.pos.y - bi.pos.y
                dz = bj.pos.z - bi.pos.z
                r2 = max(dx*dx + dy*dy + dz*dz, 0.01)
                mode = 1.0 if diff < PI*0.25 else (-1.0 if diff > PI*0.75 else 0.0)
                coupling_sum += abs(mode) / r2

                ai, aj = bi.aabb(), bj.aabb()
                if ai.overlaps(aj):
                    overlapping += 1
                    pen = ai.penetration(aj)
                    d = min(pen.x, pen.y, pen.z)
                    max_overlap = max(max_overlap, d)
                    if d > 0.1: deep_overlap += 1

        tp  = max(total_pairs, 1)
        vac = self.vacuum.kael_amplitude * nd

        # ── Pass 3: energy history ────────────────────────────────────────────
        hist = self._energy_history
        dke   = (hist[-1] - hist[-2]) if len(hist) >= 2 else 0.0
        d2ke  = ((hist[-1] - hist[-2]) - (hist[-2] - hist[-3])) if len(hist) >= 3 else 0.0
        recent = hist[-16:] if len(hist) >= 2 else [ke_sum]
        ke_var_h = 0.0
        zero_cross = 0
        if len(recent) >= 2:
            rm = sum(recent) / len(recent)
            ke_var_h = sum((x - rm)**2 for x in recent) / len(recent)
            for i in range(1, len(recent)):
                if (recent[i] - rm) * (recent[i-1] - rm) < 0:
                    zero_cross += 1

        # ── YeShu derived metrics (Pass 4) ───────────────────────────────────────
        ke_mean_v  = ke_sum / nd
        ke_std_v   = math.sqrt(sum((k - ke_mean_v)**2 for k in ke_vals) / nd) if ke_vals else eps
        freq_mean  = sum(freq_vals) / nd if freq_vals else fr
        freq_cv    = freq_std / max(freq_mean, eps)
        max_dist   = math.sqrt(max(dist_sq_vals)) if dist_sq_vals else 0.0
        world_rad  = max(6.0 * nd ** 0.333, eps)
        x_ext      = (max(x_vals) - min(x_vals)) if x_vals else 0.0
        y_ext      = (max(y_vals) - min(y_vals)) if y_vals else 0.0
        z_ext      = (max(z_vals) - min(z_vals)) if z_vals else 0.0
        spatial_extent = min(1.0, math.sqrt(x_ext**2 + y_ext**2 + z_ext**2) / max(world_rad * 2.0, eps))
        mean_vx    = sum(v.x for v in vel_vecs) / nd
        mean_vy    = sum(v.y for v in vel_vecs) / nd
        mean_vz    = sum(v.z for v in vel_vecs) / nd
        mean_velmag = math.sqrt(mean_vx**2 + mean_vy**2 + mean_vz**2)
        aligned    = sum(
            1 for v in vel_vecs
            if mean_velmag > eps and math.sqrt(v.len_sq()) > eps and
               (v.x*mean_vx + v.y*mean_vy + v.z*mean_vz) /
               (math.sqrt(v.len_sq()) * mean_velmag) > 0.8
        )
        cottus_v   = aligned / nd
        ordered_p  = sum(
            1 for i, bi in enumerate(dyn) for bj in dyn[i+1:]
            if (bj.pos.x > bi.pos.x) == (bj.phase > bi.phase)
        )
        hist_mean  = sum(hist[-8:]) / max(len(hist[-8:]), 1) if hist else ke_sum
        phoebe_v   = 1.0 / (1.0 + vel_var * self.dt**2 / max(spread_sq, eps))
        expected_t = self.steps * self.dt
        es_slice   = [v for v in self.eigenstate[1:51] if v > eps]
        es_total   = sum(es_slice) or 1.0
        arges_v    = min(1.0, (-sum(p * math.log(p) for p in (v / es_total for v in es_slice) if p > 0)) /
                       max(math.log(max(len(es_slice), 2)), eps)) if es_slice else 0.0

        # ── Eigenstate computation — all 79 tongues ───────────────────────────

        # [0] Kael vacuum floor — zero-point energy before any tongue manifests
        self.eigenstate[0] = self.vacuum.kael_amplitude

        # YeGaoh cluster — Tongues 1-8 (indices 1-8) — foundational forces
        self.eigenstate[1] = max(0.0, 1.0 - min(1.0, ke_sum / max(ke_max, eps)))   # Lotus: KE settled
        self.eigenstate[2] = max(rose_counts) / nd                                   # Rose: spectral dominant bin
        mean_pos2 = pos_sum.scale(1.0 / nd)
        self.eigenstate[3] = 1.0 / (1.0 + max(0.0, pos_sq_sum/nd - mean_pos2.len_sq()))  # Sakura: spatial coherence
        self.eigenstate[4] = rest_mean                                               # Daisy: structural elasticity
        self.eigenstate[5] = constructive / tp                                       # AppleBlossom: phase coherence
        self.eigenstate[6] = min(1.0, abs(spin_sum) / n_spin) if spin_count else 0.0  # Aster: chiral alignment
        self.eigenstate[7] = overlapping / tp                                        # Grapevine: network contact density
        self.eigenstate[8] = vac / (ke_sum + vac + eps)                             # Cannabis: observer/vacuum ratio

        # Dragon cluster — Tongues 9-16 (indices 9-16) — biological consciousness
        self.eigenstate[9]  = min(1.0, abs(dke) / max(ke_max, eps))                # Dragon: legibility — rate of change
        self.eigenstate[10] = overlapping / tp                                      # Virus: space invasion (AABB overlap)
        self.eigenstate[11] = 1.0 / (1.0 + mass_var)                               # Bacteria: homogeneous distribution
        self.eigenstate[12] = min(1.0, max(0.0, -min_y) / 5.0)                     # Excavata: excavation depth
        self.eigenstate[13] = min(1.0, self.linear_damping * 10.0) * (ke_sum / max(ke_sum + eps, eps))  # Archaeplastida: energy absorption
        self.eigenstate[14] = low_mass / nd                                         # Myxozoa: parasitic simplification
        self.eigenstate[15] = 1.0 - self.eigenstate[8]                              # Archaea: extremophile stability (anti-vacuum)
        self.eigenstate[16] = unique_bins / 7.0                                     # Protist: frequency diversity

        # Immune cluster — Tongues 17-24 (indices 17-24) — higher consciousness
        self.eigenstate[17] = (constructive + destructive) / tp                    # Immune: pattern discrimination
        self.eigenstate[18] = min(1.0, coupling_sum / max(tp, 1))                  # Neural: coupling network strength
        self.eigenstate[19] = 1.0 / (1.0 + vel_var)                                # Serpent: velocity coherence
        self.eigenstate[20] = max_ke / max(ke_sum, eps)                             # Beast: dominant power fraction
        self.eigenstate[21] = elevated / nd                                         # Cherub: elevation fraction
        self.eigenstate[22] = neutral_pairs / tp                                    # Chimera: hybrid (neither A nor O)
        self.eigenstate[23] = liminal / nd                                          # Faerie: liminal phase presence
        self.eigenstate[24] = in_motion / nd                                        # Djinn: pure motion fraction

        # YeYe forward — Tongues 25-42 (indices 25-42)
        self.eigenstate[25] = min(1.0, zero_cross / 8.0)                           # Fold: topological transitions
        self.eigenstate[26] = 1.0 / (1.0 + rest_var)                               # Topology: structural invariance
        self.eigenstate[27] = min(1.0, abs(d2ke) / max(ke_max, eps))               # Phase: phase transition rate
        self.eigenstate[28] = 1.0 / (1.0 + freq_std / max(fr, eps))               # Gradient: frequency gradient
        self.eigenstate[29] = min(1.0, ke_var_h / max(ke_max, eps))                # Curvature: trajectory bending
        self.eigenstate[30] = neg_spin / max(spin_count, 1) if spin_count else 0.0 # Prion: inverted spin (misfolded)
        self.eigenstate[31] = min(1.0, abs(dke) / max(ke_sum + eps, eps))          # Blood: circulation flow rate
        self.eigenstate[32] = min(1.0, zero_cross / 4.0)                           # Moon: oscillation period
        self.eigenstate[33] = 1.0 - abs(self.eigenstate[5] - 0.5) * 2             # Koi: balanced exchange (phase near 0.5)
        self.eigenstate[34] = constructive / tp                                     # Rope: connective tension (attractive)
        self.eigenstate[35] = deep_overlap / tp                                     # Hook: engaged deep contact
        self.eigenstate[36] = min(1.0, max_overlap / 2.0)                          # Fang: maximum penetration depth
        self.eigenstate[37] = 1.0 - min(1.0, abs(dke) / max(ke_sum + eps, eps))   # Circle: energy conservation
        self.eigenstate[38] = min(1.0, self.steps / 1000.0)                        # Ledger: accumulated history
        self.eigenstate[39] = self.eigenstate[5] * self.eigenstate[1]              # Bond: phase coherence × stability
        self.eigenstate[40] = constructive / tp                                     # Venus: attraction fraction
        self.eigenstate[41] = 1.0 / (1.0 + freq_dev)                               # Gaia: frequency balance with reference
        self.eigenstate[42] = janus_ct / nd                                         # Janus: phase transition crossovers

        # YeYe decay — Tongues 43-50 (indices 43-50) — dissolution axis
        self.eigenstate[43] = max(0.0, 1.0 - self.eigenstate[1])                   # Thanatos: dissolution (1 − Lotus)
        self.eigenstate[44] = min(1.0, max(0.0, -dke) / max(ke_sum + eps, eps))    # Saturn: consumption rate
        self.eigenstate[45] = 1.0 - rest_mean                                       # Corpse: inelastic decomposition
        self.eigenstate[46] = freq_above / nd                                        # Furnace: hot bodies (above ref freq)
        self.eigenstate[47] = sum(1 for y in y_vals if y < -3.0) / nd              # Square: geometric collapse (deep fall)
        self.eigenstate[48] = destructive / tp                                       # Eye: destructive recognition
        self.eigenstate[49] = 1.0 - self.eigenstate[35]                             # Flesh: contact loss (1 − Hook)
        self.eigenstate[50] = 1.0 - self.eigenstate[6]                              # Blade: severance (1 − Aster)

        # YeShu Group — Tongues 51-78 (indices 51-78) — hardware abstraction layer
        # Children of Gaia. Derived from Aster (chiral+time+space) × Grapevine (storage+routing+network).
        self.eigenstate[51] = spatial_extent                                          # Ouranos: virtual address space
        self.eigenstate[52] = min(1.0, momentum_sum / max(sum(b.mass for b in dyn) * 10.0, eps))  # Pontus: memory bus throughput
        self.eigenstate[53] = settled / nd                                            # Ourea: register file (still bodies)
        self.eigenstate[54] = min(1.0, ke_sum / max(ke_mean_v * nd, eps))            # Oceanus: RAM (active flow fraction)
        self.eigenstate[55] = sum((k / max(ke_sum, eps))**2 for k in ke_vals) if ke_vals else 0.0  # Coeus: CPU concentration (Herfindahl)
        self.eigenstate[56] = 1.0 / (1.0 + math.sqrt(max(0.0, pos_sq_sum/nd - mean_pos.len_sq())))  # Crius: mass centrality (bus arbiter)
        self.eigenstate[57] = 1.0 / (1.0 + freq_cv)                                  # Hyperion: clock regularity
        self.eigenstate[58] = min(1.0, max_ke / max(ke_mean_v * 3.0, eps))           # Iapetus: interrupt spike
        self.eigenstate[59] = elevated / nd                                           # Theia: display surface (elevated bodies)
        self.eigenstate[60] = min(1.0, max(0.0, in_motion / nd - overlapping / tp))  # Rhea: DMA (fast, unimpeded)
        self.eigenstate[61] = ordered_p / tp                                          # Themis: memory fence (phase ordering)
        self.eigenstate[62] = 1.0 / (1.0 + abs(ke_sum - hist_mean) / max(hist_mean, eps))  # Mnemosyne: cache (history coherence)
        self.eigenstate[63] = phoebe_v                                                # Phoebe: branch predictor (trajectory regularity)
        self.eigenstate[64] = (self.eigenstate[0] + self.eigenstate[1]) / 2.0        # Tethys: bootloader (ground persistence)
        self.eigenstate[65] = min(1.0, min(expected_t, self.time) / max(max(expected_t, self.time), eps))  # Cronus: clock cycle regularity
        self.eigenstate[66] = min(1.0, overlapping / nd)                              # Brontes: interrupt controller (collision routing)
        self.eigenstate[67] = min(1.0, max_ke / max(ke_mean_v * 5.0, eps))           # Steropes: NMI (critical threshold breach)
        self.eigenstate[68] = arges_v                                                 # Arges: system status (eigenstate entropy)
        self.eigenstate[69] = cottus_v                                                # Cottus: DMA burst (coherent bulk motion)
        self.eigenstate[70] = 1.0 - cottus_v                                         # Briareos: multi-core (velocity diversity)
        self.eigenstate[71] = min(1.0, overlapping / nd)                              # Gyges: wide bus (simultaneous contacts/body)
        self.eigenstate[72] = self.vacuum.kael_amplitude / max(ke_mean_v + self.vacuum.kael_amplitude, eps)  # Nereus: firmware (vacuum floor dominance)
        self.eigenstate[73] = min(1.0, max((abs(k - ke_mean_v) for k in ke_vals), default=0.0) / max(ke_std_v * 3.0, eps))  # Thaumas: hw exception (most anomalous body)
        self.eigenstate[74] = 1.0 - min(1.0, max_overlap / 2.0)                      # Phorcys: MPU (boundary integrity)
        self.eigenstate[75] = min(1.0, max_dist / world_rad)                          # Ceto: boundary register (edge proximity)
        self.eigenstate[76] = min(1.0, self.linear_damping * 10.0) * (ke_sum / max(ke_sum + vac, eps))  # Eurybia: power management
        self.eigenstate[77] = min(1.0, max(0.0, ke_sum / max(ke_mean_v * nd, eps) - 0.8) / 0.2) if ke_vals else 0.0  # Typhon: kernel panic (energy runaway)
        self.eigenstate[78] = self.eigenstate[1] * max(0.0, 1.0 - self.eigenstate[43])  # Antaeus: watchdog (Lotus stability × anti-dissolution)

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
        Encodes classical + photonic state without exposing raw positions.
        """
        dyn = [b for b in self.bodies[:self.body_count]
               if b.active and not b.is_static]
        rose_dist = {}
        for b in dyn:
            addr = rose_bin(b.frequency)
            rose_dist[addr] = rose_dist.get(addr, 0) + 1
        mean_phase = (sum(b.phase for b in dyn) / len(dyn)) if dyn else 0.0
        mean_freq  = (sum(b.frequency for b in dyn) / len(dyn)) if dyn else 0.0
        spin_net   = sum(b.spin for b in dyn)
        return {
            "steps":             self.steps,
            "time":              round(self.time, 4),
            "total_ke":          round(self.total_kinetic_energy(), 6),
            "total_collisions":  self.total_collisions,
            "body_count":        self.body_count,
            "settled":           self.is_settled(),
            "energy_trend":      round(self.energy_delta(), 6),
            # Photonic state
            "mean_phase":        round(mean_phase, 4),
            "mean_frequency":    round(mean_freq, 4),
            "spin_net":          spin_net,
            "rose_distribution": rose_dist,
            "eigenstate":        [round(v, 4) for v in self.eigenstate[:25]] + [round(self.eigenstate[43], 4), round(self.eigenstate[50], 4)],
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
