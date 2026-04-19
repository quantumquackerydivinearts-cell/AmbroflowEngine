"""
Ambroflow Desktop App
=====================
Pygame window that drives the KLGS game selection and startup pipeline.

Screen stack
------------
  TITLE       — splash screen, "press any key"
  NAME_ENTRY  — first-run only: player enters their name
  GAME_SELECT — 31-game grid, navigate with arrow keys
  IN_GAME     — hands off to the game engine screens (dream, chargen, play)

Each screen is a PIL-rendered PNG frame displayed as a pygame surface.
The PIL renderers are stateless; the app holds navigation state and
re-renders only on state change or animation tick.

Usage
-----
    python -m ambroflow
    # or
    from ambroflow.runner.app import run
    run()
"""

from __future__ import annotations

import io
import os
import time
import uuid
from typing import Optional

try:
    import pygame
    _PYGAME = True
except ImportError:
    _PYGAME = False

from .session import Session
from .persistence import auto_backend
from .registry import GAMES
from .game_flow import GameFlow, FlowPhase
from .screens.title      import render_title_screen
from .screens.game_select import render_game_select
from .screens.name_entry  import render_name_entry
from .screens.common import _load_font, text_size, to_png, draw_starfield
from .screens import palette as P
from ..world import WorldPlay, build_game7_world

try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False


# ── Constants ─────────────────────────────────────────────────────────────────

_WINDOW_W  = 1280
_WINDOW_H  = 800
_FPS       = 30
_TITLE_WIN = "Ko's Labyrinth  \u00b7  Ambroflow"

_DEFAULT_PLAYER_ID_FILE = os.path.expanduser("~/.ambroflow/last_player_id")


# ── PIL bytes -> pygame surface ───────────────────────────────────────────────

def _render_loading_screen(width: int, height: int) -> Optional[bytes]:
    """Full-screen 'The veil thins...' frame shown during dream pre-render."""
    if not _PIL:
        return None
    img  = Image.new("RGB", (width, height), P.VOID)
    draw = ImageDraw.Draw(img)
    draw_starfield(img, seed=0xDECA, density=0.0006)
    font = _load_font(18)
    msg  = "The veil thins\u2026"
    w, _ = text_size(draw, msg, font)
    draw.text(((width - w) // 2, height // 2 - 10), msg, fill=P.KO_GOLD, font=font)
    hint_font = _load_font(11)
    hint = "reading in progress"
    hw, _ = text_size(draw, hint, hint_font)
    draw.text(((width - hw) // 2, height // 2 + 22), hint, fill=P.TEXT_DIM, font=hint_font)
    return to_png(img)


def _png_to_surface(data: bytes) -> "pygame.Surface":
    return pygame.image.load(io.BytesIO(data))


def _blit_full(screen: "pygame.Surface", surf: "pygame.Surface") -> None:
    """Scale surf to fill the screen and blit."""
    sw, sh = screen.get_size()
    if surf.get_size() != (sw, sh):
        surf = pygame.transform.scale(surf, (sw, sh))
    screen.blit(surf, (0, 0))


# ── App ───────────────────────────────────────────────────────────────────────

class AmbroflowApp:
    """
    Main application class.  Instantiate and call run().

    Parameters
    ----------
    width, height:
        Window dimensions.
    player_id:
        If given, load this profile on startup instead of reading from file.
    atelier_url:
        Atelier API base URL for hosted persistence + Orrery.
        Defaults to ATELIER_API_URL env var or None (local only).
    """

    def __init__(
        self,
        width:  int = _WINDOW_W,
        height: int = _WINDOW_H,
        player_id: Optional[str] = None,
        atelier_url: Optional[str] = None,
    ) -> None:
        self._W = width
        self._H = height
        self._session = Session(
            backend=auto_backend(atelier_base_url=atelier_url),
            orrery_url=atelier_url,
        )
        self._player_id = player_id or self._load_last_player_id()

        # Screen state
        self._screen_name = "TITLE"
        self._frame_cache: Optional[bytes] = None   # cached PIL render
        self._dirty = True                           # re-render needed

        # Animation
        self._t0    = time.monotonic()
        self._pulse = 0.0

        # Name entry state
        self._name_buf = ""
        self._cursor_visible = True
        self._cursor_t = 0.0

        # Game select state
        self._sel_idx = 6     # default: game 7

        # In-game flow
        self._game_flow: Optional[GameFlow] = None

        # Waking play (world navigation, post-chargen)
        self._world_play: Optional[WorldPlay] = None

    # ── Persistence helpers ───────────────────────────────────────────────────

    @staticmethod
    def _load_last_player_id() -> Optional[str]:
        try:
            return open(_DEFAULT_PLAYER_ID_FILE).read().strip() or None
        except OSError:
            return None

    @staticmethod
    def _save_last_player_id(pid: str) -> None:
        try:
            os.makedirs(os.path.dirname(_DEFAULT_PLAYER_ID_FILE), exist_ok=True)
            with open(_DEFAULT_PLAYER_ID_FILE, "w") as f:
                f.write(pid)
        except OSError:
            pass

    # ── Screen transitions ────────────────────────────────────────────────────

    def _go(self, screen_name: str) -> None:
        self._screen_name = screen_name
        self._dirty = True
        self._frame_cache = None

    # ── Frame rendering ───────────────────────────────────────────────────────

    def _render_frame(self) -> Optional[bytes]:
        W, H = self._W, self._H
        statuses = self._session.all_game_statuses()
        profile  = self._session.profile

        if self._screen_name == "TITLE":
            return render_title_screen(W, H, pulse=self._pulse)

        if self._screen_name == "NAME_ENTRY":
            return render_name_entry(
                self._name_buf,
                self._cursor_visible,
                width=W, height=H,
            )

        if self._screen_name == "GAME_SELECT":
            pname = profile.name if profile else ""
            return render_game_select(
                statuses, self._sel_idx, pname,
                width=W, height=H,
            )

        if self._screen_name == "IN_GAME":
            if self._game_flow is not None:
                frame = self._game_flow.current_frame()
                if frame is not None:
                    return frame
            return _render_loading_screen(W, H)

        return None

    # ── Event handling ────────────────────────────────────────────────────────

    def _handle_title(self, event: "pygame.event.Event") -> None:
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            # First run: show name entry.  Returning player: game select.
            if self._player_id:
                prof = self._session.load_profile(self._player_id)
                if prof:
                    self._go("GAME_SELECT")
                    return
            self._go("NAME_ENTRY")

    def _handle_name_entry(self, event: "pygame.event.Event") -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_RETURN:
            name = self._name_buf.strip()
            if not name:
                return
            pid = str(uuid.uuid4())
            self._session.create_profile(name=name, player_id=pid)
            self._player_id = pid
            self._save_last_player_id(pid)
            self._name_buf = ""
            self._go("GAME_SELECT")
        elif event.key == pygame.K_BACKSPACE:
            self._name_buf = self._name_buf[:-1]
            self._dirty = True
        elif event.key == pygame.K_ESCAPE:
            self._go("TITLE")
        elif event.unicode and len(self._name_buf) < 24:
            self._name_buf += event.unicode
            self._dirty = True

    def _handle_game_select(self, event: "pygame.event.Event") -> None:
        if event.type != pygame.KEYDOWN:
            return
        n = len(GAMES)
        if event.key == pygame.K_RIGHT:
            self._sel_idx = (self._sel_idx + 1) % n
            self._dirty = True
        elif event.key == pygame.K_LEFT:
            self._sel_idx = (self._sel_idx - 1) % n
            self._dirty = True
        elif event.key == pygame.K_DOWN:
            self._sel_idx = min(n - 1, self._sel_idx + 7)
            self._dirty = True
        elif event.key == pygame.K_UP:
            self._sel_idx = max(0, self._sel_idx - 7)
            self._dirty = True
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._launch_selected()
        elif event.key == pygame.K_ESCAPE:
            self._go("TITLE")

    def _launch_selected(self) -> None:
        game = GAMES[self._sel_idx]
        if not game.built:
            # Not yet playable — flash dirty to show the selection, no transition
            self._dirty = True
            return
        status = self._session.game_status(game.slug)
        if status == "in_progress":
            self._session.resume_game(game.slug)
        else:
            self._session.start_game(game.slug)
        self._game_flow = GameFlow(game.slug, self._W, self._H)
        self._go("IN_GAME")

    def _handle_in_game(self, event: "pygame.event.Event") -> None:
        if self._game_flow is None:
            return
        if event.type == pygame.KEYDOWN:
            self._game_flow.on_key(event.key, event.unicode or "")
            self._dirty = True
            if self._game_flow.is_done():
                chargen = self._game_flow.chargen
                self._game_flow = None
                # Transition into waking play (world navigation)
                try:
                    world_map = build_game7_world()
                    self._world_play = WorldPlay(
                        chargen=chargen,
                        world_map=world_map,
                        width=self._W,
                        height=self._H,
                    )
                    self._go("WORLD_PLAY")
                except Exception:
                    self._world_play = None
                    self._go("GAME_SELECT")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        if not _PYGAME:
            raise RuntimeError("pygame is not installed: pip install pygame")

        pygame.init()
        pygame.display.set_caption(_TITLE_WIN)
        screen = pygame.display.set_mode((self._W, self._H), pygame.RESIZABLE)
        clock  = pygame.time.Clock()

        surface: Optional[pygame.Surface] = None
        _CURSOR_BLINK_S = 0.55

        while True:
            dt = clock.tick(_FPS) / 1000.0
            self._pulse = (time.monotonic() - self._t0) % 1.0

            # Cursor blink
            self._cursor_t += dt
            if self._cursor_t >= _CURSOR_BLINK_S:
                self._cursor_t -= _CURSOR_BLINK_S
                self._cursor_visible = not self._cursor_visible
                if self._screen_name == "NAME_ENTRY":
                    self._dirty = True

            # Title re-renders every frame for animation
            if self._screen_name == "TITLE":
                self._dirty = True

            # ── WORLD_PLAY: direct pygame render, bypass PIL pipeline ──────────
            if self._screen_name == "WORLD_PLAY" and self._world_play is not None:
                events = pygame.event.get()
                for event in events:
                    if event.type == pygame.QUIT:
                        self._session.save()
                        pygame.quit()
                        return
                self._world_play.tick(dt, events)
                if self._world_play.is_done():
                    self._world_play = None
                    self._go("GAME_SELECT")
                else:
                    screen.fill((0, 0, 0))
                    self._world_play.render(screen)
                    pygame.display.flip()
                continue

            # Event processing
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._session.save()
                    pygame.quit()
                    return
                if event.type == pygame.VIDEORESIZE:
                    self._W, self._H = event.w, event.h
                    # Resize during IN_GAME: recreate flow with new dimensions
                    if self._screen_name == "IN_GAME" and self._game_flow is not None:
                        old_flow = self._game_flow
                        new_flow = GameFlow(old_flow.game_slug, self._W, self._H)
                        new_flow.chargen = old_flow.chargen
                        self._game_flow = new_flow
                    self._dirty = True

                if self._screen_name == "TITLE":
                    self._handle_title(event)
                elif self._screen_name == "NAME_ENTRY":
                    self._handle_name_entry(event)
                elif self._screen_name == "GAME_SELECT":
                    self._handle_game_select(event)
                elif self._screen_name == "IN_GAME":
                    self._handle_in_game(event)

            # Re-render if needed
            if self._dirty or surface is None:
                frame = self._render_frame()
                if frame:
                    surface = _png_to_surface(frame)
                self._dirty = False

            if surface:
                _blit_full(screen, surface)
            pygame.display.flip()


# ── Entry point ───────────────────────────────────────────────────────────────

def run(
    width: int = _WINDOW_W,
    height: int = _WINDOW_H,
    player_id: Optional[str] = None,
    atelier_url: Optional[str] = None,
) -> None:
    """Start the Ambroflow desktop app."""
    app = AmbroflowApp(
        width=width,
        height=height,
        player_id=player_id,
        atelier_url=atelier_url or os.getenv("ATELIER_API_URL"),
    )
    app.run()