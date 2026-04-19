"""
mini_smoke.py — Three-stage matrix diagnostic.  SPACE=next  ESC=quit

Stage 0: Hardcoded NDC triangle, no uniforms — confirmed working
Stage 1: Same hardcoded triangle, multiplied by identity u_view/u_proj — should look identical
Stage 2: Same hardcoded triangle, multiplied by REAL camera matrices (lookAt + perspective)
         Camera looks at origin from above — triangle is in XZ plane at Y=0

Diagnosis:
  Stage 1 blank → matrix uniform upload is broken (np.array path wrong)
  Stage 2 blank → real camera matrices put geometry out of frustum
  Both work    → issue is in VBO / instance setup in demo_min
"""
import sys, ctypes
import numpy as np
import glm
import glfw
from OpenGL import GL

sys.path.insert(0, ".")
from ambroflow.engine.window import Window, InputEvent
from ambroflow.engine.shader import Shader
from ambroflow.engine.buffer import Buffer, VertexArray
from ambroflow.engine.camera import Camera

# ── shaders ───────────────────────────────────────────────────────────────────

# Stage 0: no uniforms
_V0 = """
#version 410 core
void main() {
    vec2 pos[3];
    pos[0] = vec2(-0.9, -0.9);
    pos[1] = vec2( 0.9, -0.9);
    pos[2] = vec2( 0.0,  0.9);
    gl_Position = vec4(pos[gl_VertexID], 0.0, 1.0);
}
"""

# Stage 1: identity matrices applied (result must equal stage 0)
_V1 = """
#version 410 core
uniform mat4 u_view;
uniform mat4 u_proj;
void main() {
    vec2 pos[3];
    pos[0] = vec2(-0.9, -0.9);
    pos[1] = vec2( 0.9, -0.9);
    pos[2] = vec2( 0.0,  0.9);
    gl_Position = u_proj * u_view * vec4(pos[gl_VertexID], 0.0, 1.0);
}
"""

# Stage 2: real 3D geometry + real camera matrices
_V2 = """
#version 410 core
layout(location=0) in vec3 a_pos;
uniform mat4 u_view;
uniform mat4 u_proj;
void main() { gl_Position = u_proj * u_view * vec4(a_pos, 1.0); }
"""

_F_RED = """
#version 410 core
out vec4 c;
void main() { c = vec4(1.0, 0.2, 0.2, 1.0); }
"""
_F_GREEN = """
#version 410 core
out vec4 c;
void main() { c = vec4(0.2, 0.9, 0.3, 1.0); }
"""


def main():
    win = Window("mini_smoke2 — SPACE=next  ESC=quit", 960, 540)
    win.make_current()
    W, H = win.width, win.height

    print(f"GL: {GL.glGetString(GL.GL_VERSION)}")
    print(f"Renderer: {GL.glGetString(GL.GL_RENDERER)}")

    sh0 = Shader(_V0, _F_RED)
    sh1 = Shader(_V1, _F_RED)
    sh2 = Shader(_V2, _F_GREEN)

    # Dummy VAO (required for core profile even with no attribs)
    vao_null = GL.glGenVertexArrays(1)

    # Stage 2: 4×4 ground quad at Y=0 (same as diag stage 3)
    q3d = np.array([-2,0,-2,  2,0,-2,  2,0,2,  -2,0,2], dtype=np.float32)
    qidx = np.array([0,1,2, 0,2,3], dtype=np.uint32)
    vbo3 = Buffer(q3d,  GL.GL_STATIC_DRAW)
    ebo3 = Buffer(qidx, GL.GL_STATIC_DRAW, target=GL.GL_ELEMENT_ARRAY_BUFFER)
    vao2 = VertexArray()
    vao2.bind(); vbo3.bind(); ebo3.bind()
    vao2.attrib(0, 3, 12, 0)
    vao2.unbind()

    # Camera for stages 1 and 2 — identity vs real
    cam = Camera(aspect=W/H, fov_deg=35.0, pitch_deg=35.0, distance=18.0)
    cam.target = glm.vec3(0.0, 0.0, 0.0)
    cam.update(0.016)

    # Print matrices for inspection
    view = cam.view
    proj = cam.proj
    view_np = np.array(view, dtype=np.float32)
    proj_np = np.array(proj, dtype=np.float32)
    print(f"\ncam.view (as numpy):\n{view_np}")
    print(f"\ncam.proj (as numpy, first col):\n{proj_np[:,0]}")
    print(f"cam.proj diagonal: {proj_np[0,0]:.3f}, {proj_np[1,1]:.3f}, {proj_np[2,2]:.3f}, {proj_np[3,3]:.3f}")

    # Direct GLM element access — glm mat[col][row]
    print("\ncam.view direct GLM access m[col][row]:")
    for c in range(4):
        row = [float(view[c][r]) for r in range(4)]
        print(f"  col{c}: {row}")

    # bytes() path
    view_bytes = np.frombuffer(bytes(view), dtype=np.float32)
    print(f"\nbytes(cam.view) as floats:\n{view_bytes.reshape(4,4)}")

    # What index 14 (col3[2] = tz) actually holds
    print(f"\nDirect: view[3][2] = {float(view[3][2]):.4f}  (should be ~18)")
    print(f"Direct: view[2][3] = {float(view[2][3]):.4f}  (should be ~0)")

    STAGES = 3
    labels = [
        "0: Hardcoded NDC triangle, NO uniforms (reference)",
        "1: Same triangle × identity u_view/u_proj — must match stage 0",
        "2: 4×4 ground quad × real camera matrices (like diag stage 3)",
    ]
    stage = 0
    prev_space = False
    print(f"\nStage {stage}: {labels[stage]}")

    while not win.should_close():
        dt = win.begin_frame()
        events = win.consume_events()
        for ev in events:
            if ev == InputEvent.CANCEL:
                win.destroy(); return

        space = bool(glfw.get_key(win._handle, glfw.KEY_SPACE) == glfw.PRESS)
        if space and not prev_space:
            stage = (stage + 1) % STAGES
            print(f"Stage {stage}: {labels[stage]}")
        prev_space = space

        cam.update(dt)
        W, H = win.width, win.height

        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glViewport(0, 0, W, H)
        GL.glClearColor(0.05, 0.05, 0.18, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)

        if stage == 0:
            sh0.use()
            GL.glBindVertexArray(vao_null)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            GL.glBindVertexArray(0)

        elif stage == 1:
            sh1.use()
            sh1["u_view"] = glm.mat4(1.0)   # identity
            sh1["u_proj"] = glm.mat4(1.0)   # identity
            GL.glBindVertexArray(vao_null)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            GL.glBindVertexArray(0)

        elif stage == 2:
            sh2.use()
            sh2["u_view"] = cam.view
            sh2["u_proj"] = cam.proj
            vao2.bind()
            GL.glDrawElements(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
                              ctypes.c_void_p(0))
            vao2.unbind()

        e = GL.glGetError()
        if e != GL.GL_NO_ERROR:
            print(f"  GL error stage {stage}: {hex(e)}")

        win.end_frame()

    win.destroy()


if __name__ == "__main__":
    main()