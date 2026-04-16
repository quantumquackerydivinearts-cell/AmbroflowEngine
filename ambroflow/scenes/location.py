"""
Location Scene Renderer
=======================
Procedural background scenes for Ambroflow's waking-world locations.

Each location is rendered as a 512×384 PNG (landscape).  Scenes use PIL
draw primitives plus targeted per-pixel texture passes to avoid the
performance cost of full-image pixel loops.

Implemented locations
---------------------
wiltoll_lane_interior  — Game 7 (7_KLGS)

    The player's home shop at the far southeastern edge of Azonithia,
    Aeralune.  A one-and-a-half story stone building on a narrow lane.
    Mt. Hieronymus rises above the roofline directly to the southeast.

    Composition (viewed from the doorway looking in):

    ┌────────────────────────────────────────────────────────────────┐
    │  [back wall: coarse dark stone — irregular mortared blocks]   │  ← upper 55 %
    │  [window upper-left: light source, sky, Mt. Hieronymus]       │
    │  [two wooden shelves with ingredient jars]                    │
    │  [workbench: thick surface lower-center, tools on top]        │  ← 54–72 %
    │  [brazier: warm glow, center-right]                           │  ← 44–60 %
    ├────────────────────────────────────────────────────────────────┤  floor line
    │  [floor: large rough stone flags, dark, worn smooth center]   │  ← lower 28 %
    └────────────────────────────────────────────────────────────────┘

    Time-of-day variants:
      "late_afternoon"  — amber/orange window light, warm diffuse.
      "night"           — no window light (cold moonlit square),
                         brazier is the sole warm source.

Palette (location)
------------------
  Stone wall:    (30, 28, 38)  — dark charcoal-indigo (Aeralune stone)
  Stone lit:     (52, 44, 32)  — amber-washed section near window
  Stone mortar:  (20, 18, 26)  — mortar joints, darker
  Wood (shelf):  (58, 40, 21)  — dark oak, rough-hewn
  Wood (bench):  (44, 30, 14)  — aged workbench
  Floor stone:   (22, 20, 30)  — floor flags
  Floor seam:    (13, 12, 18)  — grout between flags
  Window (day):  (210, 140, 60)  — late-afternoon amber sky
  Window (night):(18, 28, 52)   — cold moonlit blue
  Brazier glow:  (220, 95, 20)  — coals
  Brazier outer: (80, 35, 10)   — iron stand
  Jar colors:    various (6 distinct)
"""

from __future__ import annotations

import io
import math
from typing import Optional

try:
    from PIL import Image, ImageDraw
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# ── Colour constants ──────────────────────────────────────────────────────────

_STONE_BASE   = ( 30,  28,  38)
_STONE_LIT    = ( 52,  44,  32)   # amber-washed near window
_STONE_MORTAR = ( 20,  18,  26)
_WOOD_SHELF   = ( 58,  40,  21)
_WOOD_BENCH   = ( 44,  30,  14)
_FLOOR_BASE   = ( 22,  20,  30)
_FLOOR_SEAM   = ( 13,  12,  18)

_WIN_DAY      = (210, 140,  60)   # amber sky
_WIN_DAY_TOP  = (180, 110,  40)   # slightly deeper at top of window
_WIN_NIGHT    = ( 18,  28,  52)   # cold moon-blue
_WIN_NIGHT_DIM= ( 10,  16,  34)

_MOUNTAIN     = ( 16,  14,  20)   # Mt. Hieronymus silhouette in window
_MOUNTAIN_SKY = ( 38,  24,  10)   # sky behind mountain (day)
_MOUNTAIN_NIGHT = ( 8,  12,  28)  # sky behind mountain (night)

_BRAZIER_HOT  = (220,  95,  20)   # glowing coals
_BRAZIER_WARM = (160,  60,  10)
_BRAZIER_IRON = ( 55,  35,  20)   # iron body

# Ingredient jar colors (6)
_JAR_COLORS: list[tuple[int, int, int]] = [
    (180, 100,  25),   # amber
    ( 35,  90,  40),   # forest green
    (100,  20,  20),   # deep red
    ( 50,  70, 110),   # pale blue
    ( 60,  25,  80),   # dark purple
    (140,  85,  30),   # tawny gold
]

# Mortar-and-pestle on bench
_PESTLE_COLOR = ( 80,  70,  68)   # worn stone
_TOOL_DARK    = ( 35,  30,  25)


# ── Pseudo-noise (deterministic, no seed needed) ──────────────────────────────

def _nhash(x: int, y: int) -> float:
    """Deterministic [0, 1) float from pixel coordinates."""
    n = ((x * 1664525) ^ (y * 1013904223) ^ 0xBADC0DE5) & 0xFFFF_FFFF
    return n / 0xFFFF_FFFF


# ── Stone texture ─────────────────────────────────────────────────────────────

def _draw_stone_wall(
    draw: "ImageDraw.ImageDraw",
    pix: object,
    W: int,
    H: int,
    wall_top: int,
    wall_bottom: int,
    *,
    window_rect: Optional[tuple[int, int, int, int]] = None,
    ambient_light: tuple[float, float] = (0.0, 0.0),  # (x_frac, intensity)
) -> None:
    """
    Draw a coarse mortared-stone wall.

    window_rect: (x0, y0, x1, y1) — area not to be overdrawn (skip pixels inside)
    ambient_light: (x_source_frac, intensity) — x position (0=left, 1=right) and
                   intensity of a warm light source (e.g. window amber light)
    """
    draw.rectangle([0, wall_top, W - 1, wall_bottom], fill=_STONE_BASE)

    # Stone blocks: irregular horizontal courses with vertical joints offset by row
    COURSE_H = H // 14     # row height of a stone course
    if COURSE_H < 4:
        COURSE_H = 4

    y = wall_top
    course = 0
    while y < wall_bottom:
        next_y = min(y + COURSE_H + (course % 3) - 1, wall_bottom)
        # Joint offset alternates between courses
        offset = (COURSE_H * 2) if (course % 2 == 0) else 0
        BLOCK_W_BASE = W // 7

        bx = -offset
        while bx < W:
            bw = BLOCK_W_BASE + ((_nhash(bx // 20, y // 20) * 0.5 - 0.25) * (BLOCK_W_BASE * 0.5))
            bw = max(BLOCK_W_BASE // 2, int(bw))

            # Stone colour — slight variation per block
            v  = _nhash(bx // 10 + course * 7, y // 8 + 3) * 0.12 - 0.06
            sr = max(0, min(255, int(_STONE_BASE[0] * (1.0 + v))))
            sg = max(0, min(255, int(_STONE_BASE[1] * (1.0 + v))))
            sb = max(0, min(255, int(_STONE_BASE[2] * (1.0 + v))))

            # Ambient light falloff from window
            if ambient_light[1] > 0:
                dx = abs(bx / W - ambient_light[0])
                dy = abs((y + next_y) / 2.0 / H - 0.2)
                dist = math.sqrt(dx * dx + dy * dy)
                warmth = max(0.0, (1.0 - dist * 2.5)) * ambient_light[1]
                sr = min(255, sr + int((_STONE_LIT[0] - sr) * warmth))
                sg = min(255, sg + int((_STONE_LIT[1] - sg) * warmth))
                sb = min(255, sb + int((_STONE_LIT[2] - sb) * warmth))

            # Draw block face (skip window area)
            x0 = max(0, int(bx))
            x1 = min(W - 1, int(bx + bw - 2))
            if window_rect:
                wx0, wy0, wx1, wy1 = window_rect
                # If block overlaps window row, split left/right
                if y <= wy1 and next_y >= wy0:
                    # Left of window
                    if x0 < wx0:
                        draw.rectangle(
                            [x0, y + 1, min(x1, wx0 - 1), next_y - 1],
                            fill=(sr, sg, sb),
                        )
                    # Right of window
                    if x1 > wx1:
                        draw.rectangle(
                            [max(x0, wx1 + 1), y + 1, x1, next_y - 1],
                            fill=(sr, sg, sb),
                        )
                else:
                    draw.rectangle([x0, y + 1, x1, next_y - 1], fill=(sr, sg, sb))
            else:
                draw.rectangle([x0, y + 1, x1, next_y - 1], fill=(sr, sg, sb))

            # Mortar joint (right edge of block)
            jx = int(bx + bw) - 1
            if 0 <= jx < W:
                if not (window_rect and window_rect[0] <= jx <= window_rect[2]
                        and y <= window_rect[3] and next_y >= window_rect[1]):
                    draw.line([(jx, y), (jx, next_y)], fill=_STONE_MORTAR, width=1)

            bx += bw

        # Mortar joint (bottom of course — horizontal)
        draw.line([(0, next_y), (W, next_y)], fill=_STONE_MORTAR, width=1)
        y      = next_y + 1
        course += 1


# ── Window ────────────────────────────────────────────────────────────────────

def _draw_window(
    draw: "ImageDraw.ImageDraw",
    W: int, H: int,
    rect: tuple[int, int, int, int],
    *,
    time_of_day: str = "late_afternoon",
) -> None:
    """
    Draw the window with sky, mountain silhouette, and window frame.
    rect: (x0, y0, x1, y1) — outer window bounds.
    """
    x0, y0, x1, y1 = rect
    ww = x1 - x0
    wh = y1 - y0

    # Sky gradient
    if time_of_day == "night":
        sky_top = _WIN_NIGHT_DIM
        sky_bot = _WIN_NIGHT
    else:
        sky_top = _WIN_DAY_TOP
        sky_bot = _WIN_DAY

    for iy in range(y0, y1 + 1):
        t = (iy - y0) / wh if wh > 0 else 0
        r = int(sky_top[0] + (sky_bot[0] - sky_top[0]) * t)
        g = int(sky_top[1] + (sky_bot[1] - sky_top[1]) * t)
        b = int(sky_top[2] + (sky_bot[2] - sky_top[2]) * t)
        draw.line([(x0, iy), (x1, iy)], fill=(r, g, b))

    # Mt. Hieronymus silhouette — jagged peak in lower portion of window
    # Mountain fills the lower 55 % of the window
    mountain_top = y0 + int(wh * 0.38)
    mountain_y   = y1
    peak_x       = x0 + int(ww * 0.62)     # peak slightly right of center
    peak_y       = mountain_top + int(wh * 0.05)

    # Simple angular mountain profile with slight asymmetry
    pts = [
        (x0,      mountain_y),
        (x0,      mountain_top + int(wh * 0.22)),
        (x0 + int(ww * 0.18), mountain_top + int(wh * 0.10)),
        (x0 + int(ww * 0.35), mountain_top + int(wh * 0.14)),
        (peak_x,  peak_y),
        (x0 + int(ww * 0.78), mountain_top + int(wh * 0.18)),
        (x1,      mountain_top + int(wh * 0.28)),
        (x1,      mountain_y),
    ]
    sky_behind = _MOUNTAIN_NIGHT if time_of_day == "night" else _MOUNTAIN_SKY
    draw.polygon(pts, fill=_MOUNTAIN, outline=sky_behind)

    # Window frame (wooden)
    FRAME_W = max(2, ww // 18)
    draw.rectangle([x0, y0, x1, y1], outline=_WOOD_SHELF, width=FRAME_W)
    # Central cross
    cross_x = (x0 + x1) // 2
    cross_y = (y0 + y1) // 2
    draw.line([(cross_x, y0 + FRAME_W), (cross_x, y1 - FRAME_W)],
              fill=_WOOD_SHELF, width=max(1, FRAME_W - 1))
    draw.line([(x0 + FRAME_W, cross_y), (x1 - FRAME_W, cross_y)],
              fill=_WOOD_SHELF, width=max(1, FRAME_W - 1))


# ── Shelves and jars ──────────────────────────────────────────────────────────

def _draw_shelf_row(
    draw: "ImageDraw.ImageDraw",
    W: int,
    y_top: int,
    y_bottom: int,
    shelf_x0: int,
    shelf_x1: int,
    jar_count: int,
    jar_start: int = 0,     # index into _JAR_COLORS
    *,
    ambient_light: float = 0.0,
) -> None:
    """Draw a wooden shelf plank and the ingredient jars sitting on it."""
    # Shelf plank
    draw.rectangle([shelf_x0, y_top, shelf_x1, y_bottom], fill=_WOOD_SHELF)
    draw.line([(shelf_x0, y_top), (shelf_x1, y_top)], fill=_TOOL_DARK, width=1)

    # Jars sitting above the shelf
    jar_area_w = shelf_x1 - shelf_x0
    if jar_count <= 0:
        return
    spacing = jar_area_w // jar_count
    jar_h    = int((y_top - draw._image.height * 0.04) * 0.22)
    jar_h    = max(8, min(36, jar_h))
    jar_w    = max(6, spacing - spacing // 5)

    for i in range(jar_count):
        cx = shelf_x0 + i * spacing + spacing // 2
        jy_bot = y_top - 2
        jy_top = jy_bot - jar_h

        col = _JAR_COLORS[(jar_start + i) % len(_JAR_COLORS)]

        # Glass body — slightly lighter version of jar color
        body_r = min(255, int(col[0] * 0.7 + 30))
        body_g = min(255, int(col[1] * 0.7 + 30))
        body_b = min(255, int(col[2] * 0.7 + 30))

        draw.ellipse(
            [cx - jar_w // 2, jy_top, cx + jar_w // 2, jy_bot],
            fill=(body_r, body_g, body_b),
            outline=_TOOL_DARK, width=1,
        )
        # Cork/stopper
        stopper_w = max(2, jar_w // 4)
        draw.rectangle(
            [cx - stopper_w // 2, jy_top - 3, cx + stopper_w // 2, jy_top],
            fill=_WOOD_SHELF,
        )
        # Highlight
        draw.line(
            [(cx - jar_w // 2 + 2, jy_top + 3), (cx - jar_w // 2 + 2, jy_bot - 3)],
            fill=(min(255, body_r + 60), min(255, body_g + 60), min(255, body_b + 60)),
            width=1,
        )


# ── Workbench ─────────────────────────────────────────────────────────────────

def _draw_workbench(
    draw: "ImageDraw.ImageDraw",
    W: int,
    y_top: int,
    y_bottom: int,
    *,
    ambient_light: float = 0.0,
) -> None:
    """
    Draw the main workbench surface with tools (mortar/pestle, scales, candle stubs).
    """
    bench_x0 = W // 12
    bench_x1 = W - W // 7

    # Thick wooden surface
    draw.rectangle([bench_x0, y_top, bench_x1, y_bottom], fill=_WOOD_BENCH)
    draw.line([(bench_x0, y_top), (bench_x1, y_top)], fill=_TOOL_DARK, width=2)

    # Warm amber sheen if ambient light present
    if ambient_light > 0:
        sheen_r = min(255, int(_WOOD_BENCH[0] + 40 * ambient_light))
        sheen_g = min(255, int(_WOOD_BENCH[1] + 25 * ambient_light))
        sheen_b = min(255, int(_WOOD_BENCH[2] + 8  * ambient_light))
        draw.rectangle([bench_x0, y_top, bench_x0 + (bench_x1 - bench_x0) // 3, y_bottom],
                       fill=(sheen_r, sheen_g, sheen_b))

    # Wooden grain lines
    grain_col = (_WOOD_BENCH[0] - 6, _WOOD_BENCH[1] - 4, _WOOD_BENCH[2] - 3)
    for gx in range(bench_x0 + 8, bench_x1, 22):
        draw.line([(gx, y_top + 1), (gx + 5, y_bottom - 1)], fill=grain_col, width=1)

    surface_y = y_top

    # Mortar (circle) and pestle (diagonal line)
    mortar_cx = bench_x0 + (bench_x1 - bench_x0) // 4
    mortar_r  = max(6, (y_bottom - y_top) // 3)
    draw.ellipse(
        [mortar_cx - mortar_r, surface_y - mortar_r // 2,
         mortar_cx + mortar_r, surface_y + mortar_r],
        fill=_PESTLE_COLOR, outline=_TOOL_DARK, width=1,
    )
    draw.line(
        [mortar_cx - mortar_r // 2, surface_y - mortar_r,
         mortar_cx + mortar_r,       surface_y - mortar_r * 2],
        fill=(_PESTLE_COLOR[0] + 20, _PESTLE_COLOR[1] + 20, _PESTLE_COLOR[2] + 20),
        width=2,
    )

    # Small scales (simple T-shape)
    scales_cx = bench_x0 + (bench_x1 - bench_x0) * 2 // 3
    scales_y  = surface_y
    arm_half  = max(10, (y_bottom - y_top) // 2)
    draw.line([(scales_cx, scales_y - arm_half), (scales_cx, scales_y + arm_half // 2)],
              fill=_PESTLE_COLOR, width=1)
    draw.line([(scales_cx - arm_half, scales_y), (scales_cx + arm_half, scales_y)],
              fill=_PESTLE_COLOR, width=1)
    draw.ellipse([scales_cx - arm_half - 5, scales_y - 3,
                  scales_cx - arm_half + 5, scales_y + 3], fill=_PESTLE_COLOR)
    draw.ellipse([scales_cx + arm_half - 5, scales_y - 3,
                  scales_cx + arm_half + 5, scales_y + 3], fill=_PESTLE_COLOR)

    # Candle stub
    candle_x = bench_x0 + (bench_x1 - bench_x0) // 2 + 15
    candle_w  = max(3, (y_bottom - y_top) // 4)
    candle_h  = max(6, (y_bottom - y_top) // 2)
    draw.rectangle(
        [candle_x, surface_y - candle_h, candle_x + candle_w, surface_y],
        fill=(210, 200, 175),
    )
    # Flame
    draw.ellipse(
        [candle_x + 1, surface_y - candle_h - 5,
         candle_x + candle_w - 1, surface_y - candle_h],
        fill=(255, 200, 80),
    )


# ── Brazier ───────────────────────────────────────────────────────────────────

def _draw_brazier(
    draw: "ImageDraw.ImageDraw",
    pix: object,
    W: int,
    H: int,
    cx: int,
    base_y: int,
    *,
    intensity: float = 1.0,
) -> None:
    """
    Draw a small iron brazier with glowing coals and a glow halo.
    cx: horizontal center of the brazier.
    base_y: y position of the floor surface where the brazier stands.
    intensity: 0–1, scales glow.  1 = late afternoon, 1.5 = night.
    """
    brazier_h = max(18, H // 14)
    bowl_r    = max(10, H // 20)

    # Iron stand (simple tripod — three diagonal lines)
    stand_top_y = base_y - brazier_h
    for angle_deg in (-30, 0, 30):
        a = math.radians(angle_deg)
        draw.line(
            [(int(cx + bowl_r * 0.6 * math.sin(a)), stand_top_y + bowl_r // 2),
             (int(cx + bowl_r * 1.4 * math.sin(a)), base_y)],
            fill=_BRAZIER_IRON, width=2,
        )

    # Coal bowl
    draw.ellipse(
        [cx - bowl_r, stand_top_y, cx + bowl_r, stand_top_y + bowl_r],
        fill=_BRAZIER_WARM, outline=_BRAZIER_IRON, width=1,
    )
    # Glowing coals
    coal_r = max(4, bowl_r - 4)
    draw.ellipse(
        [cx - coal_r, stand_top_y + 3, cx + coal_r, stand_top_y + bowl_r - 2],
        fill=_BRAZIER_HOT,
    )

    # Glow halo — radial warm bleed into surrounding pixels
    glow_radius = int(bowl_r * 4.0 * intensity)
    glow_cx = cx
    glow_cy = stand_top_y + bowl_r // 2

    for dy in range(-glow_radius, glow_radius + 1):
        for dx in range(-glow_radius, glow_radius + 1):
            px = glow_cx + dx
            py = glow_cy + dy
            if px < 0 or px >= W or py < 0 or py >= H:
                continue
            dist = math.sqrt(dx * dx + dy * dy) + 0.1
            if dist >= glow_radius:
                continue
            alpha = max(0.0, (1.0 - dist / glow_radius) ** 2) * intensity * 0.45
            cur = pix[px, py]
            r = min(255, cur[0] + int((_BRAZIER_HOT[0] - cur[0]) * alpha))
            g = min(255, cur[1] + int((_BRAZIER_WARM[1] - cur[1]) * alpha * 0.6))
            b = min(255, cur[2] + int(0 * alpha))
            pix[px, py] = (r, g, b)


# ── Floor ─────────────────────────────────────────────────────────────────────

def _draw_floor(
    draw: "ImageDraw.ImageDraw",
    W: int,
    H: int,
    floor_y: int,
    *,
    brazier_cx: int = 0,
    brazier_intensity: float = 1.0,
) -> None:
    """
    Draw large stone floor flags below floor_y.
    Includes subtle warm glow from the brazier spreading across the floor.
    """
    draw.rectangle([0, floor_y, W - 1, H - 1], fill=_FLOOR_BASE)

    # Stone flags — irregular grid of horizontal + vertical seam lines
    FLAG_W_BASE = W // 5
    FLAG_H_BASE = (H - floor_y) // 3

    y = floor_y
    row = 0
    while y < H:
        fh = FLAG_H_BASE + (row % 3) * 3
        draw.line([(0, y), (W, y)], fill=_FLOOR_SEAM, width=1)
        # Vertical seams offset per row
        x = (row % 2) * (FLAG_W_BASE // 2)
        while x < W:
            fw = FLAG_W_BASE + ((_nhash(x // 30, y // 20) * 0.4 - 0.2) * FLAG_W_BASE * 0.5)
            fw = max(FLAG_W_BASE // 2, int(fw))
            draw.line([(int(x), y + 1), (int(x), min(y + fh, H) - 1)],
                      fill=_FLOOR_SEAM, width=1)
            # Subtle floor colour variation per flag
            v  = _nhash(x // 15 + row * 5, y // 8) * 0.08 - 0.04
            fr = max(0, min(255, int(_FLOOR_BASE[0] * (1 + v))))
            fg = max(0, min(255, int(_FLOOR_BASE[1] * (1 + v))))
            fb = max(0, min(255, int(_FLOOR_BASE[2] * (1 + v))))
            draw.rectangle(
                [int(x) + 1, y + 1, int(x + fw) - 1, min(y + fh, H) - 1],
                fill=(fr, fg, fb),
            )
            x += fw
        y   += fh
        row += 1


# ── Ambient window light spill ────────────────────────────────────────────────

def _window_light_spill(
    pix: object,
    W: int,
    H: int,
    window_rect: tuple[int, int, int, int],
    *,
    time_of_day: str,
    floor_y: int,
) -> None:
    """
    Soft light spill from the window onto the wall and workbench surface.
    Only affects pixels outside the window rect itself.
    Amber (day) or cold blue (night).
    """
    x0, y0, x1, y1 = window_rect
    wx  = (x0 + x1) / 2.0
    wy  = (y0 + y1) / 2.0
    if time_of_day == "night":
        light_col  = (18, 28, 52)
        max_reach  = W * 0.55
        max_alpha  = 0.12
    else:
        light_col  = (200, 120, 40)
        max_reach  = W * 0.65
        max_alpha  = 0.32

    for py in range(H):
        for px in range(W):
            # Skip pixels inside the window
            if x0 <= px <= x1 and y0 <= py <= y1:
                continue
            # Skip floor — brazier handles floor light
            if py >= floor_y:
                continue
            dx   = px - wx
            dy   = py - wy
            dist = math.sqrt(dx * dx + dy * dy) + 0.1
            if dist >= max_reach:
                continue
            alpha = max(0.0, (1.0 - dist / max_reach) ** 1.8) * max_alpha
            cur = pix[px, py]
            r   = min(255, cur[0] + int((light_col[0] - cur[0]) * alpha))
            g   = min(255, cur[1] + int((light_col[1] - cur[1]) * alpha))
            b   = min(255, cur[2] + int((light_col[2] - cur[2]) * alpha))
            pix[px, py] = (r, g, b)


# ── Main renderer ─────────────────────────────────────────────────────────────

def render_wiltoll_lane_interior(
    *,
    time_of_day: str = "late_afternoon",
    width:  int = 512,
    height: int = 384,
) -> Optional[bytes]:
    """
    Render the interior of the player's home shop on Wiltoll Lane, Azonithia.

    The shop is a stone-walled alchemist's workroom on the southeastern edge
    of Azonithia in Aeralune. Mt. Hieronymus rises above the roofline through
    the upper-left window.

    Parameters
    ----------
    time_of_day:
        ``"late_afternoon"`` — warm amber window light, soft shadows.
        ``"night"``          — cold moonlit window, brazier as sole warm source.
    width, height:
        Image dimensions.  Default 512×384 (landscape).

    Returns
    -------
    PNG bytes, or None if Pillow is unavailable.
    """
    if not _PIL_AVAILABLE:
        return None

    W, H = width, height

    img  = Image.new("RGB", (W, H), _STONE_BASE)
    draw = ImageDraw.Draw(img)
    pix  = img.load()

    # ── Layout constants ──────────────────────────────────────────────────────
    FLOOR_Y       = int(H * 0.72)    # floor-line y
    WALL_TOP      = 0
    WALL_BOTTOM   = FLOOR_Y

    # Window: upper-left, ~22 % width × 30 % height
    WIN_X0 = int(W * 0.06)
    WIN_Y0 = int(H * 0.07)
    WIN_X1 = int(W * 0.28)
    WIN_Y1 = int(H * 0.38)
    win_rect = (WIN_X0, WIN_Y0, WIN_X1, WIN_Y1)

    ambient_intensity = 0.80 if time_of_day != "night" else 0.15
    ambient_x         = WIN_X1 / W   # light source is at right edge of window

    # ── Stone wall ────────────────────────────────────────────────────────────
    _draw_stone_wall(
        draw, pix, W, H,
        wall_top=WALL_TOP, wall_bottom=WALL_BOTTOM,
        window_rect=win_rect,
        ambient_light=(ambient_x * 0.5, ambient_intensity),
    )

    # ── Window ────────────────────────────────────────────────────────────────
    _draw_window(draw, W, H, win_rect, time_of_day=time_of_day)

    # ── Upper shelf (back wall, roughly 42–52 % height) ───────────────────────
    SHELF1_TOP    = int(H * 0.42)
    SHELF1_BOTTOM = int(H * 0.46)
    SHELF1_X0     = int(W * 0.32)
    SHELF1_X1     = int(W * 0.94)

    _draw_shelf_row(
        draw, W,
        y_top=SHELF1_TOP, y_bottom=SHELF1_BOTTOM,
        shelf_x0=SHELF1_X0, shelf_x1=SHELF1_X1,
        jar_count=6, jar_start=0,
        ambient_light=ambient_intensity,
    )

    # ── Lower shelf (back wall, roughly 55–59 % height) ───────────────────────
    SHELF2_TOP    = int(H * 0.55)
    SHELF2_BOTTOM = int(H * 0.59)
    SHELF2_X0     = int(W * 0.52)
    SHELF2_X1     = int(W * 0.94)

    _draw_shelf_row(
        draw, W,
        y_top=SHELF2_TOP, y_bottom=SHELF2_BOTTOM,
        shelf_x0=SHELF2_X0, shelf_x1=SHELF2_X1,
        jar_count=4, jar_start=2,
        ambient_light=ambient_intensity,
    )

    # ── Workbench ─────────────────────────────────────────────────────────────
    BENCH_TOP    = int(H * 0.60)
    BENCH_BOTTOM = int(H * 0.66)
    _draw_workbench(draw, W, BENCH_TOP, BENCH_BOTTOM, ambient_light=ambient_intensity)

    # ── Floor ─────────────────────────────────────────────────────────────────
    BRAZIER_CX    = int(W * 0.62)
    BRAZIER_BASE  = FLOOR_Y
    brazier_glow  = 1.0 if time_of_day == "night" else 0.72
    _draw_floor(
        draw, W, H, FLOOR_Y,
        brazier_cx=BRAZIER_CX,
        brazier_intensity=brazier_glow,
    )

    # ── Window light spill (before brazier, so brazier overwrites edges) ──────
    _window_light_spill(
        pix, W, H, win_rect,
        time_of_day=time_of_day,
        floor_y=FLOOR_Y,
    )
    draw = ImageDraw.Draw(img)

    # ── Brazier ───────────────────────────────────────────────────────────────
    _draw_brazier(
        draw, pix, W, H,
        cx=BRAZIER_CX,
        base_y=FLOOR_Y,
        intensity=brazier_glow,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()