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
            freeze happens on the first render() call in DIALOGUE mode.
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

from enum import Enum
from typing import Optional, TYPE_CHECKING

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


# Pygame-ce (SDL2) key constants
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

# WASD aliases
_WASD: dict[int, Direction] = {
    ord('w'): Direction.NORTH,
    ord('s'): Direction.SOUTH,
    ord('a'): Direction.WEST,
    ord('d'): Direction.EAST,
}


class WorldMode(str, Enum):
    WORLD    = "world"
    DIALOGUE = "dialogue"
    DUNGEON  = "dungeon"
    DONE     = "done"


class WorldPlay:
    """
    Waking play controller.

    Constructed by app.py once GameFlow signals DONE; destroyed when
    is_done() returns True (player quits or session ends).
    """

    def __init__(
        self,
        chargen:   "ChargenState",
        world_map: WorldMap,
        width:  int = 1280,
        height: int = 800,
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
        self._zone: Zone = starting

        # Dialogue state
        self._frozen_bg:       object          = None  # pygame.Surface
        self._dialogue_bytes:  Optional[bytes] = None  # PIL dialogue frame
        self._dialogue_needs_snapshot: bool    = False

        # Dungeon state (future)
        self._dungeon_runtime: object = None

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
                # Render world once to capture the frozen background
                self._renderer.render(screen, zone, self._player)
                self._frozen_bg = self._renderer.snapshot(screen)
                self._dialogue_needs_snapshot = False
            self._renderer.render_with_dialogue(
                screen, self._frozen_bg, self._dialogue_bytes)

        elif self._mode == WorldMode.WORLD:
            self._renderer.render(screen, zone, self._player, hint=self._hint)

        elif self._mode == WorldMode.DUNGEON:
            # Placeholder: render frozen world + dungeon overlay (future)
            if self._frozen_bg is not None:
                screen.blit(self._frozen_bg, (0, 0))

    # ── Key handling ──────────────────────────────────────────────────────────

    def _handle_key(self, key: int) -> None:
        if key == _K_ESCAPE:
            if self._mode == WorldMode.DIALOGUE:
                self._end_dialogue()
            elif self._mode == WorldMode.DUNGEON:
                self._exit_dungeon()
            else:
                self._mode = WorldMode.DONE
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

    # ── Zone transition ───────────────────────────────────────────────────────

    def _transition_zone(self, exit_trig) -> None:
        target = self._world.zones.get(exit_trig.target_zone)
        if target is None:
            # Stub zone — quietly block; hint tells the player
            self._hint = "(nothing that way yet)"
            return
        self._player.zone_id = exit_trig.target_zone
        self._player.x       = exit_trig.target_x
        self._player.y       = exit_trig.target_y
        self._zone           = target

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
        # TODO: fetch PIL dialogue bytes from dialogue system using npc.character_id

    def _end_dialogue(self) -> None:
        self._frozen_bg               = None
        self._dialogue_bytes          = None
        self._dialogue_needs_snapshot = False
        self._mode                    = WorldMode.WORLD

    # ── Dungeon ───────────────────────────────────────────────────────────────

    def _enter_dungeon(self, portal) -> None:
        # Snapshot the world as background before entering
        self._mode = WorldMode.DUNGEON
        # TODO: instantiate DungeonRuntime(dungeon_def, seed, orrery, player)
        #       and implement a full dungeon render layer
        #       For now: the dungeon portal is labelled in the HUD
        self._hint = f"[ {portal.dungeon_id} ]"

    def _exit_dungeon(self) -> None:
        self._dungeon_runtime = None
        self._frozen_bg       = None
        self._mode            = WorldMode.WORLD