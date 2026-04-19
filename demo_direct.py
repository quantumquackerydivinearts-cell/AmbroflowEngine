"""
Direct tile render — isolates world shader vs VAO/EBO.

Presses 1/2/3 to switch shaders:
  1 = flat red   (same vertex layout as world, no uniforms except MVP)
  2 = tile-id colour  (colours each tile by ID, confirms instance data reaches shader)
  3 = full lapidus world shader

If 1 shows tiles but 3 doesn't → world shader bug
If 1 shows nothing → VAO/EBO/instance-buffer bug
"""
import sys, ctypes, time
import glm, numpy as np
from OpenGL import GL
import glfw

sys.path.insert(0, ".")
from ambroflow.engine.window   import Window, InputEvent
from ambroflow.engine.camera   import Camera
from ambroflow.engine.shader   import Shader
from ambroflow.engine.texture  import Texture
from ambroflow.engine.buffer   import Buffer, VertexArray
from ambroflow.render.world    import WorldRenderer, LAPIDUS_LIGHTING, _TILE_VERTS, _TILE_INDICES, _STRIDE_TILE, _STRIDE_INST
from ambroflow.world.map       import Realm, build_zone_from_ascii

from PIL import Image

# ── tiny zone ─────────────────────────────────────────────────────────────────
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

# ── solid atlas ────────────────────────────────────────────────────────────────
def make_atlas():
    img = Image.new("RGBA", (128, 32))
    for i, col in enumerate([(150,140,130,255),(70,120,50,255),(120,90,60,255),(50,50,70,255)]):
        for y in range(32):
            for x in range(32):
                img.putpixel((i*32+x, y), col)
    return img

# ── shader 1: flat red, same vertex layout, just MVP ─────────────────────────
_SH1_V = """
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
_SH1_F = """
#version 410 core
out vec4 c;
void main() { c = vec4(1.0, 0.2, 0.2, 1.0); }
"""

# ── shader 2: colour by tile_id ───────────────────────────────────────────────
_SH2_V = _SH1_V  # same vertex stage
_SH2_F = """
#version 410 core
// tile_id passed via flat interpolation from vert
flat in float v_tile_id;
out vec4 c;
void main() {
    float t = mod(v_tile_id, 4.0) / 4.0;
    c = vec4(t, 1.0-t, 0.3, 1.0);
}
"""
_SH2_V2 = """
#version 410 core
layout(location=0) in vec3 a_pos;
layout(location=1) in vec2 a_uv;
layout(location=2) in vec3 a_normal;
layout(location=3) in vec3  i_offset;
layout(location=4) in float i_tile_id;
layout(location=5) in float i_height;
uniform mat4 u_view;
uniform mat4 u_proj;
flat out float v_tile_id;
void main() {
    v_tile_id = i_tile_id;
    vec3 world = a_pos + i_offset + vec3(0.0, i_height, 0.0);
    gl_Position = u_proj * u_view * vec4(world, 1.0);
}
"""


def main():
    win = Window("Shader isolation — 1=flat  2=tile-id  3=lapidus  ESC=quit", 1280, 720)
    win.make_current()
    W, H = win.width, win.height

    atlas   = Texture.from_pil(make_atlas())
    cam     = Camera(aspect=W/H, fov_deg=35.0, pitch_deg=35.0, distance=12.0)
    sx, sz  = _ZONE.player_spawn
    cam.target = glm.vec3(float(sx), 0.0, float(sz))

    # Build shaders
    sh1 = Shader(_SH1_V,  _SH1_F)
    sh2 = Shader(_SH2_V2, _SH2_F)

    from pathlib import Path
    _SHADERS = Path("ambroflow/engine/shaders")
    sh3 = Shader(
        (_SHADERS / "world.vert").read_text(),
        (_SHADERS / "lapidus_world.frag").read_text(),
    )

    # Build VAO identical to WorldRenderer
    vbo_tile = Buffer(_TILE_VERTS.flatten(), GL.GL_STATIC_DRAW)
    ebo      = Buffer(_TILE_INDICES, GL.GL_STATIC_DRAW, target=GL.GL_ELEMENT_ARRAY_BUFFER)

    # Build instance data from zone
    from ambroflow.render.world import WorldRenderer
    instances = WorldRenderer._build_instances(_ZONE)
    instance_count = len(instances) // 5
    vbo_inst = Buffer(instances, GL.GL_STATIC_DRAW)

    print(f"Instance count: {instance_count}")
    print(f"Player spawn: {_ZONE.player_spawn}")
    print(f"Zone size: {_ZONE.width}×{_ZONE.height}")

    vao = VertexArray()
    vao.bind()
    vbo_tile.bind(); ebo.bind()
    s = _STRIDE_TILE
    vao.attrib(0, 3, s,  0)   # a_pos
    vao.attrib(1, 2, s, 12)   # a_uv
    vao.attrib(2, 3, s, 20)   # a_normal
    vbo_inst.bind()
    si = _STRIDE_INST
    vao.attrib(3, 3, si,  0)   # i_offset
    vao.attrib(4, 1, si, 12)   # i_tile_id
    vao.attrib(5, 1, si, 16)   # i_height
    vao.attrib_divisor(3, 1)
    vao.attrib_divisor(4, 1)
    vao.attrib_divisor(5, 1)
    vao.unbind()

    mode    = 1
    labels  = {1:"flat red", 2:"tile-id colour", 3:"lapidus world"}
    print(f"Mode {mode}: {labels[mode]}  (press 1/2/3 to switch)")

    while not win.should_close():
        dt     = win.begin_frame()
        events = win.consume_events()

        for ev in events:
            if ev == InputEvent.CANCEL:
                _cleanup(win, vao, vbo_tile, vbo_inst, ebo, atlas, sh1, sh2, sh3)
                return

        h = win._handle
        for key, m in [(glfw.KEY_1, 1), (glfw.KEY_2, 2), (glfw.KEY_3, 3)]:
            if glfw.get_key(h, key) == glfw.PRESS:
                if m != mode:
                    mode = m
                    print(f"Mode {mode}: {labels[mode]}")

        nW, nH = win.width, win.height
        if nW != W or nH != H:
            W, H = nW, nH
            cam.resize(W/H)
        cam.update(dt)

        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glViewport(0, 0, W, H)
        GL.glClearColor(0.1, 0.08, 0.18, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)

        if mode == 1:
            sh1.use()
            sh1["u_view"] = cam.view
            sh1["u_proj"] = cam.proj
        elif mode == 2:
            sh2.use()
            sh2["u_view"] = cam.view
            sh2["u_proj"] = cam.proj
        elif mode == 3:
            sh3.use()
            sh3["u_view"] = cam.view
            sh3["u_proj"] = cam.proj
            sh3["u_atlas_size"] = (4.0, 1.0)
            sh3["u_time"] = 0.0
            for name, val in LAPIDUS_LIGHTING.items():
                sh3[name] = val
            atlas.bind(0)
            sh3["u_atlas"] = 0

        vao.bind()
        GL.glDrawElementsInstanced(
            GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT,
            ctypes.c_void_p(0), instance_count
        )
        vao.unbind()

        if mode == 3:
            atlas.unbind(0)

        err = GL.glGetError()
        if err != GL.GL_NO_ERROR:
            print(f"GL error: {hex(err)}")

        win.end_frame()

    _cleanup(win, vao, vbo_tile, vbo_inst, ebo, atlas, sh1, sh2, sh3)


def _cleanup(win, vao, vt, vi, ebo, atlas, s1, s2, s3):
    vao.delete(); vt.delete(); vi.delete(); ebo.delete()
    atlas.delete(); s1.delete(); s2.delete(); s3.delete()
    win.destroy()


if __name__ == "__main__":
    main()