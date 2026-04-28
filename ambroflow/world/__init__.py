"""
Ambroflow World System
======================
Zone-based navigable world for the KLGS series.

Public API
----------
  WorldMap        — collection of Zones + starting zone ID
  Zone            — single tile-grid area in one Realm
  Realm           — LAPIDUS | MERCURIE | SULPHERA
  WorldTileKind   — tile enum (WALL, FLOOR, GRASS, ROAD, …)
  ZoneExit        — tile record that transitions to another zone
  DungeonPortal   — tile record that opens a DungeonRuntime session
  NPCSpawn        — fixed NPC position within a zone
  WorldPlayer     — player position, facing, and movement
  WorldRenderer   — pygame Surface renderer (tile grid + entities + HUD)
  WorldPlay       — top-level waking play controller

  build_game7_world() — assemble the starter world for 7_KLGS
"""

from .map import (
    WorldMap,
    Zone,
    Realm,
    WorldTileKind,
    ZoneExit,
    DungeonPortal,
    NPCSpawn,
    ItemSpawn,
    build_zone_from_ascii,
)
from .zones.lapidus import VENDOR_CATALOGS
from .vendor_screen import VendorScreen
from .calendar import (
    AeraluneDate,
    WorldClock,
    TimeOfDay,
    MONTHS,
    VRWUMANE,
    DAYS_PER_MONTH,
    DAYS_PER_YEAR,
    ASTRONOMICAL_ANCHORS,
    SPRING_EQUINOX,
    SUMMER_SOLSTICE,
    AUTUMN_EQUINOX,
    WINTER_SOLSTICE,
    fountain_running,
    alzedroswune_present,
    AlchemyCalendarContext,
    get_alchemy_calendar_context,
)
from .player   import WorldPlayer, Direction
from .renderer import WorldRenderer
from .play     import WorldPlay, WorldMode
from .zones    import build_game7_world
from .loaders  import (
    EncounterDef,
    AudioTrack,
    load_encounter_defs,
    load_audio_tracks,
    load_quest_steps,
    select_audio,
)
from .map_discovery import MapDiscoveryScreen, MapState
from .alchemy_screen import AlchemyScreen
from .combat        import (
    CombatScreen, CombatResult, CombatLoop,
    resolve_combat, npc_difficulty,
    begin_combat_loop, execute_round, to_result,
    player_health_from_vitality, npc_hits_to_kill,
    npc_damage_per_hit, endurance_reduction,
    AMMO_GOLD_ROUNDS, WEAPON_ANGELIC_SPEAR,
)
from .tile_trace    import (
    TileTracer, TileAttestation, LOTUS_TABLE,
    FY, PU, TA, ZO, SHA, KO,
)

__all__ = [
    "WorldMap",
    "Zone",
    "Realm",
    "WorldTileKind",
    "ZoneExit",
    "DungeonPortal",
    "NPCSpawn",
    "ItemSpawn",
    "build_zone_from_ascii",
    "VENDOR_CATALOGS",
    "VendorScreen",
    "WorldPlayer",
    "Direction",
    "WorldRenderer",
    "WorldPlay",
    "WorldMode",
    "build_game7_world",
    "EncounterDef",
    "AudioTrack",
    "load_encounter_defs",
    "load_audio_tracks",
    "load_quest_steps",
    "select_audio",
    "MapDiscoveryScreen",
    "MapState",
    "AlchemyScreen",
    "CombatScreen",
    "CombatResult",
    "CombatLoop",
    "resolve_combat",
    "npc_difficulty",
    "begin_combat_loop",
    "execute_round",
    "to_result",
    "player_health_from_vitality",
    "npc_hits_to_kill",
    "npc_damage_per_hit",
    "endurance_reduction",
    "AMMO_GOLD_ROUNDS",
    "WEAPON_ANGELIC_SPEAR",
    "TileTracer",
    "TileAttestation",
    "LOTUS_TABLE",
    "FY", "PU", "TA", "ZO", "SHA", "KO",
    # Calendar
    "AeraluneDate",
    "WorldClock",
    "TimeOfDay",
    "MONTHS",
    "VRWUMANE",
    "DAYS_PER_MONTH",
    "DAYS_PER_YEAR",
    "ASTRONOMICAL_ANCHORS",
    "SPRING_EQUINOX",
    "SUMMER_SOLSTICE",
    "AUTUMN_EQUINOX",
    "WINTER_SOLSTICE",
    "fountain_running",
    "alzedroswune_present",
    "AlchemyCalendarContext",
    "get_alchemy_calendar_context",
]