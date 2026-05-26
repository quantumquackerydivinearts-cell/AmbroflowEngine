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
        self._atelier_url = atelier_url
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

        # Live BreathOfKo — holds Akashic record across world play session
        self._active_breath = None

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

        elif self._screen == "LOADING" and _PIL:
            try:
                from PIL import Image, ImageDraw
                from .screens.common import _load_font, text_size, to_png
                from .screens import palette as P
                img  = Image.new("RGB", (W, H), (4, 3, 8))
                draw = ImageDraw.Draw(img)
                font = _load_font(18)
                text = "Loading…"
                tw, _ = text_size(draw, text, font)
                draw.text(
                    ((W - tw) // 2, H // 2 - 10),
                    text,
                    fill=(P.KO_GOLD[0], P.KO_GOLD[1], P.KO_GOLD[2]),
                    font=font,
                )
                import io
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                frame = buf.getvalue()
            except Exception:
                pass

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
        is_resume = (status == "in_progress")
        if is_resume:
            self._session.resume_game(game.slug)
        else:
            self._session.start_game(game.slug)

        # Build (or restore) the live BreathOfKo and attach an AkashicRecord
        try:
            from ..ko.breath import BreathOfKo
            from ..ko.akashic import AkashicRecord
            prof = self._session.profile
            snap = prof.breath_snapshot if prof else None
            if snap:
                self._active_breath = BreathOfKo.from_snapshot(snap)
            else:
                self._active_breath = BreathOfKo()
            # Attach or restore the Akashic record for this game
            ar = getattr(self._active_breath, "akashic_record", None)
            if ar is None or getattr(ar, "game_slug", None) != game.slug:
                self._active_breath.akashic_record = AkashicRecord(
                    game_slug=game.slug)
            if not is_resume:
                self._active_breath.akashic_record.begin_run()
        except Exception:
            self._active_breath = None

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
                on_free_roam  = self._init_starting_inventory,
                on_interact   = self._fate_gl_interact,
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
        """Populate _starting_inventory from game7_start canonical starting state."""
        try:
            from ..runner.game7_start import game7_starting_inventory
            self._starting_inventory = game7_starting_inventory()
        except Exception:
            pass

    def _fate_gl_interact(self, action_id: str) -> None:
        """Handle furniture interactions fired from FateKnocksGLPlay free roam."""
        if self._fate_gl is None:
            return
        if action_id == "stairs_up":
            self._fate_gl.change_floor(+1)
            return
        if action_id == "stairs_down":
            self._fate_gl.change_floor(-1)
            return
        # For UI modes, transition FATE_GL → WORLD_PLAY then switch mode
        # (GLWorldPlay has the mode-aware render path)
        from ..render.ui import UIRenderer
        try:
            ui = self._fate_gl._ui
        except AttributeError:
            return
        if self._gl_world_play is None:
            try:
                self._launch_world_play(ui)
            except Exception:
                return
        wp = getattr(self._gl_world_play, "_wp", None)
        if wp is None:
            return
        from ..world.play import WorldMode
        mode_map = {
            "open_shop_ui":          WorldMode.SHOP,
            "open_smelt_ui":         WorldMode.SMELT,
            "meditate":              WorldMode.ALCHEMY,   # reuse alchemy overlay until MEDITATION mode exists
            "meditation_tutorial":   WorldMode.ALCHEMY,
            "open_alchemy_ui":       WorldMode.ALCHEMY,
            "lore_books":            WorldMode.DIALOGUE,
        }
        mode = mode_map.get(action_id)
        if mode is not None:
            wp._mode = mode
            self._screen = "WORLD_PLAY"

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
            # Show loading screen for one frame before the heavy WorldPlay build
            self._screen = "LOADING"

    def _handle_loading(self, ui: "UIRenderer") -> None:
        """Render one loading frame then immediately build WorldPlay."""
        self._launch_world_play(ui)

    def _launch_world_play(self, ui: "UIRenderer") -> None:
        """Build WorldPlay + GLWorldPlay and transition to WORLD_PLAY screen."""
        import logging, traceback
        _log = logging.getLogger(__name__)

        # ── Step 1: core WorldPlay (must succeed) ──────────────────────────
        try:
            from ..world import WorldPlay, build_game7_world
            from ..world.zones.lapidus import VENDOR_CATALOGS
            from ..alchemy.system import AlchemySystem
            from ..journal.journal import Journal
            from ..orrery.client import OrreryClient

            chargen   = self._chargen
            world_map = build_game7_world()
            inv       = Inventory()
            for item_id, qty in self._starting_inventory.items():
                try:
                    inv.add(item_id, qty)
                except Exception:
                    pass

            # Skill ranks derived from VITRIOL + chargen tag picks
            from ..runner.game7_start import game7_starting_skill_ranks
            _skill_ranks = game7_starting_skill_ranks(chargen)

            orrery = OrreryClient(
                workspace_id = self._player_id or "anon",
                game_id      = "7_KLGS",
                base_url     = (self._atelier_url or "https://atelier-api.quantumquackery.com/"),
            )
            alchemy = AlchemySystem(orrery=orrery)
            journal = Journal(
                actor_id = self._player_id or "anon",
                game_id  = "7_KLGS",
                orrery   = orrery,
            )

            wp = WorldPlay(
                chargen         = chargen,
                world_map       = world_map,
                width           = self._W,
                height          = self._H,
                inventory       = inv,
                vendor_catalogs = VENDOR_CATALOGS,
                alchemy         = alchemy,
                journal         = journal,
                breath          = self._active_breath,
                physics_world   = self._session.physics,
            )
            # Post-FateKnocks: player exits through the home's front door onto
            # Wiltoll Lane.  Spawn at the exterior lane position in front of
            # the home entrance (cols 3-4, row 8 of lapidus_wiltoll_lane).
            lane_id = "lapidus_wiltoll_lane"
            if lane_id in world_map.zones:
                lane   = world_map.zones[lane_id]
                wp._player.zone_id = lane_id
                wp._player.x       = 3
                wp._player.y       = 8
                wp._zone           = lane
        except Exception:
            _log.error("WorldPlay init failed:\n%s", traceback.format_exc())
            self._go("GAME_SELECT")
            return

        # ── Step 2: scene graph + interaction entities (optional) ──────────
        graph       = None
        scene_nodes = []
        try:
            from ..world.world_graph     import WorldGraph
            from ..world.ko_scene_reader import load_ko_scene
            from pathlib import Path
            graph      = WorldGraph.load()
            start_ko   = Path("C:/DjinnOS/productions/kos-labyrnth/scenes/lapidus/home_morning.scene.ko")
            scene_data = load_ko_scene(start_ko) if start_ko.exists() else {}
            scene_nodes = [n for n in scene_data.get("nodes", []) if n.get("kind") == "interaction"]
        except Exception:
            _log.warning("Scene graph load failed (non-fatal):\n%s", traceback.format_exc())

        # ── Step 3: assemble GLWorldPlay ───────────────────────────────────
        self._gl_world_play = GLWorldPlay(
            wp, ui, self._W, self._H,
            world_graph          = graph,
            interaction_entities = scene_nodes,
        )
        self._screen = "WORLD_PLAY"

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
            # Sync BreathOfKo snapshot back to session profile before saving
            if self._active_breath is not None and self._session.profile is not None:
                try:
                    self._session.profile.breath_snapshot = \
                        self._active_breath.snapshot()
                    self._session.save()
                except Exception:
                    pass
            self._active_breath = None
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
                elif self._screen == "LOADING":
                    self._handle_loading(ui)
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