"""
World Player
============
Player position, facing, and movement within a Zone.

Movement follows the same collision model as DungeonRuntime — one tile per
step, blocked by impassable tiles.  Zone exits and dungeon portals are
detected here and surfaced to WorldPlay for handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .map import Zone, ZoneExit, DungeonPortal, NPCSpawn


class Direction(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST  = "east"
    WEST  = "west"


_DIR_DELTA: dict[Direction, tuple[int, int]] = {
    Direction.NORTH: ( 0, -1),
    Direction.SOUTH: ( 0,  1),
    Direction.EAST:  ( 1,  0),
    Direction.WEST:  (-1,  0),
}

_OPPOSITE: dict[str, str] = {
    "north": "south", "south": "north",
    "east":  "west",  "west":  "east",
}


@dataclass
class WorldPlayer:
    zone_id: str
    x:       int
    y:       int
    facing:  Direction = Direction.SOUTH
    name:    str       = "Apprentice"

    def move(
        self,
        direction: Direction,
        zone: "Zone",
    ) -> tuple[bool, Optional["ZoneExit"], Optional["DungeonPortal"]]:
        """
        Attempt to move one tile in direction.

        Returns:
            (moved, exit_triggered, portal_triggered)

        If an exit is triggered, the caller (WorldPlay) handles the zone
        transition.  If a portal is triggered, the caller opens a DungeonRuntime.
        The player's position is only updated if moved is True.
        """
        from .map import is_passable

        self.facing = direction
        dx, dy = _DIR_DELTA[direction]
        nx, ny = self.x + dx, self.y + dy

        # Check for an exit at the current tile in this direction
        ex = zone.exit_at(self.x, self.y, direction.value)
        if ex is not None:
            return True, ex, None

        # Check for edge exit (player would walk off the map)
        if nx < 0 or nx >= zone.width or ny < 0 or ny >= zone.height:
            # Edge: blocked unless there's an exit pointing this way anywhere
            # on this row/col edge (zone-wide boundary exits)
            for candidate in zone.exits:
                if candidate.direction == direction.value:
                    if direction in (Direction.EAST, Direction.WEST):
                        if candidate.y == self.y:
                            return True, candidate, None
                    else:
                        if candidate.x == self.x:
                            return True, candidate, None
            return False, None, None

        # Check dungeon portal at destination
        portal = zone.portal_at(nx, ny)
        target_tile = zone.tile_at(nx, ny)
        if portal is not None and is_passable(target_tile):
            self.x, self.y = nx, ny
            return True, None, portal

        # Normal movement
        if not is_passable(target_tile):
            return False, None, None

        self.x, self.y = nx, ny
        return True, None, None

    def facing_tile(self) -> tuple[int, int]:
        """Coordinates of the tile directly in front of the player."""
        dx, dy = _DIR_DELTA[self.facing]
        return self.x + dx, self.y + dy

    def facing_npc(self, zone: "Zone") -> Optional["NPCSpawn"]:
        """Return the NPC directly in front of the player, if any."""
        ax, ay = self.facing_tile()
        return zone.npc_at(ax, ay)

    def facing_portal(self, zone: "Zone") -> Optional["DungeonPortal"]:
        """Return the dungeon portal directly in front of the player, if any."""
        ax, ay = self.facing_tile()
        return zone.portal_at(ax, ay)