"""
ambroflow/world/gl_viewer.py
-----------------------------
Quick 3D viewer for Zone geometry using pygame-ce + moderngl.

Usage:
    python -m ambroflow.world.gl_viewer
    python -m ambroflow.world.gl_viewer <zone_id>

Controls:
    Left/Right arrows  — orbit camera
    Up/Down arrows     — tilt camera
    +/-                — zoom in/out
    W/S                — same as Up/Down
    A/D                — same as Left/Right
    ESC or Q           — quit
"""
from __future__ import annotations

import math
import struct
import sys

import numpy as np
import pygame
import moderngl

from ambroflow.world.mesh_builder import zone_to_mesh

_W, _H = 1280, 720
_FOV   = 45.0

_VERT = """\
#version 330 core
layout(location=0) in vec3 a_pos;
layout(location=1) in vec3 a_normal;
layout(location=2) in vec2 a_uv;
uniform mat4 u_mvp;
out vec3 v_normal;
void main() {
    gl_Position = u_mvp * vec4(a_pos, 1.0);
    v_normal = a_normal;
}
"""

_FRAG = """\
#version 330 core
in vec3 v_normal;
out vec4 frag_color;
void main() {
    vec3 sun  = normalize(vec3(0.8, 1.6, 1.0));
    vec3 fill = normalize(vec3(-0.4, 0.6, -0.3));
    float d = max(dot(normalize(v_normal), sun),  0.0) * 0.75
            + max(dot(normalize(v_normal), fill), 0.0) * 0.20
            + 0.10;
    // warm stone tones blended with light intensity
    vec3 dark  = vec3(0.22, 0.18, 0.14);
    vec3 light = vec3(0.80, 0.70, 0.55);
    frag_color = vec4(mix(dark, light, d), 1.0);
}
"""


def _perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f  = 1.0 / math.tan(math.radians(fov_deg) * 0.5)
    nf = near - far
    # Row-major; transpose before uploading to GL
    return np.array([
        [f / aspect, 0.0,  0.0,                      0.0],
        [0.0,        f,    0.0,                      0.0],
        [0.0,        0.0,  (far + near) / nf,        2.0 * far * near / nf],
        [0.0,        0.0, -1.0,                      0.0],
    ], dtype="f4")


def _look_at(eye: np.ndarray, target: np.ndarray) -> np.ndarray:
    up = np.array([0.0, 1.0, 0.0], dtype="f4")
    f  = target - eye;            f  /= np.linalg.norm(f)
    r  = np.cross(f, up);         r  /= np.linalg.norm(r)
    u  = np.cross(r, f)
    return np.array([
        [ r[0],  r[1],  r[2], -np.dot(r, eye)],
        [ u[0],  u[1],  u[2], -np.dot(u, eye)],
        [-f[0], -f[1], -f[2],  np.dot(f, eye)],
        [ 0.0,   0.0,   0.0,  1.0            ],
    ], dtype="f4")


def main(zone_id: str | None = None) -> None:
    from ambroflow.world.zones import build_game7_world

    wm   = build_game7_world()
    zid  = zone_id or wm.starting_zone_id
    if zid not in wm.zones:
        print(f"Zone '{zid}' not found. Available:", list(wm.zones)[:8])
        sys.exit(1)
    zone = wm.zones[zid]
    print(f"Zone: {zone.name!r}  ({zone.width}×{zone.height} tiles)")

    mesh      = zone_to_mesh(zone)
    vbo_bytes = bytes(mesh["vbo"]["data"])

    indices: list[int] = []
    for batch in mesh["batches"]:
        indices.extend(batch["index_data"])
    ibo_bytes = struct.pack(f"<{len(indices)}I", *indices)

    print(f"Mesh: {mesh['vertex_count']} verts  {mesh['face_count']} faces  {len(indices)} indices")

    pygame.init()
    pygame.display.set_caption(f"Ambroflow 3D — {zone.name}")
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK,
                                     pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.set_mode((_W, _H), pygame.OPENGL | pygame.DOUBLEBUF)

    ctx  = moderngl.create_context()
    ctx.enable(moderngl.DEPTH_TEST)
    ctx.enable(moderngl.CULL_FACE)

    prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
    vbo  = ctx.buffer(vbo_bytes)
    ibo  = ctx.buffer(ibo_bytes)
    # pos(3f) + normal(3f) + uv(2f) + pad(12x) = 44 bytes/vertex
    vao  = ctx.vertex_array(
        prog,
        [(vbo, "3f 3f 2f 12x", "a_pos", "a_normal", "a_uv")],
        ibo,
        index_element_size=4,
    )

    cx, cz = zone.width * 0.5, zone.height * 0.5
    azimuth   = 225.0
    elevation = 35.0
    dist      = max(zone.width, zone.height) * 1.1

    clock   = pygame.time.Clock()
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: azimuth   -= 1.5
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: azimuth   += 1.5
        if keys[pygame.K_UP]    or keys[pygame.K_w]: elevation  = min(elevation + 1.0, 89.0)
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: elevation  = max(elevation - 1.0, 5.0)
        if keys[pygame.K_EQUALS] or keys[pygame.K_KP_PLUS]:  dist = max(dist * 0.97, 3.0)
        if keys[pygame.K_MINUS]  or keys[pygame.K_KP_MINUS]: dist = min(dist * 1.03, 800.0)

        az = math.radians(azimuth)
        el = math.radians(elevation)
        eye = np.array([
            cx + dist * math.cos(el) * math.sin(az),
            dist * math.sin(el),
            cz + dist * math.cos(el) * math.cos(az),
        ], dtype="f4")
        target = np.array([cx, 0.5, cz], dtype="f4")

        proj = _perspective(_FOV, _W / _H, 0.1, 1000.0)
        view = _look_at(eye, target)
        mvp  = (proj @ view).astype("f4")

        ctx.clear(0.09, 0.07, 0.11)
        prog["u_mvp"].write(mvp.T.tobytes())   # transpose: row-major -> GL column-major
        vao.render(moderngl.TRIANGLES)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
