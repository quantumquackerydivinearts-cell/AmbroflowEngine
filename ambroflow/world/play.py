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

from .map import WorldMap, Zone
from .player import WorldPlayer, Direction
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
_K_FIGHT   = ord('f')
_K_ALCHEMY = ord('z')

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

        # Alchemy (optional — graceful no-ops when absent)
        self._alchemy       = alchemy
        self._presence      = presence
        self._recipe_book   = recipe_book
        self._alchemy_screen = AlchemyScreen()
        # Session state
        self._alchemy_subjects:     list  = []
        self._alchemy_subject_idx:  int   = 0
        self._alchemy_approach_idx: int   = 0
        self._alchemy_phase:        str   = "subject"   # subject | approach | result
        self._alchemy_result:       object = None
        self._alchemy_bytes:        Optional[bytes] = None
        self._alchemy_calendar_ctx: object = None

        # Vendor (optional)
        self._vendor_catalogs: Dict[str, Dict[str, int]] = vendor_catalogs or {}
        self._vendor_screen    = VendorScreen()
        self._vendor_catalog:  list  = []   # [(item_id, price), ...]
        self._vendor_name:     str   = ""
        self._vendor_idx:      int   = 0
        self._vendor_bytes:    Optional[bytes] = None

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
            self._renderer.render(screen, zone, self._player, hint=self._hint)

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
            elif self._mode == WorldMode.COMBAT:
                if self._combat_loop is None:
                    # Prompt not yet confirmed — abort cleanly
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

    # ── Movement ─────────────────────────────────────────────────────────────

    def _move(self, direction: Direction) -> None:
        zone = self._zone
        moved, exit_trig, portal_trig = self._player.move(direction, zone)

        if exit_trig is not None:
            self._transition_zone(exit_trig)
        elif portal_trig is not None:
            self._enter_dungeon(portal_trig)
        elif moved:
            self._tracer.deposit(
                self._player.zone_id, self._player.x, self._player.y, TA,
            )
            self._check_encounters()

    # ── Zone transition ───────────────────────────────────────────────────────

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

        # Advance clock one hour per zone crossing
        if self._clock is not None:
            try:
                self._clock.advance(1)
            except Exception:
                pass

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
        npc  = self._player.facing_npc(zone)
        if npc is not None and npc.character_id not in self._dead_npcs:
            if npc.character_id in self._vendor_catalogs:
                self._begin_vendor(npc)
            else:
                self._begin_dialogue(npc)
            return
        portal = self._player.facing_portal(zone)
        if portal is not None:
            self._enter_dungeon(portal)

    def _update_hint(self) -> None:
        if self._mode != WorldMode.WORLD:
            self._hint = ""
            return
        zone = self._zone
        npc  = self._player.facing_npc(zone)
        if npc is not None and npc.character_id not in self._dead_npcs:
            self._hint = "[space]  Talk     [f]  Attack"
            return
        portal = self._player.facing_portal(zone)
        if portal is not None:
            self._hint = "[space]  Enter dungeon"
            return
        if self._alchemy is not None:
            self._hint = "[z]  Alchemy"
            return
        self._hint = ""

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

        # First-meeting character note
        if char_id not in self._met_npcs:
            self._met_npcs.add(char_id)
            self._journal_npc_met(npc)

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
                self._dead_npcs.add(result.npc_id)
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
                self._alchemy_phase = "approach"
                self._alchemy_approach_idx = 0
                self._refresh_alchemy_bytes()
            elif key == _K_ESCAPE:
                self._end_alchemy()

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