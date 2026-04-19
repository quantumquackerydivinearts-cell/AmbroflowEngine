"""
GL Stack Smoke Test
===================
Opens a glfw window, clears to the Lapidus sky colour (violet-indigo),
runs the full render pipeline for ~3 seconds, then exits cleanly.

Run from repo root:
    python smoke_gl.py

Expected: A window opens, shows an animated violet-indigo sky with a
dialogue panel at the bottom, closes after 3 s with no exceptions.
Confirms: glfw, PyOpenGL, PyGLM all initialised and cooperating.
"""

import sys
import time

import numpy as np
from OpenGL import GL

sys.path.insert(0, str(__file__).replace("smoke_gl.py", ""))

from ambroflow.engine.window      import Window, InputEvent
from ambroflow.engine.shader      import Shader
from ambroflow.engine.texture     import Texture
from ambroflow.engine.camera      import Camera
from ambroflow.engine.framebuffer import Framebuffer
from ambroflow.engine.buffer      import VertexArray
from ambroflow.render.post        import PostProcessor
from ambroflow.render.ui          import UIRenderer

try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False


# ── Sky clear shader ──────────────────────────────────────────────────────────

_CLEAR_VERT = """
#version 410 core
out vec2 v_uv;
void main() {
    vec2 p;
    p.x = float((gl_VertexID & 1) << 2) - 1.0;
    p.y = float((gl_VertexID & 2) << 1) - 1.0;
    v_uv = p * 0.5 + 0.5;
    gl_Position = vec4(p, 0.0, 1.0);
}
"""

_CLEAR_FRAG = """
#version 410 core
in vec2 v_uv;
uniform float u_time;
out vec4 frag_color;
void main() {
    vec3 top    = vec3(0.10, 0.08, 0.22);
    vec3 bottom = vec3(0.22, 0.18, 0.36);
    float t     = v_uv.y + sin(u_time * 0.4) * 0.03;
    frag_color  = vec4(mix(bottom, top, t), 1.0);
}
"""


def make_dialogue_panel(w: int, h: int, text: str) -> "Image.Image":
    img  = Image.new("RGBA", (w, h), (20, 18, 32, 220))
    draw = ImageDraw.Draw(img)
    draw.rectangle([4, 4, w - 5, h - 5], outline=(160, 140, 200, 255), width=2)
    draw.text((16, 16), text, fill=(230, 220, 255, 255))
    return img


def main() -> None:
    win = Window("AmbroflowEngine — GL smoke test", 1280, 720)
    win.make_current()

    w, h = win.width, win.height

    cam  = Camera(aspect=w / h)
    fbo  = Framebuffer(w, h)
    post = PostProcessor(w, h, realm="lapidus")
    ui   = UIRenderer()

    clear_shader = Shader(_CLEAR_VERT, _CLEAR_FRAG)
    empty_vao    = VertexArray()

    dbox_tex = None
    if _PIL:
        dbox_pil = make_dialogue_panel(800, 120,
                                       "Lapidus. The Overworld.  GL stack: OK.")
        dbox_tex = Texture.from_pil(dbox_pil)

    t0    = time.perf_counter()
    frame = 0

    while not win.should_close():
        dt      = win.begin_frame()
        elapsed = time.perf_counter() - t0
        events  = win.consume_events()

        for ev in events:
            if ev in (InputEvent.QUIT, InputEvent.CANCEL):
                _cleanup(win, fbo, post, ui, clear_shader, empty_vao, dbox_tex)
                return

        if elapsed > 3.0:
            _cleanup(win, fbo, post, ui, clear_shader, empty_vao, dbox_tex)
            print(f"[smoke_gl] OK — {frame} frames in {elapsed:.2f}s "
                  f"({frame / elapsed:.0f} fps)")
            return

        # Resize tracking
        nw, nh = win.width, win.height
        if nw != w or nh != h:
            w, h = nw, nh
            fbo.resize(w, h)
            post.resize(w, h)
            cam.resize(w / h)

        cam.update(dt)

        # ── Scene → FBO ───────────────────────────────────────────────────
        fbo.bind()
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        clear_shader.use()
        clear_shader["u_time"] = elapsed
        empty_vao.bind()
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        empty_vao.unbind()
        fbo.unbind()

        # ── Post ──────────────────────────────────────────────────────────
        post.process(fbo, time=elapsed)
        post.blit_to_screen()

        # ── UI overlay ────────────────────────────────────────────────────
        GL.glViewport(0, 0, w, h)
        if dbox_tex:
            ui.add(dbox_tex, ndc_rect=(-0.6, -0.95, 0.6, -0.60), opacity=0.92)
        ui.draw()
        ui.clear()

        win.end_frame()
        frame += 1


def _cleanup(win, fbo, post, ui, shader, vao, dbox_tex):
    if dbox_tex:
        dbox_tex.delete()
    vao.delete()
    shader.delete()
    ui.delete()
    post.delete()
    fbo.delete()
    win.destroy()


if __name__ == "__main__":
    main()