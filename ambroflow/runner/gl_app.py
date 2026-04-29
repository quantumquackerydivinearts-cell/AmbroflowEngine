"""
GLApp — glfw-based Ambroflow frontend
======================================
Replaces runner/app.py (pygame).  All rendering is OpenGL; PIL-rendered
chargen / menu screens are blitted as fullscreen NDC quads via UIRenderer.

Screen flow
-----------
  TITLE      — animated splash, any key to continue
  NAME_ENTRY — first-run only: player profile name (not character name)
  GAME_SELECT — 31-game grid
  IN_GAME    — GameFlow chargen pipeline (PIL frames via UIRenderer)
  FATE_GL    — FateKnocksGLPlay: live 3-D interactive player home opening

Usage
-----
    python -m ambroflow
    # or
    from ambroflow.runner.gl_app import run
    run()
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Optional

import glfw
from OpenGL import GL

from .session import Session
from .persistence import auto_backend
from .registry import GAMES
from .game_flow import GameFlow, FlowPhase
from .fate_knocks_gl import FateKnocksGLPlay
from .gl_world_play import GLWorldPlay
from .screens.title      import render_title_screen
from .screens.game_select import render_game_select
from .screens.name_entry  import render_name_entry

from ..engine.window  import Window, InputEvent
from ..engine.texture import Texture
from ..render.ui      import UIRenderer
from ..inventory.manager import Inventory

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False


_W     = 1280
_H     = 800
_TITLE = "Ko's Labyrinth  ·  Ambroflow"
_PLAYER_ID_FILE = os.path.expanduser("~/.ambroflow/last_player_id")

# InputEvent string → pygame-style int that GameFlow.on_key() understands
_EV_TO_KEY: dict[str, int] = {
    InputEvent.INTERACT:   13,           # K_RETURN
    InputEvent.CANCEL:     27,           # K_ESCAPE
    InputEvent.MOVE_NORTH: 1073741906,   # K_UP
    InputEvent.MOVE_SOUTH: 1073741905,   # K_DOWN
    InputEvent.MOVE_WEST:  1073741904,   # K_LEFT
    InputEvent.MOVE_EAST:  1073741903,   # K_RIGHT
}


class GLApp:
    """
    Main application class.  Instantiate and call run().

    Parameters
    ----------
    width, height : window dimensions
    player_id     : load this profile on startup (skips NAME_ENTRY)
    atelier_url   : Atelier API base URL for hosted persistence + Orrery
    """

    def __init__(
        self,
        width:       int = _W,
        height:      int = _H,
        player_id:   Optional[str] = None,
        atelier_url: Optional[str] = None,
    ) -> None:
        self._W = width
        self._H = height
        self._session = Session(
            backend=auto_backend(atelier_base_url=atelier_url),
            orrery_url=atelier_url,
        )
        self._player_id = player_id or self._load_last_player_id()

        # Current screen
        self._screen = "TITLE"
        self._dirty  = True
        self._frame_cache: Optional[bytes] = None

        # Animation
        self._t0    = time.monotonic()
        self._pulse = 0.0

        # Profile name entry (app-level, pre-game)
        self._name_buf    = ""
        self._cursor_vis  = True
        self._cursor_t    = 0.0

        # Game select
        self._sel_idx = 6   # default: game 7

        # In-game chargen pipeline
        self._game_flow: Optional[GameFlow] = None

        # Chargen state carried forward into world play
        self._chargen: Optional[object] = None

        # Live 3-D opening sequence
        self._fate_gl: Optional[FateKnocksGLPlay] = None

        # Starting inventory — populated at the top of the free-roam cycle
        self._starting_inventory: dict = {}

        # Strictly-GL world play (post-chargen, post-opening)
        self._gl_world_play: Optional[GLWorldPlay] = None

        # GL texture for current PIL frame
        self._screen_tex: Optional[Texture] = None

        # Raw text input accumulated between frames
        self._chars:    list[str] = []
        self._bs_count: int       = 0

    # ── Persistence ───────────────────────────────────────────────────────────

    @staticmethod
    def _load_last_player_id() -> Optional[str]:
        try:
            return open(_PLAYER_ID_FILE).read().strip() or None
        except OSError:
            return None

    @staticmethod
    def _save_last_player_id(pid: str) -> None:
        try:
            os.makedirs(os.path.dirname(_PLAYER_ID_FILE), exist_ok=True)
            with open(_PLAYER_ID_FILE, "w") as f:
                f.write(pid)
        except OSError:
            pass

    # ── Screen transitions ────────────────────────────────────────────────────

    def _go(self, screen: str) -> None:
        self._screen      = screen
        self._dirty       = True
        self._frame_cache = None

    # ── Resize callback ───────────────────────────────────────────────────────

    def _on_resize(self, w: int, h: int) -> None:
        self._W, self._H = w, h
        if self._fate_gl:
            self._fate_gl.resize(w, h)
        if self._game_flow:
            self._game_flow.width  = w
            self._game_flow.height = h
        if self._gl_world_play:
            self._gl_world_play.resize(w, h)
        self._dirty       = True
        self._frame_cache = None
        if self._screen_tex:
            self._screen_tex.delete()
            self._screen_tex = None

    # ── PIL frame → GL texture ────────────────────────────────────────────────

    def _upload_frame(self, frame_bytes: bytes) -> None:
        if frame_bytes is self._frame_cache:
            return
        self._frame_cache = frame_bytes
        if self._screen_tex is not None:
            self._screen_tex.delete()
        self._screen_tex = Texture.from_bytes(frame_bytes)

    # ── PIL screen rendering ──────────────────────────────────────────────────

    def _render_pil_screen(self, ui: UIRenderer) -> None:
        W, H = self._W, self._H
        frame: Optional[bytes] = None

        if self._screen == "TITLE":
            frame = render_title_screen(W, H, pulse=self._pulse)

        elif self._screen == "NAME_ENTRY":
            frame = render_name_entry(
                self._name_buf, self._cursor_vis, width=W, height=H
            )

        elif self._screen == "GAME_SELECT":
            profile  = self._session.profile
            pname    = profile.name if profile else ""
            statuses = self._session.all_game_statuses()
            frame    = render_game_select(
                statuses, self._sel_idx, pname, width=W, height=H
            )

        elif self._screen == "IN_GAME" and self._game_flow is not None:
            frame = self._game_flow.current_frame()

        if frame:
            self._upload_frame(frame)

        if self._screen_tex is not None:
            ui.add(self._screen_tex, (-1.0, -1.0, 1.0, 1.0), opacity=1.0)
            ui.draw()
            ui.clear()

    # ── Input handlers ────────────────────────────────────────────────────────

    def _handle_title(self, events: list[str]) -> None:
        if events or self._chars or self._bs_count:
            self._chars.clear()
            self._bs_count = 0
            if self._player_id:
                prof = self._session.load_profile(self._player_id)
                if prof:
                    self._go("GAME_SELECT")
                    return
            self._go("NAME_ENTRY")

    def _handle_name_entry(self, events: list[str]) -> None:
        for ch in self._chars:
            if len(self._name_buf) < 24:
                self._name_buf += ch
                self._dirty = True
        self._chars.clear()
        if self._bs_count:
            self._name_buf  = self._name_buf[:-self._bs_count]
            self._bs_count  = 0
            self._dirty     = True
        for ev in events:
            if ev == InputEvent.INTERACT:
                name = self._name_buf.strip()
                if not name:
                    continue
                pid = str(uuid.uuid4())
                self._session.create_profile(name=name, player_id=pid)
                self._player_id = pid
                self._save_last_player_id(pid)
                self._name_buf = ""
                self._go("GAME_SELECT")
                return
            elif ev == InputEvent.CANCEL:
                self._go("TITLE")
                return

    def _handle_game_select(self, events: list[str]) -> None:
        self._chars.clear()
        self._bs_count = 0
        n = len(GAMES)
        for ev in events:
            if ev == InputEvent.MOVE_EAST:
                self._sel_idx = (self._sel_idx + 1) % n
                self._dirty   = True
            elif ev == InputEvent.MOVE_WEST:
                self._sel_idx = (self._sel_idx - 1) % n
                self._dirty   = True
            elif ev == InputEvent.MOVE_SOUTH:
                self._sel_idx = min(n - 1, self._sel_idx + 7)
                self._dirty   = True
            elif ev == InputEvent.MOVE_NORTH:
                self._sel_idx = max(0, self._sel_idx - 7)
                self._dirty   = True
            elif ev == InputEvent.INTERACT:
                self._launch_selected()
                return
            elif ev == InputEvent.CANCEL:
                self._go("TITLE")
                return

    def _launch_selected(self) -> None:
        game = GAMES[self._sel_idx]
        if not game.built:
            self._dirty = True
            return
        status = self._session.game_status(game.slug)
        if status == "in_progress":
            self._session.resume_game(game.slug)
        else:
            self._session.start_game(game.slug)
        self._game_flow = GameFlow(game.slug, self._W, self._H)
        self._go("IN_GAME")

    def _handle_in_game(self, events: list[str]) -> None:
        if self._game_flow is None:
            return

        # Intercept FATE_KNOCKS and hand off to live GL scene
        if self._game_flow.phase == FlowPhase.FATE_KNOCKS:
            self._chargen = self._game_flow.chargen
            self._fate_gl = FateKnocksGLPlay(
                self._W, self._H,
                on_free_roam=self._init_starting_inventory,
            )
            self._screen  = "FATE_GL"
            return

        # Raw text for GameFlow name entry phase
        for ch in self._chars:
            self._game_flow.on_key(0, ch)
            self._dirty = True
        self._chars.clear()
        for _ in range(self._bs_count):
            self._game_flow.on_key(8, "")
            self._dirty = True
        self._bs_count = 0

        # Translate InputEvent → pygame-style key ints
        for ev in events:
            key = _EV_TO_KEY.get(ev, 0)
            if key:
                self._game_flow.on_key(key, "")
                self._dirty = True

        if self._game_flow.is_done():
            self._game_flow = None
            self._go("GAME_SELECT")

    def _init_starting_inventory(self) -> None:
        """Collect home item spawns into _starting_inventory at free-roam start."""
        try:
            from ..world.zones.lapidus import build_wiltoll_home
            home = build_wiltoll_home()
            inv: dict = {}
            for spawn in home.item_spawns:
                inv[spawn.item_id] = inv.get(spawn.item_id, 0) + spawn.qty
            self._starting_inventory = inv
        except Exception:
            pass

    def _handle_fate_gl(self, events: list[str], ui: "UIRenderer") -> None:
        self._chars.clear()
        self._bs_count = 0
        if self._fate_gl is None:
            return
        for ev in events:
            self._fate_gl.handle_event(ev)
        if self._fate_gl.is_done():
            self._fate_gl.delete()
            self._fate_gl = None
            if self._game_flow is not None:
                self._game_flow.phase = FlowPhase.DONE
                self._game_flow = None
            self._launch_world_play(ui)

    def _launch_world_play(self, ui: "UIRenderer") -> None:
        """Build WorldPlay + GLWorldPlay and transition to WORLD_PLAY screen."""
        try:
            from ..world import WorldPlay, build_game7_world
            from ..world.zones.lapidus import VENDOR_CATALOGS

            chargen   = self._chargen
            world_map = build_game7_world()

            inv = Inventory()
            for item_id, qty in self._starting_inventory.items():
                try:
                    inv.add(item_id, qty)
                except Exception:
                    pass

            wp = WorldPlay(
                chargen         = chargen,
                world_map       = world_map,
                width           = self._W,
                height          = self._H,
                inventory       = inv,
                vendor_catalogs = VENDOR_CATALOGS,
            )
            self._gl_world_play = GLWorldPlay(wp, ui, self._W, self._H)
            self._screen = "WORLD_PLAY"
        except Exception:
            self._go("GAME_SELECT")

    def _handle_world_play(self, events: list[str]) -> None:
        self._chars.clear()
        self._bs_count = 0
        if self._gl_world_play is None:
            return
        for ev in events:
            self._gl_world_play.handle_event(ev)
        if self._gl_world_play.is_done():
            self._gl_world_play.delete()
            self._gl_world_play = None
            self._chargen = None
            self._starting_inventory = {}
            self._go("GAME_SELECT")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        win = Window(
            title     = _TITLE,
            width     = self._W,
            height    = self._H,
            resizable = True,
            on_resize = self._on_resize,
        )

        # Char callback for text input — separate from key_callback, no conflict
        glfw.set_char_callback(
            win._handle,
            lambda _w, codepoint: self._chars.append(chr(codepoint)),
        )

        # Extended key callback: also catches backspace, chains to Window's
        _orig = win._key_cb
        def _key_cb(w, key, sc, action, mods):
            if action in (glfw.PRESS, glfw.REPEAT) and key == glfw.KEY_BACKSPACE:
                self._bs_count += 1
            _orig(w, key, sc, action, mods)
        glfw.set_key_callback(win._handle, _key_cb)

        win.make_current()
        ui = UIRenderer()

        _CURSOR_BLINK = 0.55

        try:
            while not win.should_close():
                dt = win.begin_frame()
                self._pulse = (time.monotonic() - self._t0) % 1.0

                # Cursor blink
                self._cursor_t += dt
                if self._cursor_t >= _CURSOR_BLINK:
                    self._cursor_t -= _CURSOR_BLINK
                    self._cursor_vis = not self._cursor_vis
                    if self._screen == "NAME_ENTRY":
                        self._dirty = True

                # Title animates every frame
                if self._screen == "TITLE":
                    self._dirty = True

                events = win.consume_events()

                if self._screen == "TITLE":
                    self._handle_title(events)
                elif self._screen == "NAME_ENTRY":
                    self._handle_name_entry(events)
                elif self._screen == "GAME_SELECT":
                    self._handle_game_select(events)
                elif self._screen == "IN_GAME":
                    self._handle_in_game(events)
                elif self._screen == "FATE_GL":
                    self._handle_fate_gl(events, ui)
                elif self._screen == "WORLD_PLAY":
                    self._handle_world_play(events)

                # ── Render ──────────────────────────────────────────────────
                GL.glClearColor(0.02, 0.01, 0.05, 1.0)
                GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

                if self._screen == "FATE_GL" and self._fate_gl is not None:
                    self._fate_gl.tick(dt)
                    self._fate_gl.draw()
                elif self._screen == "WORLD_PLAY" and self._gl_world_play is not None:
                    self._gl_world_play.tick(dt)
                    self._gl_world_play.draw()
                else:
                    self._render_pil_screen(ui)

                win.end_frame()

        finally:
            self._session.save()
            if self._fate_gl:
                self._fate_gl.delete()
            if self._gl_world_play:
                self._gl_world_play.delete()
            if self._screen_tex:
                self._screen_tex.delete()
            ui.delete()
            win.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

def run(
    width:       int = _W,
    height:      int = _H,
    player_id:   Optional[str] = None,
    atelier_url: Optional[str] = None,
) -> None:
    """Start the Ambroflow GL app."""
    GLApp(
        width       = width,
        height      = height,
        player_id   = player_id,
        atelier_url = atelier_url or os.getenv("ATELIER_API_URL"),
    ).run()