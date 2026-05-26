"""
tests/test_renderer_compiled.py
================================
Validates the compiled tile renderer engine (kobra_compiled/renderer_engine.py)
emitted from tile_renderer.ko via the Kobra compiler.
All tests run headless (ctx=None) — no GL context required.
"""
from __future__ import annotations

import pytest

from ambroflow.kobra_compiled.renderer_engine import (
    RendererDecl,
    GLTexDecl,
    GLBufferDecl,
    ShaderDecl,
    DrawCallDecl,
    renderer_read_eval,
    renderer_index_el,
    shader_compile_eval,
    shader_el,
    tex_upload_eval,
    tex_upload_el,
    buf_upload_eval,
    buf_upload_el,
    draw_call_eval,
    draw_call_el,
    frame_render_eval,
    renderer_shi_wu_ung,
    renderer_ke_wu_ung,
    renderer_ep_em,
    KobraSuccess,
    KobraError,
)


# ── RendererDecl hierarchy ────────────────────────────────────────────────────

class TestRendererDeclHierarchy:
    def test_tex_is_renderer_decl(self):
        t = GLTexDecl()
        assert isinstance(t, RendererDecl)
        assert t.tongue_eq == "MavoGlTexWuUng"

    def test_buf_is_renderer_decl(self):
        b = GLBufferDecl()
        assert isinstance(b, RendererDecl)
        assert b.tongue_eq == "MavoGlBufWuUng"

    def test_shader_is_renderer_decl(self):
        s = ShaderDecl()
        assert isinstance(s, RendererDecl)
        assert s.tongue_eq == "MavoShaderWuUng"

    def test_draw_call_is_renderer_decl(self):
        c = DrawCallDecl()
        assert isinstance(c, RendererDecl)
        assert c.tongue_eq == "MavoDrawCallWuUng"


# ── renderer_read_eval ────────────────────────────────────────────────────────

class TestRendererReadEval:
    def test_valid_pipeline_returns_true(self):
        assert renderer_read_eval(
            GLTexDecl(), GLBufferDecl(), ShaderDecl(), [DrawCallDecl()]
        ) is True

    def test_empty_draw_calls_valid(self):
        assert renderer_read_eval(GLTexDecl(), GLBufferDecl(), ShaderDecl(), []) is True

    def test_wrong_tex_raises(self):
        with pytest.raises(KobraError):
            renderer_read_eval("not_tex", GLBufferDecl(), ShaderDecl(), [])

    def test_wrong_buf_raises(self):
        with pytest.raises(KobraError):
            renderer_read_eval(GLTexDecl(), "not_buf", ShaderDecl(), [])

    def test_wrong_shader_raises(self):
        with pytest.raises(KobraError):
            renderer_read_eval(GLTexDecl(), GLBufferDecl(), "not_shader", [])


# ── ShaderDecl / shader_el ────────────────────────────────────────────────────

class TestShaderEl:
    def test_headless_compile_sets_program(self):
        s = shader_el(ShaderDecl(), ctx=None)
        assert s.program == "headless"

    def test_returns_shader_decl(self):
        s = shader_el(ShaderDecl())
        assert isinstance(s, ShaderDecl)

    def test_default_vertex_src_has_gl_position(self):
        assert "gl_Position" in ShaderDecl().vertex_src

    def test_default_fragment_src_has_frag_color(self):
        assert "frag_color" in ShaderDecl().fragment_src

    def test_compile_eval_same_as_el(self):
        s1 = shader_el(ShaderDecl())
        s2 = shader_compile_eval(ShaderDecl(), None)
        assert s1.program == s2.program


# ── tex_upload_el / tex_upload_eval ──────────────────────────────────────────

class TestTexUploadEl:
    def test_headless_sets_handle(self):
        tex = GLTexDecl(width=4, height=4, data=bytes(4 * 4 * 4))
        result = tex_upload_el(tex, ctx=None)
        assert result.handle == "headless"

    def test_returns_same_instance(self):
        tex = GLTexDecl()
        result = tex_upload_el(tex)
        assert result is tex

    def test_fields_preserved(self):
        data = bytes(range(16))
        tex = GLTexDecl(width=2, height=2, data=data)
        result = tex_upload_el(tex)
        assert result.width == 2
        assert result.height == 2
        assert result.data == data


# ── buf_upload_el / buf_upload_eval ──────────────────────────────────────────

class TestBufUploadEl:
    def test_headless_sets_handle(self):
        buf = GLBufferDecl(vbo_data=bytes(44 * 4))
        result = buf_upload_el(buf, ctx=None)
        assert result.handle == "headless"

    def test_returns_same_instance(self):
        buf = GLBufferDecl()
        assert buf_upload_el(buf) is buf

    def test_real_ctx_empty_vbo_raises(self):
        class FakeCtx:
            def buffer(self, data):
                raise RuntimeError("empty")
        with pytest.raises(KobraError):
            buf_upload_eval(GLBufferDecl(vbo_data=b""), FakeCtx())


# ── draw_call_eval / draw_call_el ─────────────────────────────────────────────

class TestDrawCallEval:
    def _setup(self):
        return (
            DrawCallDecl(index_data=[0, 1, 2]),
            GLTexDecl(handle="headless"),
            GLBufferDecl(handle="headless"),
            ShaderDecl(program="headless"),
        )

    def test_returns_descriptor_dict(self):
        call, tex, buf, shader = self._setup()
        desc = draw_call_eval(call, tex, buf, shader)
        assert isinstance(desc, dict)
        assert desc["index_count"] == 3

    def test_index_data_preserved(self):
        call, tex, buf, shader = self._setup()
        desc = draw_call_eval(call, tex, buf, shader)
        assert desc["index_data"] == [0, 1, 2]

    def test_atlas_uniform_set(self):
        call, tex, buf, shader = self._setup()
        desc = draw_call_eval(call, tex, buf, shader)
        assert "u_atlas" in desc["uniforms"]

    def test_handles_forwarded(self):
        call, tex, buf, shader = self._setup()
        desc = draw_call_eval(call, tex, buf, shader)
        assert desc["tex_handle"] == "headless"
        assert desc["buf_handle"] == "headless"
        assert desc["shader"] == "headless"

    def test_wrong_call_type_raises(self):
        with pytest.raises(KobraError):
            draw_call_eval("not_a_call", GLTexDecl(), GLBufferDecl(), ShaderDecl())


# ── frame_render_eval ─────────────────────────────────────────────────────────

class TestFrameRenderEval:
    def test_headless_with_empty_inputs(self):
        result = frame_render_eval(None, b"", b"", None)
        assert result["headless"] is True
        assert result["tex_handle"] == "headless"
        assert result["buf_handle"] == "headless"
        assert result["shader"] == "headless"

    def test_vertex_count_from_vbo_bytes(self):
        result = frame_render_eval(None, b"", bytes(44 * 6), None)
        assert result["vertex_count"] == 6

    def test_atlas_dict_input(self):
        atlas = {"width": 4, "height": 4, "data": bytes(4 * 4 * 4)}
        result = frame_render_eval(None, atlas, b"", None)
        assert result["headless"] is True

    def test_mesh_dict_input(self):
        mesh = {"vbo": bytes(44 * 4)}
        result = frame_render_eval(None, b"", mesh, None)
        assert result["vertex_count"] == 4

    def test_shader_decl_accepted(self):
        s = ShaderDecl()
        result = frame_render_eval(None, b"", b"", s)
        assert result["shader"] == "headless"

    def test_zero_vbo_zero_vertices(self):
        result = frame_render_eval(None, b"", b"", None)
        assert result["vertex_count"] == 0


# ── renderer_shi_wu_ung / renderer_ke_wu_ung / renderer_ep_em ────────────────

class TestRendererConvergence:
    def test_shi_wu_ung_wraps_kobra_success(self):
        result = renderer_shi_wu_ung({"headless": True, "vertex_count": 0})
        assert isinstance(result, KobraSuccess)
        assert result.value["headless"] is True

    def test_ke_wu_ung_raises_kobra_error(self):
        with pytest.raises(KobraError):
            renderer_ke_wu_ung("test failure")

    def test_ep_em_returns_dict(self):
        result = renderer_ep_em(None, b"", b"")
        assert isinstance(result, dict)
        assert result["headless"] is True

    def test_ep_em_with_atlas_and_vbo(self):
        atlas = {"width": 4, "height": 4, "data": bytes(4 * 4 * 4)}
        vbo   = bytes(44 * 3)
        result = renderer_ep_em(None, atlas, vbo)
        assert result["vertex_count"] == 3

    def test_ep_em_result_has_all_keys(self):
        result = renderer_ep_em(None, b"", b"")
        for key in ("tex_handle", "buf_handle", "shader", "vertex_count", "headless"):
            assert key in result
