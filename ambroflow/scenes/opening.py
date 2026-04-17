"""
Quest 0001_KLST — "Fate Knocks" Opening Sequence
=================================================
The game's first waking-world narrative beat.

Sequence order
--------------
  1. Bedroom (dawn) — player wakes.  Bed is rumpled.  Cold gray light.
  2. Foyer (dawn)   — player stands at the door hearing the knock.
  3. Courier screen — Royal Courier at the door. Their line.
  4. Hypatia's letter — the parchment document rendered in full.

Immediately following this sequence, character creation begins
(gender was already set through Ko in the dream).

The Courier
-----------
  An unnamed Royal Courier from the Castle Azoth household.
  Type: SOLD (functionary, not a combatant here).
  No name — they are a function: the knock, the envelope, the departure.
  Their one line: formal, impersonal, slightly impatient.

Hypatia's Letter
-----------------
  Laconic. Academic. Slightly imperious.
  Signed "— H." — she does not feel the need to clarify.
  The letter does not explain what the work IS.  That is intentional.
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

from ambroflow.scenes.location import render_bedroom, render_foyer
from ambroflow.dialogue.render import render_character_dialogue


# ── Canonical text ────────────────────────────────────────────────────────────

COURIER_LINE = (
    "Royal Courier, Castle Azoth household. "
    "I have a sealed letter for the occupant of this address. "
    "Please confirm receipt."
)

HYPATIA_LETTER_LINES: list[str] = [
    "To the occupant of Wiltoll Lane, Azonithia:",
    "",
    "By authority of the Royal Lottery of Grant and Apprenticeship,",
    "this notice confirms your selection.",
    "",
    "You are summoned to begin a term of scholarly apprenticeship",
    "under the researcher and practitioner Hypatia of Azonithia,",
    "effective at the next new moon.",
    "",
    "Your obligations, your compensation, and the full scope",
    "of the work will be discussed at our first meeting.",
    "I suggest arriving prepared to be uncertain",
    "about most things you believed you knew.",
    "",
    "                                    — H.",
]

# The "Fate Knocks" knock — represented as a stage direction
DOOR_KNOCK_TEXT = (
    "A sharp rapping at the door. Three strikes, evenly spaced. "
    "The kind that does not ask if you are awake."
)


# ── Parchment letter renderer ─────────────────────────────────────────────────

def render_hypatia_letter(
    *,
    width:  int = 512,
    height: int = 512,
) -> Optional[bytes]:
    """
    Render Hypatia's letter as a parchment document.

    The letter is displayed on an aged parchment background with
    a thin border and wax-seal suggestion in the lower-right corner.
    Text is set in the letter's canonical wording.
    """
    if not _PIL_AVAILABLE:
        return None

    W, H = width, height

    # Parchment base — warm cream with slight texture variation
    _PARCHMENT_BG  = (185, 168, 122)
    _PARCHMENT_DARK= (158, 140, 96)
    _INK           = ( 28,  20,  12)
    _BORDER        = ( 95,  72,  35)
    _SEAL_RED      = (135,  28,  22)

    img  = Image.new("RGB", (W, H), _PARCHMENT_BG)
    draw = ImageDraw.Draw(img)
    pix  = img.load()

    # Parchment texture — very subtle noise
    for py in range(H):
        for px in range(W):
            n = ((px * 1664525) ^ (py * 1013904223) ^ 0xFADE) & 0xFFFF
            v = n / 0xFFFF * 0.06 - 0.03
            cur = pix[px, py]
            pix[px, py] = (
                max(0, min(255, int(cur[0] * (1+v)))),
                max(0, min(255, int(cur[1] * (1+v)))),
                max(0, min(255, int(cur[2] * (1+v)))),
            )

    draw = ImageDraw.Draw(img)

    # Outer border
    MARGIN = int(W * 0.06)
    draw.rectangle([MARGIN, MARGIN, W-MARGIN, H-MARGIN],
                   outline=_BORDER, width=2)
    draw.rectangle([MARGIN+4, MARGIN+4, W-MARGIN-4, H-MARGIN-4],
                   outline=(_BORDER[0]-20, _BORDER[1]-15, _BORDER[2]-10), width=1)

    # Decorative corner marks
    CL = int(W * 0.04)
    for cx, cy, sx, sy in [
        (MARGIN, MARGIN, 1, 1), (W-MARGIN, MARGIN, -1, 1),
        (MARGIN, H-MARGIN, 1, -1), (W-MARGIN, H-MARGIN, -1, -1),
    ]:
        draw.line([(cx, cy), (cx+sx*CL, cy)], fill=_BORDER, width=2)
        draw.line([(cx, cy), (cx, cy+sy*CL)], fill=_BORDER, width=2)

    # Letter text
    font_body    = _load_font_letter(13)
    font_header  = _load_font_letter(11)
    font_sign    = _load_font_letter(15)

    TEXT_X = MARGIN + int(W * 0.06)
    TEXT_Y = MARGIN + int(H * 0.08)
    LINE_H = int(H * 0.043)

    for line in HYPATIA_LETTER_LINES:
        if not line.strip():
            TEXT_Y += LINE_H // 2
            continue
        if line.startswith("                "):
            # Signature — right-aligned, larger font
            draw.text((TEXT_X + int(W * 0.25), TEXT_Y),
                      line.strip(), fill=_INK, font=font_sign)
        else:
            draw.text((TEXT_X, TEXT_Y), line, fill=_INK, font=font_body)
        TEXT_Y += LINE_H

    # Wax seal — bottom right, simple circle with "H" inside
    seal_cx = W - MARGIN - int(W * 0.08)
    seal_cy = H - MARGIN - int(H * 0.06)
    seal_r  = int(W * 0.046)
    draw.ellipse([seal_cx-seal_r, seal_cy-seal_r, seal_cx+seal_r, seal_cy+seal_r],
                 fill=_SEAL_RED, outline=(_SEAL_RED[0]-25, 10, 8), width=1)
    font_seal = _load_font_letter(16)
    tw, th = _text_sz(draw, "H", font_seal)
    draw.text((seal_cx - tw//2, seal_cy - th//2), "H",
              fill=(220, 180, 150), font=font_seal)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _load_font_letter(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _text_sz(draw, text, font):
    try:
        b = draw.textbbox((0, 0), text, font=font)
        return b[2]-b[0], b[3]-b[1]
    except AttributeError:
        return len(text)*6, 9


# ── Stage direction screen ────────────────────────────────────────────────────

def render_stage_direction(
    text: str,
    *,
    width:  int = 512,
    height: int = 512,
) -> Optional[bytes]:
    """
    A minimal screen for narrative stage directions — the knock, transitions.
    Dark background, centered italic-weight text, no character frame.
    """
    if not _PIL_AVAILABLE:
        return None

    W, H = width, height
    _BG   = ( 8,  5, 14)
    _TEXT = (130, 115, 100)

    img  = Image.new("RGB", (W, H), _BG)
    draw = ImageDraw.Draw(img)

    font = _load_font_letter(14)

    try:
        bbox = draw.textbbox((0, 0), "M", font=font)
        ch_w = max(1, bbox[2]-bbox[0])
        ch_h = max(1, bbox[3]-bbox[1]) + 4
    except AttributeError:
        ch_w, ch_h = 7, 18

    words   = text.split()
    chars   = max(12, int(W*0.72) // ch_w)
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if cur and len(cand) > chars:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)

    total_h = len(lines) * ch_h
    ty = (H - total_h) // 2

    for line in lines:
        try:
            b  = draw.textbbox((0, 0), line, font=font)
            lw = b[2]-b[0]
        except AttributeError:
            lw = len(line) * ch_w
        draw.text(((W-lw)//2, ty), line, fill=_TEXT, font=font)
        ty += ch_h

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Fate Knocks sequence ──────────────────────────────────────────────────────

def render_fate_knocks_sequence(
    *,
    scene_width:  int = 512,
    scene_height: int = 384,
    screen_size:  int = 512,
) -> list[bytes]:
    """
    Render the full "Fate Knocks" (0001_KLST) opening sequence.

    Returns frames in order:
      [0] Bedroom — dawn, rumpled bed (player wakes)
      [1] Stage direction — the knock
      [2] Foyer — dawn, door ajar (player at the door)
      [3] Courier dialogue screen
      [4] Hypatia's letter (parchment, full screen)

    Character creation screens follow — call
    ``ambroflow.chargen.screens.render_chargen_sequence()`` next.

    Parameters
    ----------
    scene_width, scene_height:
        Dimensions for location scenes (bedroom, foyer).  Default 512×384.
    screen_size:
        Dimensions for dialogue/document screens.  Default 512.
    """
    frames: list[bytes] = []

    def _add(b: Optional[bytes]) -> None:
        if b is not None:
            frames.append(b)

    # Bedroom — dawn, rumpled
    _add(render_bedroom(time_of_day="dawn", rumpled=True,
                        width=scene_width, height=scene_height))

    # Stage direction — the knock
    _add(render_stage_direction(DOOR_KNOCK_TEXT,
                                width=screen_size, height=screen_size))

    # Foyer — dawn, door ajar (player has gone to the door)
    _add(render_foyer(time_of_day="dawn",
                      width=scene_width, height=scene_height))

    # Courier dialogue
    _add(render_character_dialogue(
        name="Royal Courier",
        char_type="SOLD",
        text=COURIER_LINE,
        width=screen_size,
        height=screen_size // 2,
    ))

    # Hypatia's letter
    _add(render_hypatia_letter(width=screen_size, height=screen_size))

    return frames