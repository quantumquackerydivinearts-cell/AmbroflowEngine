"""
World Map Data Structures
=========================
Zone-based world representation extending the dungeon architecture.

The world is composed of Zones — persistent, authored tile grids in one of
three Realms.  Dungeons are accessed via DungeonPortal tiles within zones.
Zone transitions happen via ZoneExit records.

Realm hierarchy (ANMU entities):
  LAPIDUS   — Spirit of the Overworld.  Azonithia, Wiltoll Lane, surface world.
  MERCURIE  — Spirit of the Faewilds.   Fae courts, wild roads, liminal spaces.
  SULPHERA  — Spirit of the Underworld. Rings 1–9, infernal architecture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Realms ────────────────────────────────────────────────────────────────────

class Realm(str, Enum):
    LAPIDUS  = "lapidus"
    MERCURIE = "mercurie"
    SULPHERA = "sulphera"


# ── Tile kinds ────────────────────────────────────────────────────────────────

class WorldTileKind(str, Enum):
    VOID             = "void"            # out-of-zone / black — impassable
    WALL             = "wall"            # solid — impassable
    FLOOR            = "floor"           # generic passable interior
    DOOR             = "door"            # passable; triggers zone transition when entered
    GRASS            = "grass"           # passable exterior ground
    ROAD             = "road"            # passable paved/worn surface
    DIRT             = "dirt"            # passable dirt path
    STONE            = "stone"           # passable stone exterior (courtyard, plaza)
    WATER            = "water"           # impassable surface water (or lava in Sulphera)
    BRIDGE           = "bridge"          # passable — connects across water
    STAIRS_UP        = "stairs_up"       # passable — triggers floor/level transition
    STAIRS_DOWN      = "stairs_down"     # passable — triggers floor/level transition
    PORTAL           = "portal"          # passable — triggers realm transition
    DUNGEON_ENTRANCE = "dungeon_entrance"# passable — opens a DungeonRuntime session
    # ── Lapidus surface materials ──────────────────────────────────────────
    TREE             = "tree"            # impassable outdoor vegetation / forest
    MARBLE           = "marble"          # passable — hard marble paving (Azoth Sprint)
    YELLOW_BRICK     = "yellow_brick"    # passable — warm brick (Hopefare St / slum)
    CERAMIC          = "ceramic"         # passable — decorative tile (June St / market)
    SLATE            = "slate"           # passable — serious stone (Goldshoot St / temple)
    SILICA           = "silica"          # passable — extravagant surface (Youthspring Rd / nobles)


_PASSABLE: frozenset[WorldTileKind] = frozenset({
    WorldTileKind.FLOOR,
    WorldTileKind.DOOR,
    WorldTileKind.GRASS,
    WorldTileKind.ROAD,
    WorldTileKind.DIRT,
    WorldTileKind.STONE,
    WorldTileKind.BRIDGE,
    WorldTileKind.STAIRS_UP,
    WorldTileKind.STAIRS_DOWN,
    WorldTileKind.PORTAL,
    WorldTileKind.DUNGEON_ENTRANCE,
    WorldTileKind.MARBLE,
    WorldTileKind.YELLOW_BRICK,
    WorldTileKind.CERAMIC,
    WorldTileKind.SLATE,
    WorldTileKind.SILICA,
})


def is_passable(tile: WorldTileKind) -> bool:
    return tile in _PASSABLE


# ── Zone records ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ZoneExit:
    """
    A tile position that transitions the player to another zone.

    When the player attempts to move in `direction` from (x, y), or when
    movement would carry them off the map boundary on that edge, this exit
    fires and the player is placed at (target_x, target_y) in target_zone.
    """
    x:           int
    y:           int
    direction:   str    # "north" | "south" | "east" | "west"
    target_zone: str    # zone_id of destination
    target_x:    int    # player spawn x in destination
    target_y:    int    # player spawn y in destination


@dataclass(frozen=True)
class DungeonPortal:
    """A tile that opens a DungeonRuntime session when the player steps on it."""
    x:          int
    y:          int
    dungeon_id: str


@dataclass(frozen=True)
class NPCSpawn:
    """A fixed NPC position within a zone."""
    x:            int
    y:            int
    character_id: str


@dataclass(frozen=True)
class ItemSpawn:
    """A one-time item pickup at a fixed position within a zone."""
    x:       int
    y:       int
    item_id: str
    qty:     int = 1


@dataclass
class Zone:
    zone_id:      str
    realm:        Realm
    name:         str
    width:        int
    height:       int
    voxels:       dict[tuple[int, int], WorldTileKind]
    player_spawn: tuple[int, int]     = field(default=(1, 1))
    exits:        list[ZoneExit]      = field(default_factory=list)
    npc_spawns:   list[NPCSpawn]      = field(default_factory=list)
    portals:      list[DungeonPortal] = field(default_factory=list)
    item_spawns:  list[ItemSpawn]     = field(default_factory=list)

    def tile_at(self, x: int, y: int) -> WorldTileKind:
        """Return tile kind at (x, y), VOID if out of bounds."""
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return WorldTileKind.VOID
        return self.voxels.get((x, y), WorldTileKind.VOID)

    def exit_at(self, x: int, y: int, direction: str) -> Optional[ZoneExit]:
        for ex in self.exits:
            if ex.x == x and ex.y == y and ex.direction == direction:
                return ex
        return None

    def portal_at(self, x: int, y: int) -> Optional[DungeonPortal]:
        for p in self.portals:
            if p.x == x and p.y == y:
                return p
        return None

    def npc_at(self, x: int, y: int) -> Optional[NPCSpawn]:
        for n in self.npc_spawns:
            if n.x == x and n.y == y:
                return n
        return None

    def items_at(self, x: int, y: int) -> list[ItemSpawn]:
        return [i for i in self.item_spawns if i.x == x and i.y == y]

    @classmethod
    def from_export_dict(cls, data: dict) -> "Zone":
        """
        Load a Zone from the JSON produced by the Atelier's
        'Export → Ambroflow' button (exportTilesForAmbroflow).

        Expected shape:
          { zone_id, realm, name, width, height,
            voxels: {"x,y": "kind", ...},
            player_spawn: [x, y],
            exits: [...], npc_spawns: [...], portals: [...] }
        """
        voxels: dict[tuple[int, int], WorldTileKind] = {}
        for key, kind_str in (data.get("voxels") or {}).items():
            x_str, _, y_str = key.partition(",")
            try:
                x, y = int(x_str), int(y_str)
                voxels[(x, y)] = WorldTileKind(kind_str)
            except (ValueError, KeyError):
                continue

        spawn_raw = data.get("player_spawn", [1, 1])
        player_spawn = (int(spawn_raw[0]), int(spawn_raw[1]))

        exits = [
            ZoneExit(
                x=int(e["x"]), y=int(e["y"]),
                direction=e["direction"],
                target_zone=e["target_zone"],
                target_x=int(e["target_x"]), target_y=int(e["target_y"]),
            )
            for e in (data.get("exits") or [])
        ]
        npc_spawns = [
            NPCSpawn(x=int(n["x"]), y=int(n["y"]), character_id=n["character_id"])
            for n in (data.get("npc_spawns") or [])
        ]
        portals = [
            DungeonPortal(x=int(p["x"]), y=int(p["y"]), dungeon_id=p["dungeon_id"])
            for p in (data.get("portals") or [])
        ]

        realm_str = data.get("realm", "lapidus")
        try:
            realm = Realm(realm_str)
        except ValueError:
            realm = Realm.LAPIDUS

        return cls(
            zone_id=str(data.get("zone_id", "zone_export")),
            realm=realm,
            name=str(data.get("name", "Exported Zone")),
            width=int(data.get("width", 48)),
            height=int(data.get("height", 32)),
            voxels=voxels,
            player_spawn=player_spawn,
            exits=exits,
            npc_spawns=npc_spawns,
            portals=portals,
        )


@dataclass
class WorldMap:
    zones:            dict[str, Zone]
    starting_zone_id: str

    def zone(self, zone_id: str) -> Optional[Zone]:
        return self.zones.get(zone_id)


# ── ASCII zone builder ────────────────────────────────────────────────────────

_ASCII_TILE: dict[str, WorldTileKind] = {
    "#": WorldTileKind.WALL,
    ".": WorldTileKind.FLOOR,
    "+": WorldTileKind.DOOR,
    ",": WorldTileKind.GRASS,
    "=": WorldTileKind.ROAD,
    "D": WorldTileKind.DIRT,
    "S": WorldTileKind.STONE,
    "~": WorldTileKind.WATER,
    "/": WorldTileKind.BRIDGE,
    "^": WorldTileKind.STAIRS_UP,
    "v": WorldTileKind.STAIRS_DOWN,
    "P": WorldTileKind.PORTAL,
    "E": WorldTileKind.DUNGEON_ENTRANCE,
    " ": WorldTileKind.VOID,
    # Surface material tiles
    "T": WorldTileKind.TREE,
    "M": WorldTileKind.MARBLE,
    "Y": WorldTileKind.YELLOW_BRICK,
    "C": WorldTileKind.CERAMIC,
    "L": WorldTileKind.SLATE,
    "X": WorldTileKind.SILICA,
    # Placement markers — resolved to FLOOR at build time
    "@": WorldTileKind.FLOOR,   # player spawn
    "N": WorldTileKind.FLOOR,   # NPC spawn (matched to npc_ids in order)
}


def build_zone_from_ascii(
    zone_id:     str,
    realm:       Realm,
    name:        str,
    rows:        list[str],
    exits:       list[ZoneExit]      = (),
    portals:     list[DungeonPortal] = (),
    npc_ids:     list[str]           = (),
    item_spawns: list[ItemSpawn]     = (),
) -> Zone:
    """
    Parse an ASCII zone map into a Zone.

    '@' → player spawn tile (one per map).
    'N' → NPC spawn tile, matched to npc_ids in left-to-right, top-to-bottom
          order.  Excess 'N' markers get placeholder IDs.
    """
    width  = max(len(r) for r in rows) if rows else 1
    height = len(rows)
    voxels: dict[tuple[int, int], WorldTileKind] = {}
    player_spawn: tuple[int, int] = (1, 1)
    npc_spawns:   list[NPCSpawn]  = []
    npc_id_iter   = iter(npc_ids)

    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            tile = _ASCII_TILE.get(ch, WorldTileKind.VOID)
            voxels[(x, y)] = tile
            if ch == "@":
                player_spawn = (x, y)
            elif ch == "N":
                cid = next(npc_id_iter, f"npc_{x}_{y}")
                npc_spawns.append(NPCSpawn(x=x, y=y, character_id=cid))
        # Pad short rows to full width
        for x in range(len(row), width):
            voxels[(x, y)] = WorldTileKind.VOID

    return Zone(
        zone_id=zone_id,
        realm=realm,
        name=name,
        width=width,
        height=height,
        voxels=voxels,
        player_spawn=player_spawn,
        exits=list(exits),
        npc_spawns=npc_spawns,
        portals=list(portals),
        item_spawns=list(item_spawns),
    )


# ── Atelier export loader ─────────────────────────────────────────────────────

def load_zone_export(path) -> Zone:
    """Load a Zone from a JSON file exported by the Atelier's Export → Ambroflow."""
    import json
    from pathlib import Path
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Zone.from_export_dict(data)