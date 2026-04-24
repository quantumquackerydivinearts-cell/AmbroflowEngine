"""
FateKnocksGLPlay — OpenGL player-home opening scene
====================================================
Replaces FateKnocksPlay (static PIL) with the live 3D player home.

Loads PLAYER_HOME_GROUND + GROUND_FURNITURE into the GL WorldRenderer,
drives FateKnocksScene beat logic, and overlays narrative text via UIRenderer.

Beat flow
---------
  None         — player free-roams the home
  door_knock   — stage-direction panel fires as player nears the front door
  courier_meet — courier dialogue; INTERACT / 1 to confirm receipt
  letter_read  — parchment letter full-screen; INTERACT to finish
  (done)       — is_done() returns True
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Optional

import glm
import numpy as np
from OpenGL import GL

from ..engine.camera    import Camera
from ..engine.shader    import Shader
from ..engine.texture   import Texture
from ..render.world     import WorldRenderer
from ..render.ui        import UIRenderer
from ..world.map        import is_passable
from ..scenes.player_home import (
    PLAYER_HOME_GROUND, GROUND_FURNITURE,
    FurniturePlacement,
)
from ..scenes.opening import (
    FateKnocksScene,
    DOOR_KNOCK_TEXT, COURIER_LINE, HYPATIA_LETTER_LINES,
    render_hypatia_letter, render_stage_direction,
)
from .screens.common import _load_font, text_size, to_png
from .screens import palette as P

try:
    from PIL import Image, ImageDraw, ImageEnhance
    _PIL = True
except ImportError:
    _PIL = False

_SHADERS_DIR = Path(__file__).resolve().parent.parent / "engine" / "shaders"


# ── Procedural interior atlas ─────────────────────────────────────────────────
# 16 tile columns × 1 row, each cell 32×32 pixels = 512×32 RGBA image.
# Atlas slot → colour (Lapidus interior palette):

_ATLAS_COLORS = [
    ( 72,  62,  50),   #  0  FLOOR      warm flagstone
    ( 55,  90,  42),   #  1  GRASS      (unused inside)
    (100,  78,  52),   #  2  ROAD/DIRT  (unused inside)
    ( 86,  74,  58),   #  3  WALL       dark Aeralune stone
    ( 32,  58, 100),   #  4  WATER      (unused inside)
    ( 90,  84,  74),   #  5  STONE      (unused inside)
    (  8,   6,  12),   #  6  VOID       deep black
    (110,  65,  38),   #  7  BED        warm wood
    ( 88,  56,  28),   #  8  TABLE      brown wood
    (185, 160, 105),   #  9  JOURNAL    parchment
    ( 90,  42,  28),   # 10  FURNACE    ember-dark stone
    ( 62,  64,  68),   # 11  ANVIL      cold metal
    ( 78,  66,  50),   # 12  COUNTER    light wood plank
    ( 48,  52,  60),   # 13  REGISTER   dark metal
    ( 72,  56,  94),   # 14  ALTAR      violet
    ( 58,  42,  24),   # 15  BOOKSHELF  aged oak
]

_CELL = 32


def _make_interior_atlas() -> "Image.Image":
    COLS = len(_ATLAS_COLORS)
    img  = Image.new("RGBA", (COLS * _CELL, _CELL), (0, 0, 0, 0))
    pix  = img.load()
    for idx, (r, g, b) in enumerate(_ATLAS_COLORS):
        ox = idx * _CELL
        for py in range(_CELL):
            for px in range(_CELL):
                border = (px == 0 or py == 0 or
                          px == _CELL - 1 or py == _CELL - 1)
                col = (r // 2, g // 2, b // 2, 255) if border else (r, g, b, 255)
                pix[ox + px, py] = col
    return img


# ── Furniture passability set ─────────────────────────────────────────────────

def _blocked_by_furniture() -> frozenset[tuple[int, int]]:
    return frozenset(
        (p.x, p.z) for p in GROUND_FURNITURE if not p.passable
    )


# ── Beat overlay renderers ────────────────────────────────────────────────────

def _beat_overlay(beat_id: str, payload, W: int, H: int) -> Optional["Image.Image"]:
    if not _PIL:
        return None

    if beat_id == "door_knock":
        raw = render_stage_direction(DOOR_KNOCK_TEXT, width=W, height=H)
        if not raw:
            return None
        img  = Image.open(io.BytesIO(raw)).convert("RGBA")
        draw = ImageDraw.Draw(img)
        font = _load_font(11)
        hint = "[space / enter]  Continue"
        hw, _ = text_size(draw, hint, font)
        draw.text(((W - hw) // 2, int(H * 0.88)), hint,
                  fill=(130, 115, 100, 255), font=font)
        return img

    if beat_id == "courier_meet":
        line, name, ctype = payload
        return _courier_overlay(line, name, ctype, W, H)

    if beat_id == "letter_read":
        return _letter_overlay(W, H)

    return None


def _courier_overlay(
    line: str, name: str, ctype: str, W: int, H: int
) -> "Image.Image":
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    dial_h = int(H * 0.40)
    dial_y = H - dial_h

    draw.rectangle([0, dial_y, W, H], fill=(8, 5, 14, 230))
    draw.line([(0, dial_y), (W, dial_y)], fill=(78, 60, 98, 255), width=1)

    _SOLD_BG     = (12,  16,  20, 230)
    _SOLD_ACCENT = (100, 130, 160, 255)

    port_w = int(W * 0.22)
    draw.rectangle([0, dial_y, port_w, H], fill=_SOLD_BG)
    draw.line([(port_w, dial_y), (port_w, H)],
              fill=_SOLD_ACCENT, width=1)

    font_type = _load_font(20)
    lw, lh = text_size(draw, ctype, font_type)
    draw.text(
        ((port_w - lw) // 2, dial_y + (dial_h - lh) // 2),
        ctype, fill=_SOLD_ACCENT, font=font_type,
    )

    tx0     = port_w + int(W * 0.018)
    tx1     = W - int(W * 0.02)
    pad_top = int(dial_h * 0.11)

    font_name   = _load_font(14)
    font_body   = _load_font(12)
    font_choice = _load_font(11)

    draw.text((tx0, dial_y + pad_top), name,
              fill=(230, 220, 255, 255), font=font_name)
    nb = draw.textbbox((tx0, dial_y + pad_top), name, font=font_name)
    rule_y = nb[3] + 3
    draw.line([(tx0, rule_y), (tx1, rule_y)], fill=_SOLD_ACCENT, width=1)

    try:
        bm  = draw.textbbox((0, 0), "M", font=font_body)
        cw  = max(1, bm[2] - bm[0])
        ch  = max(1, bm[3] - bm[1]) + 3
    except Exception:
        cw, ch = 7, 16

    cpl    = max(10, (tx1 - tx0) // max(1, cw))
    ty     = rule_y + int(dial_h * 0.07)
    choice_h = ch + 14

    words = line.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if cur and len(cand) > cpl:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)

    for ln in lines:
        if ty + ch > H - choice_h - 4:
            break
        draw.text((tx0, ty), ln, fill=(200, 195, 215, 255), font=font_body)
        ty += ch

    cy = H - choice_h - 4
    draw.line([(tx0, cy - 5), (tx1, cy - 5)], fill=_SOLD_ACCENT, width=1)
    draw.text((tx0, cy), "1.  Confirm receipt.",
              fill=_SOLD_ACCENT, font=font_choice)

    return img


def _letter_overlay(W: int, H: int) -> "Image.Image":
    letter_h = int(H * 0.84)
    letter_w = min(int(letter_h * 0.75), int(W * 0.70))
    raw = render_hypatia_letter(width=letter_w, height=letter_h)

    canvas = Image.new("RGBA", (W, H), (4, 3, 8, 245))
    if raw:
        letter_img = Image.open(io.BytesIO(raw)).convert("RGBA")
        ox = (W - letter_w) // 2
        oy = int(H * 0.04)
        canvas.alpha_composite(letter_img, (ox, oy))

    draw = ImageDraw.Draw(canvas)
    font = _load_font(11)
    hint = "[space / enter]  The work begins."
    hw, _ = text_size(draw, hint, font)
    draw.text(((W - hw) // 2, int(H * 0.92)), hint,
              fill=(P.KO_GOLD[0], P.KO_GOLD[1], P.KO_GOLD[2], 255), font=font)
    return canvas


# ── FateKnocksGLPlay ──────────────────────────────────────────────────────────

class FateKnocksGLPlay:
    """
    Interactive Fate Knocks in the live 3D player home.

    Parameters
    ----------
    width, height : window dimensions
    """

    def __init__(self, width: int, height: int) -> None:
        self._W = width
        self._H = height

        # Atlas + GL world renderer
        atlas_img    = _make_interior_atlas()
        atlas_tex    = Texture.from_pil(atlas_img)
        vert_src     = (_SHADERS_DIR / "world.vert").read_text(encoding="utf-8")
        frag_src     = (_SHADERS_DIR / "lapidus_world.frag").read_text(encoding="utf-8")
        shader       = Shader(vert_src, frag_src)
        self._wr     = WorldRenderer(
            shader, atlas_tex,
            atlas_cols=len(_ATLAS_COLORS),
            atlas_rows=1,
        )
        self._wr.load_zone(PLAYER_HOME_GROUND)
        self._wr.load_furniture(GROUND_FURNITURE)

        # Camera — Octopath-style following the player tile
        self._cam = Camera(
            aspect       = width / max(1, height),
            fov_deg      = 35.0,
            pitch_deg    = 40.0,
            distance     = 14.0,
            follow_speed = 6.0,
        )

        # Player grid position (spawns in bedroom by the bed)
        spawn_x, spawn_y = FateKnocksScene.SPAWN
        self._px = spawn_x
        self._py = spawn_y
        self._cam.target = glm.vec3(float(self._px), 0.0, float(self._py))

        # Pre-compute furniture-blocked tiles
        self._furn_blocked = _blocked_by_furniture()

        # Beat scene
        self._scene = FateKnocksScene()

        # UI overlay
        self._ui          = UIRenderer()
        self._overlay_tex: Optional[Texture] = None
        self._overlay_on  = False
        self._done_pending = False
        self._done         = False

        self._t = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    def is_done(self) -> bool:
        return self._done

    def handle_event(self, ev: str) -> None:
        from ..engine.window import InputEvent
        if self._overlay_on:
            if ev in (InputEvent.INTERACT, InputEvent.CANCEL):
                self._overlay_on = False
                if self._done_pending:
                    self._done = True
            return

        dx, dz = {
            InputEvent.MOVE_NORTH: ( 0, -1),
            InputEvent.MOVE_SOUTH: ( 0,  1),
            InputEvent.MOVE_WEST:  (-1,  0),
            InputEvent.MOVE_EAST:  ( 1,  0),
        }.get(ev, (0, 0))

        if dx == 0 and dz == 0:
            return

        nx, nz = self._px + dx, self._py + dz
        tile   = PLAYER_HOME_GROUND.tile_at(nx, nz)
        blocked_by_furn = (nx, nz) in self._furn_blocked

        if is_passable(tile) and not blocked_by_furn:
            self._px, self._py = nx, nz
            beat = self._scene.check_beat(nx, nz)
            if beat:
                self._show_beat(beat)

    def resize(self, width: int, height: int) -> None:
        self._W, self._H = width, height
        self._cam.resize(width / max(1, height))

    def tick(self, dt: float) -> None:
        self._t += dt
        self._cam.target = glm.vec3(float(self._px), 0.0, float(self._py))
        self._cam.update(dt)

    def draw(self) -> None:
        GL.glClearColor(0.04, 0.03, 0.08, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        self._wr.draw(self._cam, time=self._t)
        if self._overlay_on and self._overlay_tex is not None:
            self._ui.add(self._overlay_tex, (-1.0, -1.0, 1.0, 1.0), opacity=0.97)
            self._ui.draw()
            self._ui.clear()

    def delete(self) -> None:
        self._wr.delete()
        self._ui.delete()
        if self._overlay_tex:
            self._overlay_tex.delete()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _show_beat(self, beat: tuple) -> None:
        beat_id, payload = beat
        img = _beat_overlay(beat_id, payload, self._W, self._H)
        if img is None:
            return
        if self._overlay_tex is not None:
            self._overlay_tex.delete()
        self._overlay_tex   = Texture.from_pil(img)
        self._overlay_on    = True
        self._done_pending  = (beat_id == "letter_read")