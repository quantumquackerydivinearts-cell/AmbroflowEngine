"""
backend.py — Physics backend selection.

Three tiers:
  python  — Pure Python mirror (always available, used in desktop/dev)
  kernel  — DjinnOS kernel physics world via ctypes ABI (native DjinnOS only)
  stub    — No-op stub (for environments where physics is not needed)

The kernel backend is the "Native" tier — when Ambroflow runs on DjinnOS,
this replaces the Python implementation with a shim that calls directly into
the live PhysicsWorld in the kernel.  Same interface, zero reimplementation.

The shim resolves djinnos_phys_* symbols from the process symbol table via
ctypes.CDLL(None).  When CPython runs inside DjinnOS the kernel IS the process,
so CDLL(None) finds the live kernel symbols without any .so file.

Backend selection via AMBROFLOW_PHYSICS_BACKEND env var:
  auto   (default) — try kernel, fall back to Python
  python            — always use Python mirror
  kernel            — require kernel (raises RuntimeError if unavailable)
  stub              — no-op world
"""

from __future__ import annotations

import os
from typing import Optional

from .world import PhysicsWorld, MAX_BODIES


# ── Backend registry ──────────────────────────────────────────────────────────

_BACKEND_ENV = os.environ.get("AMBROFLOW_PHYSICS_BACKEND", "auto").lower()


def get_backend() -> PhysicsWorld:
    """
    Return the appropriate physics backend for the current environment.

    auto  — try kernel, fall back to Python
    python — always use Python mirror
    kernel — require kernel backend (raises if unavailable)
    stub   — no-op (returns PhysicsWorld with all operations disabled)
    """
    if _BACKEND_ENV == "kernel":
        return _try_kernel(strict=True)
    if _BACKEND_ENV == "stub":
        return _stub_world()
    if _BACKEND_ENV == "python":
        return PhysicsWorld()
    # auto
    world = _try_kernel(strict=False)
    return world if world is not None else PhysicsWorld()


def _try_kernel(strict: bool = False) -> Optional[PhysicsWorld]:
    """
    Attempt to load the DjinnOS kernel physics ABI via ctypes.

    Probes for djinnos_phys_wu_tick in the process symbol table.  On DjinnOS
    these symbols resolve to the live kernel functions; on other platforms
    they will not be present and we fall through to the Python mirror.
    """
    try:
        import ctypes as ct
        lib = ct.CDLL(None)
        # Probe: if this attribute access raises AttributeError, kernel is not present
        _ = lib.djinnos_phys_wu_tick
        return KernelPhysicsWorld(lib)
    except (AttributeError, OSError):
        if strict:
            raise RuntimeError("Kernel physics backend not available — djinnos_phys_* symbols not found")
        return None
    except Exception:
        if strict:
            raise
        return None


def _stub_world() -> PhysicsWorld:
    """Return a PhysicsWorld where all operations are no-ops."""
    world = PhysicsWorld()
    world.wu_tick           = lambda: None          # type: ignore[method-assign]
    world.apply_zot         = lambda s=1.0: None    # type: ignore[method-assign]
    world.apply_mel         = lambda c=None: None   # type: ignore[method-assign]
    world.apply_puf         = lambda c=None: None   # type: ignore[method-assign]
    world.apply_shak        = lambda *a: None       # type: ignore[method-assign]
    world.apply_kael        = lambda m=0.5: None    # type: ignore[method-assign]
    return world


# ── Kernel shim ───────────────────────────────────────────────────────────────

class KernelPhysicsWorld(PhysicsWorld):
    """
    Thin ctypes shim wrapping the DjinnOS kernel's live PhysicsWorld.

    The kernel exposes a single global static PhysicsWorld through the
    djinnos_phys_* C ABI.  This class delegates every operation to that
    world, keeping the Python bookkeeping fields (steps, body_count, etc.)
    in sync after each call.

    Constructed by _try_kernel() when djinnos_phys_* symbols resolve.
    """

    def __init__(self, lib: "object") -> None:
        super().__init__()
        import ctypes as ct
        self._ct = ct

        cf  = ct.c_float
        cu8 = ct.c_uint8
        cu32= ct.c_uint32
        ci32= ct.c_int32
        pcf = ct.POINTER(ct.c_float)
        pcu32 = ct.POINTER(ct.c_uint32)
        pci32 = ct.POINTER(ct.c_int32)
        pcu8  = ct.POINTER(ct.c_uint8)

        def _fn(name, restype, argtypes):
            f = getattr(lib, name)
            f.restype   = restype
            f.argtypes  = argtypes
            return f

        self._k_add_body      = _fn("djinnos_phys_add_body",      cu8,  [cf, cf, cf, cf])
        self._k_add_static    = _fn("djinnos_phys_add_static",    cu8,  [cf, cf, cf, cf, cf, cf])
        self._k_wu_tick       = _fn("djinnos_phys_wu_tick",       None, [])
        self._k_wu_tick_flags = _fn("djinnos_phys_wu_tick_flags", None, [cu8, cu8, cu8])
        self._k_apply_zot     = _fn("djinnos_phys_apply_zot",     None, [cf])
        self._k_apply_mel     = _fn("djinnos_phys_apply_mel",     None, [cf])
        self._k_apply_puf     = _fn("djinnos_phys_apply_puf",     None, [cf])
        self._k_apply_shak    = _fn("djinnos_phys_apply_shak",    None, [cu8, cf, cf, cf])
        self._k_apply_kael    = _fn("djinnos_phys_apply_kael",    None, [cf])
        self._k_pos           = _fn("djinnos_phys_pos",           cu8,  [cu8, pcf, pcf, pcf])
        self._k_vel           = _fn("djinnos_phys_vel",           cu8,  [cu8, pcf, pcf, pcf])
        self._k_reset         = _fn("djinnos_phys_reset",         None, [])
        self._k_reset_session = _fn("djinnos_phys_reset_session", None, [])
        self._k_steps         = _fn("djinnos_phys_steps",         cu32, [])
        self._k_body_count    = _fn("djinnos_phys_body_count",    cu8,  [])
        self._k_fingerprint   = _fn("djinnos_phys_fingerprint",   None, [pcu32, pcu32, pci32, pcu8])

        # Sync bookkeeping with kernel's current state
        self._k_sync()

    # ── Sync helpers ──────────────────────────────────────────────────────────

    def _k_sync(self) -> None:
        """Pull step count and body count from kernel into Python fields."""
        self.steps      = int(self._k_steps())
        self.body_count = int(self._k_body_count())

    def _k_ke(self) -> float:
        """Read current total kinetic energy from the kernel fingerprint."""
        ct = self._ct
        ke_out = ct.c_int32(0)
        self._k_fingerprint(None, None, ct.byref(ke_out), None)
        return ke_out.value / 1000.0

    # ── Body management ───────────────────────────────────────────────────────

    def reset(self) -> None:
        self._k_reset()
        self.steps            = 0
        self.body_count       = 0
        self.total_collisions = 0
        self._energy_history.clear()

    def reset_session(self) -> None:
        """Clear player bodies only — world history persists across game boundaries."""
        self._k_reset_session()
        self.body_count = 0

    def add_body(self, mass: float, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Optional[int]:
        ct = self._ct
        idx = int(self._k_add_body(ct.c_float(mass), ct.c_float(x), ct.c_float(y), ct.c_float(z)))
        if idx == 0xFF:
            return None
        self.body_count = int(self._k_body_count())
        return idx

    def add_static(self, x: float, y: float, z: float,
                   hx: float = 50.0, hy: float = 0.5, hz: float = 50.0) -> Optional[int]:
        ct = self._ct
        idx = int(self._k_add_static(
            ct.c_float(x), ct.c_float(y), ct.c_float(z),
            ct.c_float(hx), ct.c_float(hy), ct.c_float(hz),
        ))
        if idx == 0xFF:
            return None
        self.body_count = int(self._k_body_count())
        return idx

    # ── Tick / integration ────────────────────────────────────────────────────

    def wu_tick(self) -> None:
        self._k_wu_tick()
        self.steps = int(self._k_steps())
        self._track_ke()

    def wu_tick_flags(self, zot: bool = True, mel: bool = True, puf: bool = True) -> None:
        ct = self._ct
        self._k_wu_tick_flags(
            ct.c_uint8(1 if zot else 0),
            ct.c_uint8(1 if mel else 0),
            ct.c_uint8(1 if puf else 0),
        )
        self.steps = int(self._k_steps())
        self._track_ke()

    def _track_ke(self) -> None:
        ke = self._k_ke()
        self._energy_history.append(ke)
        if len(self._energy_history) > 32:
            self._energy_history.pop(0)

    # ── Element force dispatch ────────────────────────────────────────────────

    def apply_zot(self, scale: float = 1.0) -> None:
        self._k_apply_zot(self._ct.c_float(scale))

    def apply_mel(self, coeff: Optional[float] = None) -> None:
        c = coeff if coeff is not None else self.linear_damping
        self._k_apply_mel(self._ct.c_float(c))

    def apply_puf(self, coeff: Optional[float] = None) -> None:
        c = coeff if coeff is not None else self.drag_coeff
        self._k_apply_puf(self._ct.c_float(c))

    def apply_shak(self, body_id: int, fx: float, fy: float, fz: float) -> None:
        ct = self._ct
        self._k_apply_shak(ct.c_uint8(body_id), ct.c_float(fx), ct.c_float(fy), ct.c_float(fz))

    def apply_kael(self, magnitude: float = 0.5) -> None:
        self._k_apply_kael(self._ct.c_float(magnitude))

    # ── State read-back ───────────────────────────────────────────────────────

    def pos(self, idx: int) -> tuple[float, float, float]:
        ct = self._ct
        x, y, z = ct.c_float(0.0), ct.c_float(0.0), ct.c_float(0.0)
        ok = self._k_pos(ct.c_uint8(idx), ct.byref(x), ct.byref(y), ct.byref(z))
        return (x.value, y.value, z.value) if ok else (0.0, 0.0, 0.0)

    def vel_tuple(self, idx: int) -> tuple[float, float, float]:
        ct = self._ct
        x, y, z = ct.c_float(0.0), ct.c_float(0.0), ct.c_float(0.0)
        ok = self._k_vel(ct.c_uint8(idx), ct.byref(x), ct.byref(y), ct.byref(z))
        return (x.value, y.value, z.value) if ok else (0.0, 0.0, 0.0)

    def total_kinetic_energy(self) -> float:
        return self._k_ke()

    def fingerprint(self) -> dict:
        ct = self._ct
        s_out  = ct.c_uint32(0)
        c_out  = ct.c_uint32(0)
        ke_out = ct.c_int32(0)
        st_out = ct.c_uint8(0)
        self._k_fingerprint(ct.byref(s_out), ct.byref(c_out), ct.byref(ke_out), ct.byref(st_out))
        return {
            "steps":            int(s_out.value),
            "total_collisions": int(c_out.value),
            "total_ke":         round(ke_out.value / 1000.0, 4),
            "settled":          bool(st_out.value),
            "body_count":       int(self._k_body_count()),
        }
