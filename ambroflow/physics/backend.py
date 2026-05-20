"""
backend.py — Physics backend selection.

Three tiers:
  python  — Pure Python mirror (always available, used in desktop/dev)
  kernel  — DjinnOS kernel physics world via ctypes ABI (native DjinnOS only)
  stub    — No-op stub (for environments where physics is not needed)

The kernel backend is the "Native" tier — when Ambroflow runs on DjinnOS,
this replaces the Python implementation with a shim that calls directly into
the live PhysicsWorld in the kernel.  Same interface, zero reimplementation.

The shim ABI will be defined when the kernel exposes a C-compatible export
for the physics world.  Until then, get_backend() always returns the Python
implementation.
"""

from __future__ import annotations

import os
from typing import Optional

from .world import PhysicsWorld


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
    Attempt to load the DjinnOS kernel physics ABI.

    The kernel exposes a stable C ABI at a well-known address when running
    on DjinnOS.  The ABI is TBD until the kernel exports are defined.
    Currently always returns None (kernel tier is a stub placeholder).
    """
    try:
        import ctypes as _ct
        # When kernel exposes libdjinnos_physics.so, this becomes:
        #   lib = _ct.CDLL("libdjinnos_physics.so")
        #   return KernelPhysicsWorld(lib)
        # For now: probe for the marker file that DjinnOS writes on boot.
        if not os.path.exists("/proc/djinnos/physics"):
            return None
        # TODO: implement KernelPhysicsWorld(ctypes shim)
        return None
    except Exception:
        if strict:
            raise RuntimeError("Kernel physics backend not available")
        return None


def _stub_world() -> PhysicsWorld:
    """Return a PhysicsWorld where all operations are no-ops."""
    world = PhysicsWorld()
    # Monkey-patch all mutating methods to no-ops
    world.wu_tick           = lambda: None          # type: ignore[method-assign]
    world.apply_zot         = lambda s=1.0: None    # type: ignore[method-assign]
    world.apply_mel         = lambda c=None: None   # type: ignore[method-assign]
    world.apply_puf         = lambda c=None: None   # type: ignore[method-assign]
    world.apply_shak        = lambda *a: None       # type: ignore[method-assign]
    world.apply_kael        = lambda m=0.5: None    # type: ignore[method-assign]
    return world
