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

        # Map discovery
        self._map_screen: Optional[MapDiscoveryScreen] = None
        self._map_state:  MapState                     = MapState.FOLDED
        self._map_bytes:  Optional[bytes]              = None
        self._map_item_collected: bool                 = False

        # HUD hint text
        self._hint: str = ""

    # ── Public interface ──────────────────────────────────────────────────────

    def is_done(self) -> bool:
        return self._mode == WorldMode.DONE

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

    def advance_quest(self, entry_id: str, candidate: str) -> None:
        """
        Witness a quest entry with the given candidate choice.

        Delegates to WitnessTracker.advance() when qqva is available;
        applies a structural fallback update to the quest_state dict otherwise.
        """
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
            else:
                self._mode = WorldMode.DONE
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

        if self._mode == WorldMode.WORLD:
            direction = _DIR_KEYS.get(key) or _WASD.get(key)
            if direction is not None:
                self._move(direction)
            elif key in (_K_RETURN, _K_SPACE):
                self._interact()

    # ── Movement ─────────────────────────────────────────────────────────────

    def _move(self, direction: Direction) -> None:
        zone = self._zone
        moved, exit_trig, portal_trig = self._player.move(direction, zone)

        if exit_trig is not None:
            self._transition_zone(exit_trig)
        elif portal_trig is not None:
            self._enter_dungeon(portal_trig)
        elif moved:
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

    # ── Encounter checking ────────────────────────────────────────────────────

    def _check_encounters(self) -> None:
        """Evaluate all encounter defs; trigger the first matching one."""
        zone_id = self._player.zone_id
        for enc in self._encounter_defs:
            if enc.fires(self._quest_state, zone_id):
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
        if npc is not None:
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
        if npc is not None:
            self._hint = "[space]  Talk"
            return
        portal = self._player.facing_portal(zone)
        if portal is not None:
            self._hint = "[space]  Enter dungeon"
            return
        self._hint = ""

    # ── Dialogue ─────────────────────────────────────────────────────────────

    def _begin_dialogue(self, npc) -> None:
        self._mode                    = WorldMode.DIALOGUE
        self._dialogue_needs_snapshot = True
        self._frozen_bg               = None
        self._dialogue_bytes          = None

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

    # ── Map discovery ─────────────────────────────────────────────────────────

    def _begin_map_discovery(self) -> None:
        """Open the map discovery screen at FOLDED state."""
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