"""
tests/test_mesh_compiled.py
============================
Validates the compiled tile mesh engine (kobra_compiled/mesh_engine.py)
emitted from tile_mesh.ko via the Kobra compiler.
"""
from __future__ import annotations

import struct
import pytest

from ambroflow.kobra_compiled.mesh_engine import (
    MeshDecl,
    MeshVertexDecl,
    MeshFaceDecl,
    MeshBatchDecl,
    FaceOrientDecl,
    MeshTransformDecl,
    FACE_NORMALS,
    mesh_read_eval,
    mesh_index_el,
    mesh_buffer_eval,
    vertex_buffer_el,
    face_orient_eval,
    top_face_el,
    front_face_el,
    mesh_transform_eval,
    mesh_batch_el,
    mesh_render_eval,
    mesh_shi_wu_ung,
    mesh_ke_wu_ung,
    mesh_ep_em,
)
from ambroflow.kobra_compiled.mesh_engine import KobraSuccess, KobraError


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _quad_vertices():
    """Four corners of a unit quad lying in the XZ plane."""
    return [
        MeshVertexDecl(position=(-0.5, 0.0, -0.5), normal=(0.0, 1.0, 0.0), uv=(0.0, 0.0)),
        MeshVertexDecl(position=( 0.5, 0.0, -0.5), normal=(0.0, 1.0, 0.0), uv=(1.0, 0.0)),
        MeshVertexDecl(position=( 0.5, 0.0,  0.5), normal=(0.0, 1.0, 0.0), uv=(1.0, 1.0)),
        MeshVertexDecl(position=(-0.5, 0.0,  0.5), normal=(0.0, 1.0, 0.0), uv=(0.0, 1.0)),
    ]


def _quad_faces():
    """Two triangles forming the quad (CCW winding)."""
    return [
        MeshFaceDecl(vertex_indices=[0, 1, 2], orient_dir="MavoJyWuUng"),
        MeshFaceDecl(vertex_indices=[0, 2, 3], orient_dir="MavoJyWuUng"),
    ]


# ── MeshDecl hierarchy ────────────────────────────────────────────────────────

class TestMeshDeclHierarchy:
    def test_vertex_is_mesh_decl(self):
        v = MeshVertexDecl()
        assert isinstance(v, MeshDecl)
        assert v.tongue_eq == "MavoVertexWuUng"

    def test_face_is_mesh_decl(self):
        f = MeshFaceDecl()
        assert isinstance(f, MeshDecl)
        assert f.tongue_eq == "MavoFaceWuUng"

    def test_batch_is_mesh_decl(self):
        b = MeshBatchDecl()
        assert isinstance(b, MeshDecl)
        assert b.tongue_eq == "MavoBatchWuUng"

    def test_orient_is_mesh_decl(self):
        o = FaceOrientDecl()
        assert isinstance(o, MeshDecl)
        assert o.tongue_eq == "MavoJyWuUng"

    def test_transform_is_mesh_decl(self):
        t = MeshTransformDecl()
        assert isinstance(t, MeshDecl)
        assert t.tongue_eq == "MavoBatchWuUng"


# ── FACE_NORMALS / FaceOrientDecl ─────────────────────────────────────────────

class TestFaceNormals:
    def test_six_directions_defined(self):
        assert len(FACE_NORMALS) == 6

    def test_all_normals_unit_length(self):
        import math
        for key, n in FACE_NORMALS.items():
            mag = math.sqrt(sum(x * x for x in n))
            assert abs(mag - 1.0) < 1e-9, f"{key}: magnitude {mag} != 1"

    def test_jy_is_up(self):
        assert FACE_NORMALS["MavoJyWuUng"] == (0.0, 1.0, 0.0)

    def test_ju_is_down(self):
        assert FACE_NORMALS["MavoJuWuUng"] == (0.0, -1.0, 0.0)

    def test_ja_and_jo_are_opposite(self):
        ja = FACE_NORMALS["MavoJaWuUng"]
        jo = FACE_NORMALS["MavoJoWuUng"]
        for a, b in zip(ja, jo):
            assert abs(a + b) < 1e-9

    def test_ji_and_je_are_opposite(self):
        ji = FACE_NORMALS["MavoJiWuUng"]
        je = FACE_NORMALS["MavoJeWuUng"]
        for a, b in zip(ji, je):
            assert abs(a + b) < 1e-9

    def test_face_orient_decl_normal_property(self):
        o = FaceOrientDecl(direction="MavoJyWuUng")
        assert o.normal == (0.0, 1.0, 0.0)

    def test_face_orient_decl_unknown_direction_fallback(self):
        o = FaceOrientDecl(direction="unknown")
        assert o.normal == (0.0, 1.0, 0.0)


# ── mesh_read_eval ────────────────────────────────────────────────────────────

class TestMeshReadEval:
    def test_valid_mesh_returns_true(self):
        verts  = _quad_vertices()
        faces  = _quad_faces()
        batch  = MeshBatchDecl(faces=faces)
        assert mesh_read_eval(verts, faces, [batch]) is True

    def test_out_of_range_index_raises(self):
        verts = _quad_vertices()
        faces = [MeshFaceDecl(vertex_indices=[0, 1, 99])]
        with pytest.raises(KobraError):
            mesh_read_eval(verts, faces, [])

    def test_negative_index_raises(self):
        verts = _quad_vertices()
        faces = [MeshFaceDecl(vertex_indices=[-1, 0, 1])]
        with pytest.raises(KobraError):
            mesh_read_eval(verts, faces, [])

    def test_empty_mesh_valid(self):
        assert mesh_read_eval([], [], []) is True


# ── mesh_index_el ─────────────────────────────────────────────────────────────

class TestMeshIndexEl:
    def test_returns_zero_for_first_face(self):
        face  = MeshFaceDecl(vertex_indices=[0, 1, 2])
        batch = MeshBatchDecl()
        idx   = mesh_index_el(face, batch)
        assert idx == 0

    def test_batch_grows(self):
        batch = MeshBatchDecl()
        for i in range(5):
            mesh_index_el(MeshFaceDecl(vertex_indices=[i, i+1, i+2]), batch)
        assert len(batch.faces) == 5

    def test_returns_incrementing_indices(self):
        batch = MeshBatchDecl()
        indices = [mesh_index_el(MeshFaceDecl(vertex_indices=[0, 1, 2]), batch)
                   for _ in range(3)]
        assert indices == [0, 1, 2]


# ── mesh_buffer_eval / vertex_buffer_el ──────────────────────────────────────

class TestMeshBufferEval:
    STRIDE = 44

    def test_buffer_length_correct(self):
        verts = _quad_vertices()
        buf   = mesh_buffer_eval(verts, [])
        assert len(buf) == len(verts) * self.STRIDE

    def test_first_vertex_position_packed(self):
        v   = MeshVertexDecl(position=(1.0, 2.0, 3.0), normal=(0.0, 1.0, 0.0), uv=(0.5, 0.5))
        buf = mesh_buffer_eval([v], [])
        px, py, pz = struct.unpack_from("<3f", buf, 0)
        assert abs(px - 1.0) < 1e-6
        assert abs(py - 2.0) < 1e-6
        assert abs(pz - 3.0) < 1e-6

    def test_normal_packed_after_position(self):
        v   = MeshVertexDecl(position=(0.0, 0.0, 0.0), normal=(0.0, 1.0, 0.0), uv=(0.0, 0.0))
        buf = mesh_buffer_eval([v], [])
        nx, ny, nz = struct.unpack_from("<3f", buf, 12)
        assert abs(ny - 1.0) < 1e-6

    def test_uv_packed_after_normal(self):
        v   = MeshVertexDecl(position=(0.0, 0.0, 0.0), normal=(0.0, 1.0, 0.0), uv=(0.25, 0.75))
        buf = mesh_buffer_eval([v], [])
        u, v_coord = struct.unpack_from("<2f", buf, 24)
        assert abs(u      - 0.25) < 1e-6
        assert abs(v_coord - 0.75) < 1e-6

    def test_vertex_buffer_el_has_correct_keys(self):
        verts = _quad_vertices()
        desc  = vertex_buffer_el(verts)
        assert desc["vertex_count"] == 4
        assert desc["stride"] == self.STRIDE
        assert len(desc["data"]) == 4 * self.STRIDE


# ── face_orient_eval ──────────────────────────────────────────────────────────

class TestFaceOrientEval:
    def test_returns_dict_with_normal(self):
        face = MeshFaceDecl(orient_dir="MavoJyWuUng")
        result = face_orient_eval(face)
        assert "normal" in result
        assert result["normal"] == (0.0, 1.0, 0.0)

    def test_all_dirs_present(self):
        face = MeshFaceDecl(orient_dir="MavoJaWuUng")
        result = face_orient_eval(face)
        assert len(result["all_dirs"]) == 6

    def test_face_dir_recorded(self):
        face = MeshFaceDecl(orient_dir="MavoJuWuUng")
        result = face_orient_eval(face)
        assert result["face_dir"] == "MavoJuWuUng"


# ── top_face_el / front_face_el ───────────────────────────────────────────────

class TestFaceConstructors:
    def test_top_face_orient_dir(self):
        f = top_face_el([0, 1, 2])
        assert f.orient_dir == "MavoJyWuUng"

    def test_front_face_orient_dir(self):
        f = front_face_el([0, 1, 2])
        assert f.orient_dir == "MavoJaWuUng"

    def test_vertex_indices_copied(self):
        indices = [3, 4, 5]
        f = top_face_el(indices)
        assert f.vertex_indices == [3, 4, 5]
        indices.append(99)          # mutation doesn't affect face
        assert len(f.vertex_indices) == 3

    def test_atlas_tile_set(self):
        f = top_face_el([0, 1, 2], atlas_tile="stone.png")
        assert f.atlas_tile == "stone.png"

    def test_both_constructors_return_mesh_face_decl(self):
        assert isinstance(top_face_el([0, 1, 2]),   MeshFaceDecl)
        assert isinstance(front_face_el([0, 1, 2]), MeshFaceDecl)


# ── mesh_batch_el ─────────────────────────────────────────────────────────────

class TestMeshBatchEl:
    def test_returns_batch_descriptor(self):
        faces = _quad_faces()
        batch = MeshBatchDecl(faces=faces, batch_id=7)
        t     = MeshTransformDecl()
        desc  = mesh_batch_el(batch, t)
        assert desc["batch_id"]   == 7
        assert desc["face_count"] == 2

    def test_index_data_flattened(self):
        face  = MeshFaceDecl(vertex_indices=[0, 1, 2])
        batch = MeshBatchDecl(faces=[face])
        desc  = mesh_batch_el(batch, MeshTransformDecl())
        assert desc["index_data"] == [0, 1, 2]

    def test_identity_transform_in_output(self):
        batch = MeshBatchDecl(faces=_quad_faces())
        t     = MeshTransformDecl()
        desc  = mesh_batch_el(batch, t)
        assert len(desc["transform"]) == 16
        assert desc["transform"][0]  == 1.0   # identity diagonal
        assert desc["transform"][5]  == 1.0
        assert desc["transform"][10] == 1.0
        assert desc["transform"][15] == 1.0


# ── mesh_render_eval ──────────────────────────────────────────────────────────

class TestMeshRenderEval:
    def test_returns_render_dict(self):
        verts  = _quad_vertices()
        faces  = _quad_faces()
        batch  = MeshBatchDecl(faces=faces)
        result = mesh_render_eval(verts, faces, [batch])
        assert "vbo"          in result
        assert "batches"      in result
        assert "winding"      in result
        assert "face_count"   in result
        assert "vertex_count" in result

    def test_vertex_and_face_counts(self):
        verts  = _quad_vertices()
        faces  = _quad_faces()
        batch  = MeshBatchDecl(faces=faces)
        result = mesh_render_eval(verts, faces, [batch])
        assert result["vertex_count"] == 4
        assert result["face_count"]   == 2

    def test_winding_table_contains_used_direction(self):
        verts  = _quad_vertices()
        faces  = _quad_faces()        # all MavoJyWuUng
        batch  = MeshBatchDecl(faces=faces)
        result = mesh_render_eval(verts, faces, [batch])
        assert "MavoJyWuUng" in result["winding"]
        assert result["winding"]["MavoJyWuUng"] == (0.0, 1.0, 0.0)

    def test_invalid_face_indices_raise(self):
        verts = _quad_vertices()
        faces = [MeshFaceDecl(vertex_indices=[0, 1, 99])]
        with pytest.raises(KobraError):
            mesh_render_eval(verts, faces, [])

    def test_empty_mesh_valid(self):
        result = mesh_render_eval([], [], [])
        assert result["vertex_count"] == 0
        assert result["face_count"]   == 0


# ── mesh_shi_wu_ung / mesh_ke_wu_ung / mesh_ep_em ────────────────────────────

class TestMeshConvergence:
    def test_shi_wu_ung_wraps_in_kobra_success(self):
        payload = {"vertex_count": 4}
        result  = mesh_shi_wu_ung(payload)
        assert isinstance(result, KobraSuccess)
        assert result.value["vertex_count"] == 4

    def test_ke_wu_ung_raises_kobra_error(self):
        with pytest.raises(KobraError):
            mesh_ke_wu_ung("test failure")

    def test_ep_em_returns_dict_on_success(self):
        verts  = _quad_vertices()
        faces  = _quad_faces()
        batch  = MeshBatchDecl(faces=faces)
        result = mesh_ep_em(verts, faces, [batch])
        assert isinstance(result, dict)
        assert result["vertex_count"] == 4

    def test_ep_em_propagates_kobra_error_on_bad_indices(self):
        verts = _quad_vertices()
        faces = [MeshFaceDecl(vertex_indices=[0, 1, 999])]
        with pytest.raises(KobraError):
            mesh_ep_em(verts, faces, [])
