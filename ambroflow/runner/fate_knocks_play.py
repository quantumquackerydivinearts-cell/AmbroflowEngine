"""
FateKnocksPlay — Interactive 0001_KLST Opening
===============================================
Handles the five interactive beats of "Fate Knocks" once the player lands
in waking play after the chargen pipeline.  Called from GameFlow during
the FATE_KNOCKS phase.

Beat order
----------
  BEDROOM  —  dawn, rumpled bed.  "Rise."
  KNOCK    —  stage direction: three strikes at the door.
  FOYER    —  cross to the door.  "Open it."
  COURIER  —  Royal Courier delivers the sealed letter.  Choice: confirm.
  LETTER   —  Hypatia's parchment letter in full.  "The work begins."
  DONE     —  transitions back to GameFlow → DONE.

All frames are full-screen PIL composites sized to the current window.
"""

from __future__ import annotations

import io
from enum import Enum
from typing import Optional

from ..scenes.opening import (
    COURIER_LINE, DOOR_KNOCK_TEXT,
    render_stage_direction, render_hypatia_letter,
)
from ..scenes.location import render_bedroom, render_foyer
from .screens.common import _load_font, text_size, to_png
from .screens import palette as P

try:
    from PIL import Image, ImageDraw, ImageEnhance
    _PIL = True
except ImportError:
    _PIL = False


# ── Beat sequence ─────────────────────────────────────────────────────────────

class FKBeat(str, Enum):
    BEDROOM = "bedroom"
    KNOCK   = "knock"
    FOYER   = "foyer"
    COURIER = "courier"
    LETTER  = "letter"
    DONE    = "done"


_BEAT_ORDER = [
    FKBeat.BEDROOM,
    FKBeat.KNOCK,
    FKBeat.FOYER,
    FKBeat.COURIER,
    FKBeat.LETTER,
    FKBeat.DONE,
]

# Raw pygame key constants (avoiding pygame import here)
_K_RETURN    = 13
_K_SPACE     = 32
_K_ESCAPE    = 27
_K_1         = ord('1')


# ── FateKnocksPlay ────────────────────────────────────────────────────────────

class FateKnocksPlay:
    """
    Interactive Fate Knocks sequence.

    Parameters
    ----------
    player_name:
        The player's character name, shown in the room status bar.
    width, height:
        Current window dimensions.
    """

    def __init__(self, player_name: str, width: int, height: int) -> None:
        self._name   = player_name
        self._W      = width
        self._H      = height
        self._beat   = FKBeat.BEDROOM

    # ── State ─────────────────────────────────────────────────────────────────

    def is_done(self) -> bool:
        return self._beat == FKBeat.DONE

    def _advance(self) -> None:
        idx = _BEAT_ORDER.index(self._beat)
        if idx + 1 < len(_BEAT_ORDER):
            self._beat = _BEAT_ORDER[idx + 1]

    # ── Key handling ──────────────────────────────────────────────────────────

    def on_key(self, key: int, unicode: str = "") -> None:
        if key == _K_ESCAPE:
            self._beat = FKBeat.DONE
            return

        if self._beat == FKBeat.COURIER:
            # Require explicit confirmation — Space, Enter, or "1"
            if key in (_K_RETURN, _K_SPACE, _K_1):
                self._advance()
        else:
            if key in (_K_RETURN, _K_SPACE):
                self._advance()

    # ── Frame rendering ───────────────────────────────────────────────────────

    def current_frame(self) -> Optional[bytes]:
        if self._beat == FKBeat.BEDROOM:
            return self._room_scene(
                room="bedroom",
                location="Wiltoll Lane, Azonithia",
                detail="Your bedroom.  The morning has not started yet.",
                hint="[space]  Rise",
            )

        if self._beat == FKBeat.KNOCK:
            return self._stage_dir(DOOR_KNOCK_TEXT, hint="[space]  Continue")

        if self._beat == FKBeat.FOYER:
            return self._room_scene(
                room="foyer",
                location="Wiltoll Lane — foyer",
                detail="You cross to the door.  The knocking does not repeat.",
                hint="[space]  Open the door",
            )

        if self._beat == FKBeat.COURIER:
            return self._courier_scene()

        if self._beat == FKBeat.LETTER:
            return self._letter_scene()

        return None

    # ── Room scene composite ──────────────────────────────────────────────────

    def _room_scene(
        self,
        room: str,
        location: str,
        detail: str,
        hint: str,
    ) -> Optional[bytes]:
        if not _PIL:
            return None
        W, H = self._W, self._H

        # Render room to full window size
        if room == "bedroom":
            raw = render_bedroom(time_of_day="dawn", rumpled=True,
                                 width=W, height=H)
        else:
            raw = render_foyer(time_of_day="dawn", width=W, height=H)

        if not raw:
            return None

        img = Image.open(io.BytesIO(raw)).convert("RGB")

        # --- bottom status bar ---
        bar_h = max(90, int(H * 0.17))
        bar_y = H - bar_h

        # Alpha-composite a dark gradient over the bottom strip
        rgba    = img.convert("RGBA")
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        # Lighter at the top of the bar, opaque at the bottom
        for dy in range(bar_h):
            alpha = int(dy / bar_h * 215)
            ov_draw.line(
                [(0, bar_y + dy), (W - 1, bar_y + dy)],
                fill=(P.VOID[0], P.VOID[1], P.VOID[2], alpha),
            )
        img  = Image.alpha_composite(rgba, overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        pad    = int(W * 0.028)
        top_y  = bar_y + int(bar_h * 0.16)

        font_loc  = _load_font(14)
        font_det  = _load_font(12)
        font_hint = _load_font(11)
        font_nm   = _load_font(11)

        # Location name (gold, top-left of bar)
        draw.text((pad, top_y), location, fill=P.KO_GOLD, font=font_loc)
        # Detail line (dim, below location)
        draw.text((pad, top_y + 20), detail, fill=P.TEXT_PRIMARY, font=font_det)

        # Player name (dim, top-right of bar)
        nw, _ = text_size(draw, self._name, font_nm)
        draw.text((W - pad - nw, top_y), self._name, fill=P.TEXT_DIM, font=font_nm)

        # Hint centered near bottom of bar
        hw, _ = text_size(draw, hint, font_hint)
        draw.text(((W - hw) // 2, H - int(bar_h * 0.28)),
                  hint, fill=P.TEXT_DIM, font=font_hint)

        return to_png(img)

    # ── Stage direction ───────────────────────────────────────────────────────

    def _stage_dir(self, text: str, hint: str) -> Optional[bytes]:
        if not _PIL:
            return None
        W, H = self._W, self._H
        raw = render_stage_direction(text, width=W, height=H)
        if not raw:
            return None
        img  = Image.open(io.BytesIO(raw)).convert("RGB")
        draw = ImageDraw.Draw(img)
        font = _load_font(11)
        hw, _ = text_size(draw, hint, font)
        draw.text(((W - hw) // 2, int(H * 0.88)), hint,
                  fill=P.TEXT_DIM, font=font)
        return to_png(img)

    # ── Courier dialogue scene ────────────────────────────────────────────────

    def _courier_scene(self) -> Optional[bytes]:
        """
        Dimmed foyer background + dialogue bar in bottom 38 % of screen.
        """
        if not _PIL:
            return None
        W, H = self._W, self._H

        # Background: foyer at dawn, heavily dimmed
        raw_foyer = render_foyer(time_of_day="dawn", width=W, height=H)
        if raw_foyer:
            bg = ImageEnhance.Brightness(
                Image.open(io.BytesIO(raw_foyer)).convert("RGB")
            ).enhance(0.28)
        else:
            bg = Image.new("RGB", (W, H), P.VOID)

        draw = ImageDraw.Draw(bg)

        # Dialogue bar dimensions
        dial_h = int(H * 0.40)
        dial_y = H - dial_h
        _SOLD_BG     = ( 12,  16,  20)
        _SOLD_ACCENT = (100, 130, 160)

        # Bar background
        draw.rectangle([0, dial_y, W, H], fill=(8, 5, 14))
        draw.line([(0, dial_y), (W, dial_y)], fill=(78, 60, 98), width=1)

        # Portrait swatch — left 22 %
        port_w = int(W * 0.22)
        draw.rectangle([0, dial_y, port_w, H], fill=_SOLD_BG)
        draw.line([(port_w, dial_y), (port_w, H)], fill=_SOLD_ACCENT, width=1)

        font_type = _load_font(22)
        lw, lh = text_size(draw, "SOLD", font_type)
        draw.text(
            ((port_w - lw) // 2, dial_y + (dial_h - lh) // 2),
            "SOLD", fill=_SOLD_ACCENT, font=font_type,
        )

        # Text region
        tx0     = port_w + int(W * 0.018)
        tx1     = W - int(W * 0.020)
        pad_top = int(dial_h * 0.11)

        font_name   = _load_font(14)
        font_body   = _load_font(13)
        font_choice = _load_font(12)

        draw.text((tx0, dial_y + pad_top), "Royal Courier",
                  fill=(230, 220, 255), font=font_name)
        name_b = draw.textbbox((tx0, dial_y + pad_top), "Royal Courier",
                               font=font_name)
        rule_y = name_b[3] + 3
        draw.line([(tx0, rule_y), (tx1, rule_y)], fill=_SOLD_ACCENT, width=1)

        # Wrapped dialogue text
        ch_w, ch_h = _char_dims(draw, font_body)
        cpl = max(10, (tx1 - tx0) // max(1, ch_w))
        ty  = rule_y + int(dial_h * 0.07)
        choice_h = ch_h + 14

        for line in _wrap(COURIER_LINE, cpl):
            if ty + ch_h > H - choice_h - 4:
                break
            draw.text((tx0, ty), line, fill=(200, 195, 215), font=font_body)
            ty += ch_h

        # Choice
        cy = H - choice_h - 4
        draw.line([(tx0, cy - 5), (tx1, cy - 5)], fill=_SOLD_ACCENT, width=1)
        draw.text((tx0, cy), "1.  Confirm receipt.",
                  fill=_SOLD_ACCENT, font=font_choice)

        return to_png(bg)

    # ── Letter scene ──────────────────────────────────────────────────────────

    def _letter_scene(self) -> Optional[bytes]:
        """
        Parchment letter centered on void, hint at bottom.
        """
        if not _PIL:
            return None
        W, H = self._W, self._H

        letter_h = int(H * 0.84)
        letter_w = min(int(letter_h * 0.75), int(W * 0.70))
        raw = render_hypatia_letter(width=letter_w, height=letter_h)

        canvas = Image.new("RGB", (W, H), P.VOID)
        if raw:
            letter_img = Image.open(io.BytesIO(raw)).convert("RGB")
            ox = (W - letter_w) // 2
            oy = int(H * 0.04)
            canvas.paste(letter_img, (ox, oy))

        draw = ImageDraw.Draw(canvas)
        font = _load_font(11)
        hint = "[space]  The work begins."
        hw, _ = text_size(draw, hint, font)
        draw.text(((W - hw) // 2, int(H * 0.92)), hint,
                  fill=P.KO_GOLD, font=font)

        return to_png(canvas)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _char_dims(draw: "ImageDraw.ImageDraw", font) -> tuple[int, int]:
    try:
        b = draw.textbbox((0, 0), "M", font=font)
        return max(1, b[2] - b[0]), max(1, b[3] - b[1]) + 3
    except Exception:
        return 7, 16


def _wrap(text: str, chars_per_line: int) -> list[str]:
    words  = text.split()
    lines: list[str] = []
    cur    = ""
    for word in words:
        candidate = (cur + " " + word).strip()
        if cur and len(candidate) > chars_per_line:
            lines.append(cur)
            cur = word
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    return lines