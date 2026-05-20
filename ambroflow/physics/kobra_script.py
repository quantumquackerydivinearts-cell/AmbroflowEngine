"""
kobra_script.py — Kobra physics script parser and executor.

A .kobra physics script is a plain text file using the same syntax as the
Kobra REPL.  When loaded by a game zone, it initialises the physics world
for that zone.  The same script runs identically on DjinnOS native (via the
Rust eval) and through Ambroflow on a desktop (via this Python executor).

Supported syntax (subset matching the Kobra grammar):
  body(M)           — create body with mass M at origin
  body(M:x,y,z)     — create body with mass M at position x,y,z
  floor             — add static floor at y=−5
  Wu(Zot)           — tick with gravity
  Wu([Zot Mel])     — tick with gravity + damping
  Wu([Zot Mel Puf]) — tick with gravity + damping + drag
  Zot(S)            — apply gravity at scale S
  Mel(C)            — apply damping at coefficient C
  Puf(C)            — apply drag at coefficient C
  Shak(ID:FX,FY,FZ) — apply impulse to body ID
  tick N            — advance N steps
  reset             — clear world
  status            — print world status (returned as string, not printed)

Scripts are run line-by-line; lines starting with # are comments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .world import PhysicsWorld
from .elements import ADDR_SHAK, ADDR_PUF, ADDR_MEL, ADDR_ZOT


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class ScriptResult:
    ok:      bool
    output:  list[str] = field(default_factory=list)
    errors:  list[str] = field(default_factory=list)
    steps:   int       = 0


# ── Executor ──────────────────────────────────────────────────────────────────

def execute(script: str, world: Optional[PhysicsWorld] = None) -> ScriptResult:
    """
    Execute a Kobra physics script against a PhysicsWorld.
    Creates a new world if none is provided.
    Returns the result including any output lines.
    """
    if world is None:
        world = PhysicsWorld()

    result = ScriptResult(ok=True)

    for raw_line in script.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out = _exec_line(line, world)
            if out:
                result.output.append(out)
        except Exception as e:
            result.errors.append(f"error in '{line}': {e}")
            result.ok = False

    result.steps = world.steps
    return result


def _exec_line(line: str, w: PhysicsWorld) -> Optional[str]:
    """Execute one Kobra physics line. Returns optional output string."""

    # ── Wu(forces) — tick ─────────────────────────────────────────────────────
    if line.startswith("Wu(") or line == "Wu":
        zot = "Zot" in line
        mel = "Mel" in line
        puf = "Puf" in line
        if not any([zot, mel, puf]):
            w.wu_tick()
        else:
            w.wu_tick_flags(zot=zot, mel=mel, puf=puf)
        return f"wu#{w.steps}"

    # ── tick N — advance N steps ──────────────────────────────────────────────
    if line.startswith("tick"):
        n = _parse_int(line[4:].strip(), default=1)
        for _ in range(n):
            w.wu_tick()
        return f"ticked {n}"

    # ── body(M) or body(M:x,y,z) ─────────────────────────────────────────────
    if line.startswith("body(") and line.endswith(")"):
        inner = line[5:-1]
        if ":" in inner:
            mass_s, pos_s = inner.split(":", 1)
            mass = _parse_f(mass_s)
            coords = [_parse_f(c) for c in pos_s.split(",")]
            x = coords[0] if len(coords) > 0 else 0.0
            y = coords[1] if len(coords) > 1 else 0.0
            z = coords[2] if len(coords) > 2 else 0.0
        else:
            mass = _parse_f(inner)
            x = y = z = 0.0
        idx = w.add_body(mass, x, y, z)
        if idx is None:
            return "error: max bodies"
        return f"body{idx} mass={mass}"

    # ── floor — static ground plane ───────────────────────────────────────────
    if line == "floor":
        idx = w.add_static(0.0, -5.0, 0.0, 50.0, 0.5, 50.0)
        return f"floor body{idx}"

    # ── reset ─────────────────────────────────────────────────────────────────
    if line == "reset":
        w.reset()
        return "reset"

    # ── status ────────────────────────────────────────────────────────────────
    if line == "status":
        return w.status()

    # ── pos(ID) ───────────────────────────────────────────────────────────────
    if line.startswith("pos(") and line.endswith(")"):
        idx = _parse_int(line[4:-1])
        px, py, pz = w.pos(idx)
        return f"body{idx} pos=({px:.2f},{py:.2f},{pz:.2f})"

    # ── vel(ID) ───────────────────────────────────────────────────────────────
    if line.startswith("vel(") and line.endswith(")"):
        idx = _parse_int(line[4:-1])
        vx, vy, vz = w.vel_tuple(idx)
        return f"body{idx} vel=({vx:.2f},{vy:.2f},{vz:.2f})"

    # ── Zot(S) — gravity scale ────────────────────────────────────────────────
    if line.startswith("Zot(") and line.endswith(")"):
        s = _parse_f(line[4:-1], default=1.0)
        w.apply_zot(s)
        return f"Zot({s})"

    # ── Mel(C) — damping ──────────────────────────────────────────────────────
    if line.startswith("Mel(") and line.endswith(")"):
        c = _parse_f(line[4:-1], default=w.linear_damping)
        w.apply_mel(c)
        return f"Mel({c})"

    # ── Puf(C) — drag ─────────────────────────────────────────────────────────
    if line.startswith("Puf(") and line.endswith(")"):
        c = _parse_f(line[4:-1], default=w.drag_coeff)
        w.apply_puf(c)
        return f"Puf({c})"

    # ── Shak(ID:FX,FY,FZ) — impulse ──────────────────────────────────────────
    if line.startswith("Shak(") and line.endswith(")"):
        inner = line[5:-1]
        if ":" in inner:
            id_s, force_s = inner.split(":", 1)
            idx = _parse_int(id_s)
            coords = [_parse_f(c) for c in force_s.split(",")]
            fx = coords[0] if len(coords) > 0 else 0.0
            fy = coords[1] if len(coords) > 1 else 10.0
            fz = coords[2] if len(coords) > 2 else 0.0
        else:
            idx = _parse_int(inner)
            fx, fy, fz = 0.0, 10.0, 0.0
        w.apply_shak(idx, fx, fy, fz)
        return f"shak->body{idx}"

    # ── Kael(M) — noise ───────────────────────────────────────────────────────
    if line.startswith("Kael(") and line.endswith(")"):
        m = _parse_f(line[5:-1], default=0.5)
        w.apply_kael(m)
        return f"Kael({m})"

    return f"?({line})"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_f(s: str, default: float = 0.0) -> float:
    try:
        return float(s.strip())
    except (ValueError, AttributeError):
        return default


def _parse_int(s: str, default: int = 0) -> int:
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return default


def load_and_run(path: str, world: Optional[PhysicsWorld] = None) -> ScriptResult:
    """Load a .kobra file and execute it."""
    try:
        with open(path, encoding="utf-8") as f:
            script = f.read()
        return execute(script, world)
    except FileNotFoundError:
        return ScriptResult(ok=False, errors=[f"file not found: {path}"])
    except Exception as e:
        return ScriptResult(ok=False, errors=[str(e)])
