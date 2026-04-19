"""
demo_min.py — Stepped isolation from known-good diag→world renderer.

SPACE to advance, ESC to quit.

Stages:
  0: Exact diag-stage-4 geometry (pos-only 4×4 quad, 3×3 instanced) — should work
  1: World tile verts, pos-only attrib (stride=32, offset=0), 3×3 fake instances
  2: World tile verts, pos-only, real 63-tile instance data
  3: Full interleaved 6-attrib VAO (non-zero offsets), flat-red shader
  4: Same as 3 but DrawArraysInstanced (no EBO) — isolates EBO issue
  5: Full 6-attrib + EBO DrawElementsInstanced (same as demo_direct mode 1)

Diagnosis key:
  Stage 0 fails → environment broken (run diag.py first)
  Stage 1 fails → tile quad geometry bad (float layout issue)
  Stage 2 fails → instance data bad (wrong count / stride)
  Stage 3 fails → non-zero vertex attrib offsets broken
  Stage 4 passes but 5 fails → EBO issue
  Stage 5 passes → the bug is elsewhere in demo_direct/demo_scape
"""
import sys, ctypes, time
import numpy as np
import glm
from OpenGL import GL

sys.path.insert(0, ".")
from ambroflow.engine.window   import Window, InputEvent
from ambroflow.engine.shader   import Shader
from ambroflow.engine.buffer   import Buffer, VertexArray
from ambroflow.engine.camera   import Camera
from ambroflow.render.world    import WorldRenderer, _TILE_VERTS, _TILE_INDICES, _STRIDE_TILE, _STRIDE_INST
from ambroflow.world.map       import Realm, build_zone_from_ascii
import glfw

# ── test zone (9×7, 63 tiles) ─────────────────────────────────────────────────
_MAP = [
    "#########",
    "#,,,,,,,#",
    "#,S.S.S,#",
    "#,S@S.S,#",
    "#,S.S.S,#",
    "#,,,,,,,#",
    "#########",
]
_ZONE = build_zone_from_ascii("test", Realm.LAPIDUS, "Test", _MAP)

# ── shaders ───────────────────────────────────────────────────────────────────
# Minimal: only a_pos + i_offset (for stages 0-2)
_V_MIN = """
#version 410 core
layout(location=0) in vec3 a_pos;
layout(location=1) in vec3 i_offset;
uniform mat4 u_view;
uniform mat4 u_proj;
void main() {
    gl_Position = u_proj * u_view * vec4(a_pos + i_offset, 1.0);
}
"""
# Full 6-attrib (for stages 3-5) — flat red
_V_FULL = """
#version 410 core
layout(location=0) in vec3 a_pos;
layout(location=1) in vec2 a_uv;
layout(location=2) in vec3 a_normal;
layout(location=3) in vec3  i_offset;
layout(location=4) in float i_tile_id;
layout(location=5) in float i_height;
uniform mat4 u_view;
uniform mat4 u_proj;
void main() {
    vec3 world = a_pos + i_offset + vec3(0.0, i_height, 0.0);
    gl_Position = u_proj * u_view * vec4(world, 1.0);
}
"""
_F_RED = """
#version 410 core
out vec4 frag_color;
void main() { frag_color = vec4(1.0, 0.2, 0.2, 1.0); }
"""


def gl_drain(label: str) -> bool:
    """Drain all GL errors; return True if any found."""
    found = False
    while True:
        e = GL.glGetError()
        if e == GL.GL_NO_ERROR:
            break
        print(f"  GL ERROR at [{label}]: {hex(e)}")
        found = True
    if not found:
        print(f"  GL OK at [{label}]")
    return found


def main():
    win = Window("demo_min — SPACE=next  ESC=quit", 1280, 720)
    win.make_current()
    W, H = win.width, win.height

    gl_drain("context_init")

    sh_min  = Shader(_V_MIN, _F_RED)
    sh_full = Shader(_V_FULL, _F_RED)
    gl_drain("shader_compile")

    # ── stage 0: exact diag stage 4 geometry ─────────────────────────────────
    q3d_v = np.array([-2,0,-2,  2,0,-2,  2,0,2,  -2,0,2], dtype=np.float32)
    q3d_i = np.array([0,1,2, 0,2,3], dtype=np.uint32)
    offsets = []
    for row in range(3):
        for col in range(3):
            offsets += [col*5.0 - 5.0, 0.0, row*5.0 - 5.0]
    inst_diag = np.array(offsets, dtype=np.float32)

    vbo_diag  = Buffer(q3d_v,   GL.GL_STATIC_DRAW)
    ebo_diag  = Buffer(q3d_i,   GL.GL_STATIC_DRAW, target=GL.GL_ELEMENT_ARRAY_BUFFER)
    ivbo_diag = Buffer(inst_diag, GL.GL_STATIC_DRAW)

    vao0 = VertexArray()
    vao0.bind(); vbo_diag.bind(); ebo_diag.bind()
    vao0.attrib(0, 3, 12, 0)   # pos
    ivbo_diag.bind()
    vao0.attrib(1, 3, 12, 0)   # instance offset
    vao0.attrib_divisor(1, 1)
    vao0.unbind()
    gl_drain("vao0_setup")

    # ── stage 1: world tile verts, pos-only (stride=32, offset=0), 3×3 ───────
    tile_pos_only = _TILE_VERTS.flatten()  # 32 floats interleaved, but we only use pos
    vbo_tile  = Buffer(tile_pos_only, GL.GL_STATIC_DRAW)
    ebo_tile  = Buffer(_TILE_INDICES, GL.GL_STATIC_DRAW, target=GL.GL_ELEMENT_ARRAY_BUFFER)

    # Reuse diag instances (3×3 grid, offset=0 in instance attrib)
    vao1 = VertexArray()
    vao1.bind(); vbo_tile.bind(); ebo_tile.bind()
    vao1.attrib(0, 3, _STRIDE_TILE, 0)   # pos only, stride=32, offset=0
    ivbo_diag.bind()
    vao1.attrib(1, 3, 12, 0)   # diag instance offsets (stride=12, offset=0)
    vao1.attrib_divisor(1, 1)
    vao1.unbind()
    gl_drain("vao1_setup")

    # ── stage 2: world tile verts pos-only, real 63-tile world instances ──────
    world_inst = WorldRenderer._build_instances(_ZONE)
    inst_count = len(world_inst) // 5
    # Extract only xyz from each 5-float record to create a minimal offset buffer
    world_inst_reshape = world_inst.reshape(-1, 5)
    world_xyz = np.ascontiguousarray(world_inst_reshape[:, :3], dtype=np.float32)
    ivbo_world_xyz = Buffer(world_xyz.flatten(), GL.GL_STATIC_DRAW)

    vao2 = VertexArray()
    vao2.bind(); vbo_tile.bind(); ebo_tile.bind()
    vao2.attrib(0, 3, _STRIDE_TILE, 0)   # pos only, stride=32, offset=0
    ivbo_world_xyz.bind()
    vao2.attrib(1, 3, 12, 0)   # world xyz only (stride=12, offset=0)
    vao2.attrib_divisor(1, 1)
    vao2.unbind()
    gl_drain("vao2_setup")

    print(f"  World instance count: {inst_count}")
    print(f"  First 5 instances: {world_inst_reshape[:5, :3].tolist()}")

    # ── stage 3: full 6-attrib interleaved (non-zero offsets), DrawElements ──
    ivbo_full = Buffer(world_inst, GL.GL_STATIC_DRAW)

    vao3 = VertexArray()
    vao3.bind(); vbo_tile.bind(); ebo_tile.bind()
    vao3.attrib(0, 3, _STRIDE_TILE, 0)    # a_pos
    vao3.attrib(1, 2, _STRIDE_TILE, 12)   # a_uv    ← non-zero offset
    vao3.attrib(2, 3, _STRIDE_TILE, 20)   # a_normal ← non-zero offset
    ivbo_full.bind()
    vao3.attrib(3, 3, _STRIDE_INST, 0)    # i_offset
    vao3.attrib(4, 1, _STRIDE_INST, 12)   # i_tile_id ← non-zero
    vao3.attrib(5, 1, _STRIDE_INST, 16)   # i_height  ← non-zero
    vao3.attrib_divisor(3, 1)
    vao3.attrib_divisor(4, 1)
    vao3.attrib_divisor(5, 1)
    vao3.unbind()
    gl_drain("vao3_setup")

    # ── stage 4: same layout but DrawArraysInstanced (no EBO) ────────────────
    # Need explicit triangle list (not indexed)
    # Two triangles: [v0,v1,v2, v0,v2,v3] → 6 vertices (with duplication)
    tile_tris = np.array([
        # tri 0: v0, v1, v2
        -0.5, 0.0, -0.5,   0.0, 0.0,   0.0, 1.0, 0.0,
         0.5, 0.0, -0.5,   1.0, 0.0,   0.0, 1.0, 0.0,
         0.5, 0.0,  0.5,   1.0, 1.0,   0.0, 1.0, 0.0,
        # tri 1: v0, v2, v3
        -0.5, 0.0, -0.5,   0.0, 0.0,   0.0, 1.0, 0.0,
         0.5, 0.0,  0.5,   1.0, 1.0,   0.0, 1.0, 0.0,
        -0.5, 0.0,  0.5,   0.0, 1.0,   0.0, 1.0, 0.0,
    ], dtype=np.float32)
    vbo_tris = Buffer(tile_tris, GL.GL_STATIC_DRAW)

    vao4 = VertexArray()
    vao4.bind(); vbo_tris.bind()
    # No EBO here — plain array draw
    vao4.attrib(0, 3, _STRIDE_TILE, 0)
    vao4.attrib(1, 2, _STRIDE_TILE, 12)
    vao4.attrib(2, 3, _STRIDE_TILE, 20)
    ivbo_full.bind()
    vao4.attrib(3, 3, _STRIDE_INST, 0)
    vao4.attrib(4, 1, _STRIDE_INST, 12)
    vao4.attrib(5, 1, _STRIDE_INST, 16)
    vao4.attrib_divisor(3, 1)
    vao4.attrib_divisor(4, 1)
    vao4.attrib_divisor(5, 1)
    vao4.unbind()
    gl_drain("vao4_setup")

    # stage 5 reuses vao3 (same as demo_direct mode 1)

    # ── camera ────────────────────────────────────────────────────────────────
    cam_diag = Camera(aspect=W/H, fov_deg=35.0, pitch_deg=35.0, distance=18.0)
    cam_diag.target = glm.vec3(0.0, 0.0, 0.0)
    cam_diag.update(0.016)

    cam_world = Camera(aspect=W/H, fov_deg=35.0, pitch_deg=35.0, distance=12.0)
    sx, sz = _ZONE.player_spawn
    cam_world.target = glm.vec3(float(sx), 0.0, float(sz))
    cam_world.update(0.016)

    STAGES = 6
    labels = [
        "0: Diag stage-4 equivalent (4×4 quad, 3×3 instances) — MUST work",
        "1: World tile verts (pos-only, stride=32 offset=0), 3×3 instances",
        "2: World tile verts (pos-only), real 63-tile instances",
        "3: Full 6-attrib interleaved (non-zero offsets) + EBO",
        "4: Full 6-attrib interleaved + DrawArraysInstanced (no EBO)",
        "5: Identical to demo_direct mode 1 (full 6-attrib + EBO)",
    ]
    stage = 0
    prev_space = False

    print(f"\n=== demo_min ===  SPACE=next  ESC=quit")
    print(f"Stage {stage}: {labels[stage]}")

    while not win.should_close():
        dt = win.begin_frame()
        events = win.consume_events()
        for ev in events:
            if ev == InputEvent.CANCEL:
                _cleanup(win); return

        space = bool(glfw.get_key(win._handle, glfw.KEY_SPACE) == glfw.PRESS)
        if space and not prev_space:
            stage = (stage + 1) % STAGES
            print(f"\nStage {stage}: {labels[stage]}")
        prev_space = space

        cam_diag.update(dt)
        cam_world.update(dt)

        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glViewport(0, 0, W, H)
        GL.glClearColor(0.05, 0.05, 0.15, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)

        if stage == 0:
            sh_min.use()
            sh_min["u_view"] = cam_diag.view
            sh_min["u_proj"] = cam_diag.proj
            vao0.bind()
            GL.glDrawElementsInstanced(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
                                        ctypes.c_void_p(0), 9)
            vao0.unbind()

        elif stage == 1:
            sh_min.use()
            sh_min["u_view"] = cam_diag.view
            sh_min["u_proj"] = cam_diag.proj
            vao1.bind()
            GL.glDrawElementsInstanced(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
                                        ctypes.c_void_p(0), 9)
            vao1.unbind()

        elif stage == 2:
            sh_min.use()
            sh_min["u_view"] = cam_world.view
            sh_min["u_proj"] = cam_world.proj
            vao2.bind()
            GL.glDrawElementsInstanced(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
                                        ctypes.c_void_p(0), inst_count)
            vao2.unbind()

        elif stage == 3:
            sh_full.use()
            sh_full["u_view"] = cam_world.view
            sh_full["u_proj"] = cam_world.proj
            vao3.bind()
            GL.glDrawElementsInstanced(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
                                        ctypes.c_void_p(0), inst_count)
            vao3.unbind()

        elif stage == 4:
            sh_full.use()
            sh_full["u_view"] = cam_world.view
            sh_full["u_proj"] = cam_world.proj
            vao4.bind()
            GL.glDrawArraysInstanced(GL.GL_TRIANGLES, 0, 6, inst_count)
            vao4.unbind()

        elif stage == 5:
            sh_full.use()
            sh_full["u_view"] = cam_world.view
            sh_full["u_proj"] = cam_world.proj
            vao3.bind()  # same as stage 3 but explicit draw
            GL.glDrawElementsInstanced(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
                                        ctypes.c_void_p(0), inst_count)
            vao3.unbind()

        # drain errors once per second-ish (only on first few frames)
        win.end_frame()

    _cleanup(win)


def _cleanup(win):
    win.destroy()


if __name__ == "__main__":
    main()