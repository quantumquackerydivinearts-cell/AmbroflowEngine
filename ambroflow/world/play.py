"""
WorldPlay — Waking Play Controller
====================================
Top-level state machine for waking play after the GameFlow intro pipeline.

Accepts pygame events via tick(), renders directly to a pygame Surface via
render().  No PIL intermediate for tile rendering.

Modes
-----
  WORLD     Free navigation — tile grid rendered every frame.
  DIALOGUE  Talking to an NPC — world frozen, PIL dialogue panel overlaid.
            Freeze happens on the first render() call in DIALOGUE mode.
  DUNGEON   Inside a DungeonRuntime session (future: full dungeon renderer).
  DONE      Session complete — app returns to GAME_SELECT.

Frozen background
-----------------
When entering DIALOGUE, the world is not re-rendered.  On the first render()
call in that mode the current screen is snapshot()d into _frozen_bg.  Every
subsequent dialogue frame blits the frozen copy + the PIL dialogue bytes.
Dialogue ends via Space / Enter / Escape; the frozen copy is discarded.
"""

from __future__ import annotations

import random
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..chargen.data import ChargenState

try:
    import pygame
    _PG = True
except ImportError:
    _PG = False

from dataclasses import dataclass as _dataclass

from .map import WorldMap, Zone, NPCSchedule, is_passable as _is_passable
from ..pathfinding.astar import astar as _astar
from .player import WorldPlayer, Direction


_TICKS_PER_HOUR:  int = 3_000   # ~50 real-seconds per game-hour at 60 fps
_SCHED_STEP_TICKS: int = 45    # path-following step rate (slightly faster than patrol)


def _time_of_day_at(hour: int) -> str:
    """Map a 0–23 hour to a TimeOfDay.value string (mirrors calendar.py logic)."""
    h = hour % 24
    if h in (5, 6):       return "dawn"
    if 7  <= h <= 11:     return "morning"
    if 12 <= h <= 16:     return "afternoon"
    if h in (17, 18):     return "late_afternoon"
    if h in (19, 20):     return "dusk"
    return "night"


def _route_for(zone: Zone, cid: str):
    """Return the NPCRoute for character_id in zone, or None."""
    for r in getattr(zone, "npc_routes", []):
        if r.character_id == cid:
            return r
    return None


@_dataclass
class _MobileNPCState:
    x:          int
    y:          int
    wp_idx:     int         # current waypoint index (route fallback)
    wp_dir:     int         # +1 forward / -1 reverse (pingpong only)
    tick_acc:   int         # ticks since last step
    # Schedule fields
    sched_tx:   int  = -1  # A* target x (-1 = no active schedule target)
    sched_ty:   int  = -1
    activity:   str  = "idle"
    sched_path: object = None   # list[tuple[int,int]] | None — pending path
    path_idx:   int  = 0        # next step index in sched_path
from .renderer import WorldRenderer
from .loaders import EncounterDef, AudioTrack, select_audio
from .map_discovery import MapDiscoveryScreen, MapState, ITEM_ID as _MAP_ITEM_ID, _JOURNAL_TITLE, _JOURNAL_BODY
from .tile_trace import TileTracer, FY, KO, TA, PU, ZO
from .combat    import (
    CombatScreen, CombatResult, CombatLoop,
    resolve_combat, begin_combat_loop, execute_round, to_result,
    AMMO_GOLD_ROUNDS, WEAPON_ANGELIC_SPEAR,
)
from .alchemy_screen import AlchemyScreen, _APPROACHES
from .vendor_screen import VendorScreen, COIN_ID
from .journal_screen import JournalScreen
from .inventory_screen import InventoryScreen
from ..inventory.equipment import EquipmentSlots, slot_for, EQUIPPABLE

# ── qqva quest engine (graceful fallback) ────────────────────────────────────

try:
    from qqva.quest_engine import WitnessTracker  # type: ignore
    _HAS_QQVA = True
except Exception:
    WitnessTracker = None  # type: ignore
    _HAS_QQVA = False

# ── Dialogue selector (graceful fallback) ────────────────────────────────────

try:
    from ..dialogue.selector import select as _dialogue_select, DialogueScreen
    _HAS_DIALOGUE = True
except Exception:
    _dialogue_select = None  # type: ignore
    DialogueScreen = None    # type: ignore
    _HAS_DIALOGUE = False

# ── DungeonRuntime (graceful fallback) ───────────────────────────────────────

try:
    from ..dungeon.runtime import DungeonRuntime, PlayerState as DungeonPlayerState
    _HAS_DUNGEON = True
except Exception:
    DungeonRuntime = None         # type: ignore
    DungeonPlayerState = None     # type: ignore
    _HAS_DUNGEON = False


# ── Pygame-ce (SDL2) key constants ───────────────────────────────────────────

_K_UP     = 1073741906
_K_DOWN   = 1073741905
_K_LEFT   = 1073741904
_K_RIGHT  = 1073741903
_K_RETURN = 13
_K_SPACE  = 32
_K_ESCAPE = 27
_K_FIGHT     = ord('f')
_K_ALCHEMY   = ord('z')
_K_JOURNAL   = ord('j')
_K_INVENTORY = ord('i')
_K_TAB       = 9

_DIR_KEYS: dict[int, Direction] = {
    _K_UP:    Direction.NORTH,
    _K_DOWN:  Direction.SOUTH,
    _K_LEFT:  Direction.WEST,
    _K_RIGHT: Direction.EAST,
}

_WASD: dict[int, Direction] = {
    ord('w'): Direction.NORTH,
    ord('s'): Direction.SOUTH,
    ord('a'): Direction.WEST,
    ord('d'): Direction.EAST,
}


class WorldMode(str, Enum):
    WORLD         = "world"
    DIALOGUE      = "dialogue"
    DUNGEON       = "dungeon"
    MAP_DISCOVERY = "map_discovery"
    COMBAT        = "combat"
    ALCHEMY       = "alchemy"
    VENDOR        = "vendor"
    SHOP          = "shop"     # player-operated trade screen
    SMELT         = "smelt"      # forge / smelting UI
    JOURNAL       = "journal"    # in-game journal overlay
    INVENTORY     = "inventory"  # player inventory overlay
    DEAD          = "dead"
    DONE          = "done"


class WorldPlay:
    """
    Waking play controller.

    Constructed by app.py once GameFlow signals DONE; destroyed when
    is_done() returns True (player quits or session ends).

    Optional parameters wire in the dialogue, encounter, audio, and
    dungeon systems.  Any omitted system degrades gracefully (dialogue
    shows a blank panel, encounters are skipped, etc.).
    """

    def __init__(
        self,
        chargen:          "ChargenState",
        world_map:        WorldMap,
        width:            int  = 1280,
        height:           int  = 800,
        *,
        bundle:           object                          = None,  # GameDataBundle
        paths_by_char:    Optional[Dict[str, list]]       = None,
        quest_state:      Optional[Dict[str, Any]]        = None,
        encounter_defs:   Optional[List[EncounterDef]]    = None,
        audio_tracks:     Optional[List[AudioTrack]]      = None,
        dungeon_registry: Optional[Dict[str, object]]     = None,  # dungeon_id → DungeonDef
        orrery:           object                          = None,  # OrreryClient
        inventory:        object                          = None,  # Inventory instance
        journal:          object                          = None,  # Journal instance
        tile_tracer:      Optional[TileTracer]            = None,
        clock:            object                          = None,  # WorldClock instance
        alchemy:          object                          = None,  # AlchemySystem instance
        presence:         object                          = None,  # PresenceState instance
        recipe_book:      object                          = None,  # RecipeBook instance
        vendor_catalogs:  Optional[Dict[str, Dict[str, int]]] = None,
        breath:           object                          = None,  # BreathOfKo instance
        physics_world:    object                          = None,  # PhysicsWorld instance
        quest_runtime:    object                          = None,  # QuestRuntime instance
    ) -> None:
        self.width     = width
        self.height    = height
        self._mode     = WorldMode.WORLD
        self._world    = world_map
        self._renderer = WorldRenderer(width, height)

        starting = world_map.zones[world_map.starting_zone_id]
        sx, sy   = starting.player_spawn
        self._player = WorldPlayer(
            zone_id=world_map.starting_zone_id,
            x=sx, y=sy,
            name=chargen.name or "Apprentice",
        )
        self._zone:    Zone         = starting
        self._chargen: "ChargenState" = chargen

        # Dialogue system
        self._bundle         = bundle
        self._paths_by_char  = paths_by_char or {}
        self._frozen_bg:     object          = None
        self._dialogue_bytes: Optional[bytes] = None
        self._dialogue_needs_snapshot: bool   = False

        # Quest state
        self._quest_state: Dict[str, Any] = quest_state or {
            "quest_id": "", "game_id": "", "entries": {},
            "soa_artifacts": [], "current_frame": "frame_0",
        }
        self._witness_tracker = WitnessTracker() if _HAS_QQVA else None

        # Encounter + audio
        self._encounter_defs    = encounter_defs  or []
        self._audio_tracks      = audio_tracks    or []
        self._active_track: Optional[AudioTrack]  = None

        # Dungeon
        self._dungeon_registry  = dungeon_registry or {}
        self._orrery            = orrery
        self._dungeon_runtime: object = None

        # Inventory + journal (optional — graceful no-ops when absent)
        self._inventory = inventory
        self._journal   = journal

        # Clock (optional — advances 1 hour per zone transition)
        self._clock = clock

        # BreathOfKo — Akashic write target (optional)
        self._breath = breath

        # Physics world — passed into treat() for session-persistent simulation
        self._physics_world = physics_world

        # Quest runtime — KeyRing + QuestTracker + SceneRunner bundle
        self._quest_runtime = quest_runtime

        # Alchemy (optional — graceful no-ops when absent)
        self._alchemy       = alchemy
        self._presence      = presence
        self._recipe_book   = recipe_book
        self._alchemy_screen = AlchemyScreen()
        # Session state
        self._alchemy_subjects:     list  = []
        self._alchemy_subject_idx:  int   = 0
        self._alchemy_approach_idx: int   = 0
        self._alchemy_phase:        str   = "subject"   # subject | lab | lab_flash | approach | result
        self._alchemy_result:       object = None
        self._alchemy_bytes:        Optional[bytes] = None
        self._alchemy_calendar_ctx: object = None
        # Lab session state (populated when phase == "lab")
        self._lab_session:          object = None   # LaboratorySession or None
        self._lab_op_idx:           int    = 0
        self._lab_op_result:        object = None   # last OperationResult (flash screen)

        # Vendor (optional)
        self._vendor_catalogs: Dict[str, Dict[str, int]] = vendor_catalogs or {}
        self._vendor_screen    = VendorScreen()
        self._vendor_catalog:  list  = []   # [(item_id, price), ...]
        self._vendor_name:     str   = ""
        self._vendor_idx:      int   = 0
        self._vendor_bytes:    Optional[bytes] = None

        # Journal overlay
        self._journal_screen  = JournalScreen()
        self._journal_cursor  = 0
        self._journal_page    = 0
        self._journal_detail  = False   # True = expanded detail view
        self._journal_bytes:  Optional[bytes] = None

        # Inventory overlay
        self._inventory_screen = InventoryScreen()
        self._inventory_cursor: int            = 0
        self._inventory_bytes:  Optional[bytes] = None
        self._inv_tab:          str             = "items"
        self._equip_cursor:     int             = 0
        self._equipment:        EquipmentSlots  = EquipmentSlots()

        # Item spawn tracking — zone_ids whose spawns have been collected
        self._collected_zones: set[str] = set()

        # Collect item spawns for the starting zone
        self._collect_zone_items(starting)

        # Zone/NPC discovery tracking for journal auto-writes
        self._seen_zones: set[str] = set()
        self._met_npcs:   set[str] = set()

        # Tile tracer — created fresh if not supplied
        self._tracer: TileTracer = tile_tracer or TileTracer(orrery=orrery)

        # Map discovery
        self._map_screen: Optional[MapDiscoveryScreen] = None
        self._map_state:  MapState                     = MapState.FOLDED
        self._map_bytes:  Optional[bytes]              = None
        self._map_item_collected: bool                 = False

        # Free combat
        self._combat_screen:   CombatScreen            = CombatScreen()
        self._combat_npc:      object                  = None   # NPCSpawn | None
        self._combat_loop:     Optional[CombatLoop]    = None
        self._combat_result:   Optional[CombatResult]  = None
        self._combat_bytes:    Optional[bytes]         = None
        self._dead_npcs:       set[str]                = set()
        self._necromancy_npcs: set[str]                = set()   # raised once by Lakota's perk
        self._permanently_dead: set[str]               = set()   # raised then killed again — no re-raise

        # Mobile NPC live positions — keyed by character_id
        self._mobile_state:    dict[str, _MobileNPCState] = {}
        self._tick_count:      int  = 0
        self._schedule_index:  dict = {}   # character_id → NPCSchedule
        self._passable_cache:  dict = {}   # passable voxels for A* (reset per zone)
        self._hour_tick_acc:   int  = 0
        self._current_hour:    int  = 6    # dawn default; syncs from WorldClock when present
        self._init_mobile_npcs(starting)

        # HUD hint text
        self._hint: str = ""

    # ── Public interface ──────────────────────────────────────────────────────

    def is_done(self) -> bool:
        return self._mode == WorldMode.DONE

    @property
    def tile_tracer(self) -> TileTracer:
        return self._tracer

    def current_tile_context(self) -> dict:
        """
        Wraith context dict for the tile the player is currently standing on.
        Passed to dialogue selectors so NPC responses can be informed by what
        Ko, Haldoro, and Vios have already witnessed here.
        """
        return self._tracer.wraith_context(
            self._player.zone_id, self._player.x, self._player.y)

    def tick(self, dt: float, events: list) -> None:
        """Process pygame events for the current frame."""
        if not _PG:
            return
        self._tick_count  += 1
        self._hour_tick_acc += 1
        if self._hour_tick_acc >= _TICKS_PER_HOUR:
            self._hour_tick_acc = 0
            if self._clock is not None:
                try:
                    self._current_hour = self._clock.hour
                except Exception:
                    self._current_hour = (self._current_hour + 1) % 24
            else:
                self._current_hour = (self._current_hour + 1) % 24
            self._evaluate_schedules()
        self._advance_mobile_npcs()
        for event in events:
            if not hasattr(event, "type"):
                continue
            if event.type != pygame.KEYDOWN:
                continue
            self._handle_key(event.key)
        self._update_hint()

    def render(self, screen: object) -> None:
        """Render the current frame directly to the pygame screen Surface."""
        if not _PG:
            return
        zone = self._zone

        if self._mode == WorldMode.DIALOGUE:
            if self._dialogue_needs_snapshot:
                self._renderer.render(screen, zone, self._player)
                self._frozen_bg = self._renderer.snapshot(screen)
                self._dialogue_needs_snapshot = False
            self._renderer.render_with_dialogue(
                screen, self._frozen_bg, self._dialogue_bytes)

        elif self._mode == WorldMode.WORLD:
            self._renderer.render(screen, zone, self._player, hint=self._hint,
                                  npc_overrides=self._mobile_positions(),
                                  visible_npc_ids=self._visible_npc_ids())

        elif self._mode == WorldMode.DUNGEON:
            if self._frozen_bg is not None:
                screen.blit(self._frozen_bg, (0, 0))

        elif self._mode == WorldMode.COMBAT:
            if self._combat_bytes is not None:
                import io as _io
                try:
                    from PIL import Image as _Img
                    pil = _Img.open(_io.BytesIO(self._combat_bytes))
                    surf = pygame.image.fromstring(pil.tobytes(), pil.size, pil.mode)
                    screen.blit(surf, (0, 0))
                except Exception:
                    pass

        elif self._mode == WorldMode.MAP_DISCOVERY:
            if self._map_bytes is not None:
                import io
                try:
                    from PIL import Image
                    pil_img = Image.open(io.BytesIO(self._map_bytes))
                    surf    = pygame.image.fromstring(
                        pil_img.tobytes(), pil_img.size, pil_img.mode)
                    screen.blit(surf, (0, 0))
                except Exception:
                    pass

        elif self._mode == WorldMode.ALCHEMY:
            if self._alchemy_bytes is not None:
                import io as _io2
                try:
                    from PIL import Image as _Img2
                    pil = _Img2.open(_io2.BytesIO(self._alchemy_bytes))
                    surf = pygame.image.fromstring(pil.tobytes(), pil.size, pil.mode)
                    screen.blit(surf, (0, 0))
                except Exception:
                    pass

        elif self._mode == WorldMode.VENDOR:
            if self._vendor_bytes is not None:
                import io as _io3
                try:
                    from PIL import Image as _Img3
                    pil = _Img3.open(_io3.BytesIO(self._vendor_bytes))
                    surf = pygame.image.fromstring(pil.tobytes(), pil.size, pil.mode)
                    screen.blit(surf, (0, 0))
                except Exception:
                    pass

        elif self._mode == WorldMode.JOURNAL:
            if self._journal_bytes is not None:
                import io as _io4
                try:
                    from PIL import Image as _Img4
                    pil = _Img4.open(_io4.BytesIO(self._journal_bytes))
                    surf = pygame.image.fromstring(pil.tobytes(), pil.size, pil.mode)
                    screen.blit(surf, (0, 0))
                except Exception:
                    pass

        elif self._mode == WorldMode.INVENTORY:
            if self._inventory_bytes is not None:
                import io as _io5
                try:
                    from PIL import Image as _Img5
                    pil = _Img5.open(_io5.BytesIO(self._inventory_bytes))
                    surf = pygame.image.fromstring(pil.tobytes(), pil.size, pil.mode)
                    screen.blit(surf, (0, 0))
                except Exception:
                    pass

    def akashic_context(self) -> object:
        """Return the AkashicContext for this session, or None if unavailable."""
        if self._breath is not None:
            ar = getattr(self._breath, "akashic_record", None)
            if ar is not None:
                try:
                    return ar.context()
                except Exception:
                    pass
        return None

    def advance_quest(self, entry_id: str, candidate: str) -> None:
        """
        Witness a quest entry with the given candidate choice.

        Delegates to WitnessTracker.advance() when qqva is available;
        applies a structural fallback update to the quest_state dict otherwise.
        """
        self._tracer.deposit(
            self._player.zone_id, self._player.x, self._player.y, KO,
            context={"quest_entry": entry_id, "candidate": candidate},
        )
        # Akashic: record this choice
        if self._breath is not None:
            ar = getattr(self._breath, "akashic_record", None)
            if ar is not None:
                try:
                    ar.record_choice(entry_id)
                except Exception:
                    pass

        if self._witness_tracker is not None:
            event = {
                "event_type": "witness",
                "entry_id":   entry_id,
                "candidate":  candidate,
            }
            self._quest_state = self._witness_tracker.advance(
                self._quest_state, event)
        else:
            entries = dict(self._quest_state.get("entries") or {})
            entry = dict(entries.get(entry_id) or {})
            entry["witness_state"]       = "witnessed"
            entry["witnessed_candidate"] = candidate
            entries[entry_id] = entry
            self._quest_state = {**self._quest_state, "entries": entries}

        # Propagate through the KeyRing / SceneRunner pipeline
        if self._quest_runtime is not None:
            try:
                self._quest_runtime.grant(entry_id)
            except Exception:
                pass

    # ── Key handling ──────────────────────────────────────────────────────────

    def _handle_key(self, key: int) -> None:
        if key == _K_ESCAPE:
            if self._mode == WorldMode.DIALOGUE:
                self._end_dialogue()
            elif self._mode == WorldMode.DUNGEON:
                self._exit_dungeon()
            elif self._mode == WorldMode.MAP_DISCOVERY:
                self._close_map()
            elif self._mode == WorldMode.ALCHEMY:
                self._end_alchemy()
            elif self._mode == WorldMode.JOURNAL:
                self._end_journal()
            elif self._mode == WorldMode.INVENTORY:
                self._end_inventory()
            elif self._mode in (WorldMode.VENDOR, WorldMode.SHOP):
                # VENDOR is WorldPlay's internal shop mode; SHOP is set directly
                # by the GL layer — both dismiss the overlay and return to free roam.
                self._end_vendor()
            elif self._mode == WorldMode.SMELT:
                self._mode = WorldMode.WORLD
            elif self._mode == WorldMode.COMBAT:
                if self._combat_loop is None:
                    self._abort_combat()
                # else: flee is handled in the COMBAT block below
            else:
                self._mode = WorldMode.DONE
            return

        if self._mode == WorldMode.DEAD:
            if key in (_K_RETURN, _K_SPACE, _K_ESCAPE):
                self._mode = WorldMode.DONE
            return

        if self._mode == WorldMode.COMBAT:
            if self._combat_result is not None:
                # Result phase — loop is over, outcome shown
                if key in (_K_RETURN, _K_SPACE):
                    self._end_combat()
            elif self._combat_loop is not None:
                # Active loop
                if key == _K_FIGHT:
                    self._process_round("attack")
                elif key == _K_ESCAPE:
                    self._process_round("flee")
                    return   # esc consumed by flee, not by outer esc handler
            return

        if self._mode == WorldMode.MAP_DISCOVERY:
            if key in (_K_RETURN, _K_SPACE):
                if self._map_state == MapState.FOLDED:
                    self._map_state = MapState.UNFOLDED
                    self._refresh_map_bytes()
                else:
                    self._close_map()
            return

        if self._mode == WorldMode.DIALOGUE:
            if key in (_K_RETURN, _K_SPACE):
                self._end_dialogue()
            return

        if self._mode == WorldMode.DUNGEON:
            # TODO: route to DungeonRuntime.move() / act()
            return

        if self._mode == WorldMode.ALCHEMY:
            self._handle_alchemy_key(key)
            return

        if self._mode == WorldMode.VENDOR:
            self._handle_vendor_key(key)
            return

        if self._mode == WorldMode.JOURNAL:
            self._handle_journal_key(key)
            return

        if self._mode == WorldMode.INVENTORY:
            self._handle_inventory_key(key)
            return

        if self._mode == WorldMode.WORLD:
            direction = _DIR_KEYS.get(key) or _WASD.get(key)
            if direction is not None:
                self._move(direction)
            elif key in (_K_RETURN, _K_SPACE):
                self._interact()
            elif key == _K_FIGHT:
                self._try_attack()
            elif key == _K_ALCHEMY:
                self._begin_alchemy()
            elif key == _K_JOURNAL:
                self._begin_journal()
            elif key == _K_INVENTORY:
                self._begin_inventory()

    # ── Movement ─────────────────────────────────────────────────────────────

    def _move(self, direction: Direction) -> None:
        zone = self._zone
        moved, exit_trig, portal_trig = self._player.move(direction, zone)

        if exit_trig is not None:
            if not self._cond_met(exit_trig.condition):
                self._hint = "(the way is not yet open)"
                return
            self._transition_zone(exit_trig)
        elif portal_trig is not None:
            if not self._cond_met(portal_trig.condition):
                self._hint = "(the way is not yet open)"
                return
            self._enter_dungeon(portal_trig)
        elif moved:
            self._tracer.deposit(
                self._player.zone_id, self._player.x, self._player.y, TA,
            )
            self._check_encounters()

    # ── Zone transition ───────────────────────────────────────────────────────

    # ── Mobile NPCs ───────────────────────────────────────────────────────────

    def _init_mobile_npcs(self, zone: Zone) -> None:
        """Build live mobile state for the new zone and evaluate initial schedules."""
        self._mobile_state.clear()
        self._schedule_index.clear()

        # Passable voxel cache for A* (rebuilt per zone)
        self._passable_cache = {
            pos: kind for pos, kind in zone.voxels.items()
            if _is_passable(kind)
        }

        # Schedule index — only schedules whose condition is currently met
        for sched in getattr(zone, "npc_schedules", []):
            if self._cond_met(sched.condition):
                self._schedule_index[sched.character_id] = sched

        # States for route-based NPCs — skip routes whose condition is not met
        for route in getattr(zone, "npc_routes", []):
            if not route.waypoints:
                continue
            if not self._cond_met(route.condition):
                continue
            wx, wy = route.waypoints[0]
            self._mobile_state[route.character_id] = _MobileNPCState(
                x=wx, y=wy, wp_idx=0, wp_dir=1, tick_acc=0,
            )

        # States for schedule-only NPCs (no patrol route)
        for cid in self._schedule_index:
            if cid in self._mobile_state:
                continue
            spawn = zone.npc_by_char(cid)
            if spawn is not None:
                self._mobile_state[cid] = _MobileNPCState(
                    x=spawn.x, y=spawn.y, wp_idx=0, wp_dir=1, tick_acc=0,
                )

        self._evaluate_schedules()

    def _evaluate_schedules(self) -> None:
        """
        Re-evaluate every NPCSchedule against the current hour.

        Called on zone init and every time the game-clock advances one hour.
        Sets A* paths toward new targets, or marks NPCs absent when their
        schedule puts them in another zone.
        """
        tod      = _time_of_day_at(self._current_hour)
        zone_id  = self._zone.zone_id
        passable = self._passable_cache

        for cid, sched in self._schedule_index.items():
            if cid in self._dead_npcs:
                continue
            state = self._mobile_state.get(cid)
            if state is None:
                continue

            # First matching entry wins
            entry = None
            for e in sched.entries:
                if e.time_of_day != tod:
                    continue
                if not self._cond_met(e.condition):
                    continue
                entry = e
                break

            if entry is None:
                # No matching entry — clear any active schedule target
                state.sched_tx   = -1
                state.sched_ty   = -1
                state.sched_path = None
                state.path_idx   = 0
                continue

            # NPC is in a different zone at this hour
            if entry.zone_id and entry.zone_id != zone_id:
                state.sched_tx = -2   # sentinel: absent from current zone
                continue

            # Clear absent flag if re-entering this zone's schedule
            if state.sched_tx == -2:
                state.sched_tx = -1

            state.activity = entry.activity

            # Already at target — nothing to path toward
            if state.x == entry.x and state.y == entry.y:
                state.sched_tx   = entry.x
                state.sched_ty   = entry.y
                state.sched_path = None
                state.path_idx   = 0
                continue

            # Target unchanged — keep existing path
            if state.sched_tx == entry.x and state.sched_ty == entry.y:
                continue

            # New target — compute A* path
            path = _astar(
                start=(state.x, state.y),
                goal=(entry.x, entry.y),
                voxels=passable,
            )
            state.sched_tx   = entry.x
            state.sched_ty   = entry.y
            state.sched_path = path[1:] if path else []
            state.path_idx   = 0

    def _cond_met(self, condition) -> bool:
        """
        Return True if a ZoneCondition is satisfied (or if condition is None).

        "witnessed" — the quest key has been witnessed in this session.
        "pending"   — the quest key has NOT yet been witnessed.

        Checks the legacy quest_state dict first, then the KeyRing as fallback
        so both the old advance_quest() path and the new QuestRuntime path work.
        """
        if condition is None:
            return True
        entries = self._quest_state.get("entries") or {}
        done    = entries.get(condition.key, {}).get("witness_state") == "witnessed"
        if not done and self._quest_runtime is not None:
            try:
                done = self._quest_runtime.keyring.has(condition.key)
            except Exception:
                pass
        return done if condition.mode == "witnessed" else not done

    def _visible_npc_ids(self) -> set:
        """
        Character IDs of NPCs that should be drawn and be interactable this frame.

        Filters by:  quest condition on NPCSpawn, dead_npcs, schedule absent flag.
        """
        absent = {cid for cid, s in self._mobile_state.items() if s.sched_tx == -2}
        return {
            npc.character_id
            for npc in self._zone.npc_spawns
            if self._cond_met(npc.condition)
            and npc.character_id not in self._dead_npcs
            and npc.character_id not in absent
        }

    def _advance_mobile_npcs(self) -> None:
        """
        Step each mobile NPC one tile per tick cycle.

        Priority: schedule path > waypoint route > idle.
        NPCs absent from this zone (sched_tx == -2) are skipped entirely.
        """
        if self._mode != WorldMode.WORLD:
            return
        zone       = self._zone
        player_pos = (self._player.x, self._player.y)

        for cid, state in self._mobile_state.items():
            if cid in self._dead_npcs or state.sched_tx == -2:
                continue

            state.tick_acc += 1

            # ── Schedule path movement ─────────────────────────────────────────
            path = state.sched_path
            if path and state.path_idx < len(path):
                if state.tick_acc < _SCHED_STEP_TICKS:
                    continue
                state.tick_acc = 0
                tx, ty = path[state.path_idx]
                if _is_passable(zone.tile_at(tx, ty)) and (tx, ty) != player_pos:
                    state.x, state.y = tx, ty
                state.path_idx += 1
                continue

            # ── Waypoint route fallback ────────────────────────────────────────
            route = _route_for(zone, cid)
            if route is None or len(route.waypoints) < 2:
                continue
            if state.tick_acc < route.ticks_per_step:
                continue
            state.tick_acc = 0
            wps      = route.waypoints
            next_idx = state.wp_idx + state.wp_dir
            if route.loop == "pingpong":
                if next_idx >= len(wps):
                    state.wp_dir = -1
                    next_idx     = len(wps) - 2
                elif next_idx < 0:
                    state.wp_dir = 1
                    next_idx     = 1
            else:
                next_idx = next_idx % len(wps)
            tx, ty = wps[next_idx]
            if _is_passable(zone.tile_at(tx, ty)) and (tx, ty) != player_pos:
                state.x, state.y = tx, ty
                state.wp_idx     = next_idx

    def _mobile_positions(self) -> dict:
        """Current live positions of mobile NPCs present in this zone."""
        return {
            cid: (s.x, s.y)
            for cid, s in self._mobile_state.items()
            if s.sched_tx != -2   # -2 = NPC is in another zone right now
        }

    def _facing_npc(self):
        """
        Return the NPC directly in front of the player.

        Checks mobile live positions first (so patrolling NPCs are interactable
        wherever they stand), then falls back to static zone spawns.
        Skips NPCs currently scheduled to be in another zone.
        """
        ax, ay = self._player.facing_tile()
        for char_id, state in self._mobile_state.items():
            if state.sched_tx == -2:
                continue
            if state.x == ax and state.y == ay:
                spawn = self._zone.npc_by_char(char_id)
                if spawn is not None:
                    return spawn
        npc = self._zone.npc_at(ax, ay)
        if npc is not None and not self._cond_met(npc.condition):
            return None
        return npc

    # ── Necromancy ────────────────────────────────────────────────────────────
    # Perk granted by Lakota (2018_GODS) after 0026_KLST + 0043_KLST both
    # witnessed.  Raising requires a three-part ritual:
    #   1. Pick up the corpse (any state of decay) at its death location.
    #   2. Carry it to the zodiac fountain in front of Castle Azoth.
    #   3. On a solar day (solstice / equinox) — apply Infernal Salve (0037_KLIT)
    #      and meditate / pray to Lakota.
    # The causal debt — consumed life.time.energy entangled with the fabric of
    # causality, manifesting as infant mortality, sudden elder deaths, etc. — is
    # recorded as a semantic journal entry.  It is real in the lore layer; it is
    # not simulated as mechanical NPC death in this session.

    _INFERNAL_SALVE: str = "0037_KLIT"
    # Castle Azoth fountain tile bounds (rows 5–9, cols 10–18 in lapidus_castle_azoth)
    _FOUNTAIN_ZONE: str  = "lapidus_castle_azoth"
    _FOUNTAIN_X0:   int  = 10
    _FOUNTAIN_X1:   int  = 18
    _FOUNTAIN_Y0:   int  = 5
    _FOUNTAIN_Y1:   int  = 9

    def _has_necromancy_perk(self) -> bool:
        """True when both quests gating Lakota's perk have been witnessed."""
        entries = self._quest_state.get("entries") or {}
        def _w(key: str) -> bool:
            return entries.get(key, {}).get("witness_state") == "witnessed"
        return _w("0026_KLST") and _w("0043_KLST")

    def _is_solar_day(self) -> bool:
        """True on the four astronomical anchors when the fountain runs."""
        if self._clock is None:
            return False
        try:
            return self._clock.date.is_astronomical_anchor()
        except Exception:
            return False

    def _facing_fountain(self) -> bool:
        """True when the player's facing tile is within the Castle Azoth fountain bounds."""
        if self._player.zone_id != self._FOUNTAIN_ZONE:
            return False
        fx, fy = self._player.facing_tile()
        return (self._FOUNTAIN_X0 <= fx <= self._FOUNTAIN_X1
                and self._FOUNTAIN_Y0 <= fy <= self._FOUNTAIN_Y1)

    def _facing_dead_npc(self):
        """
        Return the NPCSpawn of a raiseable dead NPC at the player's facing tile
        whose corpse has not yet been picked up.

        Uses last known mobile-state position.  Permanently-dead NPCs and NPCs
        whose corpse is already in the player's inventory are excluded.
        """
        if self._inventory is None:
            return None
        ax, ay = self._player.facing_tile()
        for cid in self._dead_npcs:
            if cid in self._permanently_dead:
                continue
            if self._inventory.has(f"corpse_{cid}"):
                continue   # already carrying this body
            state = self._mobile_state.get(cid)
            if state is not None and state.x == ax and state.y == ay:
                return self._zone.npc_by_char(cid)
        return None

    def _pickup_corpse(self, cid: str) -> None:
        """Add the corpse of a dead NPC to the player's inventory."""
        if self._inventory is not None:
            try:
                self._inventory.add(f"corpse_{cid}", 1)
            except Exception:
                pass
        self._tracer.deposit(
            self._player.zone_id, self._player.x, self._player.y, PU,
            context={"event": "corpse_picked_up", "npc": cid},
        )
        self._hint = "(carrying the body)"

    def _try_fountain_ritual(self) -> bool:
        """
        Attempt the raising ritual at the Castle Azoth fountain.

        Returns True if this interaction was consumed (even when blocked by a
        missing item or wrong day) so the caller can stop further processing.
        """
        if not self._is_solar_day():
            self._hint = "(the fountain is still — return on a day the sun speaks)"
            return True

        # Find a carried corpse
        raiseable: Optional[str] = None
        if self._inventory is not None:
            for cid in list(self._dead_npcs):
                if cid in self._permanently_dead:
                    continue
                try:
                    if self._inventory.has(f"corpse_{cid}"):
                        raiseable = cid
                        break
                except Exception:
                    pass

        if raiseable is None:
            self._hint = "(bring a body to the fountain)"
            return True

        if self._inventory is None or not self._inventory.has(self._INFERNAL_SALVE):
            self._hint = "(you need Infernal Salve)"
            return True

        # Consume ritual items
        try:
            self._inventory.remove(self._INFERNAL_SALVE, 1)
            self._inventory.remove(f"corpse_{raiseable}", 1)
        except Exception:
            pass

        self._raise_npc(raiseable)
        return True

    def _raise_npc(self, cid: str) -> None:
        """
        Return a dead NPC to perfect healthful life via Lakota's perk.

        Called from the fountain ritual.  The NPC materialises at the player's
        position (the fountain) and resumes their schedule from there.
        """
        self._dead_npcs.discard(cid)
        self._necromancy_npcs.add(cid)

        self._tracer.deposit(
            self._player.zone_id, self._player.x, self._player.y, KO,
            context={"event": "npc_raised", "npc": cid},
        )
        self.advance_quest(f"raised_{cid}", "raised")

        if self._journal is not None:
            try:
                from ..journal.journal import EntryKind
                self._journal.write(
                    EntryKind.LORE_FRAGMENT,
                    f"Raised: {cid}",
                    (
                        f"{cid} was returned to a state of perfect healthful life.\n"
                        f"Their other life.time.energy was consumed in the weaving —\n"
                        f"an eternal debt woven into the fabric of causality itself.\n"
                        f"Lakota's fire burns in both directions."
                    ),
                    tags=[cid, "0026_KLST", "0043_KLST", "2018_GODS"],
                )
            except Exception:
                pass

        # Materialise at the ritual site; schedule paths from here
        state = self._mobile_state.get(cid)
        if state is not None:
            state.x        = self._player.x
            state.y        = self._player.y
            state.sched_tx   = -1
            state.sched_ty   = -1
            state.activity   = "idle"
            state.sched_path = None
            state.path_idx   = 0
            state.tick_acc   = 0
        else:
            self._mobile_state[cid] = _MobileNPCState(
                x=self._player.x, y=self._player.y,
                wp_idx=0, wp_dir=1, tick_acc=0,
            )
        self._evaluate_schedules()

    def _transition_zone(self, exit_trig) -> None:
        target = self._world.zones.get(exit_trig.target_zone)
        if target is None:
            self._hint = "(nothing that way yet)"
            return
        self._player.zone_id = exit_trig.target_zone
        self._player.x       = exit_trig.target_x
        self._player.y       = exit_trig.target_y
        self._zone           = target
        self._active_track   = self._select_audio_track()

        # Advance clock one hour per zone crossing, then re-init NPCs in the
        # new zone (which also calls _evaluate_schedules with the updated hour)
        if self._clock is not None:
            try:
                self._clock.advance(1)
                self._current_hour = self._clock.hour
            except Exception:
                self._current_hour = (self._current_hour + 1) % 24
        else:
            self._current_hour = (self._current_hour + 1) % 24

        self._init_mobile_npcs(target)

        # Sync runner hour with clock
        if self._quest_runtime is not None:
            self._quest_runtime.set_hour(self._current_hour)

        # Fire auto-scenes and grant their keys (ENV-only, non-interactive)
        if self._quest_runtime is not None:
            new_keys = self._quest_runtime.on_zone_entry(exit_trig.target_zone)
            for key in new_keys:
                entries = dict(self._quest_state.get("entries") or {})
                if key not in entries:
                    entries[key] = {"witness_state": "witnessed", "witnessed_candidate": "auto"}
                    self._quest_state = {**self._quest_state, "entries": entries}

        # First-visit: journal entry + item spawn collection
        zone_id = exit_trig.target_zone
        if zone_id not in self._seen_zones:
            self._seen_zones.add(zone_id)
            self._journal_zone_discovered(zone_id, target)
            self._collect_zone_items(target)

    def _collect_zone_items(self, zone) -> None:
        """Auto-collect all ItemSpawns in `zone` on first visit."""
        if self._inventory is None:
            return
        zone_id = getattr(zone, "zone_id", None)
        if zone_id is None or zone_id in self._collected_zones:
            return
        self._collected_zones.add(zone_id)
        for spawn in getattr(zone, "item_spawns", []):
            if not self._cond_met(spawn.condition):
                continue
            try:
                self._inventory.add(spawn.item_id, spawn.qty)
            except Exception:
                pass

    # ── Encounter checking ────────────────────────────────────────────────────

    def _check_encounters(self) -> None:
        """Evaluate all encounter defs; trigger the first matching one."""
        zone_id = self._player.zone_id
        for enc in self._encounter_defs:
            if enc.fires(self._quest_state, zone_id):
                self._tracer.deposit(
                    self._player.zone_id, self._player.x, self._player.y, KO,
                    context={"encounter": enc.name},
                )
                if enc.name == "forest_journal_discovery":
                    self._begin_map_discovery()
                else:
                    self._hint = f"[ encounter: {enc.name} ]"
                return

    # ── Audio track selection ─────────────────────────────────────────────────

    def _select_audio_track(self) -> Optional[AudioTrack]:
        """Pick the best audio track for current realm + quest state."""
        realm_id = self._zone.realm.value if hasattr(self._zone.realm, "value") else str(self._zone.realm)
        return select_audio(self._audio_tracks, self._quest_state, realm_id)

    # ── Interaction ───────────────────────────────────────────────────────────

    def _interact(self) -> None:
        zone = self._zone
        npc  = self._facing_npc()
        if npc is not None and npc.character_id not in self._dead_npcs:
            if npc.character_id in self._vendor_catalogs:
                self._begin_vendor(npc)
            else:
                self._begin_dialogue(npc)
            return
        if self._has_necromancy_perk():
            # Fountain ritual — facing fountain stone/water tiles in Castle Azoth
            if self._facing_fountain():
                self._try_fountain_ritual()
                return
            # Corpse pickup — facing a dead body at its last position
            dead_npc = self._facing_dead_npc()
            if dead_npc is not None:
                self._pickup_corpse(dead_npc.character_id)
                return
        portal = self._player.facing_portal(zone)
        if portal is not None:
            self._enter_dungeon(portal)

    def _update_hint(self) -> None:
        if self._mode != WorldMode.WORLD:
            self._hint = ""
            return
        zone = self._zone
        npc  = self._facing_npc()
        if npc is not None and npc.character_id not in self._dead_npcs:
            self._hint = "[space]  Talk     [f]  Attack"
            return
        if self._has_necromancy_perk():
            if self._facing_fountain():
                if self._is_solar_day():
                    self._hint = "[space]  Ritual"
                else:
                    self._hint = "(the fountain is still)"
                return
            dead_npc = self._facing_dead_npc()
            if dead_npc is not None:
                self._hint = "[space]  Pick up body"
                return
        portal = self._player.facing_portal(zone)
        if portal is not None:
            self._hint = "[space]  Enter dungeon"
            return
        hints = []
        if self._alchemy is not None:
            hints.append("[z] Alchemy")
        if self._journal is not None:
            hints.append("[j] Journal")
        self._hint = "   ".join(hints)

    # ── Dialogue ─────────────────────────────────────────────────────────────

    def _begin_dialogue(self, npc) -> None:
        char_id = getattr(npc, "character_id", str(npc))
        self._tracer.deposit(
            self._player.zone_id, self._player.x, self._player.y, FY,
            context={"npc": char_id},
        )
        self._mode                    = WorldMode.DIALOGUE
        self._dialogue_needs_snapshot = True
        self._frozen_bg               = None
        self._dialogue_bytes          = None

        # First-meeting character note + quest key grant
        if char_id not in self._met_npcs:
            self._met_npcs.add(char_id)
            self._journal_npc_met(npc)
            # Grant "met_<char_id>" key so quests can gate on first encounter
            self.advance_quest(f"met_{char_id}", "met")

        # Fire available dialogue topics for this character (grants topic keys)
        if self._quest_runtime is not None:
            try:
                for topic in self._quest_runtime.available_topics(char_id):
                    self._quest_runtime.runner.fire_topic(topic)
            except Exception:
                pass

        if _HAS_DIALOGUE and self._bundle is not None:
            realm_id = (
                self._zone.realm.value
                if hasattr(self._zone.realm, "value")
                else str(self._zone.realm)
            )
            paths = self._paths_by_char.get(npc.character_id) or []
            screen: Optional[DialogueScreen] = _dialogue_select(
                self._quest_state, realm_id, npc.character_id, paths, self._bundle
            )
            if screen is not None:
                self._dialogue_bytes = screen.render()

    def _end_dialogue(self) -> None:
        self._frozen_bg               = None
        self._dialogue_bytes          = None
        self._dialogue_needs_snapshot = False
        self._mode                    = WorldMode.WORLD

    # ── Dungeon ───────────────────────────────────────────────────────────────

    def _enter_dungeon(self, portal) -> None:
        self._mode = WorldMode.DUNGEON

        if _HAS_DUNGEON and self._orrery is not None:
            dungeon_def = self._dungeon_registry.get(portal.dungeon_id)
            if dungeon_def is not None:
                player_state = DungeonPlayerState(
                    actor_id=getattr(self._chargen, "character_id", "0000_0451"),
                    unlocked_perks=list(getattr(self._chargen, "unlocked_perks", []) or []),
                    completed_quests=list(getattr(self._chargen, "completed_quests", []) or []),
                    held_tokens=list(getattr(self._chargen, "held_tokens", []) or []),
                    skill_ranks=dict(getattr(self._chargen, "skill_ranks", {}) or {}),
                )
                seed = random.randint(0, 0xFFFFFFFF)
                self._dungeon_runtime = DungeonRuntime(
                    dungeon_def, seed, self._orrery, player_state)
                self._dungeon_runtime.start()
                self._hint = f"[ {dungeon_def.name} ]"
                return

        self._hint = f"[ {portal.dungeon_id} ]"

    def _exit_dungeon(self) -> None:
        self._dungeon_runtime = None
        self._frozen_bg       = None
        self._mode            = WorldMode.WORLD

    # ── Free combat ───────────────────────────────────────────────────────────

    def _try_attack(self) -> None:
        npc = self._player.facing_npc(self._zone)
        if npc is None or npc.character_id in self._dead_npcs:
            return
        self._begin_combat(npc)

    def _get_vitriol_stat(self, stat: str, default: int = 5) -> int:
        v = getattr(self._chargen, stat, None)
        if isinstance(v, int):
            return v
        profile = getattr(self._chargen, "vitriol", None)
        if profile is not None:
            v = getattr(profile, stat, None)
            if isinstance(v, int):
                return v
        return default

    def _get_equipped(self) -> str | None:
        if self._inventory is not None:
            if self._inventory.has(AMMO_GOLD_ROUNDS):
                return AMMO_GOLD_ROUNDS
            if self._inventory.has(WEAPON_ANGELIC_SPEAR):
                return WEAPON_ANGELIC_SPEAR
        return None

    def _begin_combat(self, npc) -> None:
        self._tracer.deposit(
            self._player.zone_id, self._player.x, self._player.y, FY,
            context={"event": "combat_initiated", "npc": npc.character_id},
        )
        self._combat_npc    = npc
        self._combat_result = None
        ranks    = dict(getattr(self._chargen, "skill_ranks", {}) or {})
        vitality = self._get_vitriol_stat("vitality")
        tactility = self._get_vitriol_stat("tactility")
        equipped = self._get_equipped()
        npc_name = getattr(npc, "name", npc.character_id)
        self._combat_loop  = begin_combat_loop(
            npc.character_id, npc_name, ranks, vitality, tactility, equipped,
        )
        self._combat_bytes = self._combat_screen.render_prompt(
            npc_name, npc.character_id, self.width, self.height)
        self._mode = WorldMode.COMBAT

    def _process_round(self, action: str) -> None:
        """Execute one turn.  Deposits FY each round; transitions on loop end."""
        loop = self._combat_loop
        if loop is None or loop.is_over:
            return
        # FY per round — persistence of intent
        self._tracer.deposit(
            self._player.zone_id, self._player.x, self._player.y, FY,
            context={"event": "combat_round", "round": loop.round_num + 1,
                     "npc": loop.npc_id},
        )
        execute_round(loop, action)
        if loop.is_over:
            self._combat_result = to_result(loop)
            if loop.outcome == "player_dead":
                self._combat_bytes = self._combat_screen.render_dead(
                    loop, self.width, self.height)
            else:
                self._combat_bytes = self._combat_screen.render_result(
                    self._combat_result, self.width, self.height)
        else:
            self._combat_bytes = self._combat_screen.render_round(
                loop, self.width, self.height)

    def _end_combat(self) -> None:
        result = self._combat_result
        if result is not None:
            if result.outcome == "player_wins":
                # Ku (7, death) + Zo (16, absence) — the kill
                self._tracer.deposit(
                    self._player.zone_id, self._player.x, self._player.y,
                    7, ZO,
                    context={"event": "npc_killed", "npc": result.npc_id},
                )
                if result.npc_id in self._necromancy_npcs:
                    # Second death after a raising — permanent, no re-raise possible
                    self._permanently_dead.add(result.npc_id)
                self._dead_npcs.add(result.npc_id)
                # Keep mobile state — preserves last position for necromancy raise
                self.advance_quest(f"killed_{result.npc_id}", "killed")
            elif result.outcome == "player_flees":
                # Pu (5, stasis) — arrested motion
                self._tracer.deposit(
                    self._player.zone_id, self._player.x, self._player.y, PU,
                    context={"event": "combat_fled", "npc": result.npc_id},
                )
            elif result.outcome == "player_dead":
                # La (11, tense/excited) — the lethal exchange
                self._tracer.deposit(
                    self._player.zone_id, self._player.x, self._player.y, 11,
                    context={"event": "combat_died", "npc": result.npc_id},
                )
                # Akashic: record the death
                if self._breath is not None:
                    ar = getattr(self._breath, "akashic_record", None)
                    if ar is not None:
                        try:
                            game_day = 0
                            if self._clock is not None:
                                game_day = getattr(
                                    getattr(self._clock, "date", None), "day", 0)
                            ar.record_death(
                                zone_id  = self._player.zone_id,
                                cause    = f"combat:{result.npc_id}",
                                game_day = game_day,
                            )
                        except Exception:
                            pass
                self._combat_npc    = None
                self._combat_loop   = None
                self._combat_result = None
                self._combat_bytes  = None
                self._mode          = WorldMode.DEAD
                return
            else:
                # npc_wins (immune entity, no angelic gear)
                self._tracer.deposit(
                    self._player.zone_id, self._player.x, self._player.y, 11,
                    context={"event": "combat_lost", "npc": result.npc_id},
                )

        self._combat_npc    = None
        self._combat_loop   = None
        self._combat_result = None
        self._combat_bytes  = None
        self._mode          = WorldMode.WORLD

    def _abort_combat(self) -> None:
        """Player pressed esc at the prompt before confirming — no consequence."""
        self._combat_npc    = None
        self._combat_loop   = None
        self._combat_result = None
        self._combat_bytes  = None
        self._mode          = WorldMode.WORLD

    # ── Map discovery ─────────────────────────────────────────────────────────

    def _begin_map_discovery(self) -> None:
        """Open the map discovery screen at FOLDED state."""
        self._tracer.deposit(
            self._player.zone_id, self._player.x, self._player.y, FY,
            context={"event": "map_discovery_opened"},
        )
        self._map_screen = MapDiscoveryScreen()
        self._map_state  = MapState.FOLDED
        self._refresh_map_bytes()
        self._mode = WorldMode.MAP_DISCOVERY

    def _refresh_map_bytes(self) -> None:
        if self._map_screen is not None:
            self._map_bytes = self._map_screen.render(
                self._map_state, self.width, self.height)

    def _close_map(self) -> None:
        """Close the map screen; add item to inventory and write journal entry."""
        self._tracer.deposit(
            self._player.zone_id, self._player.x, self._player.y, KO,
            context={"event": "map_collected", "item_id": _MAP_ITEM_ID},
        )
        if not self._map_item_collected:
            self._map_item_collected = True

            # Add to inventory if available
            if self._inventory is not None:
                try:
                    self._inventory.add(_MAP_ITEM_ID)
                except Exception:
                    pass

            # Write journal entry if available
            if self._journal is not None:
                try:
                    from ..journal.journal import EntryKind
                    self._journal.write(
                        EntryKind.LORE_FRAGMENT,
                        _JOURNAL_TITLE,
                        _JOURNAL_BODY,
                        tags=["0007_WTCH", "mercurie", "0036_KLIT"],
                    )
                except Exception:
                    pass

            # Mark quest entry witnessed so the encounter does not re-fire
            self.advance_quest("forest_journal_discovery", "map_received")

        self._map_screen = None
        self._map_bytes  = None
        self._mode       = WorldMode.WORLD

    # ── Journal auto-writes ───────────────────────────────────────────────────

    def _journal_zone_discovered(self, zone_id: str, zone) -> None:
        if self._journal is None:
            return
        try:
            from ..journal.journal import EntryKind
            name = getattr(zone, "name", zone_id)
            self._journal.write(
                EntryKind.OBSERVATION,
                f"Arrived: {name}",
                f"First visit to {name} ({zone_id}).",
                tags=[zone_id, getattr(zone.realm, "value", "lapidus")],
            )
        except Exception:
            pass

    def _journal_npc_met(self, npc) -> None:
        if self._journal is None:
            return
        try:
            from ..journal.journal import EntryKind
            char_id  = getattr(npc, "character_id", str(npc))
            npc_name = getattr(npc, "name", char_id)
            self._journal.write(
                EntryKind.CHARACTER_NOTE,
                f"Met {npc_name}",
                f"First encounter with {npc_name} ({char_id}) in {self._player.zone_id}.",
                tags=[char_id, self._player.zone_id],
            )
        except Exception:
            pass

    def _journal_alchemy_note(self, result, subject) -> None:
        if self._journal is None:
            return
        try:
            from ..journal.journal import EntryKind
            subject_name = getattr(subject, "name", str(subject))
            q = result.resonance_quality
            outs = ", ".join(f"{k}×{v}" for k, v in result.outputs.items()) if result.outputs else "none"
            body = (
                f"Subject: {subject_name}\n"
                f"Resonance: {q:.2f}\n"
                f"Outputs: {outs}\n"
            )
            if result.recipe_discovered:
                body += "Recipe discovered.\n"
            kind = EntryKind.LORE_FRAGMENT if result.epiphanic else EntryKind.ALCHEMY_NOTE
            self._journal.write(
                kind,
                f"Alchemy: {subject_name}",
                body,
                tags=[getattr(subject, "id", ""), self._player.zone_id],
            )
        except Exception:
            pass

    # ── Alchemy session ───────────────────────────────────────────────────────

    def _begin_alchemy(self) -> None:
        if self._alchemy is None:
            self._hint = "(alchemy not available)"
            return
        try:
            from ..alchemy.system import SUBJECTS
            all_subjects = list(SUBJECTS)
        except Exception:
            self._hint = "(alchemy unavailable)"
            return

        # Derive calendar context and filter season-locked subjects
        cal_ctx = None
        if self._clock is not None:
            try:
                from .calendar import get_alchemy_calendar_context
                cal_ctx = get_alchemy_calendar_context(self._clock.date)
            except Exception:
                pass
        self._alchemy_calendar_ctx = cal_ctx

        locked   = cal_ctx.locked_subject_ids if cal_ctx is not None else frozenset()
        inv_dict = self._inventory.as_dict() if self._inventory is not None else {}
        available = [
            s for s in self._alchemy.available_subjects(inv_dict)
            if s.id not in locked
        ]

        if not available:
            self._hint = "(no subjects available — check apparatus and materials)"
            return

        self._alchemy_subjects     = available
        self._alchemy_subject_idx  = 0
        self._alchemy_approach_idx = 0
        self._alchemy_phase        = "subject"
        self._alchemy_result       = None
        self._mode = WorldMode.ALCHEMY
        self._refresh_alchemy_bytes()

    def _end_alchemy(self) -> None:
        self._alchemy_bytes  = None
        self._alchemy_result = None
        self._mode = WorldMode.WORLD

    def _handle_alchemy_key(self, key: int) -> None:
        phase = self._alchemy_phase

        if phase == "subject":
            if key in (_K_UP, ord('w')):
                self._alchemy_subject_idx = max(0, self._alchemy_subject_idx - 1)
                self._refresh_alchemy_bytes()
            elif key in (_K_DOWN, ord('s')):
                self._alchemy_subject_idx = min(
                    len(self._alchemy_subjects) - 1, self._alchemy_subject_idx + 1)
                self._refresh_alchemy_bytes()
            elif key in (_K_RETURN, _K_SPACE):
                self._begin_lab_session()
            elif key == _K_ESCAPE:
                self._end_alchemy()

        elif phase == "lab":
            if key in (_K_UP, ord('w')):
                self._lab_op_idx = max(0, self._lab_op_idx - 1)
                self._refresh_alchemy_bytes()
            elif key in (_K_DOWN, ord('s')):
                try:
                    from ..alchemy.laboratory import OPERATIONS
                    max_idx = len(OPERATIONS)  # last = Conclude
                except Exception:
                    max_idx = 0
                self._lab_op_idx = min(max_idx, self._lab_op_idx + 1)
                self._refresh_alchemy_bytes()
            elif key in (_K_RETURN, _K_SPACE):
                self._execute_lab_operation()
            elif key == _K_ESCAPE:
                self._lab_session = None
                self._alchemy_phase = "subject"
                self._refresh_alchemy_bytes()

        elif phase == "lab_flash":
            # Any key dismisses the operation result flash and returns to the menu
            self._lab_op_result = None
            self._alchemy_phase = "lab"
            self._refresh_alchemy_bytes()

        elif phase == "approach":
            if key in (_K_UP, ord('w')):
                self._alchemy_approach_idx = max(0, self._alchemy_approach_idx - 1)
                self._refresh_alchemy_bytes()
            elif key in (_K_DOWN, ord('s')):
                self._alchemy_approach_idx = min(2, self._alchemy_approach_idx + 1)
                self._refresh_alchemy_bytes()
            elif key in (_K_RETURN, _K_SPACE):
                self._execute_treatment()
            elif key == _K_ESCAPE:
                self._alchemy_phase = "subject"
                self._refresh_alchemy_bytes()

        elif phase == "result":
            if key in (_K_RETURN, _K_SPACE, _K_ESCAPE):
                self._end_alchemy()

    def _begin_lab_session(self) -> None:
        try:
            from ..alchemy.laboratory import LaboratorySession, SubstanceState
        except Exception:
            # Lab module unavailable — fall back to approach select
            self._alchemy_phase = "approach"
            self._alchemy_approach_idx = 0
            self._refresh_alchemy_bytes()
            return

        subject = self._alchemy_subjects[self._alchemy_subject_idx]
        inv_dict = self._inventory.as_dict() if self._inventory is not None else {}

        # Available equipment = every KLOB ID in inventory with qty >= 1
        available_equipment = frozenset(
            k for k, v in inv_dict.items() if k.endswith("_KLOB") and v >= 1
        )

        # Starting substance = primary required material (first non-apparatus entry)
        start_klob = next(
            (k for k in subject.required_materials if k.endswith("_KLOB")),
            "0073_KLOB",
        )

        self._lab_session = LaboratorySession(
            subject_id=subject.id,
            available_equipment=available_equipment,
            starting_substance=SubstanceState.default_for(start_klob),
            actor_id=getattr(self._chargen, "character_id", "0000_0451"),
        )
        self._lab_op_idx    = 0
        self._lab_op_result = None
        self._alchemy_phase = "lab"
        self._refresh_alchemy_bytes()

    def _execute_lab_operation(self) -> None:
        try:
            from ..alchemy.laboratory import OPERATIONS
        except Exception:
            return

        if self._lab_session is None:
            return

        # Conclude selected
        if self._lab_op_idx >= len(OPERATIONS):
            self._execute_treatment_from_lab()
            return

        op = OPERATIONS[self._lab_op_idx]
        available_op_ids = {o.op_id for o in self._lab_session.available_operations()}

        if op.op_id not in available_op_ids:
            return  # op not available — no-op, player sees dim entry

        vitriol_scores = {}
        if self._chargen is not None:
            try:
                vitriol_scores = dict(getattr(self._chargen, "vitriol_scores", {}))
            except Exception:
                pass

        alchemy_rank = 50
        if self._chargen is not None:
            try:
                alchemy_rank = getattr(self._chargen, "alchemy_rank", 50)
            except Exception:
                pass

        result = self._lab_session.perform(op.op_id, alchemy_rank, vitriol_scores)
        self._lab_op_result = result
        self._alchemy_phase = "lab_flash"
        self._refresh_alchemy_bytes()

    def _execute_treatment_from_lab(self) -> None:
        if self._lab_session is None:
            self._end_alchemy()
            return

        try:
            reading, approach = self._lab_session.conclude()
        except Exception:
            self._end_alchemy()
            return

        subject = self._alchemy_subjects[self._alchemy_subject_idx]
        inv_dict = self._inventory.as_dict() if self._inventory is not None else {}
        presence = self._presence

        try:
            from ..alchemy.system import PresenceState
            if presence is None:
                presence = PresenceState()
        except Exception:
            self._end_alchemy()
            return

        try:
            result = self._alchemy.treat(
                subject_id=subject.id,
                actor_id=getattr(self._chargen, "character_id", "0000_0451"),
                reading=reading,
                approach=approach,
                presence=presence,
                inventory=inv_dict,
                recipe_book=self._recipe_book,
                calendar_context=self._alchemy_calendar_ctx,
                physics_world=self._physics_world,
            )
        except Exception:
            self._end_alchemy()
            return

        if self._presence is not None:
            try:
                from ..alchemy.system import AlchemySystem
                delta = AlchemySystem.derive_presence_delta(result.resonance_quality, result.epiphanic)
                self._presence.permeability = min(1.0, max(0.0,
                    self._presence.permeability + delta.permeability_delta))
                charge_gain = delta.epiphanic_charge_delta
                if self._alchemy_calendar_ctx is not None:
                    charge_gain *= self._alchemy_calendar_ctx.charge_multiplier
                self._presence.epiphanic_charge = min(1.0, max(0.0,
                    self._presence.epiphanic_charge + charge_gain))
                self._presence.mania_level = min(1.0, max(0.0,
                    self._presence.mania_level + delta.mania_level_delta))
            except Exception:
                pass

        if self._inventory is not None:
            try:
                self._inventory.sync_from(inv_dict)
            except Exception:
                pass

        self._lab_session   = None
        self._alchemy_result = result
        self._alchemy_phase  = "result"
        self._journal_alchemy_note(result, subject)
        self._refresh_alchemy_bytes()

    def _execute_treatment(self) -> None:
        try:
            from ..alchemy.system import (
                DiagnosticReading, TreatmentApproach, PresenceState,
            )
        except Exception:
            self._end_alchemy()
            return

        subject = self._alchemy_subjects[self._alchemy_subject_idx]
        approach_mode = _APPROACHES[self._alchemy_approach_idx]

        inv_dict = {}
        if self._inventory is not None:
            try:
                inv_dict = self._inventory.as_dict()
            except Exception:
                pass

        presence = self._presence or PresenceState()
        perm = presence.permeability

        # Build a diagnostic reading scaled by permeability
        identified_axes = subject.field.axes() if perm >= 0.5 else frozenset()
        mode_engagement = {
            "ontological":  min(1.0, perm * 1.2),
            "cosmological": min(1.0, perm * 0.8),
            "narrative":    min(1.0, perm * 1.0),
            "somatic":      min(1.0, perm * 0.9),
        }
        reading = DiagnosticReading(
            subject_id=subject.id,
            identified_axes=identified_axes,
            mode_engagement=mode_engagement,
            presence_score=perm,
        )
        approach = TreatmentApproach(approach_mode=approach_mode)

        try:
            result = self._alchemy.treat(
                subject_id=subject.id,
                actor_id=getattr(self._chargen, "character_id", "0000_0451"),
                reading=reading,
                approach=approach,
                presence=presence,
                inventory=inv_dict,
                recipe_book=self._recipe_book,
                calendar_context=self._alchemy_calendar_ctx,
                physics_world=self._physics_world,
            )
        except Exception:
            self._end_alchemy()
            return

        # Apply presence delta with calendar charge multiplier
        if self._presence is not None:
            try:
                from ..alchemy.system import AlchemySystem
                delta = AlchemySystem.derive_presence_delta(result.resonance_quality, result.epiphanic)
                self._presence.permeability = min(1.0, max(0.0,
                    self._presence.permeability + delta.permeability_delta))
                charge_gain = delta.epiphanic_charge_delta
                if self._alchemy_calendar_ctx is not None:
                    charge_gain *= self._alchemy_calendar_ctx.charge_multiplier
                self._presence.epiphanic_charge = min(1.0, max(0.0,
                    self._presence.epiphanic_charge + charge_gain))
                self._presence.mania_level = min(1.0, max(0.0,
                    self._presence.mania_level + delta.mania_level_delta))
            except Exception:
                pass

        # treat() already mutated inv_dict (consumed materials, added outputs).
        # Sync the real Inventory to match.
        if self._inventory is not None:
            try:
                self._inventory.sync_from(inv_dict)
            except Exception:
                pass

        self._alchemy_result = result
        self._alchemy_phase  = "result"
        self._journal_alchemy_note(result, subject)
        self._refresh_alchemy_bytes()

    def _refresh_alchemy_bytes(self) -> None:
        inv_dict = {}
        if self._inventory is not None:
            try:
                inv_dict = self._inventory.as_dict()
            except Exception:
                pass

        cal  = self._alchemy_calendar_ctx
        phase = self._alchemy_phase
        if phase == "subject":
            season_note = getattr(cal, "season_note", "") if cal is not None else ""
            self._alchemy_bytes = self._alchemy_screen.render_subject_select(
                self._alchemy_subjects,
                self._alchemy_subject_idx,
                inv_dict,
                self.width, self.height,
                season_note=season_note,
            )
        elif phase == "lab" and self._lab_session is not None:
            try:
                from ..alchemy.laboratory import OPERATIONS
                subject = self._alchemy_subjects[self._alchemy_subject_idx]
                available_op_ids = {
                    o.op_id for o in self._lab_session.available_operations()
                }
                self._alchemy_bytes = self._alchemy_screen.render_lab_operation_menu(
                    subject_name=getattr(subject, "name", subject.id),
                    all_ops=OPERATIONS,
                    available_op_ids=available_op_ids,
                    cursor_idx=self._lab_op_idx,
                    mode_scores=dict(self._lab_session._mode_scores),
                    substance=self._lab_session.substance,
                    history=self._lab_session.history,
                    width=self.width,
                    height=self.height,
                )
            except Exception:
                pass
        elif phase == "lab_flash" and self._lab_op_result is not None:
            try:
                subject = self._alchemy_subjects[self._alchemy_subject_idx]
                self._alchemy_bytes = self._alchemy_screen.render_lab_operation_result(
                    result=self._lab_op_result,
                    subject_name=getattr(subject, "name", subject.id),
                    width=self.width,
                    height=self.height,
                )
            except Exception:
                pass
        elif phase == "approach":
            subject = self._alchemy_subjects[self._alchemy_subject_idx]
            formula_bonus = getattr(cal, "formula_approach_bonus", 0.0) if cal is not None else 0.0
            peak_axis     = getattr(cal, "peak_axis", None) if cal is not None else None
            self._alchemy_bytes = self._alchemy_screen.render_approach_select(
                subject,
                self._alchemy_approach_idx,
                self.width, self.height,
                formula_bonus=formula_bonus,
                peak_axis=peak_axis,
            )
        elif phase == "result":
            subject = self._alchemy_subjects[self._alchemy_subject_idx]
            self._alchemy_bytes = self._alchemy_screen.render_result(
                self._alchemy_result,
                getattr(subject, "name", subject.id),
                self.width, self.height,
            )

    # ── Vendor mode ───────────────────────────────────────────────────────────

    def _begin_vendor(self, npc) -> None:
        raw_catalog = self._vendor_catalogs.get(npc.character_id, {})
        self._vendor_catalog = sorted(raw_catalog.items(), key=lambda kv: kv[0])
        self._vendor_name    = npc.character_id
        self._vendor_idx     = 0
        self._mode           = WorldMode.VENDOR
        self._refresh_vendor_bytes()

    def _end_vendor(self) -> None:
        self._vendor_bytes = None
        self._mode = WorldMode.WORLD

    def _handle_vendor_key(self, key: int) -> None:
        if key == _K_ESCAPE:
            self._end_vendor()
        elif key in (_K_UP, ord('w')):
            self._vendor_idx = max(0, self._vendor_idx - 1)
            self._refresh_vendor_bytes()
        elif key in (_K_DOWN, ord('s')):
            self._vendor_idx = min(len(self._vendor_catalog) - 1, self._vendor_idx + 1)
            self._refresh_vendor_bytes()
        elif key in (_K_RETURN, _K_SPACE):
            self._execute_purchase()

    def _execute_purchase(self) -> None:
        if not self._vendor_catalog or self._inventory is None:
            return
        if self._vendor_idx >= len(self._vendor_catalog):
            return
        item_id, price = self._vendor_catalog[self._vendor_idx]
        coin_qty = self._inventory.quantity(COIN_ID)
        if coin_qty < price:
            return
        try:
            self._inventory.remove(COIN_ID, price)
            self._inventory.add(item_id, 1)
        except Exception:
            pass
        self._refresh_vendor_bytes()

    def _refresh_vendor_bytes(self) -> None:
        coin_qty = self._inventory.quantity(COIN_ID) if self._inventory is not None else 0
        self._vendor_bytes = self._vendor_screen.render(
            vendor_name = self._vendor_name,
            catalog     = self._vendor_catalog,
            cursor_idx  = self._vendor_idx,
            coin_qty    = coin_qty,
            width       = self.width,
            height      = self.height,
        )

    # ── Journal overlay ───────────────────────────────────────────────────────

    def _begin_journal(self) -> None:
        self._journal_cursor = 0
        self._journal_page   = 0
        self._journal_detail = False
        self._mode = WorldMode.JOURNAL
        self._refresh_journal_bytes()

    def _end_journal(self) -> None:
        self._journal_bytes = None
        self._mode = WorldMode.WORLD

    def _handle_journal_key(self, key: int) -> None:
        entries = self._journal_entries()

        if self._journal_detail:
            if key in (_K_RETURN, _K_SPACE, _K_ESCAPE):
                self._journal_detail = False
                self._refresh_journal_bytes()
            return

        # List view
        if key == _K_ESCAPE:
            self._end_journal()
        elif key in (_K_UP, ord('w')):
            if self._journal_cursor > 0:
                self._journal_cursor -= 1
                page = self._journal_cursor // JournalScreen._PAGE_ENTRIES
                if page != self._journal_page:
                    self._journal_page = page
                self._refresh_journal_bytes()
        elif key in (_K_DOWN, ord('s')):
            if self._journal_cursor < len(entries) - 1:
                self._journal_cursor += 1
                page = self._journal_cursor // JournalScreen._PAGE_ENTRIES
                if page != self._journal_page:
                    self._journal_page = page
                self._refresh_journal_bytes()
        elif key in (_K_RETURN, _K_SPACE):
            if entries:
                self._journal_detail = True
                self._refresh_journal_bytes()

    def _journal_entries(self) -> list:
        if self._journal is None:
            return []
        try:
            return list(self._journal._entries)
        except Exception:
            return []

    def _refresh_journal_bytes(self) -> None:
        entries = self._journal_entries()
        if self._journal_detail and entries:
            idx   = min(self._journal_cursor, len(entries) - 1)
            self._journal_bytes = self._journal_screen.render_detail(
                entries[idx], self.width, self.height)
        else:
            self._journal_bytes = self._journal_screen.render_list(
                entries, self._journal_cursor, self._journal_page,
                self.width, self.height)

    # ── Inventory overlay ─────────────────────────────────────────────────────

    def _begin_inventory(self) -> None:
        self._inventory_cursor = 0
        self._equip_cursor     = 0
        self._inv_tab          = "items"
        self._mode             = WorldMode.INVENTORY
        self._refresh_inventory_bytes()

    def _end_inventory(self) -> None:
        self._inventory_bytes = None
        self._mode = WorldMode.WORLD

    def _handle_inventory_key(self, key: int) -> None:
        if key in (_K_ESCAPE, _K_INVENTORY):
            self._end_inventory()
            return

        if key == _K_TAB:
            self._inv_tab = "equipment" if self._inv_tab == "items" else "items"
            self._refresh_inventory_bytes()
            return

        if self._inv_tab == "items":
            self._handle_items_key(key)
        else:
            self._handle_equip_key(key)

    def _handle_items_key(self, key: int) -> None:
        inv_dict = self._inventory_dict()
        rows = sorted(inv_dict.items(), key=lambda kv: (
            0 if kv[0].endswith("_KLIT") else
            1 if kv[0].endswith("_KLOB") else 2,
            kv[0],
        ))
        total = len(rows)
        if key in (_K_UP, ord('w')):
            if self._inventory_cursor > 0:
                self._inventory_cursor -= 1
                self._refresh_inventory_bytes()
        elif key in (_K_DOWN, ord('s')):
            if self._inventory_cursor < total - 1:
                self._inventory_cursor += 1
                self._refresh_inventory_bytes()
        elif key in (_K_RETURN, _K_SPACE):
            if rows and self._inventory_cursor < len(rows):
                item_id, _ = rows[self._inventory_cursor]
                self._try_equip(item_id)

    def _handle_equip_key(self, key: int) -> None:
        from ..inventory.equipment import SLOT_ORDER
        n = len(SLOT_ORDER)
        if key in (_K_UP, ord('w')):
            if self._equip_cursor > 0:
                self._equip_cursor -= 1
                self._refresh_inventory_bytes()
        elif key in (_K_DOWN, ord('s')):
            if self._equip_cursor < n - 1:
                self._equip_cursor += 1
                self._refresh_inventory_bytes()
        elif key in (_K_RETURN, _K_SPACE):
            slot = SLOT_ORDER[self._equip_cursor]
            self._try_unequip(slot)

    def _try_equip(self, item_id: str) -> None:
        if self._inventory is None or item_id not in EQUIPPABLE:
            return
        try:
            _, displaced = self._equipment.equip(item_id)
            self._inventory.remove(item_id)
            if displaced is not None:
                self._inventory.add(displaced)
            self._refresh_inventory_bytes()
        except Exception:
            pass

    def _try_unequip(self, slot: str) -> None:
        if self._inventory is None:
            return
        item_id = self._equipment.unequip(slot)
        if item_id is not None:
            try:
                self._inventory.add(item_id)
            except Exception:
                self._equipment.equip(item_id)  # rollback
        self._refresh_inventory_bytes()

    def _inventory_dict(self) -> dict:
        if self._inventory is None:
            return {}
        try:
            return self._inventory.as_dict()
        except Exception:
            return {}

    def _refresh_inventory_bytes(self) -> None:
        inv_dict = self._inventory_dict()
        self._inventory_bytes = self._inventory_screen.render(
            inv_dict        = inv_dict,
            cursor_idx      = self._inventory_cursor,
            width           = self.width,
            height          = self.height,
            tab             = self._inv_tab,
            equipment_slots = self._equipment.as_dict(),
            equip_cursor    = self._equip_cursor,
        )