"""
Dream Scene Director
====================
Orchestrates the full Ko dream calibration sequence as a series of visual screens.

The dream has six distinct visual states, rendered as 512×512 PNG images:

  ARRIVAL (3 frames)
    Ko materializes progressively from void.
    Stage 0 — void + inverse-radial shimmer. "You are here."
               Ko is not present yet. Light radiates inward from the edges,
               darkest at the center — a pupil dilating in the void.
    Stage 1 — Ko silhouette emerging (~30 % opacity). Ground line:
               "The ground has not assembled yet. Stay in that."
    Stage 2 — Ko fully present. No dialogue box. Final arrival line floats
               below the portrait: "The reading begins from what is already
               true. The questions are not the reading — you are."

  SAKURA phase (3 prompts)
    Ko portrait + phase ribbon + dialogue box.
    Background: high-frequency deterministic particle scatter.
    Pale rose-pink. Reads: orientation capacity, liminal boundary handling.

  ROSE phase (3 prompts)
    Ko portrait + phase ribbon + dialogue box.
    Background: mid-frequency sine interference wave at the lower 45 %.
    Deep rose/magenta. Reads: pre-linguistic spectral register, polarity.

  LOTUS phase (3 prompts)
    Ko portrait + phase ribbon + dialogue box.
    Background: slow crystalline hexagonal lattice growing from all four edges.
    Water-blue. Reads: elemental threshold character, material ground.

  VITRIOL ASSIGNMENT (7 screens, one per stat)
    Ko portrait (left ~40 % width).
    VITRIOL spine (right side): V I T R I O L letters with values.
      — Current stat: bright gold letter + value.
      — Already assigned: dim gold letter + value.
      — Pending: near-void letter only (no value).
    Ko's recognition line: bottom text box, phase accent = gold.

  CLOSING (3 frames, Ko dissolving)
    Frame 0 — Ko full, centered unboxed text.
    Frame 1 — Ko at 50 % opacity. Unboxed text.
    Frame 2 — Ko gone. "Wake." — single large word, centered, warm gold,
               on void with a faint dawn bloom rising from below.

Palette
-------
  VOID         (7, 0, 15)         — Ko's interior / base background
  GOLD         (200, 140, 40)     — primary Ko presence
  GOLD_BRIGHT  (255, 220, 100)    — peak brightness / current stat
  GOLD_DIM     (80, 55, 15)       — revealed stat (past Ko recognition)
  GOLD_GHOST   (22, 16, 5)        — pending stat (barely visible)
  SAKURA_PINK  (220, 160, 190)    — Sakura phase accent
  ROSE_DEEP    (200, 90, 120)     — Rose phase accent
  LOTUS_BLUE   (60, 110, 200)     — Lotus phase accent
  DAWN_GRAY    (38, 30, 42)       — arrival/closing shimmer horizon
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

from .dialogue_render import (
    _portrait_image,      # internal — same package
    _load_font,
    _wrap_text,
    _VOID,
    _GOLD,
    _GOLD_BRIGHT,
    _BOX_BG,
    _BOX_BORDER,
    _PHASE_COLOR,
    _PHASE_LABEL,
)
from .vitriol import VITRIOL_STATS


# ── Extended palette ──────────────────────────────────────────────────────────

_GOLD_DIM     = (80,  55,  15)
_GOLD_GHOST   = (22,  16,   5)
_SAKURA       = (220, 160, 190)
_ROSE         = (200,  90, 120)
_LOTUS        = ( 60, 110, 200)
_DAWN         = ( 38,  30,  42)    # horizon color for closing bloom
_TEXT_FLOAT   = (230, 220, 200)    # unboxed floating text color
_WHITE        = (255, 255, 255)

# Stat spine: initial letter for each VITRIOL stat (display order)
_VITRIOL_LETTERS: dict[str, str] = {
    "vitality":      "V",
    "introspection": "I",
    "tactility":     "T",
    "reflectivity":  "R",
    "ingenuity":     "I",
    "ostentation":   "O",
    "levity":        "L",
}


# ── Background generators ─────────────────────────────────────────────────────

def _fill_void(img: "Image.Image") -> None:
    """Fill image with the void-indigo base color."""
    img.paste(_VOID, [0, 0, img.width, img.height])


def _arrival_shimmer(draw: "ImageDraw.ImageDraw", size: int) -> None:
    """
    Inverse-radial shimmer for the arrival stage.
    Light radiates inward from the edges — darkest at the center.
    Rendered as concentric rectangles with decreasing luminosity toward center.
    """
    cx = cy = size // 2
    steps = 32
    for i in range(steps, 0, -1):
        t = i / steps                  # 1.0 at edge, near 0 at center
        margin = int(cx * (1.0 - t))
        r = int(_VOID[0] + (_DAWN[0] - _VOID[0]) * t * 0.6)
        g = int(_VOID[1] + (_DAWN[1] - _VOID[1]) * t * 0.6)
        b = int(_VOID[2] + (_DAWN[2] - _VOID[2]) * t * 0.6)
        draw.rectangle(
            [margin, margin, size - margin, size - margin],
            outline=(r, g, b), width=1,
        )


def _faint_spiral_trace(draw: "ImageDraw.ImageDraw", size: int, opacity: float) -> None:
    """
    Draw Ko's Ouroboros as faint dotted traces — used in arrival stage 1
    before the full portrait materializes.  opacity ∈ [0, 1].
    """
    if opacity <= 0.0:
        return

    R  = size * 0.36
    cx = cy = size * 0.5
    N_SPIRALS = 7
    b = -0.25
    points_per_arm = 80

    for k in range(N_SPIRALS):
        base_angle = k * (2.0 * math.pi / N_SPIRALS)
        pts: list[tuple[float, float]] = []
        for j in range(points_per_arm):
            t = base_angle + j * (2.0 * math.pi / points_per_arm)
            r = R * math.exp(b * t)
            if r < 2 or r > R * 1.9:
                continue
            x = cx + r * math.cos(t)
            y = cy + r * math.sin(t)
            pts.append((x, y))
        if len(pts) >= 2:
            col_v = int(_GOLD[0] * opacity * 0.6)
            col = (col_v, int(_GOLD[1] * opacity * 0.6), int(_GOLD[2] * opacity * 0.6))
            draw.line(pts, fill=col, width=1)


def _sakura_scatter(pix: object, size: int, density: float = 0.006) -> None:
    """
    Deterministic high-frequency particle scatter — orientation layer.
    Reads the Sakura register (fast, ephemeral bright points).
    """
    for y in range(size):
        for x in range(size):
            # Deterministic hash from pixel coords
            h = ((x * 1664525) ^ (y * 1013904223) ^ 0xDEAD_BEEF) & 0xFFFF_FFFF
            if (h / 0xFFFF_FFFF) < density:
                bright_mod = (h >> 16) % 80
                r = min(255, _SAKURA[0] + bright_mod // 3)
                g = min(255, _SAKURA[1] + bright_mod // 5)
                b = min(255, _SAKURA[2] + bright_mod // 3)
                pix[x, y] = (r, g, b)


def _rose_interference(pix: object, size: int) -> None:
    """
    Mid-frequency sine interference wave — relational/spectral layer.
    Two interfering sine waves in the lower 45 % of the screen.
    Where the waves constructively interfere, rose color bleeds up through the void.
    """
    base_y = int(size * 0.55)
    total  = size - base_y or 1
    for row in range(base_y, size):
        t = (row - base_y) / total          # 0→1 top to bottom of the wave zone
        for col in range(size):
            phase1 = col / size * 2 * math.pi * 7
            phase2 = col / size * 2 * math.pi * 7 + 1.9436   # ≈ golden-ratio offset
            wave   = (math.sin(phase1) + math.sin(phase2)) * 0.5   # −1 → +1
            if wave > 0.0:
                alpha = t * wave * 0.50
                r = int(_VOID[0] + (_ROSE[0] - _VOID[0]) * alpha)
                g = int(_VOID[1] + (_ROSE[1] - _VOID[1]) * alpha)
                b = int(_VOID[2] + (_ROSE[2] - _VOID[2]) * alpha)
                pix[col, row] = (
                    max(0, min(255, r)),
                    max(0, min(255, g)),
                    max(0, min(255, b)),
                )


def _lotus_hex_lattice(draw: "ImageDraw.ImageDraw", size: int) -> None:
    """
    Crystalline hexagonal lattice growing from all four edges toward the center.
    Represents material ground assembling itself — slow, structural, water-blue.
    Opacity: maximum at edges, fades to zero by 35 % in from each edge.
    """
    CELL = size // 14     # hexagon cell radius
    if CELL < 3:
        return

    rows = size // CELL + 3
    cols = size // CELL + 3

    for row in range(-1, rows):
        for col in range(-1, cols):
            # Offset alternate rows by half a cell (hex grid)
            hx = col * CELL * 1.5 - CELL
            hy = row * CELL * 1.732 + (col % 2) * CELL * 0.866 - CELL * 0.866

            # Distance from nearest edge, normalized to [0, 1]
            # 0 = at the edge, 1 = at the center
            edge_dx = min(hx, size - hx) / size
            edge_dy = min(hy, size - hy) / size
            center_dist = min(edge_dx, edge_dy)

            # Only draw within the outer 35 % from each edge
            if center_dist > 0.35:
                continue

            # Fade in from outer edge
            fade = max(0.0, 0.35 - center_dist) / 0.35   # 1 at edge, 0 at 35%

            for step in range(6):
                a1 = math.radians(step * 60)
                a2 = math.radians((step + 1) * 60)
                x1 = int(hx + CELL * 0.48 * math.cos(a1))
                y1 = int(hy + CELL * 0.48 * math.sin(a1))
                x2 = int(hx + CELL * 0.48 * math.cos(a2))
                y2 = int(hy + CELL * 0.48 * math.sin(a2))

                intensity = fade * 0.55
                r = int(_VOID[0] + (_LOTUS[0] - _VOID[0]) * intensity)
                g = int(_VOID[1] + (_LOTUS[1] - _VOID[1]) * intensity)
                b = int(_VOID[2] + (_LOTUS[2] - _VOID[2]) * intensity)

                draw.line([(x1, y1), (x2, y2)], fill=(r, g, b), width=1)


def _dawn_bloom(pix: object, size: int, intensity: float) -> None:
    """
    Dawn bloom for the closing stage — faint warm gray rising from below.
    intensity ∈ [0, 1]: 0 = none, 1 = full bloom at maximum.
    """
    if intensity <= 0.0:
        return
    for row in range(size):
        # Bloom rises from the bottom
        t = (size - row) / size   # 1 at bottom, 0 at top
        t = max(0.0, t * intensity)
        for col in range(size):
            r = int(_VOID[0] + (_DAWN[0] - _VOID[0]) * t)
            g = int(_VOID[1] + (_DAWN[1] - _VOID[1]) * t)
            b = int(_VOID[2] + (_DAWN[2] - _VOID[2]) * t)
            cur = pix[col, row]
            pix[col, row] = (
                max(cur[0], r),
                max(cur[1], g),
                max(cur[2], b),
            )


# ── Floating text (no dialogue box) ──────────────────────────────────────────

def _draw_floating_text(
    draw: "ImageDraw.ImageDraw",
    text: str,
    size: int,
    *,
    y_frac: float = 0.78,
    color: tuple = _TEXT_FLOAT,
    font_size: int = 15,
    large: bool = False,
) -> None:
    """
    Draw centered text that floats on the void — no box, no border.
    y_frac: vertical position as fraction of screen height.
    large: if True, renders as a single larger headline word.
    """
    font = _load_font(font_size * (3 if large else 1))

    try:
        bbox  = draw.textbbox((0, 0), "M", font=font)
        ch_w  = max(1, bbox[2] - bbox[0])
        ch_h  = max(1, bbox[3] - bbox[1]) + 4
    except AttributeError:
        ch_w, ch_h = 7, (font_size * 3 if large else font_size)

    chars_per_line = max(6, int(size * 0.80) // ch_w)
    lines = [text] if large else _wrap_text(text, chars_per_line)

    total_h = len(lines) * ch_h
    y = int(size * y_frac) - total_h // 2

    for line in lines:
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            lw   = bbox[2] - bbox[0]
        except AttributeError:
            lw = len(line) * ch_w
        draw.text(((size - lw) // 2, y), line, fill=color, font=font)
        y += ch_h


# ── Public rendering functions ────────────────────────────────────────────────

def render_arrival_screen(
    text:  str,
    stage: int = 0,
    *,
    size:  int  = 512,
) -> Optional[bytes]:
    """
    Render a Ko arrival screen (before calibration begins).

    Parameters
    ----------
    text:
        The arrival line Ko speaks (one of GAME_OPENING_LINES[game_id]).
    stage:
        0 — Void only. Ko is not yet present. Inverse-radial shimmer.
        1 — Ko silhouette faintly emerging (~30 % opacity + spiral traces).
        2 — Ko fully present. Text floats below portrait. No dialogue box.
    size:
        Width and height in pixels.
    """
    if not _PIL_AVAILABLE:
        return None

    img  = Image.new("RGB", (size, size), _VOID)
    draw = ImageDraw.Draw(img)
    pix  = img.load()

    if stage == 0:
        # Inverse-radial shimmer — Ko has not arrived
        _arrival_shimmer(draw, size)
        _draw_floating_text(draw, text, size, y_frac=0.72, color=_TEXT_FLOAT)

    elif stage == 1:
        # Ko materializing — faint spiral traces
        _arrival_shimmer(draw, size)
        _faint_spiral_trace(draw, size, opacity=0.30)
        _draw_floating_text(draw, text, size, y_frac=0.80, color=_TEXT_FLOAT)

    else:
        # Ko fully present — portrait composited, text floats below
        portrait_size = int(size * 0.54)
        portrait_y    = int(size * 0.06)
        portrait_img  = _portrait_image(portrait_size)
        img.paste(portrait_img, ((size - portrait_size) // 2, portrait_y))
        # Re-acquire draw after paste
        draw = ImageDraw.Draw(img)
        text_y_frac = (portrait_y + portrait_size + int(size * 0.06)) / size
        _draw_floating_text(draw, text, size, y_frac=text_y_frac + 0.05, color=_TEXT_FLOAT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_phase_screen(
    text:  str,
    phase: str,
    *,
    size:  int = 512,
) -> Optional[bytes]:
    """
    Render a Ko calibration prompt screen with phase-specific background.

    Extends the base dialogue_render layout with a background layer that
    reflects the epistemic register being probed:

    sakura — high-freq particle scatter (orientation/fast layer)
    rose   — sine interference wave at lower 45 % (relational/spectral)
    lotus  — crystalline hex lattice at edges (material ground assembling)

    Parameters
    ----------
    text:   Prompt text Ko speaks.
    phase:  "sakura" | "rose" | "lotus"
    size:   Width and height in pixels.
    """
    if not _PIL_AVAILABLE:
        return None

    phase  = phase.lower()
    accent = _PHASE_COLOR.get(phase, _GOLD)
    label  = _PHASE_LABEL.get(phase, phase.upper())

    img  = Image.new("RGB", (size, size), _VOID)
    draw = ImageDraw.Draw(img)
    pix  = img.load()

    # ── Phase background ──────────────────────────────────────────────────────
    if phase == "sakura":
        _sakura_scatter(pix, size, density=0.0055)
    elif phase == "rose":
        _rose_interference(pix, size)
    elif phase == "lotus":
        _lotus_hex_lattice(draw, size)
        # Re-acquire draw after lattice drawing
        draw = ImageDraw.Draw(img)

    # ── Ko portrait ───────────────────────────────────────────────────────────
    portrait_size = int(size * 0.54)
    portrait_y    = int(size * 0.024)
    portrait_img  = _portrait_image(portrait_size)
    img.paste(portrait_img, ((size - portrait_size) // 2, portrait_y))
    draw = ImageDraw.Draw(img)

    # ── Phase ribbon ──────────────────────────────────────────────────────────
    ribbon_y   = portrait_y + portrait_size + int(size * 0.008)
    font_phase = _load_font(11)
    try:
        bbox       = draw.textbbox((0, 0), label, font=font_phase)
        lw, lh     = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        lw, lh = len(label) * 6, 9

    label_x = (size - lw) // 2
    label_y = ribbon_y + 2
    line_y  = label_y + lh // 2
    margin  = int(size * 0.08)
    draw.line([(margin, line_y), (label_x - 8, line_y)], fill=accent, width=1)
    draw.line([(label_x + lw + 8, line_y), (size - margin, line_y)], fill=accent, width=1)
    draw.text((label_x, label_y), label, fill=accent, font=font_phase)

    # ── Dialogue box ──────────────────────────────────────────────────────────
    box_margin = int(size * 0.042)
    box_top    = ribbon_y + lh + int(size * 0.038)
    box_bottom = size - box_margin
    box_left   = box_margin
    box_right  = size - box_margin

    draw.rectangle([box_left, box_top, box_right, box_bottom],
                   fill=_BOX_BG, outline=_BOX_BORDER, width=1)

    corner_len = int(size * 0.022)
    for cx, cy, sx, sy in [
        (box_left,  box_top,    1,  1),
        (box_right, box_top,   -1,  1),
        (box_left,  box_bottom,  1, -1),
        (box_right, box_bottom, -1, -1),
    ]:
        draw.line([(cx, cy), (cx + sx * corner_len, cy)], fill=accent, width=1)
        draw.line([(cx, cy), (cx, cy + sy * corner_len)], fill=accent, width=1)

    font_text = _load_font(15)
    pad_x = int(size * 0.032)
    pad_y = int(size * 0.022)
    text_x = box_left  + pad_x
    text_y = box_top   + pad_y
    max_w  = box_right - box_left - pad_x * 2
    try:
        bbox   = draw.textbbox((0, 0), "M", font=font_text)
        ch_w   = max(1, bbox[2] - bbox[0])
        ch_h   = max(1, bbox[3] - bbox[1]) + 4
    except AttributeError:
        ch_w, ch_h = 7, 18
    chars_per_line = max(10, int(max_w) // int(ch_w))
    for line in _wrap_text(text, chars_per_line):
        if text_y + ch_h > box_bottom - pad_y:
            break
        draw.text((text_x, text_y), line, fill=_WHITE, font=font_text)
        text_y += ch_h

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_vitriol_screen(
    stat:     str,
    value:    int,
    ko_line:  str,
    revealed: dict[str, int],
    *,
    size:     int = 512,
) -> Optional[bytes]:
    """
    Render a VITRIOL assignment screen.

    Ko's portrait occupies the left ~40 % of the screen.
    The VITRIOL stat spine is drawn on the right side: V I T R I O L,
    one letter per line, with values for revealed stats.
    Ko's recognition line is shown in a dialogue box at the bottom.

    Parameters
    ----------
    stat:
        The stat currently being assigned (e.g. ``"reflectivity"``).
    value:
        Ko's assigned integer value for this stat.
    ko_line:
        Ko's recognition line for this stat (from GAME_ASSIGNMENT_LINES).
    revealed:
        Dict of stats already assigned in prior screens,
        including the current one: ``{"vitality": 4, "introspection": 6, ...}``.
    size:
        Width and height in pixels.
    """
    if not _PIL_AVAILABLE:
        return None

    img  = Image.new("RGB", (size, size), _VOID)
    draw = ImageDraw.Draw(img)

    # ── Ko portrait (left ~42 %) ──────────────────────────────────────────────
    portrait_w   = int(size * 0.42)
    portrait_img = _portrait_image(portrait_w)
    portrait_y   = int(size * 0.04)
    img.paste(portrait_img, (0, portrait_y))
    draw = ImageDraw.Draw(img)

    # Thin vertical divider
    div_x = portrait_w + int(size * 0.018)
    draw.line([(div_x, int(size * 0.06)), (div_x, int(size * 0.72))],
              fill=_GOLD_DIM, width=1)

    # ── VITRIOL stat spine (right side) ──────────────────────────────────────
    spine_x  = div_x + int(size * 0.035)
    spine_y0 = int(size * 0.09)
    row_h    = int(size * 0.085)

    font_letter = _load_font(26)
    font_val    = _load_font(18)

    for i, sname in enumerate(VITRIOL_STATS):
        letter = _VITRIOL_LETTERS[sname]
        ry = spine_y0 + i * row_h
        is_current = (sname == stat)

        if is_current:
            letter_color = _GOLD_BRIGHT
            val_color    = _GOLD_BRIGHT
        elif sname in revealed:
            letter_color = _GOLD_DIM
            val_color    = _GOLD_DIM
        else:
            letter_color = _GOLD_GHOST
            val_color    = _GOLD_GHOST

        draw.text((spine_x, ry), letter, fill=letter_color, font=font_letter)

        if sname in revealed:
            val_str = str(revealed[sname])
        elif is_current:
            val_str = str(value)
        else:
            val_str = "·"

        val_x = spine_x + int(size * 0.085)
        draw.text((val_x, ry + int(row_h * 0.12)), val_str, fill=val_color, font=font_val)

        # Separator line under current stat
        if is_current:
            line_x0 = spine_x
            line_x1 = spine_x + int(size * 0.42)
            draw.line([(line_x0, ry + row_h - 2), (line_x1, ry + row_h - 2)],
                      fill=_GOLD, width=1)

    # ── Ko's recognition line (bottom box) ───────────────────────────────────
    box_margin = int(size * 0.042)
    box_top    = int(size * 0.74)
    box_bottom = size - box_margin
    box_left   = box_margin
    box_right  = size - box_margin

    draw.rectangle([box_left, box_top, box_right, box_bottom],
                   fill=_BOX_BG, outline=_GOLD_DIM, width=1)

    # Gold corner accent marks
    cl = int(size * 0.022)
    for cx, cy, sx, sy in [
        (box_left,  box_top,    1,  1),
        (box_right, box_top,   -1,  1),
        (box_left,  box_bottom,  1, -1),
        (box_right, box_bottom, -1, -1),
    ]:
        draw.line([(cx, cy), (cx + sx * cl, cy)], fill=_GOLD, width=1)
        draw.line([(cx, cy), (cx, cy + sy * cl)], fill=_GOLD, width=1)

    font_text = _load_font(14)
    pad_x = int(size * 0.032)
    pad_y = int(size * 0.018)
    text_x = box_left  + pad_x
    text_y = box_top   + pad_y
    max_w  = box_right - box_left - pad_x * 2
    try:
        bbox   = draw.textbbox((0, 0), "M", font=font_text)
        ch_w   = max(1, bbox[2] - bbox[0])
        ch_h   = max(1, bbox[3] - bbox[1]) + 3
    except AttributeError:
        ch_w, ch_h = 7, 16
    chars_per_line = max(10, int(max_w) // int(ch_w))
    for line in _wrap_text(ko_line, chars_per_line):
        if text_y + ch_h > box_bottom - pad_y:
            break
        draw.text((text_x, text_y), line, fill=_WHITE, font=font_text)
        text_y += ch_h

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_closing_screen(
    text:    str,
    stage:   int = 0,
    *,
    size:    int = 512,
) -> Optional[bytes]:
    """
    Render a Ko closing screen (after VITRIOL assignment, before waking).

    Stage 0 — Ko fully present. Text floats unboxed below portrait.
              Ko names the reading without prescription.
    Stage 1 — Ko portrait at 50 % opacity. Text floats. Ko names the gap.
    Stage 2 — Ko portrait gone. "Wake." — single large word, centered,
              warm gold, on void with faint dawn bloom rising from below.

    Parameters
    ----------
    text:   The closing line (from GAME_CLOSING_LINES[game_id]).
    stage:  0 | 1 | 2
    size:   Width and height in pixels.
    """
    if not _PIL_AVAILABLE:
        return None

    img  = Image.new("RGB", (size, size), _VOID)
    draw = ImageDraw.Draw(img)
    pix  = img.load()

    is_final = (text.strip() == "Wake." or stage == 2)

    if is_final:
        # No Ko. Dawn bloom. "Wake." large and centered.
        _dawn_bloom(pix, size, intensity=0.55)
        draw = ImageDraw.Draw(img)
        _draw_floating_text(draw, "Wake.", size, y_frac=0.50,
                            color=_GOLD_BRIGHT, font_size=18, large=True)
    else:
        portrait_size = int(size * 0.54)
        portrait_y    = int(size * 0.06)
        portrait_img  = _portrait_image(portrait_size)

        if stage == 1:
            # Blend portrait with void at 50 % — composite on RGBA layer
            void_layer = Image.new("RGB", (portrait_size, portrait_size), _VOID)
            blended    = Image.blend(void_layer, portrait_img, 0.5)
            img.paste(blended, ((size - portrait_size) // 2, portrait_y))
        else:
            img.paste(portrait_img, ((size - portrait_size) // 2, portrait_y))

        draw = ImageDraw.Draw(img)
        text_y_start = (portrait_y + portrait_size) / size + 0.05
        _draw_floating_text(draw, text, size,
                            y_frac=text_y_start + 0.06, color=_TEXT_FLOAT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Sequence orchestrator ─────────────────────────────────────────────────────

def render_dream_sequence(
    game_id:          str,
    calibration_prompts: dict[str, list[str]],  # {phase: [p1, p2, p3]}
    assignment_lines: dict[str, str],            # {stat: ko_line}
    vitriol_profile:  dict[str, int],            # {stat: value}
    opening_lines:    list[str],                 # GAME_OPENING_LINES[game_id]
    closing_lines:    list[str],                 # GAME_CLOSING_LINES[game_id]
    *,
    size:             int = 512,
) -> list[bytes]:
    """
    Render the complete dream sequence as an ordered list of PNG frames.

    Returns frames in playback order:
      opening[0], opening[1], opening[2]
      sakura prompts × 3
      rose prompts × 3
      lotus prompts × 3
      vitriol assignment × 7
      closing[0], closing[1], closing[2]

    Frames where the renderer returns None (PIL unavailable) are excluded.

    Parameters
    ----------
    game_id:
        Active game slug.
    calibration_prompts:
        Dict keyed by phase name (``"sakura"``, ``"rose"``, ``"lotus"``),
        each containing the 3 prompt strings for that phase.
    assignment_lines:
        Dict keyed by stat name, containing Ko's recognition line for that stat.
    vitriol_profile:
        The complete Ko-assigned VITRIOL profile as a ``{stat: value}`` dict.
    opening_lines:
        The 3 opening lines (before calibration).
    closing_lines:
        The 3 closing lines (after assignment).
    size:
        Pixel size of each frame.
    """
    frames: list[bytes] = []

    def _add(b: Optional[bytes]) -> None:
        if b is not None:
            frames.append(b)

    # Arrival
    for i, line in enumerate(opening_lines[:3]):
        _add(render_arrival_screen(line, stage=min(i, 2), size=size))

    # Calibration phases
    for phase in ("sakura", "rose", "lotus"):
        for prompt in calibration_prompts.get(phase, []):
            _add(render_phase_screen(prompt, phase, size=size))

    # VITRIOL assignment — accumulate revealed stats progressively
    revealed: dict[str, int] = {}
    for sname in VITRIOL_STATS:
        v    = vitriol_profile.get(sname, 1)
        line = assignment_lines.get(sname, f"{sname.capitalize()}: {v}.")
        revealed[sname] = v
        _add(render_vitriol_screen(sname, v, line, dict(revealed), size=size))

    # Closing
    for i, line in enumerate(closing_lines[:3]):
        stage = i
        _add(render_closing_screen(line, stage=stage, size=size))

    return frames