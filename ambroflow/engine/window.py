"""
Window
======
glfw window with an OpenGL 4.1 core-profile context.

Replaces pygame as the window and event layer.  All input is normalized
to a small set of engine-level events (move, interact, cancel, menu)
rather than raw key constants — avoids the SDL1/SDL2 constant mismatch
that broke the pygame prototype.

Usage
-----
    win = Window("Ko's Labyrinth", 1280, 800)
    win.make_current()

    while not win.should_close():
        dt = win.begin_frame()
        # ... render ...
        win.end_frame()
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import glfw

from OpenGL import GL


# Engine-level input events — decoupled from raw key codes.
class InputEvent:
    MOVE_NORTH   = "move_north"
    MOVE_SOUTH   = "move_south"
    MOVE_EAST    = "move_east"
    MOVE_WEST    = "move_west"
    INTERACT     = "interact"
    CANCEL       = "cancel"
    MENU         = "menu"
    QUIT         = "quit"


# Key → InputEvent mapping (WASD + arrows, Esc, Enter/Space)
_KEY_MAP: dict[int, str] = {
    glfw.KEY_W:      InputEvent.MOVE_NORTH,
    glfw.KEY_UP:     InputEvent.MOVE_NORTH,
    glfw.KEY_S:      InputEvent.MOVE_SOUTH,
    glfw.KEY_DOWN:   InputEvent.MOVE_SOUTH,
    glfw.KEY_A:      InputEvent.MOVE_WEST,
    glfw.KEY_LEFT:   InputEvent.MOVE_WEST,
    glfw.KEY_D:      InputEvent.MOVE_EAST,
    glfw.KEY_RIGHT:  InputEvent.MOVE_EAST,
    glfw.KEY_ENTER:  InputEvent.INTERACT,
    glfw.KEY_SPACE:  InputEvent.INTERACT,
    glfw.KEY_ESCAPE: InputEvent.CANCEL,
    glfw.KEY_TAB:    InputEvent.MENU,
}

# Movement events that participate in held-key continuous repeat
_MOVE_EVENTS = frozenset({
    InputEvent.MOVE_NORTH,
    InputEvent.MOVE_SOUTH,
    InputEvent.MOVE_EAST,
    InputEvent.MOVE_WEST,
})

# Seconds before the first auto-repeat fires after initial press
_MOVE_INITIAL_DELAY: float = 0.20
# Seconds between each subsequent repeat step
_MOVE_REPEAT_INTERVAL: float = 0.10


class Window:
    """
    glfw window with an OpenGL 4.1 core-profile context.

    Parameters
    ----------
    title:        Window title string.
    width/height: Initial window dimensions in pixels.
    resizable:    Whether the window can be resized.
    on_resize:    Called with (width, height) whenever the window resizes.
    """

    def __init__(
        self,
        title:     str = "Ambroflow",
        width:     int = 1280,
        height:    int = 800,
        resizable: bool = True,
        on_resize: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        if not glfw.init():
            raise RuntimeError("glfw.init() failed")

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
        glfw.window_hint(glfw.RESIZABLE, glfw.TRUE if resizable else glfw.FALSE)
        glfw.window_hint(glfw.SAMPLES, 4)   # 4× MSAA

        self._handle = glfw.create_window(width, height, title, None, None)
        if not self._handle:
            glfw.terminate()
            raise RuntimeError("glfw.create_window() failed — no OpenGL 4.1 context available")

        self._width     = width
        self._height    = height
        self._on_resize = on_resize
        self._events:   list[str]         = []
        self._t_last    = time.monotonic()

        # Held movement keys: event → seconds until next repeat fires
        self._held_move: dict[str, float] = {}

        glfw.set_key_callback(self._handle, self._key_cb)
        glfw.set_framebuffer_size_callback(self._handle, self._resize_cb)

    # ── Context ───────────────────────────────────────────────────────────────

    def make_current(self) -> None:
        glfw.make_context_current(self._handle)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_MULTISAMPLE)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

    # ── Frame timing ──────────────────────────────────────────────────────────

    def begin_frame(self) -> float:
        """Poll events, tick held-key repeats, and return dt in seconds."""
        self._events.clear()
        glfw.poll_events()
        now = time.monotonic()
        dt  = min(now - self._t_last, 0.1)   # cap at 100ms (e.g. debugger pause)
        self._t_last = now

        # Continuous movement: decrement timers and emit when they expire
        for ev in list(self._held_move):
            self._held_move[ev] -= dt
            while self._held_move[ev] <= 0.0:
                self._events.append(ev)
                self._held_move[ev] += _MOVE_REPEAT_INTERVAL

        return dt

    def end_frame(self) -> None:
        """Swap buffers."""
        glfw.swap_buffers(self._handle)

    # ── State ─────────────────────────────────────────────────────────────────

    def should_close(self) -> bool:
        return bool(glfw.window_should_close(self._handle))

    def close(self) -> None:
        glfw.set_window_should_close(self._handle, True)

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def aspect(self) -> float:
        return self._width / max(1, self._height)

    def consume_events(self) -> list[str]:
        """Return and clear the pending input event list."""
        evs = list(self._events)
        self._events.clear()
        return evs

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _key_cb(self, window, key: int, scancode: int, action: int, mods: int) -> None:
        ev = _KEY_MAP.get(key)
        if not ev:
            return
        if ev in _MOVE_EVENTS:
            if action == glfw.PRESS:
                # Emit immediately, then arm the repeat timer
                self._events.append(ev)
                self._held_move[ev] = _MOVE_INITIAL_DELAY
            elif action == glfw.RELEASE:
                self._held_move.pop(ev, None)
            # REPEAT action is ignored — begin_frame() handles the cadence
        else:
            # Non-movement events fire once on PRESS only
            if action == glfw.PRESS:
                self._events.append(ev)

    def _resize_cb(self, window, width: int, height: int) -> None:
        self._width  = width
        self._height = height
        GL.glViewport(0, 0, width, height)
        if self._on_resize:
            self._on_resize(width, height)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def destroy(self) -> None:
        glfw.destroy_window(self._handle)
        glfw.terminate()

    def __enter__(self) -> "Window":
        self.make_current()
        return self

    def __exit__(self, *_) -> None:
        self.destroy()