"""
Character Creation Screens
==========================
PIL renderers for the Game 7 character creation sequence.

Screens in order:
  1. Ko gender question     — render_ko_gender_question()
  2. Name entry             — render_name_screen()
  3. Lineage selection      — render_lineage_screen()
  4. VITRIOL assignment     — render_vitriol_assignment_sheet()

All screens share the void-indigo background and Ko's visual register.
The gender screen IS Ko's screen — rendered in her palette.
The name and lineage screens use a waking-world palette (darker, warmer).
The VITRIOL sheet bridges both: Ko's read (gold) vs. player's choice.

Palette (chargen)
-----------------
  _VOID        (7, 0, 15)          Ko's background
  _GOLD        (200, 140, 40)      Ko's colour
  _WAKING_BG   (14, 10, 20)        name/lineage background
  _PANEL_BG    (18, 12, 26)        selection panel background
  _PANEL_EDGE  (55, 40, 70)        panel border
  _SELECTED    (200, 140, 40)      selected option highlight
  _UNSELECTED  (130, 110, 150)     unselected option text
  _STAT_KO     (80, 55, 15)        Ko's VITRIOL read (dim gold reference)
  _STAT_PLAYER (200, 140, 40)      player's current assignment (bright gold)
  _STAT_OVER   (180, 80, 40)       over-budget indicator
"""

from __future__ import annotations

import io
import math
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from .data import (
    GENDER_OPTIONS, LINEAGE_OPTIONS,
    GenderOption, LineageOption,
    KO_GENDER_PROMPT,
)

# ── Palette ───────────────────────────────────────────────────────────────────

_VOID         = (  7,   0,  15)
_GOLD         = (200, 140,  40)
_GOLD_BRIGHT  = (255, 220, 100)
_WAKING_BG    = ( 14,  10,  20)
_PANEL_BG     = ( 18,  12,  26)
_PANEL_EDGE   = ( 55,  40,  70)
_SELECTED_BG  = ( 35,  26,   8)
_SELECTED     = (200, 140,  40)
_UNSELECTED   = (130, 110, 150)
_WHITE        = (230, 225, 235)
_DIM          = ( 80,  65,  90)
_STAT_KO      = ( 80,  55,  15)
_STAT_PLAYER  = (200, 140,  40)
_STAT_OVER    = (180,  80,  40)
_BUDGET_OK    = ( 60, 130,  60)
_BUDGET_SPENT = (150,  80,  30)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_font(size: int) -> "ImageFont.FreeTypeFont | ImageFont.ImageFont":
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap(text: str, chars: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if cur and len(cand) > chars:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def _text_size(draw, text, font):
    try:
        b = draw.textbbox((0, 0), text, font=font)
        return b[2]-b[0], b[3]-b[1]
    except AttributeError:
        return len(text)*6, 9


def _centered_text(draw, text, y, W, *, font, color):
    tw, _ = _text_size(draw, text, font)
    draw.text(((W - tw) // 2, y), text, fill=color, font=font)


# ── Ko gender question ────────────────────────────────────────────────────────

def render_ko_gender_question(
    options:      Optional[list[GenderOption]] = None,
    selected_idx: Optional[int] = None,
    *,
    size: int = 512,
) -> Optional[bytes]:
    """
    Ko's gender selection screen — delivered during the dream arrival sequence.

    Ko's portrait occupies the upper portion.  Her prompt floats below.
    The options are listed in a panel at the bottom.
    Selected option is highlighted in gold.

    Parameters
    ----------
    options:
        List of gender options to display. Defaults to ``GENDER_OPTIONS``.
    selected_idx:
        Index of the currently-highlighted option, or None for no selection.
    size:
        Width and height in pixels.
    """
    if not _PIL_AVAILABLE:
        return None

    if options is None:
        options = list(GENDER_OPTIONS)

    # Ko portrait (re-use the same renderer)
    from ambroflow.ko.dialogue_render import _portrait_image, _VOID as _KVO, _BOX_BG

    img  = Image.new("RGB", (size, size), _VOID)
    draw = ImageDraw.Draw(img)

    # Ko portrait (top 40 %)
    portrait_size = int(size * 0.40)
    portrait_y    = int(size * 0.02)
    portrait_img  = _portrait_image(portrait_size)
    img.paste(portrait_img, ((size - portrait_size) // 2, portrait_y))
    draw = ImageDraw.Draw(img)

    # Ko's prompt — floats between portrait and options
    prompt_y  = portrait_y + portrait_size + int(size * 0.010)
    font_prompt = _load_font(14)
    _centered_text(draw, KO_GENDER_PROMPT, prompt_y, size,
                   font=font_prompt, color=(200, 185, 145))

    # Options panel
    PANEL_TOP    = prompt_y + int(size * 0.06)
    PANEL_BOT    = size - int(size * 0.030)
    PANEL_LEFT   = int(size * 0.08)
    PANEL_RIGHT  = size - int(size * 0.08)
    PANEL_H      = PANEL_BOT - PANEL_TOP
    ROW_H        = PANEL_H // max(len(options), 1)

    draw.rectangle([PANEL_LEFT, PANEL_TOP, PANEL_RIGHT, PANEL_BOT],
                   fill=_PANEL_BG, outline=_PANEL_EDGE, width=1)

    font_opt = _load_font(13)
    for i, opt in enumerate(options):
        ry     = PANEL_TOP + i * ROW_H
        is_sel = (selected_idx == i)

        if is_sel:
            draw.rectangle([PANEL_LEFT+1, ry, PANEL_RIGHT-1, ry+ROW_H-1],
                           fill=_SELECTED_BG)
            # Gold mark
            draw.rectangle([PANEL_LEFT+1, ry+2, PANEL_LEFT+4, ry+ROW_H-3],
                           fill=_SELECTED)

        col = _SELECTED if is_sel else _UNSELECTED
        tw, th = _text_size(draw, opt.label, font_opt)
        draw.text((PANEL_LEFT + 12, ry + (ROW_H - th) // 2),
                  opt.label, fill=col, font=font_opt)

        # Row divider
        if i > 0:
            draw.line([(PANEL_LEFT+1, ry), (PANEL_RIGHT-1, ry)],
                      fill=_PANEL_EDGE, width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Name entry screen ─────────────────────────────────────────────────────────

def render_name_screen(
    current_name: str = "",
    *,
    size: int = 512,
) -> Optional[bytes]:
    """
    Name entry screen — waking-world palette, plain.

    A simple field with Ko's question above and the current name below.
    Ko's question: "What do they call you?"
    """
    if not _PIL_AVAILABLE:
        return None

    img  = Image.new("RGB", (size, size), _WAKING_BG)
    draw = ImageDraw.Draw(img)

    # Header rule
    rule_y = int(size * 0.28)
    draw.line([(int(size*0.1), rule_y), (int(size*0.9), rule_y)],
              fill=_PANEL_EDGE, width=1)

    # Ko's prompt
    font_prompt = _load_font(16)
    prompt = "What do they call you?"
    _centered_text(draw, prompt, rule_y - int(size*0.10), size,
                   font=font_prompt, color=(180, 165, 125))

    # Name field
    field_y0 = rule_y + int(size * 0.06)
    field_y1 = field_y0 + int(size * 0.10)
    field_x0 = int(size * 0.15)
    field_x1 = size - int(size * 0.15)

    draw.rectangle([field_x0, field_y0, field_x1, field_y1],
                   fill=_PANEL_BG, outline=_SELECTED if current_name else _PANEL_EDGE, width=1)

    font_name = _load_font(20)
    display = current_name if current_name else "▌"
    tw, th   = _text_size(draw, display, font_name)
    pad_x    = int(size * 0.04)
    name_x   = field_x0 + pad_x
    name_y   = field_y0 + ((field_y1 - field_y0) - th) // 2
    draw.text((name_x, name_y), display,
              fill=_SELECTED if current_name else _DIM, font=font_name)

    # Instruction
    font_hint = _load_font(11)
    hint = "Your name will be known to those who know you."
    _centered_text(draw, hint, field_y1 + int(size*0.04), size,
                   font=font_hint, color=_DIM)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Lineage selection screen ──────────────────────────────────────────────────

def render_lineage_screen(
    options:      Optional[list[LineageOption]] = None,
    selected_idx: Optional[int] = None,
    *,
    size: int = 512,
) -> Optional[bytes]:
    """
    Lineage selection screen — waking-world palette.

    Lists the 5 lineage options with descriptions.
    Selected option shows its description and Ko's note in a detail panel.

    Parameters
    ----------
    options:
        Lineage options to display. Defaults to ``LINEAGE_OPTIONS``.
    selected_idx:
        Currently-highlighted index, or None.
    size:
        Width and height in pixels.
    """
    if not _PIL_AVAILABLE:
        return None

    if options is None:
        options = list(LINEAGE_OPTIONS)

    img  = Image.new("RGB", (size, size), _WAKING_BG)
    draw = ImageDraw.Draw(img)

    # Header
    font_header = _load_font(15)
    header = "Where do you come from?"
    _centered_text(draw, header, int(size*0.04), size,
                   font=font_header, color=(180, 165, 125))
    draw.line([(int(size*0.1), int(size*0.12)), (int(size*0.9), int(size*0.12))],
              fill=_PANEL_EDGE, width=1)

    # Split layout: option list (left 45 %) | detail panel (right 50 %)
    LIST_X0  = int(size * 0.04)
    LIST_X1  = int(size * 0.46)
    LIST_TOP = int(size * 0.14)
    LIST_BOT = size - int(size * 0.04)
    LIST_H   = LIST_BOT - LIST_TOP
    ROW_H    = LIST_H // max(len(options), 1)

    DETAIL_X0  = int(size * 0.50)
    DETAIL_X1  = size - int(size * 0.04)
    DETAIL_TOP = int(size * 0.14)
    DETAIL_BOT = LIST_BOT

    draw.rectangle([LIST_X0, LIST_TOP, LIST_X1, LIST_BOT],
                   fill=_PANEL_BG, outline=_PANEL_EDGE, width=1)
    draw.rectangle([DETAIL_X0, DETAIL_TOP, DETAIL_X1, DETAIL_BOT],
                   fill=_PANEL_BG, outline=_PANEL_EDGE, width=1)

    font_name = _load_font(13)
    font_desc = _load_font(11)

    for i, lin in enumerate(options):
        ry     = LIST_TOP + i * ROW_H
        is_sel = (selected_idx == i)

        if is_sel:
            draw.rectangle([LIST_X0+1, ry, LIST_X1-1, ry+ROW_H-1], fill=_SELECTED_BG)
            draw.rectangle([LIST_X0+1, ry+2, LIST_X0+4, ry+ROW_H-3], fill=_SELECTED)

        col = _SELECTED if is_sel else _UNSELECTED
        draw.text((LIST_X0 + 10, ry + 6), lin.name, fill=col, font=font_name)

        if i > 0:
            draw.line([(LIST_X0+1, ry), (LIST_X1-1, ry)], fill=_PANEL_EDGE, width=1)

    # Detail panel: selected option's description + Ko's note
    if selected_idx is not None and 0 <= selected_idx < len(options):
        sel = options[selected_idx]
        pad = int(size * 0.025)
        ty  = DETAIL_TOP + pad

        # Name header
        draw.text((DETAIL_X0 + pad, ty), sel.name, fill=_SELECTED, font=font_name)
        ty += int(size * 0.055)

        # Description (wrapped)
        desc_chars = max(10, (DETAIL_X1 - DETAIL_X0 - pad*2) // 6)
        for line in _wrap(sel.description, desc_chars):
            draw.text((DETAIL_X0 + pad, ty), line, fill=_WHITE, font=font_desc)
            ty += int(size * 0.030)

        ty += int(size * 0.025)
        draw.line([(DETAIL_X0+pad, ty), (DETAIL_X1-pad, ty)],
                  fill=_PANEL_EDGE, width=1)
        ty += int(size * 0.020)

        # Ko's note (italic-style with smaller font)
        draw.text((DETAIL_X0+pad, ty), "Ko:", fill=_GOLD, font=font_desc)
        ty += int(size * 0.028)
        for line in _wrap(sel.ko_note, desc_chars):
            draw.text((DETAIL_X0+pad, ty), line, fill=(180, 160, 100), font=font_desc)
            ty += int(size * 0.028)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── VITRIOL assignment sheet ──────────────────────────────────────────────────

TOTAL_BUDGET = 31
STAT_MIN     = 1
STAT_MAX     = 10

_STAT_LABELS: dict[str, str] = {
    "vitality":      "Vitality      V",
    "introspection": "Introspection I",
    "tactility":     "Tactility     T",
    "reflectivity":  "Reflectivity  R",
    "ingenuity":     "Ingenuity     I",
    "ostentation":   "Ostentation   O",
    "levity":        "Levity        L",
}


def render_vitriol_assignment_sheet(
    ko_profile:       dict[str, int],
    player_values:    dict[str, int],
    budget_remaining: int,
    *,
    active_stat: Optional[str] = None,
    size: int = 512,
) -> Optional[bytes]:
    """
    VITRIOL manual assignment screen.

    Left column: Ko's read (immutable, dim gold — the reference).
    Right column: Player's current assignment (bright gold — the choice).
    A bar graph shows both side-by-side for each stat.
    Budget tracker at the bottom.

    Parameters
    ----------
    ko_profile:
        Ko's assigned profile as ``{stat: value}``.
    player_values:
        Player's current assignment (may be partial — missing stats show as 0).
    budget_remaining:
        Points left to distribute (TOTAL_BUDGET - sum(player_values)).
    active_stat:
        Currently-selected stat for editing, or None.
    size:
        Width and height in pixels.
    """
    if not _PIL_AVAILABLE:
        return None

    from ambroflow.ko.vitriol import VITRIOL_STATS

    img  = Image.new("RGB", (size, size), _WAKING_BG)
    draw = ImageDraw.Draw(img)

    # Header
    font_hdr  = _load_font(14)
    font_stat = _load_font(12)
    font_val  = _load_font(18)
    font_tiny = _load_font(10)

    _centered_text(draw, "VITRIOL", int(size*0.03), size,
                   font=_load_font(20), color=_GOLD_BRIGHT)
    draw.line([(int(size*0.08), int(size*0.10)), (int(size*0.92), int(size*0.10))],
              fill=_PANEL_EDGE, width=1)

    # Column headers
    COL_LABEL_X = int(size * 0.04)
    COL_KO_X    = int(size * 0.50)
    COL_PLAY_X  = int(size * 0.68)
    COL_BAR_X0  = int(size * 0.50)
    COL_BAR_X1  = size - int(size * 0.04)
    HEADER_Y    = int(size * 0.12)
    BAR_MAXW    = COL_BAR_X1 - COL_BAR_X0 - 10

    draw.text((COL_KO_X,   HEADER_Y), "Ko",     fill=_STAT_KO,     font=font_tiny)
    draw.text((COL_PLAY_X, HEADER_Y), "You",    fill=_STAT_PLAYER, font=font_tiny)

    # Per-stat rows
    ROW_Y0    = int(size * 0.16)
    ROW_H     = int(size * 0.087)
    BAR_H     = max(4, ROW_H // 4)

    for i, stat in enumerate(VITRIOL_STATS):
        ry       = ROW_Y0 + i * ROW_H
        is_active = (active_stat == stat)
        ko_v     = getattr(ko_profile, stat, 1)
        pl_v     = player_values.get(stat, 0)

        # Row background if active
        if is_active:
            draw.rectangle([int(size*0.02), ry, size-int(size*0.02), ry+ROW_H-2],
                           fill=(22, 16, 32))

        # Stat label
        draw.text((COL_LABEL_X, ry+2), _STAT_LABELS[stat],
                  fill=_SELECTED if is_active else _UNSELECTED, font=font_stat)

        # Ko's value
        draw.text((COL_KO_X, ry+2), str(ko_v), fill=_STAT_KO, font=font_stat)

        # Player's value
        pl_col = _STAT_OVER if pl_v > STAT_MAX else (
            _STAT_PLAYER if pl_v > 0 else _DIM
        )
        draw.text((COL_PLAY_X, ry+2), str(pl_v) if pl_v > 0 else "—",
                  fill=pl_col, font=font_stat)

        # Bar (starts at COL_BAR_X0 + offset, height BAR_H)
        bar_y = ry + ROW_H - BAR_H - 4

        # Ko bar (dim gold, behind)
        ko_bar_w = int(BAR_MAXW * ko_v / STAT_MAX)
        draw.rectangle([COL_BAR_X0+8, bar_y, COL_BAR_X0+8+ko_bar_w, bar_y+BAR_H],
                       fill=_STAT_KO)

        # Player bar (bright gold, overlaid or offset)
        if pl_v > 0:
            pl_bar_w = int(BAR_MAXW * pl_v / STAT_MAX)
            pl_bar_col = _STAT_OVER if pl_v > STAT_MAX else _STAT_PLAYER
            draw.rectangle([COL_BAR_X0+8, bar_y+2, COL_BAR_X0+8+pl_bar_w, bar_y+BAR_H-2],
                           fill=pl_bar_col)

        # Separator
        draw.line([(int(size*0.02), ry+ROW_H-1), (size-int(size*0.02), ry+ROW_H-1)],
                  fill=_PANEL_EDGE, width=1)

    # Budget tracker
    BUDGET_Y = ROW_Y0 + len(VITRIOL_STATS) * ROW_H + int(size * 0.018)
    draw.line([(int(size*0.08), BUDGET_Y-2), (int(size*0.92), BUDGET_Y-2)],
              fill=_PANEL_EDGE, width=1)

    budget_col = _BUDGET_OK if budget_remaining >= 0 else _STAT_OVER
    budget_str = f"{budget_remaining} points remaining" if budget_remaining >= 0 else \
                 f"{abs(budget_remaining)} points over budget"
    _centered_text(draw, budget_str, BUDGET_Y + int(size*0.010), size,
                   font=font_stat, color=budget_col)

    # Legend
    legend_y = BUDGET_Y + int(size * 0.065)
    draw.rectangle([int(size*0.12), legend_y, int(size*0.17), legend_y+8],
                   fill=_STAT_KO)
    draw.text((int(size*0.19), legend_y), "Ko's read", fill=_DIM, font=font_tiny)
    draw.rectangle([int(size*0.45), legend_y, int(size*0.50), legend_y+8],
                   fill=_STAT_PLAYER)
    draw.text((int(size*0.52), legend_y), "Your choice", fill=_DIM, font=font_tiny)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Export chargen sequence ───────────────────────────────────────────────────

def render_chargen_sequence(
    ko_profile:    dict[str, int],
    chargen_state: "ChargenState",   # type: ignore[name-defined]
    *,
    size: int = 512,
) -> list[bytes]:
    """
    Render the full character creation sequence as an ordered list of frames.

    Frames in order:
      1. Ko gender question (no selection highlighted — initial state)
      2. Name entry screen
      3. Lineage selection (no selection highlighted — initial state)
      4. VITRIOL assignment sheet (Ko's read as reference, player budget = 31)

    For interactive use, re-render individual screens as the player makes
    selections — these are the initial (blank) states.
    """
    frames: list[bytes] = []

    def _add(b: Optional[bytes]) -> None:
        if b is not None:
            frames.append(b)

    _add(render_ko_gender_question(size=size))
    _add(render_name_screen(size=size))
    _add(render_lineage_screen(size=size))
    _add(render_vitriol_assignment_sheet(
        ko_profile=ko_profile,
        player_values={},
        budget_remaining=TOTAL_BUDGET,
        size=size,
    ))
    return frames