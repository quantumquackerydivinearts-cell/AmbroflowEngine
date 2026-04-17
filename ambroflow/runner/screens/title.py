"""
Title Screen
============
The first thing the player sees.  Void palette.  Ko's spiral drifting.
Series title + "Press any key to begin."

render_title_screen(width, height) -> bytes (PNG)
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


def render_title_screen(
    width:  int = 1280,
    height: int = 800,
    *,
    pulse: float = 0.0,   # 0.0–1.0 animation phase (for frame sequences)
) -> Optional[bytes]:
    """
    Render the Ko's Labyrinth title screen.

    Parameters
    ----------
    width, height:
        Window dimensions.
    pulse:
        Animation phase [0, 1).  Affects Ko spiral brightness and the
        prompt blink.  Use 0.0 for a static render.
    """
    if not _PIL:
        return None

    W, H = width, height
    img  = Image.new("RGB", (W, H), P.VOID)
    draw = ImageDraw.Draw(img)

    # Star field
    draw_starfield(img, seed=0xA31C, density=0.0015)

    # ── Ko spiral — large, centred, very dim ──────────────────────────────────
    spiral_r = int(min(W, H) * 0.28)
    spiral_col = (
        max(0, min(255, int(P.KO_SPIRAL_DIM[0] + pulse * 20))),
        max(0, min(255, int(P.KO_SPIRAL_DIM[1] + pulse * 15))),
        max(0, min(255, int(P.KO_SPIRAL_DIM[2] + pulse * 28))),
    )
    draw_ko_spiral(
        draw,
        cx=W // 2,
        cy=H // 2 - int(H * 0.06),
        radius=spiral_r,
        col=spiral_col,
        turns=3.5,
        steps=260,
    )

    # ── Outer ring around spiral ──────────────────────────────────────────────
    ring_r = spiral_r + 8
    ring_col = (
        max(0, min(255, P.BORDER[0] + int(pulse * 18))),
        max(0, min(255, P.BORDER[1] + int(pulse * 14))),
        max(0, min(255, P.BORDER[2] + int(pulse * 22))),
    )
    cx, cy = W // 2, H // 2 - int(H * 0.06)
    draw.arc([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
             0, 360, fill=ring_col, width=1)

    # ── Series subtitle ───────────────────────────────────────────────────────
    font_sub  = _load_font(13)
    sub_text  = "Ko's Labyrinth  \u00b7  A 31-Game Anthology"
    sw, sh = text_size(draw, sub_text, font_sub)
    draw.text(((W - sw) // 2, int(H * 0.15)), sub_text,
              fill=P.TEXT_DIM, font=font_sub)

    # ── Main title ────────────────────────────────────────────────────────────
    font_title = _load_font(38)
    title_text = "KLGS"
    tw, th = text_size(draw, title_text, font_title)
    title_y = int(H * 0.20)
    draw.text(((W - tw) // 2, title_y), title_text,
              fill=P.KO_GOLD, font=font_title)

    # Thin rule below title
    rule_y = title_y + th + 10
    rule_x0 = (W - int(W * 0.22)) // 2
    rule_x1 = W - rule_x0
    draw.line([rule_x0, rule_y, rule_x1, rule_y], fill=P.BORDER, width=1)

    # ── Current game tagline ──────────────────────────────────────────────────
    font_game = _load_font(16)
    game_text = "An Alchemist's Labor of Love"
    gw, gh = text_size(draw, game_text, font_game)
    draw.text(((W - gw) // 2, rule_y + 14), game_text,
              fill=P.TEXT_PRIMARY, font=font_game)

    # ── "Press any key" prompt — blinks with pulse ────────────────────────────
    font_prompt = _load_font(12)
    prompt_text = "Press any key to begin"
    pw, ph = text_size(draw, prompt_text, font_prompt)
    alpha = int(120 + 110 * math.sin(pulse * math.pi * 2))
    prompt_col = (
        min(255, int(P.TEXT_DIM[0] * alpha / 255)),
        min(255, int(P.TEXT_DIM[1] * alpha / 255)),
        min(255, int(P.TEXT_DIM[2] * alpha / 255)),
    )
    draw.text(((W - pw) // 2, int(H * 0.88)), prompt_text,
              fill=prompt_col, font=font_prompt)

    # ── Bottom rule ───────────────────────────────────────────────────────────
    draw.line([rule_x0, int(H * 0.92), rule_x1, int(H * 0.92)],
              fill=P.BORDER, width=1)

    # ── Version / build indicator ─────────────────────────────────────────────
    font_tiny = _load_font(10)
    ver_text = "Ambroflow Engine  \u00b7  7_KLGS build"
    vw, _ = text_size(draw, ver_text, font_tiny)
    draw.text((W - vw - 16, int(H * 0.94)), ver_text,
              fill=P.TEXT_DIM, font=font_tiny)

    return to_png(img)