"""
Game Selection Screen
=====================
31-game grid.  Void palette.  All games visible.

Layout: 7 columns x 5 rows = 35 slots.  Games 1-31 fill left-to-right,
top-to-bottom.  Last 4 slots are empty (the series is still being written).

Each tile shows:
  - Game number (large, gold)
  - Title (truncated to fit)
  - Status dot + label  (not started | in progress | complete)
  - Faint Ko spiral watermark in top-right corner
  - A subtle "built" indicator for games that are playable in this build

Selected tile gets a warm gold border and the full title + subtitle rendered
in an info panel at the bottom of the screen.

render_game_select(game_statuses, selected_idx, player_name, width, height)
  -> bytes (PNG)

game_statuses: dict[slug -> "not_started" | "in_progress" | "complete"]
selected_idx:  0-30 (index into GAMES tuple)
"""

from __future__ import annotations

import math
from typing import Optional

try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False

from .common import (
    _load_font, text_size, to_png, draw_starfield, draw_ko_spiral,
    draw_rounded_rect,
)
from . import palette as P
from ..registry import GAMES, GameEntry

# Grid dimensions
_COLS = 7
_ROWS = 5     # 7x5 = 35 slots >= 31 games


def _status_colour(status: str) -> tuple:
    return {
        "not_started": P.STATUS_IDLE,
        "in_progress":  P.STATUS_ACTIVE,
        "complete":     P.STATUS_DONE,
    }.get(status, P.STATUS_IDLE)


def _status_label(status: str) -> str:
    return {
        "not_started": "not started",
        "in_progress":  "in progress",
        "complete":     "complete",
    }.get(status, "not started")


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 1] + "\u2026"


def render_game_select(
    game_statuses:  Optional[dict[str, str]] = None,
    selected_idx:   int = 6,    # default: game 7
    player_name:    str = "",
    *,
    width:  int = 1280,
    height: int = 800,
) -> Optional[bytes]:
    """
    Render the game selection grid.

    Parameters
    ----------
    game_statuses:
        Dict mapping game slug to status string.
        Missing entries default to "not_started".
    selected_idx:
        Index into GAMES (0-based) for the highlighted tile.
    player_name:
        Shown in the top bar.
    width, height:
        Output dimensions.
    """
    if not _PIL:
        return None

    statuses = game_statuses or {}
    W, H = width, height

    img  = Image.new("RGB", (W, H), P.VOID)
    draw = ImageDraw.Draw(img)

    draw_starfield(img, seed=0xB9F2, density=0.0010)

    # ── Fonts ─────────────────────────────────────────────────────────────────
    font_num    = _load_font(20)
    font_title  = _load_font(11)
    font_sub    = _load_font(9)
    font_status = _load_font(9)
    font_tiny   = _load_font(9)
    font_header = _load_font(13)
    font_info_t = _load_font(15)
    font_info_s = _load_font(11)

    # ── Top bar ───────────────────────────────────────────────────────────────
    TOP_BAR_H = 52
    draw.rectangle([0, 0, W, TOP_BAR_H], fill=(12, 8, 20))
    draw.line([0, TOP_BAR_H, W, TOP_BAR_H], fill=P.BORDER, width=1)

    hdr_text = "Ko's Labyrinth"
    hw, hh = text_size(draw, hdr_text, font_header)
    draw.text((24, (TOP_BAR_H - hh) // 2), hdr_text, fill=P.KO_GOLD, font=font_header)

    if player_name:
        pn_text = f"Player: {player_name}"
        pw, _ = text_size(draw, pn_text, font_sub)
        draw.text((W - pw - 24, (TOP_BAR_H - hh) // 2 + 2), pn_text,
                  fill=P.TEXT_DIM, font=font_sub)

    # ── Bottom info panel ─────────────────────────────────────────────────────
    BOTTOM_H   = 90
    BOTTOM_Y   = H - BOTTOM_H
    draw.rectangle([0, BOTTOM_Y, W, H], fill=(10, 6, 18))
    draw.line([0, BOTTOM_Y, W, BOTTOM_Y], fill=P.BORDER, width=1)

    sel_game: Optional[GameEntry] = GAMES[selected_idx] if 0 <= selected_idx < len(GAMES) else None
    if sel_game:
        sel_status = statuses.get(sel_game.slug, "not_started")
        num_text = f"{sel_game.number:02d} / 31"
        nw, _ = text_size(draw, num_text, font_header)
        draw.text((24, BOTTOM_Y + 14), num_text, fill=P.TEXT_GOLD, font=font_header)
        draw.text((24 + nw + 12, BOTTOM_Y + 16), sel_game.title,
                  fill=P.TEXT_WHITE, font=font_info_t)
        if sel_game.subtitle:
            draw.text((24, BOTTOM_Y + 42), sel_game.subtitle,
                      fill=P.TEXT_DIM, font=font_info_s)
        # Status
        sdot_x, sdot_y = 24, BOTTOM_Y + 66
        sdot_col = _status_colour(sel_status)
        draw.ellipse([sdot_x, sdot_y, sdot_x + 7, sdot_y + 7], fill=sdot_col)
        draw.text((sdot_x + 12, sdot_y - 1), _status_label(sel_status),
                  fill=P.TEXT_DIM, font=font_status)
        if sel_game.built:
            built_text = "  \u25b6  playable in this build"
            bw, _ = text_size(draw, built_text, font_status)
            draw.text((sdot_x + 12 + 80, sdot_y - 1), built_text,
                      fill=P.BORDER_BUILT, font=font_status)

        # Controls hint right side
        ctrl = "[arrow keys] navigate    [enter] play    [esc] back"
        cw, _ = text_size(draw, ctrl, font_tiny)
        draw.text((W - cw - 24, BOTTOM_Y + 66), ctrl, fill=P.TEXT_DIM, font=font_tiny)

    # ── Grid layout math ──────────────────────────────────────────────────────
    GRID_Y0    = TOP_BAR_H + 8
    GRID_Y1    = BOTTOM_Y - 8
    GRID_X0    = 16
    GRID_X1    = W - 16
    GRID_W     = GRID_X1 - GRID_X0
    GRID_H     = GRID_Y1 - GRID_Y0

    GAP_X      = 8
    GAP_Y      = 7
    TILE_W     = (GRID_W - GAP_X * (_COLS - 1)) // _COLS
    TILE_H     = (GRID_H - GAP_Y * (_ROWS - 1)) // _ROWS
    CORNER_R   = 5

    # ── Draw tiles ────────────────────────────────────────────────────────────
    for idx, game in enumerate(GAMES):
        col   = idx % _COLS
        row   = idx // _COLS
        tx    = GRID_X0 + col * (TILE_W + GAP_X)
        ty    = GRID_Y0 + row * (TILE_H + GAP_Y)
        tx1   = tx + TILE_W
        ty1   = ty + TILE_H

        is_selected = (idx == selected_idx)
        status = statuses.get(game.slug, "not_started")

        # Tile background
        bg = P.CARD_ACTIVE if is_selected else P.CARD
        draw_rounded_rect(draw, (tx, ty, tx1, ty1), CORNER_R, fill=bg)

        # Tile border
        if is_selected:
            border = P.BORDER_SELECT
            bw = 2
        elif game.built:
            border = P.BORDER_BUILT
            bw = 1
        else:
            border = P.BORDER
            bw = 1
        draw_rounded_rect(draw, (tx, ty, tx1, ty1), CORNER_R, outline=border, width=bw)

        # Ko spiral watermark — top right corner
        spiral_r = TILE_H // 5
        draw_ko_spiral(
            draw,
            cx=tx1 - spiral_r - 6,
            cy=ty + spiral_r + 6,
            radius=spiral_r,
            col=(
                P.KO_SPIRAL_DIM[0] + (8 if is_selected else 0),
                P.KO_SPIRAL_DIM[1] + (6 if is_selected else 0),
                P.KO_SPIRAL_DIM[2] + (12 if is_selected else 0),
            ),
            turns=1.8,
            steps=60,
        )

        # Game number — top-left, large gold
        num_str = f"{game.number:02d}"
        nw, nh = text_size(draw, num_str, font_num)
        num_col = P.KO_GOLD if is_selected else P.TEXT_GOLD
        draw.text((tx + 8, ty + 6), num_str, fill=num_col, font=font_num)

        # Title — below number
        title_str = _truncate(game.title, 22)
        draw.text((tx + 8, ty + nh + 10), title_str,
                  fill=P.TEXT_WHITE if is_selected else P.TEXT_PRIMARY,
                  font=font_title)

        # Status dot — bottom-left
        dot_x = tx + 8
        dot_y = ty1 - 14
        dot_col = _status_colour(status)
        draw.ellipse([dot_x, dot_y, dot_x + 6, dot_y + 6], fill=dot_col)

        # Built indicator chevron
        if game.built:
            draw.text((dot_x + 10, dot_y - 1), "\u25b6",
                      fill=P.BORDER_BUILT, font=font_status)

    # ── Selection glow — thin extra ring around selected tile ─────────────────
    if 0 <= selected_idx < len(GAMES):
        gi = selected_idx
        gc = gi % _COLS
        gr = gi // _COLS
        gx = GRID_X0 + gc * (TILE_W + GAP_X) - 2
        gy = GRID_Y0 + gr * (TILE_H + GAP_Y) - 2
        gx1 = gx + TILE_W + 4
        gy1 = gy + TILE_H + 4
        glow_col = (
            min(255, P.BORDER_SELECT[0] - 30),
            min(255, P.BORDER_SELECT[1] - 25),
            min(255, P.BORDER_SELECT[2] - 20),
        )
        draw_rounded_rect(draw, (gx, gy, gx1, gy1), CORNER_R + 2,
                          outline=glow_col, width=1)

    return to_png(img)