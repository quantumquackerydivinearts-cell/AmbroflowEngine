"""
ambroflow/world/mesh_builder.py
================================
Converts a Zone voxel grid into a mesh_render_eval result ready for the
3D tile renderer.  Geometry rules:

  WALL tile  — top cap at WALL_HEIGHT + one side face per adjacent non-wall cell
  Floor-like — a single top-facing quad at y=0
  VOID       — skipped entirely

All faces use CCW winding viewed from outside the surface.
Stride is 44 bytes/vertex (position 12B + normal 12B + uv 8B + pad 12B).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ambroflow.kobra_compiled.mesh_engine import (
    MeshBatchDecl,
    MeshFaceDecl,
    MeshVertexDecl,
    mesh_render_eval,
)

if TYPE_CHECKING:
    from ambroflow.world.map import Zone

TILE_SIZE: float = 1.0
WALL_HEIGHT: float = 2.0

_SOLID = frozenset({"WALL", "VOID", "WATER", "TREE", "WALL_FACE"})

_FLOOR_ATLAS: dict[str, str] = {
    "FLOOR":            "tiles/floor.png",
    "DOOR":             "tiles/door.png",
    "GRASS":            "tiles/grass.png",
    "ROAD":             "tiles/road.png",
    "DIRT":             "tiles/dirt.png",
    "STONE":            "tiles/stone.png",
    "BRIDGE":           "tiles/bridge.png",
    "STAIRS_UP":        "tiles/stairs_up.png",
    "STAIRS_DOWN":      "tiles/stairs_down.png",
    "PORTAL":           "tiles/portal.png",
    "DUNGEON_ENTRANCE": "tiles/dungeon.png",
    "TREE":             "tiles/tree_top.png",
    "MARBLE":           "tiles/marble.png",
    "YELLOW_BRICK":     "tiles/yellow_brick.png",
    "CERAMIC":          "tiles/ceramic.png",
    "SLATE":            "tiles/slate.png",
    "SILICA":           "tiles/silica.png",
    "WALL_FACE":        "tiles/wall_face.png",
    "WATER":            "tiles/water.png",
}

_WALL_TOP  = "tiles/wall_top.png"
_WALL_SIDE = "tiles/wall_side.png"

# (neighbor delta, orient_dir, outward normal, quad corner order)
_WALL_SIDES: list[tuple] = [
    ((0, -1), "MavoJaWuUng", (0.0, 0.0, -1.0), "south"),
    ((0,  1), "MavoJoWuUng", (0.0, 0.0,  1.0), "north"),
    ((-1, 0), "MavoJeWuUng", (-1.0, 0.0, 0.0), "west"),
    (( 1, 0), "MavoJiWuUng", ( 1.0, 0.0, 0.0), "east"),
]


def _quad(
    vertices: list[MeshVertexDecl],
    faces: list[MeshFaceDecl],
    p0: tuple, p1: tuple, p2: tuple, p3: tuple,
    normal: tuple,
    orient_dir: str,
    atlas_tile: str,
) -> None:
    base = len(vertices)
    for pos, uv in zip(
        (p0, p1, p2, p3),
        ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
    ):
        vertices.append(MeshVertexDecl(position=pos, normal=normal, uv=uv))
    faces.append(MeshFaceDecl(vertex_indices=[base, base+1, base+2],
                               orient_dir=orient_dir, atlas_tile=atlas_tile))
    faces.append(MeshFaceDecl(vertex_indices=[base, base+2, base+3],
                               orient_dir=orient_dir, atlas_tile=atlas_tile))


def zone_to_mesh(zone: "Zone") -> dict:
    """Return a mesh_render_eval result dict for the given Zone."""
    vertices: list[MeshVertexDecl] = []
    faces: list[MeshFaceDecl] = []

    def neighbor_kind(cx: int, cy: int) -> str:
        k = zone.voxels.get((cx, cy))
        return k.name if k is not None else "VOID"

    for (cx, cy), kind in zone.voxels.items():
        kn = kind.name
        x0, x1 = cx * TILE_SIZE, (cx + 1) * TILE_SIZE
        z0, z1 = cy * TILE_SIZE, (cy + 1) * TILE_SIZE
        H = WALL_HEIGHT

        if kn == "VOID":
            continue

        if kn == "WALL":
            # Top cap
            _quad(vertices, faces,
                  (x0, H, z0), (x1, H, z0), (x1, H, z1), (x0, H, z1),
                  (0.0, 1.0, 0.0), "MavoJyWuUng", _WALL_TOP)
            # Side faces — emit only where the adjacent cell is not a wall
            side_corners = {
                "south": ((x0, 0.0, z0), (x1, 0.0, z0), (x1, H, z0), (x0, H, z0)),
                "north": ((x1, 0.0, z1), (x0, 0.0, z1), (x0, H, z1), (x1, H, z1)),
                "west":  ((x0, 0.0, z1), (x0, 0.0, z0), (x0, H, z0), (x0, H, z1)),
                "east":  ((x1, 0.0, z0), (x1, 0.0, z1), (x1, H, z1), (x1, H, z0)),
            }
            for (dx, dy), orient, normal, label in _WALL_SIDES:
                if neighbor_kind(cx + dx, cy + dy) != "WALL":
                    p0, p1, p2, p3 = side_corners[label]
                    _quad(vertices, faces, p0, p1, p2, p3, normal, orient, _WALL_SIDE)
        else:
            tile_path = _FLOOR_ATLAS.get(kn, "tiles/floor.png")
            _quad(vertices, faces,
                  (x0, 0.0, z0), (x1, 0.0, z0), (x1, 0.0, z1), (x0, 0.0, z1),
                  (0.0, 1.0, 0.0), "MavoJyWuUng", tile_path)

    batch = MeshBatchDecl(faces=faces)
    return mesh_render_eval(vertices, faces, [batch])
