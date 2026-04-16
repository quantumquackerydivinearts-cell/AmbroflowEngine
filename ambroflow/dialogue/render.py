"""
Character Dialogue Renderer
============================
Renders NPC dialogue screens for Ambroflow.

Unlike Ko's dream-sequence renderer (ko/dialogue_render.py), this module
renders waking-world character interactions.  Portraits come from assets
constructed in the Atelier and loaded via GameDataBundle.get_portrait().

When a portrait PNG is provided it is displayed in a left-side panel.
When no portrait is available a type-coded placeholder is drawn instead —
a colored swatch with the character's type abbreviation.

Layout (512 × 256 default — landscape for dialogue bars):

  ┌──────────┬────────────────────────────────────┐
  │          │  CHARACTER NAME                    │
  │ portrait │  ─────────────────────────────     │
  │ or type  │  ┌──────────────────────────────┐  │
  │ swatch   │  │ Dialogue text here...        │  │
  │          │  └──────────────────────────────┘  │
  └──────────┴────────────────────────────────────┘

Type-code swatch colors map each character type to a distinct hue so the
type is immediately readable even without portrait art.

Usage
-----
    from ambroflow.dialogue.render import render_character_dialogue
    from ambroflow.dialogue.loader import load_from_file

    bundle = load_from_file("path/to/exports/7_KLGS/registry.json")
    char   = bundle.character("0006_WTCH")
    screen = render_character_dialogue(
        name          = char.name,
        char_type     = char.type,
        text          = "The Infernal perk is yours. Use it carefully.",
        portrait_bytes= bundle.get_portrait(char.id),
    )
"""

from __future__ import annotations

import io
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# ── Type swatch palette ───────────────────────────────────────────────────────
# Each character type gets a (bg, text) pair for the placeholder swatch.
# Colors chosen to be immediately distinct and reflect each type's nature.

_TYPE_COLORS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    # bg                   accent/text
    "GODS": ((30, 25, 60),   (180, 180, 255)),   # pale silver-violet
    "ANMU": ((20, 15, 40),   (140, 100, 220)),   # deep realm-purple
    "PRIM": ((15, 15, 20),   (210, 210, 210)),   # near-white on near-black
    "VDWR": ((8,   5, 12),   ( 80,  60, 100)),   # barely-there void
    "DJNN": ((25, 18, 10),   (200, 145,  55)),   # bronze-gold
    "DMON": ((35,  5,  5),   (180,  40,  40)),   # deep crimson
    "DEMI": ((30, 20,  5),   (220, 165,  60)),   # half-divine gold
    "DRYA": ((10, 25,  8),   ( 60, 140,  45)),   # forest green
    "NYMP": ((10, 30, 40),   ( 80, 170, 200)),   # pale water-blue
    "UNDI": (( 5, 15, 40),   ( 50, 120, 210)),   # deep water-blue
    "SALA": ((40, 12,  0),   (220,  90,  20)),   # flame orange
    "GNOM": ((18, 14,  6),   (120,  95,  55)),   # earth brown
    "ROYL": ((22, 12, 35),   (160, 110, 210)),   # royal purple
    "WTCH": ((12, 22, 22),   ( 80, 140, 130)),   # forest-teal
    "PRST": ((32, 28, 12),   (200, 180, 100)),   # holy gold
    "ASSN": (( 8,  8, 12),   (110, 110, 140)),   # dark steel
    "SOLD": ((12, 16, 20),   (100, 130, 160)),   # blue-grey
    "TOWN": ((22, 16, 10),   (150, 120,  90)),   # warm beige
    "HIST": ((18, 12, 28),   (160, 120, 200)),   # historical purple (Hypatia)
}

_DEFAULT_TYPE_COLORS: tuple[tuple[int,int,int], tuple[int,int,int]] = (
    (18, 14, 24), (130, 110, 150)
)

_VOID       = (7,   0,  15)
_BOX_BG     = (12,  3,  22)
_BOX_BORDER = (60,  50,  80)
_NAME_COLOR = (230, 220, 255)
_TEXT_COLOR = (200, 195, 215)


# ── Placeholder swatch ────────────────────────────────────────────────────────

def render_character_portrait_placeholder(
    char_type: str,
    width:  int = 160,
    height: int = 200,
) -> Optional[bytes]:
    """
    Render a type-coded placeholder portrait when no Atelier asset is available.

    Draws a colored swatch with the type abbreviation centred inside.
    Returns PNG bytes, or None if Pillow is unavailable.
    """
    if not _PIL_AVAILABLE:
        return None

    bg, accent = _TYPE_COLORS.get(char_type.upper(), _DEFAULT_TYPE_COLORS)

    img  = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    # Thin accent border
    draw.rectangle([0, 0, width - 1, height - 1], outline=accent, width=1)

    # Type label centred
    label = char_type.upper()[:4]
    try:
        font = ImageFont.load_default(size=22)
        bbox = draw.textbbox((0, 0), label, font=font)
        lw   = bbox[2] - bbox[0]
        lh   = bbox[3] - bbox[1]
    except TypeError:
        font = ImageFont.load_default()
        lw, lh = len(label) * 8, 12

    draw.text(
        ((width - lw) // 2, (height - lh) // 2),
        label, fill=accent, font=font,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_font(size: int) -> "ImageFont.ImageFont | ImageFont.FreeTypeFont":
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap_text(text: str, chars_per_line: int) -> list[str]:
    words   = text.split()
    lines:  list[str] = []
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


# ── Main renderer ─────────────────────────────────────────────────────────────

def render_character_dialogue(
    name:           str,
    char_type:      str,
    text:           str,
    *,
    portrait_bytes: Optional[bytes] = None,
    choices:        Optional[list[str]] = None,
    width:  int = 512,
    height: int = 256,
) -> Optional[bytes]:
    """
    Render a character dialogue screen.

    Parameters
    ----------
    name:
        Speaker's display name.
    char_type:
        Character type code (e.g. "WTCH", "ROYL", "DJNN").  Used for accent
        color and as portrait placeholder label if no portrait is provided.
    text:
        Dialogue text the character is speaking.
    portrait_bytes:
        PNG/JPEG portrait from GameDataBundle.get_portrait().
        If None, a type-coded color swatch is drawn instead.
    choices:
        Optional list of player response choices to display below the text.
        If provided, each is drawn as a numbered option.
    width, height:
        Screen dimensions.  Default 512×256 (landscape bar).

    Returns
    -------
    PNG bytes, or None if Pillow is unavailable.
    """
    if not _PIL_AVAILABLE:
        return None

    _, accent = _TYPE_COLORS.get(char_type.upper(), _DEFAULT_TYPE_COLORS)

    # ── Canvas ────────────────────────────────────────────────────────────────
    screen = Image.new("RGB", (width, height), _VOID)
    draw   = ImageDraw.Draw(screen)

    # ── Portrait panel (left 30 %) ────────────────────────────────────────────
    portrait_w = int(width * 0.30)
    portrait_h = height

    if portrait_bytes:
        try:
            port_img = Image.open(io.BytesIO(portrait_bytes)).convert("RGB")
            port_img = port_img.resize((portrait_w, portrait_h), Image.Resampling.LANCZOS)
            screen.paste(port_img, (0, 0))
        except Exception:
            portrait_bytes = None  # fall through to placeholder

    if not portrait_bytes:
        bg, _ = _TYPE_COLORS.get(char_type.upper(), _DEFAULT_TYPE_COLORS)
        draw.rectangle([0, 0, portrait_w - 1, portrait_h - 1], fill=bg, outline=accent, width=1)
        label = char_type.upper()[:4]
        try:
            fp    = _load_font(20)
            bbox  = draw.textbbox((0, 0), label, font=fp)
            lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            fp = _load_font(14)
            lw, lh = len(label) * 8, 12
        draw.text(
            ((portrait_w - lw) // 2, (portrait_h - lh) // 2),
            label, fill=accent, font=fp,
        )

    # Vertical divider
    draw.line([(portrait_w, 0), (portrait_w, height)], fill=accent, width=1)

    # ── Text region (right 70 %) ──────────────────────────────────────────────
    text_x0  = portrait_w + int(width * 0.022)
    text_x1  = width - int(width * 0.022)
    pad_top  = int(height * 0.10)
    pad_bot  = int(height * 0.08)

    # Speaker name
    font_name = _load_font(14)
    try:
        bbox  = draw.textbbox((0, 0), name, font=font_name)
        name_h = bbox[3] - bbox[1]
    except Exception:
        name_h = 14
    draw.text((text_x0, pad_top), name, fill=_NAME_COLOR, font=font_name)
    line_y = pad_top + name_h + 3
    draw.line([(text_x0, line_y), (text_x1, line_y)], fill=accent, width=1)

    # Dialogue text
    font_text = _load_font(13)
    try:
        bbox   = draw.textbbox((0, 0), "M", font=font_text)
        ch_w   = max(1, bbox[2] - bbox[0])
        ch_h   = max(1, bbox[3] - bbox[1]) + 3
    except Exception:
        ch_w, ch_h = 7, 16

    text_region_w = text_x1 - text_x0
    chars_per_line = max(10, int(text_region_w) // int(ch_w))

    ty = line_y + int(height * 0.06)
    for line in _wrap_text(text, chars_per_line):
        if ty + ch_h > height - pad_bot - (len(choices or []) * (ch_h + 2)):
            break
        draw.text((text_x0, ty), line, fill=_TEXT_COLOR, font=font_text)
        ty += ch_h

    # ── Choice options ────────────────────────────────────────────────────────
    if choices:
        cy = height - pad_bot - len(choices) * (ch_h + 2)
        draw.line([(text_x0, cy - 4), (text_x1, cy - 4)], fill=accent, width=1)
        for i, choice in enumerate(choices, start=1):
            label_line = f"{i}. {choice}"
            draw.text((text_x0, cy), label_line, fill=accent, font=font_text)
            cy += ch_h + 2

    buf = io.BytesIO()
    screen.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
