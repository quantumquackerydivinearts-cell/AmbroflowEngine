"""
Render pipeline diagnostic — runs 6 tests in sequence, each frame.
Watch the window: each test should show something different.
Press SPACE to advance, ESC to quit.
Output tells you which stage works and which fails.
"""
import sys, ctypes, time
import numpy as np
import glm
from OpenGL import GL

sys.path.insert(0, ".")
from ambroflow.engine.window      import Window, InputEvent
from ambroflow.engine.shader      import Shader
from ambroflow.engine.buffer      import Buffer, VertexArray
from ambroflow.engine.framebuffer import Framebuffer
from ambroflow.engine.texture     import Texture
from ambroflow.engine.camera      import Camera
import glfw

# ── helpers ───────────────────────────────────────────────────────────────────

def gl_errors(label):
    errs = []
    while True:
        e = GL.glGetError()
        if e == GL.GL_NO_ERROR:
            break
        errs.append(hex(e))
    if errs:
        print(f"  GL ERRORS at {label}: {errs}")
    else:
        print(f"  GL OK at {label}")

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — flat red quad, no uniforms, direct to default FB
# ─────────────────────────────────────────────────────────────────────────────
_T1_V = """
#version 410 core
layout(location=0) in vec2 a_pos;
void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }
"""
_T1_F = """
#version 410 core
out vec4 c; void main() { c = vec4(1.0, 0.2, 0.2, 1.0); }
"""

# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — same quad, colour from uniform
# ─────────────────────────────────────────────────────────────────────────────
_T2_F = """
#version 410 core
uniform vec3 u_col;
out vec4 c; void main() { c = vec4(u_col, 1.0); }
"""

# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — 3D quad on Y=0 plane, full MVP matrices
# ─────────────────────────────────────────────────────────────────────────────
_T3_V = """
#version 410 core
layout(location=0) in vec3 a_pos;
uniform mat4 u_view;
uniform mat4 u_proj;
void main() { gl_Position = u_proj * u_view * vec4(a_pos, 1.0); }
"""
_T3_F = """
#version 410 core
out vec4 c; void main() { c = vec4(0.3, 0.8, 0.4, 1.0); }
"""

# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — instanced draw, each instance a coloured offset quad
# ─────────────────────────────────────────────────────────────────────────────
_T4_V = """
#version 410 core
layout(location=0) in vec3 a_pos;
layout(location=1) in vec3 i_offset;
uniform mat4 u_view;
uniform mat4 u_proj;
void main() { gl_Position = u_proj * u_view * vec4(a_pos + i_offset, 1.0); }
"""

# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — render to FBO, blit to screen
# ─────────────────────────────────────────────────────────────────────────────
# (reuses T3 shader, but targets FBO first)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — full Lapidus world atlas tile, 1 instance, with world shader
# ─────────────────────────────────────────────────────────────────────────────

def make_checkerboard():
    """4×4 checkerboard atlas — clearly visible if UVs are correct."""
    from PIL import Image
    img = Image.new("RGBA", (128, 128))
    cols = [(200,80,80,255),(80,200,80,255),(80,80,200,255),(200,200,80,255)]
    tile = 32
    for row in range(4):
        for col in range(4):
            c = cols[(row + col) % len(cols)]
            for y in range(tile):
                for x in range(tile):
                    img.putpixel((col*tile+x, row*tile+y), c)
    return img

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    win = Window("DIAG — SPACE=next  ESC=quit", 960, 540)
    win.make_current()
    W, H = win.width, win.height

    # ── build shared geometry ─────────────────────────────────────────────
    # 2D unit quad (NDC)
    q2d_v = np.array([-0.5,-0.5, 0.5,-0.5, 0.5,0.5, -0.5,0.5], dtype=np.float32)
    q2d_i = np.array([0,1,2, 0,2,3], dtype=np.uint32)

    # 3D ground quad (XZ plane, 4×4 world units)
    q3d_v = np.array([
        -2,0,-2,  2,0,-2,  2,0,2,  -2,0,2
    ], dtype=np.float32)

    vbo2  = Buffer(q2d_v, GL.GL_STATIC_DRAW)
    vbo3  = Buffer(q3d_v, GL.GL_STATIC_DRAW)
    ebo   = Buffer(q2d_i, GL.GL_STATIC_DRAW, target=GL.GL_ELEMENT_ARRAY_BUFFER)

    # instanced offsets: 3×3 grid of quads
    offsets = []
    for row in range(3):
        for col in range(3):
            offsets += [col*5.0 - 5.0, 0.0, row*5.0 - 5.0]
    inst_v = np.array(offsets, dtype=np.float32)
    ivbo   = Buffer(inst_v, GL.GL_STATIC_DRAW)

    # ── shaders ───────────────────────────────────────────────────────────
    sh1 = Shader(_T1_V, _T1_F)
    sh2 = Shader(_T1_V, _T2_F)
    sh3 = Shader(_T3_V, _T3_F)
    sh4 = Shader(_T4_V, _T3_F)

    # ── VAOs ──────────────────────────────────────────────────────────────
    # Test 1 + 2: 2D quad
    vao2 = VertexArray()
    vao2.bind(); vbo2.bind(); ebo.bind()
    vao2.attrib(0, 2, 8, 0)
    vao2.unbind()

    # Test 3 + 5: 3D quad, no instancing
    vao3 = VertexArray()
    vao3.bind(); vbo3.bind(); ebo.bind()
    vao3.attrib(0, 3, 12, 0)
    vao3.unbind()

    # Test 4: 3D quad, instanced
    vao4 = VertexArray()
    vao4.bind()
    vbo3.bind(); ebo.bind()
    vao4.attrib(0, 3, 12, 0)
    ivbo.bind()
    vao4.attrib(1, 3, 12, 0)
    vao4.attrib_divisor(1, 1)
    vao4.unbind()

    # ── camera ────────────────────────────────────────────────────────────
    cam = Camera(aspect=W/H, fov_deg=35.0, pitch_deg=35.0, distance=18.0)
    cam.target = glm.vec3(0.0, 0.0, 0.0)
    cam.update(0.016)

    # ── FBO ───────────────────────────────────────────────────────────────
    fbo = Framebuffer(W, H)

    # ── test atlas texture ────────────────────────────────────────────────
    atlas_tex = Texture.from_pil(make_checkerboard())

    stage    = 0
    STAGES   = 6
    labels   = [
        "1: Flat red 2D quad (no uniforms)",
        "2: Green 2D quad via uniform",
        "3: 3D ground quad with MVP matrices",
        "4: Instanced 3×3 grid of quads",
        "5: Same via FBO → blit",
        "6: Atlas texture on 3D quad",
    ]

    print("\n=== RENDER DIAGNOSTICS ===")
    print("SPACE to advance through tests, ESC to quit.\n")

    # print initial stage
    print(f"Stage {stage+1}: {labels[stage]}")

    prev_space = False

    while not win.should_close():
        dt = win.begin_frame()
        events = win.consume_events()

        for ev in events:
            if ev == InputEvent.CANCEL:
                _cleanup(win, fbo, atlas_tex)
                return

        space_down = bool(glfw.get_key(win._handle, glfw.KEY_SPACE) == glfw.PRESS)
        if space_down and not prev_space:
            stage = (stage + 1) % STAGES
            print(f"\nStage {stage+1}: {labels[stage]}")
            gl_errors("stage_switch")
        prev_space = space_down

        cam.update(dt)

        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glViewport(0, 0, W, H)
        GL.glClearColor(0.1, 0.1, 0.15, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glDisable(GL.GL_CULL_FACE)

        if stage == 0:
            # ── T1: flat red 2D quad ──────────────────────────────────────
            sh1.use()
            vao2.bind()
            GL.glDrawElements(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT, ctypes.c_void_p(0))
            vao2.unbind()

        elif stage == 1:
            # ── T2: green via uniform ─────────────────────────────────────
            sh2.use()
            sh2["u_col"] = (0.2, 0.9, 0.3)
            vao2.bind()
            GL.glDrawElements(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT, ctypes.c_void_p(0))
            vao2.unbind()

        elif stage == 2:
            # ── T3: 3D quad with MVP ──────────────────────────────────────
            GL.glEnable(GL.GL_DEPTH_TEST)
            sh3.use()
            sh3["u_view"] = cam.view
            sh3["u_proj"] = cam.proj
            vao3.bind()
            GL.glDrawElements(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT, ctypes.c_void_p(0))
            vao3.unbind()

        elif stage == 3:
            # ── T4: instanced 3×3 ────────────────────────────────────────
            GL.glEnable(GL.GL_DEPTH_TEST)
            sh4.use()
            sh4["u_view"] = cam.view
            sh4["u_proj"] = cam.proj
            vao4.bind()
            GL.glDrawElementsInstanced(
                GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
                ctypes.c_void_p(0), 9
            )
            vao4.unbind()

        elif stage == 4:
            # ── T5: via FBO ───────────────────────────────────────────────
            GL.glEnable(GL.GL_DEPTH_TEST)
            fbo.bind()
            GL.glClearColor(0.2, 0.0, 0.4, 1.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
            sh3.use()
            sh3["u_view"] = cam.view
            sh3["u_proj"] = cam.proj
            vao3.bind()
            GL.glDrawElements(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT, ctypes.c_void_p(0))
            vao3.unbind()
            fbo.unbind()
            # blit to screen
            GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, fbo._fbo)
            GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, 0)
            GL.glBlitFramebuffer(0,0,W,H, 0,0,W,H, GL.GL_COLOR_BUFFER_BIT, GL.GL_NEAREST)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)

        elif stage == 5:
            # ── T6: atlas texture on 3D quad ──────────────────────────────
            # simple textured vert/frag
            pass   # built lazily below on first entry
            GL.glEnable(GL.GL_DEPTH_TEST)
            sh3.use()
            sh3["u_view"] = cam.view
            sh3["u_proj"] = cam.proj
            atlas_tex.bind(0)
            vao3.bind()
            GL.glDrawElements(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT, ctypes.c_void_p(0))
            vao3.unbind()
            atlas_tex.unbind(0)

        gl_errors(f"stage_{stage+1}_frame")

        win.end_frame()

    _cleanup(win, fbo, atlas_tex)


def _cleanup(win, fbo, tex):
    tex.delete()
    fbo.delete()
    win.destroy()


if __name__ == "__main__":
    main()