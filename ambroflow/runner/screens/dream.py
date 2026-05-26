"""
Dream Screen
============
Shown when the player sleeps.  Full-screen void with Ko's spiral, sparse
stars, an atmospheric fragment, and a dim "Wake" prompt.

render_dream_screen(width, height, *, pulse, player_name, date_str) -> bytes
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


# Slightly darker than VOID — the inside of sleep.
_DREAM_BG = (4, 3, 8)

# Atmospheric fragments drawn in sequence; index advances with in-game time.
_FRAGMENTS = [
    "The work is not finished.",
    "Something is watching from the other side of the fire.",
    "You remember a door you have never opened.",
    "The equation resolves, briefly, and then forgets itself.",
    "A voice — not Ko's — says your name.",
    "The Labyrinth does not sleep.",
    "There is a city beneath the city.",
    "You are not the first apprentice.",
    "The spiral tightens.",
    "What Hypatia knows, she has not yet said.",
]


def render_dream_screen(
    width:       int   = 1280,
    height:      int   = 800,
    *,
    pulse:       float = 0.0,
    player_name: str   = "",
    date_str:    str   = "",
    fragment_idx: int  = 0,
) -> Optional[bytes]:
    if not _PIL:
        return None

    W, H = width, height
    img  = Image.new("RGB", (W, H), _DREAM_BG)

    # Sparse star field — fewer than the title, more intimate
    draw_starfield(img, seed=0x4E19, density=0.0006)

    draw = ImageDraw.Draw(img)

    # Ko spiral — large, very dim, centred in the upper half
    spiral_r   = int(min(W, H) * 0.22)
    cy_spiral  = int(H * 0.38)
    glow       = int(pulse * 12)
    spiral_col = (
        max(0, min(255, P.KO_SPIRAL_DIM[0] + glow)),
        max(0, min(255, P.KO_SPIRAL_DIM[1] + glow)),
        max(0, min(255, P.KO_SPIRAL_DIM[2] + glow + 4)),
    )
    draw_ko_spiral(
        draw,
        cx=W // 2,
        cy=cy_spiral,
        radius=spiral_r,
        col=spiral_col,
        turns=4.0,
        steps=320,
    )

    # Thin horizontal rule below spiral
    rule_y  = int(H * 0.60)
    rule_w  = int(W * 0.30)
    rule_x0 = (W - rule_w) // 2
    draw.line([rule_x0, rule_y, rule_x0 + rule_w, rule_y],
              fill=P.BORDER, width=1)

    # Atmospheric fragment
    fragment = _FRAGMENTS[fragment_idx % len(_FRAGMENTS)]
    f_font   = _load_font(15)
    fw, _    = text_size(draw, fragment, f_font)
    draw.text(((W - fw) // 2, rule_y + 16), fragment,
              fill=P.TEXT_DIM, font=f_font)

    # In-game date (if supplied)
    if date_str:
        d_font  = _load_font(11)
        dw, _   = text_size(draw, date_str, d_font)
        draw.text(((W - dw) // 2, rule_y + 38), date_str,
                  fill=(40, 36, 52), font=d_font)

    # Player name — bottom left
    if player_name:
        n_font = _load_font(11)
        draw.text((20, H - 28), player_name, fill=(40, 36, 52), font=n_font)

    # "Wake" prompt — blinking, bottom centre
    wake_alpha  = int(80 + 60 * math.sin(pulse * math.pi * 2))
    wake_col    = (
        min(255, int(P.TEXT_DIM[0] * wake_alpha // 140)),
        min(255, int(P.TEXT_DIM[1] * wake_alpha // 140)),
        min(255, int(P.TEXT_DIM[2] * wake_alpha // 140)),
    )
    w_font  = _load_font(12)
    w_text  = "Press any key to wake"
    ww, _   = text_size(draw, w_text, w_font)
    draw.text(((W - ww) // 2, H - 28), w_text, fill=wake_col, font=w_font)

    return to_png(img)
