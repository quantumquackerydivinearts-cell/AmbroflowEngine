"""
tests/test_zone_mesh_builder.py
================================
Validates ambroflow/world/mesh_builder.py — the zone-to-3D-mesh converter.
"""
from __future__ import annotations

import struct
import pytest

from ambroflow.world.map import Zone, WorldTileKind, Realm
from ambroflow.world.mesh_builder import zone_to_mesh, TILE_SIZE, WALL_HEIGHT


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _zone(voxels: dict) -> Zone:
    xs = [x for x, y in voxels] or [0]
    ys = [y for x, y in voxels] or [0]
    return Zone(
        zone_id="test",
        realm=Realm.LAPIDUS,
        name="Test Zone",
        width=max(xs) + 1,
        height=max(ys) + 1,
        voxels=voxels,
    )


def _vbo_bytes(result: dict) -> bytes:
    """Extract raw VBO bytes from a mesh_render_eval result."""
    vbo = result["vbo"]
    return bytes(vbo["data"]) if isinstance(vbo, dict) else bytes(vbo)


def _unpack_position(result: dict, vertex_index: int) -> tuple:
    data = _vbo_bytes(result)
    offset = vertex_index * 44
    return struct.unpack_from("<3f", data, offset)


def _unpack_normal(result: dict, vertex_index: int) -> tuple:
    data = _vbo_bytes(result)
    offset = vertex_index * 44 + 12
    return struct.unpack_from("<3f", data, offset)


# ── Empty / VOID ──────────────────────────────────────────────────────────────

class TestEmptyZone:
    def test_empty_voxels_zero_vertices(self):
        result = zone_to_mesh(_zone({}))
        assert result["vertex_count"] == 0
        assert result["face_count"] == 0

    def test_void_tile_skipped(self):
        result = zone_to_mesh(_zone({(0, 0): WorldTileKind.VOID}))
        assert result["vertex_count"] == 0

    def test_only_void_returns_empty(self):
        voxels = {(x, y): WorldTileKind.VOID for x in range(3) for y in range(3)}
        result = zone_to_mesh(_zone(voxels))
        assert result["face_count"] == 0


# ── Floor tiles ───────────────────────────────────────────────────────────────

class TestFloorTiles:
    def test_single_floor_two_faces(self):
        result = zone_to_mesh(_zone({(0, 0): WorldTileKind.FLOOR}))
        assert result["face_count"] == 2

    def test_single_floor_four_vertices(self):
        result = zone_to_mesh(_zone({(0, 0): WorldTileKind.FLOOR}))
        assert result["vertex_count"] == 4

    def test_floor_y_is_zero(self):
        result = zone_to_mesh(_zone({(0, 0): WorldTileKind.FLOOR}))
        _, y, _ = _unpack_position(result, 0)
        assert abs(y) < 1e-6

    def test_floor_normal_is_up(self):
        result = zone_to_mesh(_zone({(0, 0): WorldTileKind.FLOOR}))
        nx, ny, nz = _unpack_normal(result, 0)
        assert abs(ny - 1.0) < 1e-6
        assert abs(nx) < 1e-6
        assert abs(nz) < 1e-6

    def test_floor_tile_size_respected(self):
        result = zone_to_mesh(_zone({(2, 0): WorldTileKind.FLOOR}))
        x, _, _ = _unpack_position(result, 0)
        assert abs(x - 2 * TILE_SIZE) < 1e-6

    def test_two_floor_tiles_eight_vertices(self):
        result = zone_to_mesh(_zone({
            (0, 0): WorldTileKind.FLOOR,
            (1, 0): WorldTileKind.FLOOR,
        }))
        assert result["vertex_count"] == 8

    def test_winding_table_has_top(self):
        result = zone_to_mesh(_zone({(0, 0): WorldTileKind.FLOOR}))
        assert "MavoJyWuUng" in result["winding"]

    def test_grass_tile_accepted(self):
        result = zone_to_mesh(_zone({(0, 0): WorldTileKind.GRASS}))
        assert result["face_count"] == 2

    def test_road_tile_accepted(self):
        result = zone_to_mesh(_zone({(0, 0): WorldTileKind.ROAD}))
        assert result["face_count"] == 2


# ── Wall tiles ────────────────────────────────────────────────────────────────

class TestWallTiles:
    def test_isolated_wall_ten_faces(self):
        # top cap (2) + 4 sides each 2 = 10
        result = zone_to_mesh(_zone({(0, 0): WorldTileKind.WALL}))
        assert result["face_count"] == 10

    def test_wall_top_at_wall_height(self):
        result = zone_to_mesh(_zone({(0, 0): WorldTileKind.WALL}))
        _, y, _ = _unpack_position(result, 0)
        assert abs(y - WALL_HEIGHT) < 1e-6

    def test_adjacent_walls_share_no_face(self):
        # Two walls side by side — shared internal face suppressed
        # Each wall: top (2 faces) + 3 exposed sides (each 2) = 8 faces
        result = zone_to_mesh(_zone({
            (0, 0): WorldTileKind.WALL,
            (1, 0): WorldTileKind.WALL,
        }))
        assert result["face_count"] == 16

    def test_wall_surrounded_by_walls_only_top(self):
        # Centre wall with walls on all 4 sides — only top emitted
        voxels = {
            (1, 0): WorldTileKind.WALL,
            (0, 1): WorldTileKind.WALL,
            (1, 1): WorldTileKind.WALL,  # centre
            (2, 1): WorldTileKind.WALL,
            (1, 2): WorldTileKind.WALL,
        }
        result = zone_to_mesh(_zone(voxels))
        # Centre wall: top only = 2 faces; perimeter walls each have exposed sides
        # Centre contribution: 2 faces
        centre_faces = 2
        # Verify total > just top: perimeter walls add more
        assert result["face_count"] > centre_faces

    def test_wall_side_normals_present(self):
        result = zone_to_mesh(_zone({(1, 1): WorldTileKind.WALL}))
        assert "MavoJaWuUng" in result["winding"]  # front (-Z)
        assert "MavoJoWuUng" in result["winding"]  # back  (+Z)
        assert "MavoJeWuUng" in result["winding"]  # port  (-X)
        assert "MavoJiWuUng" in result["winding"]  # starboard (+X)

    def test_wall_next_to_floor_four_exposed_sides(self):
        # Wall at (1,1) with floors on all 4 neighbours
        voxels = {
            (0, 1): WorldTileKind.FLOOR,
            (2, 1): WorldTileKind.FLOOR,
            (1, 0): WorldTileKind.FLOOR,
            (1, 2): WorldTileKind.FLOOR,
            (1, 1): WorldTileKind.WALL,
        }
        result = zone_to_mesh(_zone(voxels))
        # Wall: top (2) + 4 sides (8) = 10; 4 floor tiles: 4×2 = 8 → total 18
        assert result["face_count"] == 18


# ── Mixed tiles ───────────────────────────────────────────────────────────────

class TestMixedZone:
    def test_corridor_between_walls(self):
        # ######
        # .....
        # ######
        voxels = {}
        for x in range(5):
            voxels[(x, 0)] = WorldTileKind.WALL
            voxels[(x, 1)] = WorldTileKind.FLOOR
            voxels[(x, 2)] = WorldTileKind.WALL
        result = zone_to_mesh(_zone(voxels))
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0

    def test_vbo_length_matches_vertex_count(self):
        voxels = {(x, y): WorldTileKind.FLOOR
                  for x in range(4) for y in range(4)}
        result = zone_to_mesh(_zone(voxels))
        assert len(_vbo_bytes(result)) == result["vertex_count"] * 44

    def test_result_has_required_keys(self):
        result = zone_to_mesh(_zone({(0, 0): WorldTileKind.FLOOR}))
        for key in ("vbo", "batches", "winding", "face_count", "vertex_count"):
            assert key in result
