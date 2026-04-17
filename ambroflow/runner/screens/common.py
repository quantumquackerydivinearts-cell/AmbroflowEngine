"""
Common PIL drawing utilities shared across runner screens.
"""

from __future__ import annotations

import io
import math
import struct
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False

from . import palette as P


def _load_font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def text_size(draw: "ImageDraw.ImageDraw", text: str, font) -> tuple[int, int]:
    try:
        b = draw.textbbox((0, 0), text, font=font)
        return b[2] - b[0], b[3] - b[1]
    except AttributeError:
        return len(text) * 6, 10


def to_png(img: "Image.Image") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def png_dims(data: bytes) -> tuple[int, int]:
    w = struct.unpack(">I", data[16:20])[0]
    h = struct.unpack(">I", data[20:24])[0]
    return w, h


# ── Star field ────────────────────────────────────────────────────────────────

def draw_starfield(
    img: "Image.Image",
    seed: int = 0x7E3A,
    density: float = 0.0012,
) -> None:
    """Scatter dim stars across the image. Deterministic for given seed."""
    W, H = img.size
    draw = ImageDraw.Draw(img)
    n = int(W * H * density)
    lcg = seed
    for _ in range(n):
        lcg = (lcg * 1664525 + 1013904223) & 0xFFFFFFFF
        x   = lcg % W
        lcg = (lcg * 1664525 + 1013904223) & 0xFFFFFFFF
        y   = lcg % H
        lcg = (lcg * 1664525 + 1013904223) & 0xFFFFFFFF
        v   = lcg % 3
        col = (P.STAR_BRIGHT, P.STAR_MID, P.STAR_DIM)[v]
        draw.point((x, y), fill=col)


# ── Ko spiral motif ───────────────────────────────────────────────────────────

def draw_ko_spiral(
    draw: "ImageDraw.ImageDraw",
    cx: int,
    cy: int,
    radius: int,
    col: tuple = P.KO_SPIRAL_DIM,
    turns: float = 2.5,
    steps: int = 120,
) -> None:
    """Draw a small Archimedean spiral (Ko's motif) at (cx, cy)."""
    pts = []
    for i in range(steps):
        t   = (i / steps) * turns * 2 * math.pi
        r   = radius * (i / steps)
        pts.append((int(cx + r * math.cos(t)), int(cy + r * math.sin(t))))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=col, width=1)


# ── Rounded rectangle ─────────────────────────────────────────────────────────

def draw_rounded_rect(
    draw: "ImageDraw.ImageDraw",
    xy: tuple[int, int, int, int],
    radius: int,
    fill: Optional[tuple] = None,
    outline: Optional[tuple] = None,
    width: int = 1,
) -> None:
    x0, y0, x1, y1 = xy
    r = min(radius, (x1 - x0) // 2, (y1 - y0) // 2)
    if fill:
        draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
        draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
        draw.ellipse([x0, y0, x0 + 2*r, y0 + 2*r], fill=fill)
        draw.ellipse([x1 - 2*r, y0, x1, y0 + 2*r], fill=fill)
        draw.ellipse([x0, y1 - 2*r, x0 + 2*r, y1], fill=fill)
        draw.ellipse([x1 - 2*r, y1 - 2*r, x1, y1], fill=fill)
    if outline:
        draw.arc([x0, y0, x0 + 2*r, y0 + 2*r], 180, 270, fill=outline, width=width)
        draw.arc([x1 - 2*r, y0, x1, y0 + 2*r], 270, 360, fill=outline, width=width)
        draw.arc([x0, y1 - 2*r, x0 + 2*r, y1], 90, 180,  fill=outline, width=width)
        draw.arc([x1 - 2*r, y1 - 2*r, x1, y1], 0, 90,   fill=outline, width=width)
        draw.line([x0 + r, y0, x1 - r, y0], fill=outline, width=width)
        draw.line([x0 + r, y1, x1 - r, y1], fill=outline, width=width)
        draw.line([x0, y0 + r, x0, y1 - r], fill=outline, width=width)
        draw.line([x1, y0 + r, x1, y1 - r], fill=outline, width=width)