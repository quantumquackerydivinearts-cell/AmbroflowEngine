"""
A* Pathfinding
==============
A* over the dungeon collision map (dict[(x,y)] → TileKind).

Passable tiles: FLOOR, DOOR, ENTRY, EXIT, CHEST, FORGE, CRYSTAL, ALTAR, SPECIAL
Impassable:     WALL (absent from the voxels dict)

Usage:
    path = astar(start=(0,0), goal=(5,5), voxels=layout.voxels)
    # path is a list of (x, y) tuples from start to goal,
    # or None if no path exists.
"""

from __future__ import annotations

import heapq
from typing import Optional


def _h(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


_NEIGHBORS = [(0, 1), (0, -1), (1, 0), (-1, 0)]


def astar(
    start: tuple[int, int],
    goal: tuple[int, int],
    voxels: dict[tuple[int, int], object],
) -> Optional[list[tuple[int, int]]]:
    """
    Return the shortest path from `start` to `goal` over `voxels`, or None.

    Any tile present in the voxels dict is considered passable.
    Missing tiles are walls.
    """
    if start == goal:
        return [start]
    if start not in voxels or goal not in voxels:
        return None

    open_heap: list[tuple[int, int, tuple[int, int]]] = []
    heapq.heappush(open_heap, (0 + _h(start, goal), 0, start))
    came_from: dict[tuple[int, int], Optional[tuple[int, int]]] = {start: None}
    g_score:   dict[tuple[int, int], int] = {start: 0}

    while open_heap:
        _, g, current = heapq.heappop(open_heap)

        if current == goal:
            path: list[tuple[int, int]] = []
            node: Optional[tuple[int, int]] = current
            while node is not None:
                path.append(node)
                node = came_from[node]
            return list(reversed(path))

        if g > g_score.get(current, float("inf")):
            continue

        for dx, dy in _NEIGHBORS:
            neighbor = (current[0] + dx, current[1] + dy)
            if neighbor not in voxels:
                continue
            tentative = g + 1
            if tentative < g_score.get(neighbor, float("inf")):
                g_score[neighbor] = tentative
                came_from[neighbor] = current
                f = tentative + _h(neighbor, goal)
                heapq.heappush(open_heap, (f, tentative, neighbor))

    return None
