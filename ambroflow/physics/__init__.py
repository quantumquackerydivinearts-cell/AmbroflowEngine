"""
ambroflow.physics — Shygazun-native physics engine.

Python mirror of the DjinnOS Kobra physics engine.
Same API, same integration scheme, same element addresses.
Backend selection: Python (always) or kernel (native DjinnOS, future).

Quick start:
    from ambroflow.physics import PhysicsWorld, get_backend

    world = get_backend()           # Python mirror (or kernel if on DjinnOS)
    world.add_body(1.0, 0, 5, 0)   # 1kg body at y=5
    world.add_static(0, -5, 0)     # floor at y=-5
    for _ in range(120):
        world.wu_tick()             # 2 seconds at 60fps
    print(world.pos(0))             # final position

Kobra script execution:
    from ambroflow.physics.kobra_script import execute
    result = execute("body(1.0)\\nfloor\\ntick 120")

Element constants (match Kobra byte addresses):
    ADDR_SHAK = 104   # Fire — impulse
    ADDR_PUF  = 105   # Air  — drag
    ADDR_MEL  = 106   # Water — damping
    ADDR_ZOT  = 107   # Earth — gravity
    ADDR_WU   =  45   # Process — tick

Compound reactions (AppleBlossom 108–123):
    from ambroflow.physics.elements import react, compound_name
    react(104, 106)  # Shak × Mel = 110 (Alkahest)
    react(106, 104)  # Mel × Shak = 116 (Steam)
"""

from .world     import PhysicsWorld, Body, Vec3, Aabb, MAX_BODIES
from .elements  import (
    ADDR_SHAK, ADDR_PUF, ADDR_MEL, ADDR_ZOT, ADDR_WU,
    COMPOUNDS, REACTION_TABLE, COMPOUND_PHYSICS,
    react, compound_name, compound_symbol,
)
from .backend   import get_backend
from .kobra_script import execute as execute_kobra, load_and_run, ScriptResult

__all__ = [
    "PhysicsWorld", "Body", "Vec3", "Aabb", "MAX_BODIES",
    "ADDR_SHAK", "ADDR_PUF", "ADDR_MEL", "ADDR_ZOT", "ADDR_WU",
    "COMPOUNDS", "REACTION_TABLE", "COMPOUND_PHYSICS",
    "react", "compound_name", "compound_symbol",
    "get_backend",
    "execute_kobra", "load_and_run", "ScriptResult",
]
