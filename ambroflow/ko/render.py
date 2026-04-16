"""
Breath of Ko — Julia Set Renderer
====================================
Renders the BreathOfKo as a Julia set image.

    Azoth² + Gaoh = f(x)

Each pixel is a starting point z₀ on the complex plane.
c = Gaoh (the player's constant, derived from coil position).
The image is centered on the player's Azoth position.

Why Julia set, not Mandelbrot:
  The Mandelbrot set maps varying c with z₀=0.
  This formula gives fixed c = Gaoh and asks: which starting points z₀ integrate?
  That is the Julia set for c = Gaoh.

  The player's Azoth is their position IN the fractal — the starting point
  from which the system has been iterating their state. The image shows the
  structure of their constant (Gaoh) and where they stand within it (Azoth).

Coloring conveys epistemological state:

  Interior  (bounded — integrated, coherent):
    Deep void. Density, not emptiness. The work has cohered.

  Boundary  (edge — living philosophical inquiry):
    Gold → rose → white. The most intricate, most beautiful region.
    Players doing the most philosophically alive work produce images here.

  Exterior  (unbounded — accumulation without comprehension):
    Dark with faint violet haze. Escape speed sets the depth.
    Fast escape = far from integration. Slow escape = near the boundary.

Gaoh ≈ 0.122 (coil midpoint) places us near the Mandelbrot boundary's
main cardioid — the Julia set for this c is connected and complex.
As the coil advances, Gaoh's imaginary component shifts, rotating the
Julia set slightly. Each game played rotates the player's constant.

Image format: PNG, returned as bytes.
Requires Pillow (PIL). If not installed, render() returns None.

Usage:
    from ambroflow.ko.render import render
    png_bytes = render(breath, size=512)
"""

from __future__ import annotations

import math
import struct
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .breath import BreathOfKo

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# ── Color mapping ─────────────────────────────────────────────────────────────
# Sinusoidal banding over smooth iteration count.
# Three sine waves at different phases (R / G / B) produce color bands
# that cycle through the exterior as iteration depth increases.
# This makes the full exterior visible rather than concentrating all color
# at the boundary edge.
#
# Alchemical palette theme: gold and deep violet, with rose at the peaks.
# The three channels are offset by ~2.1 rad (~120°) apart, producing
# complementary color cycles.
#
# Multiplied by a slow envelope that brightens near the boundary
# (high smooth_i values) to still reward the edge with the most light.

_INTERIOR_COLOR = (7, 0, 15)   # Deep void indigo — density, not emptiness


def _banded_color(smooth_i: float) -> tuple[int, int, int]:
    """
    Sinusoidal color banding over exterior iteration count.
    Produces visible concentric rings of gold/violet/rose throughout the exterior.

    Two superimposed frequencies:
      f1 (broad bands, ~25 iter period) — large visible rings
      f2 (fine texture, ~8 iter period) — detail within rings

    Phases offset by 120° per channel to produce complementary color cycling.
    Gold-dominant at peaks; deep violet at troughs.
    """
    f1, f2 = 0.25, 0.80

    # Broad bands — primary color structure
    r = 115 + 100 * math.sin(f1 * smooth_i + 0.00)
    g =  55 +  45 * math.sin(f1 * smooth_i + 2.09)   # +120°
    b =  90 +  80 * math.sin(f1 * smooth_i + 4.19)   # +240°

    # Fine texture overlay — adds detail without overwhelming the broad bands
    r += 20 * math.sin(f2 * smooth_i + 0.50)
    g += 10 * math.sin(f2 * smooth_i + 2.60)
    b += 15 * math.sin(f2 * smooth_i + 4.70)

    return (
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))),
    )


# ── Smooth coloring ───────────────────────────────────────────────────────────
# Standard smooth iteration count to eliminate banding:
#   smooth_i = i - log2(log2(|z|))
# Gives continuous values instead of hard integer steps.

_MAX_ITER = 512   # Higher resolution for rendering than the grid function


def _mandelbrot_smooth(z0: complex, c: complex) -> float:
    """
    Returns a smooth iteration count ∈ [0, _MAX_ITER].
    Returns float(_MAX_ITER) for bounded points (interior).
    """
    z = z0
    for i in range(_MAX_ITER):
        if abs(z) > 2.0:
            # Smooth escape
            log_zn = math.log(abs(z))
            nu = math.log(log_zn / math.log(2)) / math.log(2)
            return float(i) + 1.0 - nu
        z = z * z + c
    return float(_MAX_ITER)


def _pixel_color(smooth_i: float) -> tuple[int, int, int]:
    if smooth_i >= _MAX_ITER:
        return _INTERIOR_COLOR
    return _banded_color(smooth_i)


# ── Main renderer ─────────────────────────────────────────────────────────────

def render(breath: "BreathOfKo", size: int = 512) -> Optional[bytes]:
    """
    Render the BreathOfKo as a Julia set PNG image.

    Each pixel is a z₀ value on the complex plane.
    c = Gaoh (player's constant from coil position).
    The image is centered on the player's Azoth position.

    Parameters
    ----------
    breath:
        The player's BreathOfKo state.
    size:
        Width and height in pixels.  Default 512.

    Returns
    -------
    PNG bytes, or None if Pillow is not installed.
    """
    if not _PIL_AVAILABLE:
        return None

    azoth = breath.azoth()
    c     = breath.gaoh_constant()

    # Fixed view: always show the full Julia set for c = Gaoh.
    # Julia sets live within |z| < 2; a half-width of 1.8 shows the full
    # structure with a small margin.  The set is always centered at the origin.
    half  = 1.8
    x_min, x_max = -half, half
    y_min, y_max = -half, half

    img = Image.new("RGB", (size, size))
    pix = img.load()
    assert pix is not None

    for row in range(size):
        im = y_min + (y_max - y_min) * row / size
        for col in range(size):
            re    = x_min + (x_max - x_min) * col / size
            z0    = complex(re, im)
            smooth = _mandelbrot_smooth(z0, c)
            pix[col, row] = _pixel_color(smooth)

    # Mark Azoth position — the player's standing point in the fractal.
    # Clamp to image bounds, draw a small crosshair in white.
    ax = int((azoth.real - x_min) / (x_max - x_min) * size)
    ay = int((azoth.imag - y_min) / (y_max - y_min) * size)
    ax = max(2, min(size - 3, ax))
    ay = max(2, min(size - 3, ay))
    crosshair = (255, 255, 255)
    for d in range(-4, 5):
        if 0 <= ax + d < size:
            pix[ax + d, ay] = crosshair
        if 0 <= ay + d < size:
            pix[ax, ay + d] = crosshair

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_to_file(breath: "BreathOfKo", path: str, size: int = 512) -> bool:
    """
    Render and write a PNG file.
    Returns True on success, False if Pillow is not available.
    """
    data = render(breath, size=size)
    if data is None:
        return False
    with open(path, "wb") as f:
        f.write(data)
    return True


def render_grid_ascii(breath: "BreathOfKo", size: int = 40) -> str:
    """
    ASCII fallback — useful for debugging and terminal inspection.
    Uses a ramp of characters from void to bright boundary.

    Requires no dependencies.
    """
    azoth = breath.azoth()
    c     = breath.gaoh_constant()

    half = 1.8
    cx, cy = 0.0, 0.0

    # Terminal chars: void interior → exterior banding → boundary bright
    _RAMP = " ░▒▓█▓▒░·:;!|o0O@#*"

    lines: list[str] = []
    for row in range(size):
        line: list[str] = []
        im = (cy - half) + (2 * half) * row / size
        for col in range(size * 2):   # 2:1 aspect for terminal
            re = (cx - half) + (2 * half) * col / (size * 2)
            smooth = _mandelbrot_smooth(complex(re, im), c)
            if smooth >= _MAX_ITER:
                ch = " "   # interior — void
            else:
                t  = smooth / float(_MAX_ITER)
                ch = _RAMP[min(len(_RAMP) - 1, int(t * len(_RAMP)))]
            line.append(ch)
        lines.append("".join(line))
    return "\n".join(lines)
