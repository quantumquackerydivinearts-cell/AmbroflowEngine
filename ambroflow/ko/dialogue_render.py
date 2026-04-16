"""
Ko Dialogue Renderer
====================
Renders Ko's dream-sequence dialogue as PIL images.

Two primary outputs:

  render_ko_portrait(size)
      The character popup — Ko's portrait alone.
      A Black Ouroboros with 7 logarithmic spiral arms and 10 radial arms,
      rendered procedurally pixel-by-pixel. Gold/white on void indigo.

  render_dialogue_screen(text, phase, size)
      Full dialogue screen: portrait in the upper portion, phase ribbon
      below it, then a dialogue text box at the bottom.

Ko — God of Dreams, the Unconscious, the Moon.
Appearance: Black Ouroboros, 10 arms, 7 spirals.
Ko assigns VITRIOL stats from dream calibration. Fresh each time.

Layout (512 × 512 default):

  ┌──────────────────────────┐
  │                          │
  │      [Ko portrait]       │   ~55 % of height
  │                          │
  │  ── SAKURA / ROSE / LOTUS│   phase ribbon
  │                          │
  │ ┌──────────────────────┐ │
  │ │ Prompt text here...  │ │   dialogue box
  │ └──────────────────────┘ │
  └──────────────────────────┘

PIL ≥ 10.0 required (matches pyproject.toml).
Returns None gracefully when PIL is unavailable.
"""

from __future__ import annotations

import io
import math
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .breath import BreathOfKo
    from .calibration import CalibrationTongue

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# ── Palette ───────────────────────────────────────────────────────────────────

_VOID         = (7,   0,  15)    # deep void indigo — Ko's interior
_GOLD         = (200, 140, 40)   # Ko's primary presence
_GOLD_BRIGHT  = (255, 220, 100)  # peak brightness
_WHITE        = (255, 255, 255)
_BOX_BG       = (12,  3,  22)    # dialogue box fill
_BOX_BORDER   = (160, 115, 28)   # dialogue box border

# Per-phase accent colors (also used for the ribbon line and label)
_PHASE_COLOR: dict[str, tuple[int, int, int]] = {
    "sakura": (220, 160, 190),   # pale rose-pink
    "rose":   (200,  90, 120),   # deep rose
    "lotus":  ( 60, 110, 200),   # deep water-blue
}
_PHASE_LABEL: dict[str, str] = {
    "sakura": "S A K U R A",
    "rose":   "R O S E",
    "lotus":  "L O T U S",
}


# ── Ko portrait — pixel-level generation ──────────────────────────────────────

def _ko_pixel(dx: float, dy: float, R: float) -> float:
    """
    Ko presence value [0, 1] for a pixel offset (dx, dy) from the portrait center.
    R = Ouroboros ring radius in pixels.

    Combines:
      • Ouroboros ring — Gaussian bell at r ≈ R
      • 7 logarithmic spiral arms coiling clockwise inward from the ring
      • 10 radial arms extending outward from the ring
      • Faint inner void glow
    """
    r     = math.sqrt(dx * dx + dy * dy) + 1e-10
    theta = math.atan2(dy, dx)

    # ── Ring ─────────────────────────────────────────────────────────────────
    sigma_ring = R * 0.065
    ring = math.exp(-((r - R) ** 2) / (2.0 * sigma_ring * sigma_ring))

    # ── 7 logarithmic spiral arms (clockwise inward, b < 0) ──────────────────
    N_SPIRALS  = 7
    spiral_val = 0.0
    b          = -0.25
    sigma_sp   = R * 0.048
    for k in range(N_SPIRALS):
        base = k * (2.0 * math.pi / N_SPIRALS)
        # Sweep winding numbers to handle theta discontinuity
        for n in (-1, 0, 1, 2):
            t = theta - base + n * 2.0 * math.pi
            expected_r = R * math.exp(b * t)
            if 0.0 < expected_r < R * 2.1:
                d = r - expected_r
                spiral_val = max(
                    spiral_val,
                    math.exp(-(d * d) / (2.0 * sigma_sp * sigma_sp)),
                )

    # ── 10 radial arms (outward from ring) ───────────────────────────────────
    N_ARMS  = 10
    arm_val = 0.0
    sigma_a = 0.052   # radians
    # Fade arms: invisible inside half-ring, full presence at ring edge
    arm_fade = max(0.0, min(1.0, (r - R * 0.50) / (R * 0.55)))
    if arm_fade > 0.0:
        for k in range(N_ARMS):
            arm_angle = k * (2.0 * math.pi / N_ARMS)
            diff = math.atan2(
                math.sin(theta - arm_angle),
                math.cos(theta - arm_angle),
            )
            arm_val = max(
                arm_val,
                math.exp(-(diff * diff) / (2.0 * sigma_a * sigma_a)) * arm_fade,
            )

    # ── Inner void glow ───────────────────────────────────────────────────────
    inner = math.exp(-(r * r) / (2.0 * (R * 0.28) ** 2)) * 0.22

    return min(1.0, ring * 0.85 + spiral_val * 0.70 + arm_val * 0.45 + inner)


def _portrait_image(size: int) -> "Image.Image":
    R  = size * 0.36
    cx = cy = size * 0.5

    img = Image.new("RGB", (size, size), _VOID)
    pix = img.load()
    assert pix is not None

    for row in range(size):
        dy = row - cy
        for col in range(size):
            v = _ko_pixel(col - cx, dy, R)

            if v < 0.006:
                continue   # leave as void background

            # Interpolate: void → gold → bright gold/white
            if v <= 0.5:
                t = v * 2.0
                r = int(_VOID[0] + (_GOLD[0] - _VOID[0]) * t)
                g = int(_VOID[1] + (_GOLD[1] - _VOID[1]) * t)
                b = int(_VOID[2] + (_GOLD[2] - _VOID[2]) * t)
            else:
                t = (v - 0.5) * 2.0
                r = int(_GOLD[0] + (_GOLD_BRIGHT[0] - _GOLD[0]) * t)
                g = int(_GOLD[1] + (_GOLD_BRIGHT[1] - _GOLD[1]) * t)
                b = int(_GOLD[2] + (_GOLD_BRIGHT[2] - _GOLD[2]) * t)

            pix[col, row] = (
                max(0, min(255, r)),
                max(0, min(255, g)),
                max(0, min(255, b)),
            )

    return img


def render_ko_portrait(size: int = 128) -> Optional[bytes]:
    """
    Render Ko's character portrait as a PNG image.

    Ko appears as a Black Ouroboros ring with 7 logarithmic spiral arms
    and 10 radial arms, gold on a void-indigo background.

    Parameters
    ----------
    size:
        Width and height in pixels.  Default 128.

    Returns
    -------
    PNG bytes, or None if Pillow is unavailable.
    """
    if not _PIL_AVAILABLE:
        return None
    img = _portrait_image(size)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Text utilities ─────────────────────────────────────────────────────────────

def _wrap_text(text: str, chars_per_line: int) -> list[str]:
    """Word-wrap text to fit within chars_per_line."""
    words   = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if current and len(candidate) > chars_per_line:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _load_font(size: int) -> "ImageFont.ImageFont | ImageFont.FreeTypeFont":
    """Load PIL's default font at the requested size (Pillow ≥ 10)."""
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ── Dialogue screen ───────────────────────────────────────────────────────────

def render_dialogue_screen(
    text:   str,
    phase:  str,
    *,
    size:   int = 512,
) -> Optional[bytes]:
    """
    Render a complete Ko dialogue screen as a PNG image.

    Layout:
      • Ko's portrait — top ~55 % of screen
      • Phase ribbon  — single line label (SAKURA / ROSE / LOTUS)
      • Dialogue box  — bottom portion with wrapped prompt text

    Parameters
    ----------
    text:
        The prompt text Ko is speaking.
    phase:
        One of ``"sakura"``, ``"rose"``, or ``"lotus"``.
        Controls ribbon color and accent.
    size:
        Width and height in pixels.  Default 512.

    Returns
    -------
    PNG bytes, or None if Pillow is unavailable.
    """
    if not _PIL_AVAILABLE:
        return None

    phase = phase.lower()

    # ── Portrait ──────────────────────────────────────────────────────────────
    portrait_size = int(size * 0.54)
    portrait_y    = int(size * 0.024)
    portrait_img  = _portrait_image(portrait_size)

    screen = Image.new("RGB", (size, size), _VOID)
    screen.paste(portrait_img, ((size - portrait_size) // 2, portrait_y))

    draw = ImageDraw.Draw(screen)

    # ── Phase ribbon ──────────────────────────────────────────────────────────
    accent      = _PHASE_COLOR.get(phase, _GOLD)
    label_text  = _PHASE_LABEL.get(phase, phase.upper())
    ribbon_y    = portrait_y + portrait_size + int(size * 0.008)

    font_phase = _load_font(11)
    try:
        bbox   = draw.textbbox((0, 0), label_text, font=font_phase)
        lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        lw, lh = len(label_text) * 6, 9

    label_x = (size - lw) // 2
    label_y = ribbon_y + 2

    # Flanking lines
    line_y = label_y + lh // 2
    margin = int(size * 0.08)
    draw.line([(margin, line_y), (label_x - 8, line_y)],         fill=accent, width=1)
    draw.line([(label_x + lw + 8, line_y), (size - margin, line_y)], fill=accent, width=1)
    draw.text((label_x, label_y), label_text, fill=accent, font=font_phase)

    # ── Dialogue box ──────────────────────────────────────────────────────────
    box_margin = int(size * 0.042)
    box_top    = ribbon_y + lh + int(size * 0.038)
    box_bottom = size - box_margin
    box_left   = box_margin
    box_right  = size - box_margin

    draw.rectangle(
        [box_left, box_top, box_right, box_bottom],
        fill=_BOX_BG,
        outline=_BOX_BORDER,
        width=1,
    )

    # Accent corner marks
    corner_len = int(size * 0.022)
    for cx, cy, sx, sy in [
        (box_left,  box_top,    1,  1),
        (box_right, box_top,   -1,  1),
        (box_left,  box_bottom,  1, -1),
        (box_right, box_bottom, -1, -1),
    ]:
        draw.line([(cx, cy), (cx + sx * corner_len, cy)], fill=accent, width=1)
        draw.line([(cx, cy), (cx, cy + sy * corner_len)], fill=accent, width=1)

    # Prompt text
    font_text = _load_font(15)
    pad_x     = int(size * 0.032)
    pad_y     = int(size * 0.022)
    text_x    = box_left  + pad_x
    text_y    = box_top   + pad_y
    max_width = box_right - box_left - pad_x * 2

    try:
        bbox = draw.textbbox((0, 0), "M", font=font_text)
        ch_w = max(1, bbox[2] - bbox[0])
        ch_h = max(1, bbox[3] - bbox[1]) + 4
    except AttributeError:
        ch_w, ch_h = 7, 18

    chars_per_line = max(10, int(max_width) // int(ch_w))
    lines = _wrap_text(text, chars_per_line)

    for line in lines:
        if text_y + ch_h > box_bottom - pad_y:
            break
        draw.text((text_x, text_y), line, fill=_WHITE, font=font_text)
        text_y += ch_h

    buf = io.BytesIO()
    screen.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Convenience: render all three phases of a session ────────────────────────

def render_calibration_screens(
    prompts: dict[str, list[str]],
    *,
    size: int = 512,
) -> dict[str, list[Optional[bytes]]]:
    """
    Render all dialogue screens for a calibration sequence.

    Parameters
    ----------
    prompts:
        ``{"sakura": [...], "rose": [...], "lotus": [...]}``
        matching ``DreamCalibrationSession.PROMPTS``.
    size:
        Pixel size of each screen.

    Returns
    -------
    Same structure with PNG bytes (or None) in place of text strings.
    """
    return {
        phase: [render_dialogue_screen(text, phase, size=size) for text in texts]
        for phase, texts in prompts.items()
    }
