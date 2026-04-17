"""
Player Name Entry Screen
========================
First-time setup: player enters their name.
Void palette. Ko prompt. Cursor blink.

render_name_entry(current_name, cursor_visible, width, height) -> bytes (PNG)
"""

from __future__ import annotations

import math
from typing import Optional

try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False

from .common import _load_font, text_size, to_png, draw_starfield, draw_ko_spiral
from . import palette as P

_KO_PROMPT = "What do they call you?"
_MAX_NAME  = 24


def render_name_entry(
    current_name:   str = "",
    cursor_visible: bool = True,
    *,
    width:  int = 1280,
    height: int = 800,
) -> Optional[bytes]:
    if not _PIL:
        return None

    W, H = width, height
    img  = Image.new("RGB", (W, H), P.VOID)
    draw = ImageDraw.Draw(img)

    draw_starfield(img, seed=0xC5D1, density=0.0010)

    # Ko spiral — centre-top
    draw_ko_spiral(draw, cx=W // 2, cy=int(H * 0.28),
                   radius=int(min(W, H) * 0.14),
                   col=P.KO_SPIRAL_DIM, turns=2.5, steps=160)

    font_prompt = _load_font(18)
    font_input  = _load_font(22)
    font_hint   = _load_font(11)

    # Ko's prompt
    pw, ph = text_size(draw, _KO_PROMPT, font_prompt)
    draw.text(((W - pw) // 2, int(H * 0.50)), _KO_PROMPT,
              fill=P.TEXT_PRIMARY, font=font_prompt)

    # Thin rule below prompt
    ry = int(H * 0.50) + ph + 12
    draw.line([(W // 2 - 180, ry), (W // 2 + 180, ry)], fill=P.BORDER, width=1)

    # Input field
    display  = current_name + ("|" if cursor_visible else " ")
    iw, ih   = text_size(draw, display, font_input)
    field_y  = ry + 18
    draw.text(((W - iw) // 2, field_y), display,
              fill=P.TEXT_WHITE, font=font_input)

    # Hint
    hint_text = "[enter] confirm    [backspace] delete"
    hw, _ = text_size(draw, hint_text, font_hint)
    draw.text(((W - hw) // 2, int(H * 0.80)), hint_text,
              fill=P.TEXT_DIM, font=font_hint)

    return to_png(img)