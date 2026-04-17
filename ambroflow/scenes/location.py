"""
Location Scene Renderer — Wiltoll Lane Home
============================================
Procedural background scenes for the player's home on Wiltoll Lane,
southeastern edge of Azonithia, Aeralune.  Game 7 (7_KLGS).

The building is one-and-a-half stories of dark Aeralune stone on a
narrow lane.  Mt. Hieronymus rises above the roofline to the southeast.

Floor plan
----------
  Ground floor:
    [FOYER]  →  [WORKBENCH AREA]  →  [KITCHEN]

  Upper half-floor (accessed via rear stair):
    [BEDROOM]  |  [MEDITATION ROOM]  |  [STUDY / LIBRARY]

Each room is rendered as a separate 512×384 PNG via front-elevation view
(standing in the doorway, looking into the room).

Furnace/brazier placement
  Furnace (stone hearth with cooking fire) → Kitchen back wall
  Brazier (iron stand, alchemical heat)    → Workbench area

Time-of-day variants for all rooms:
  "dawn"           — pre-sunrise, cold gray-blue sky, barely any ambient
  "late_afternoon" — warm amber light, rich and diffused
  "night"          — no window light; fire sources only

Shared palette
--------------
  _STONE_BASE   (30, 28, 38)   dark charcoal-indigo Aeralune stone
  _STONE_LIT    (52, 44, 32)   amber-washed under a warm light source
  _WOOD_SHELF   (58, 40, 21)   dark oak, rough-hewn
  _WOOD_BENCH   (44, 30, 14)   aged workbench surface
  _WOOD_PLANK   (50, 34, 18)   floorboard planks
  _FLOOR_BASE   (22, 20, 30)   stone flags
  _FLOOR_SEAM   (13, 12, 18)   mortar between flags
  _HEARTH_STONE (24, 22, 28)   kitchen hearth block
  _PARCHMENT    (160,145,100)  light through dawn window
"""

from __future__ import annotations

import io
import math
from enum import Enum
from typing import Optional

try:
    from PIL import Image, ImageDraw
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# ── Palette ───────────────────────────────────────────────────────────────────

_STONE_BASE    = ( 30,  28,  38)
_STONE_LIT     = ( 52,  44,  32)
_STONE_MORTAR  = ( 20,  18,  26)
_WOOD_SHELF    = ( 58,  40,  21)
_WOOD_BENCH    = ( 44,  30,  14)
_WOOD_PLANK    = ( 50,  34,  18)
_WOOD_PLANK_D  = ( 38,  26,  12)   # darker plank grain
_FLOOR_BASE    = ( 22,  20,  30)
_FLOOR_SEAM    = ( 13,  12,  18)
_HEARTH_STONE  = ( 24,  22,  28)
_HEARTH_FIRE   = (220,  90,  18)
_HEARTH_EMBER  = (160,  55,   8)
_BEDDING       = (195, 185, 168)   # worn linen
_BEDDING_SHADE = (150, 140, 120)
_IRON          = ( 45,  38,  32)
_IRON_WARM     = ( 65,  50,  35)

# Window sky colours (top, bottom) per time of day
_SKY: dict[str, tuple[tuple, tuple]] = {
    "dawn":          ((18,  22,  38), (85,  65,  35)),    # cold blue → pale amber
    "late_afternoon":((140, 100,  45), (210, 140,  60)),  # orange sky
    "night":         ((8,   12,  24), (14,  20,  38)),    # void-dark blue
}

_MOUNTAIN       = ( 16,  14,  20)
_WIN_FRAME      = ( 55,  38,  20)   # window/door wood frame

_BRAZIER_HOT    = (220,  95,  20)
_BRAZIER_WARM   = (150,  55,   8)
_BOOK_COLORS    = [
    ( 80,  40,  30), (50,  70, 100), (100, 80, 30),
    ( 40,  60,  40), (90,  40, 80), (70, 50, 30),
    ( 55,  35,  65), (110, 75, 40), (40, 80, 70),
]
_PARCHMENT      = (160, 145, 100)
_JAR_COLORS: list[tuple[int,int,int]] = [
    (180, 100,  25), ( 35,  90,  40), (100,  20,  20),
    ( 50,  70, 110), ( 60,  25,  80), (140,  85,  30),
]


# ── Room enum ─────────────────────────────────────────────────────────────────

class HomeRoom(str, Enum):
    FOYER      = "foyer"
    WORKBENCH  = "workbench"
    KITCHEN    = "kitchen"
    BEDROOM    = "bedroom"
    MEDITATION = "meditation"
    STUDY      = "study"


# ── Deterministic noise ───────────────────────────────────────────────────────

def _nhash(x: int, y: int) -> float:
    n = ((x * 1664525) ^ (y * 1013904223) ^ 0xBADC0DE5) & 0xFFFF_FFFF
    return n / 0xFFFF_FFFF


# ── Shared drawing primitives ─────────────────────────────────────────────────

def _draw_stone_wall(
    draw: "ImageDraw.ImageDraw",
    W: int, H: int,
    wall_top: int, wall_bottom: int,
    *,
    window_rect:    Optional[tuple[int,int,int,int]] = None,
    door_rect:      Optional[tuple[int,int,int,int]] = None,
    ambient_light:  tuple[float, float] = (0.5, 0.0),
) -> None:
    """Coarse mortared stone wall with per-block colour variation."""
    draw.rectangle([0, wall_top, W-1, wall_bottom], fill=_STONE_BASE)

    COURSE_H   = max(4, H // 14)
    BLOCK_W_BASE = W // 7
    y, course = wall_top, 0

    while y < wall_bottom:
        next_y = min(y + COURSE_H + (course % 3) - 1, wall_bottom)
        offset = (COURSE_H * 2) if (course % 2 == 0) else 0
        bx = -offset

        while bx < W:
            bw = max(BLOCK_W_BASE // 2, int(
                BLOCK_W_BASE * (1 + (_nhash(bx//20, y//20) * 0.5 - 0.25))
            ))
            v  = _nhash(bx//10 + course*7, y//8+3) * 0.12 - 0.06
            sr = max(0, min(255, int(_STONE_BASE[0] * (1+v))))
            sg = max(0, min(255, int(_STONE_BASE[1] * (1+v))))
            sb = max(0, min(255, int(_STONE_BASE[2] * (1+v))))

            if ambient_light[1] > 0:
                dx = abs(bx/W - ambient_light[0])
                dy = abs((y + next_y)/2/H - 0.2)
                dist = math.sqrt(dx*dx + dy*dy)
                warmth = max(0.0, 1 - dist*2.5) * ambient_light[1]
                sr = min(255, sr + int((_STONE_LIT[0] - sr) * warmth))
                sg = min(255, sg + int((_STONE_LIT[1] - sg) * warmth))
                sb = min(255, sb + int((_STONE_LIT[2] - sb) * warmth))

            x0, x1 = max(0, int(bx)), min(W-1, int(bx+bw-2))
            skip_rects = []
            if window_rect:
                skip_rects.append(window_rect)
            if door_rect:
                skip_rects.append(door_rect)

            def _rect_overlaps_row(r):
                return r and y <= r[3] and next_y >= r[1]

            row_y0 = y + 1
            row_y1 = next_y - 1
            if row_y1 < row_y0:
                pass  # row too thin to render at this canvas size
            elif any(_rect_overlaps_row(r) for r in skip_rects):
                for r in skip_rects:
                    if not _rect_overlaps_row(r):
                        continue
                    # left of opening
                    if x0 < r[0]:
                        lx1 = min(x1, r[0] - 1)
                        if lx1 >= x0:
                            draw.rectangle([x0, row_y0, lx1, row_y1],
                                           fill=(sr, sg, sb))
                    # right of opening
                    if x1 > r[2]:
                        rx0 = max(x0, r[2] + 1)
                        if rx0 <= x1:
                            draw.rectangle([rx0, row_y0, x1, row_y1],
                                           fill=(sr, sg, sb))
            else:
                draw.rectangle([x0, row_y0, x1, row_y1], fill=(sr, sg, sb))

            jx = int(bx + bw) - 1
            if 0 <= jx < W:
                draw.line([(jx, y), (jx, next_y)], fill=_STONE_MORTAR, width=1)
            bx += bw

        draw.line([(0, next_y), (W, next_y)], fill=_STONE_MORTAR, width=1)
        y, course = next_y + 1, course + 1


def _draw_window(
    draw: "ImageDraw.ImageDraw",
    W: int, H: int,
    rect: tuple[int,int,int,int],
    *,
    time_of_day: str = "late_afternoon",
    show_mountain: bool = True,
) -> None:
    x0, y0, x1, y1 = rect
    ww, wh = x1 - x0, y1 - y0

    sky_top, sky_bot = _SKY.get(time_of_day, _SKY["late_afternoon"])
    for iy in range(y0, y1+1):
        t = (iy - y0) / wh if wh else 0
        r = int(sky_top[0] + (sky_bot[0]-sky_top[0])*t)
        g = int(sky_top[1] + (sky_bot[1]-sky_top[1])*t)
        b = int(sky_top[2] + (sky_bot[2]-sky_top[2])*t)
        draw.line([(x0, iy), (x1, iy)], fill=(r, g, b))

    if show_mountain:
        mtop = y0 + int(wh * 0.40)
        pts  = [
            (x0, y1), (x0, mtop + int(wh*0.22)),
            (x0+int(ww*0.18), mtop+int(wh*0.10)),
            (x0+int(ww*0.35), mtop+int(wh*0.14)),
            (x0+int(ww*0.62), mtop+int(wh*0.05)),
            (x0+int(ww*0.78), mtop+int(wh*0.18)),
            (x1, mtop+int(wh*0.28)), (x1, y1),
        ]
        draw.polygon(pts, fill=_MOUNTAIN)

    FRAME_W = max(2, ww // 18)
    draw.rectangle([x0, y0, x1, y1], outline=_WIN_FRAME, width=FRAME_W)
    cx, cy = (x0+x1)//2, (y0+y1)//2
    draw.line([(cx, y0+FRAME_W), (cx, y1-FRAME_W)], fill=_WIN_FRAME, width=max(1, FRAME_W-1))
    draw.line([(x0+FRAME_W, cy), (x1-FRAME_W, cy)], fill=_WIN_FRAME, width=max(1, FRAME_W-1))


def _draw_stone_floor(
    draw: "ImageDraw.ImageDraw",
    W: int, H: int,
    floor_y: int,
) -> None:
    """Large irregular stone flags."""
    draw.rectangle([0, floor_y, W-1, H-1], fill=_FLOOR_BASE)
    FLAG_W = W // 5
    FLAG_H = max(8, (H - floor_y) // 3)
    y, row = floor_y, 0
    while y < H:
        fh = FLAG_H + (row % 3) * 3
        draw.line([(0, y), (W, y)], fill=_FLOOR_SEAM, width=1)
        x = (row % 2) * (FLAG_W // 2)
        while x < W:
            fw = max(FLAG_W//2, int(FLAG_W*(1+(_nhash(x//30,y//20)*0.4-0.2))))
            draw.line([(int(x), y+1), (int(x), min(y+fh, H)-1)],
                      fill=_FLOOR_SEAM, width=1)
            v  = _nhash(x//15+row*5, y//8)*0.08-0.04
            draw.rectangle([int(x)+1, y+1, int(x+fw)-1, min(y+fh,H)-1],
                           fill=(
                               max(0, min(255, int(_FLOOR_BASE[0]*(1+v)))),
                               max(0, min(255, int(_FLOOR_BASE[1]*(1+v)))),
                               max(0, min(255, int(_FLOOR_BASE[2]*(1+v)))),
                           ))
            x += fw
        y, row = y + fh, row + 1


def _draw_wooden_floor(
    draw: "ImageDraw.ImageDraw",
    W: int, H: int,
    floor_y: int,
) -> None:
    """Warm wooden planks running left-to-right."""
    PLANK_H = max(6, (H - floor_y) // 8)
    y, row = floor_y, 0
    while y < H:
        ph = PLANK_H + (row % 3)
        v  = _nhash(row * 13, 7) * 0.12 - 0.06
        pr = max(0, min(255, int(_WOOD_PLANK[0]*(1+v))))
        pg = max(0, min(255, int(_WOOD_PLANK[1]*(1+v))))
        pb = max(0, min(255, int(_WOOD_PLANK[2]*(1+v))))
        draw.rectangle([0, y, W-1, min(y+ph-1, H-1)], fill=(pr, pg, pb))
        # Grain lines
        for gx in range(8 + row*3 % 22, W, 26):
            draw.line([(gx, y+1), (gx+4, min(y+ph-1, H-1))],
                      fill=_WOOD_PLANK_D, width=1)
        # Plank seam
        draw.line([(0, y), (W, y)], fill=_WOOD_PLANK_D, width=1)
        y, row = y + ph, row + 1


def _draw_shelf_row(
    draw: "ImageDraw.ImageDraw",
    W: int,
    y_top: int, y_bottom: int,
    shelf_x0: int, shelf_x1: int,
    jar_count: int,
    jar_start: int = 0,
) -> None:
    draw.rectangle([shelf_x0, y_top, shelf_x1, y_bottom], fill=_WOOD_SHELF)
    draw.line([(shelf_x0, y_top), (shelf_x1, y_top)], fill=(30, 20, 8), width=1)
    if jar_count <= 0:
        return
    spacing = (shelf_x1 - shelf_x0) // jar_count
    jar_h   = max(8, (y_top - 4) // 5)
    jar_w   = max(6, spacing - spacing // 5)
    for i in range(jar_count):
        cx    = shelf_x0 + i * spacing + spacing // 2
        jy_b  = y_top - 2
        jy_t  = jy_b - jar_h
        col   = _JAR_COLORS[(jar_start + i) % len(_JAR_COLORS)]
        br    = min(255, int(col[0]*0.7+30))
        bg    = min(255, int(col[1]*0.7+30))
        bb    = min(255, int(col[2]*0.7+30))
        draw.ellipse([cx-jar_w//2, jy_t, cx+jar_w//2, jy_b],
                     fill=(br, bg, bb), outline=(20,14,8), width=1)
        sw = max(2, jar_w//4)
        draw.rectangle([cx-sw//2, jy_t-3, cx+sw//2, jy_t], fill=_WOOD_SHELF)
        draw.line([(cx-jar_w//2+2, jy_t+3), (cx-jar_w//2+2, jy_b-3)],
                  fill=(min(255,br+55), min(255,bg+55), min(255,bb+55)), width=1)


def _draw_brazier(
    draw: "ImageDraw.ImageDraw",
    pix:  object,
    W: int, H: int,
    cx: int, base_y: int,
    *,
    intensity: float = 1.0,
) -> None:
    bh     = max(18, H // 14)
    bowl_r = max(10, H // 20)
    top_y  = base_y - bh

    for a_deg in (-30, 0, 30):
        a = math.radians(a_deg)
        draw.line(
            [(int(cx + bowl_r*0.6*math.sin(a)), top_y + bowl_r//2),
             (int(cx + bowl_r*1.4*math.sin(a)), base_y)],
            fill=_IRON, width=2,
        )
    draw.ellipse([cx-bowl_r, top_y, cx+bowl_r, top_y+bowl_r],
                 fill=_BRAZIER_WARM, outline=_IRON, width=1)
    draw.ellipse([cx-bowl_r+4, top_y+3, cx+bowl_r-4, top_y+bowl_r-2],
                 fill=_BRAZIER_HOT)

    glow_r  = int(bowl_r * 4.0 * intensity)
    glow_cy = top_y + bowl_r // 2
    for dy in range(-glow_r, glow_r+1):
        for dx in range(-glow_r, glow_r+1):
            px, py = cx+dx, glow_cy+dy
            if not (0 <= px < W and 0 <= py < H):
                continue
            dist = math.sqrt(dx*dx + dy*dy) + 0.1
            if dist >= glow_r:
                continue
            a = max(0.0, (1-dist/glow_r)**2) * intensity * 0.42
            cur = pix[px, py]
            pix[px, py] = (
                min(255, cur[0] + int((_BRAZIER_HOT[0]-cur[0])*a)),
                min(255, cur[1] + int((_BRAZIER_WARM[1]-cur[1])*a*0.55)),
                min(255, cur[2]),
            )


def _draw_hearth(
    draw: "ImageDraw.ImageDraw",
    pix: object,
    W: int, H: int,
    rect: tuple[int,int,int,int],   # outer stone arch bounds
    *,
    intensity: float = 1.0,
) -> None:
    """Stone hearth with cooking fire and hanging pot."""
    x0, y0, x1, y1 = rect
    hw, hh = x1-x0, y1-y0

    # Stone arch surround
    ARCH_W = max(4, hw//10)
    draw.rectangle([x0, y0, x1, y1], fill=_HEARTH_STONE)
    draw.rectangle([x0+ARCH_W, y0+ARCH_W, x1-ARCH_W, y1-1],
                   fill=(8, 6, 10))   # opening interior — near-black

    # Fire glow inside opening
    fire_cx = (x0 + x1) // 2
    fire_cy = y1 - hh // 5
    for dy in range(-hh//2, hh//3):
        for dx in range(-hw//2, hw//2):
            px, py = fire_cx+dx, fire_cy+dy
            if not (0 <= px < W and 0 <= py < H):
                continue
            if not (x0+ARCH_W < px < x1-ARCH_W and y0+ARCH_W < py < y1):
                continue
            dist = math.sqrt(dx*dx + (dy*1.4)**2) / (hw//2)
            if dist >= 1.0:
                continue
            a = max(0.0, (1-dist)**1.5) * intensity
            r = min(255, int(a * _HEARTH_FIRE[0]))
            g = min(255, int(a * _HEARTH_FIRE[1] * 0.6))
            b = 0
            cur = pix[px, py]
            pix[px, py] = (max(cur[0], r), max(cur[1], g), max(cur[2], b))

    # Arch keystone decoration
    draw.arc([x0, y0, x1, y0+hh//2], 180, 0, fill=_STONE_MORTAR, width=1)

    # Iron hook and pot
    hook_x  = (x0+x1)//2
    hook_y0 = y0 + hh//4
    hook_y1 = y1 - hh//4
    draw.line([(hook_x, hook_y0), (hook_x, hook_y1)], fill=_IRON, width=2)
    pot_w = max(8, hw//4)
    pot_h = max(6, hh//6)
    draw.ellipse([hook_x-pot_w, hook_y1-pot_h, hook_x+pot_w, hook_y1+pot_h//2],
                 fill=_IRON_WARM, outline=_IRON, width=1)

    # Hearth glow radiated onto wall/floor around opening
    glow_r = int(hw * 2.2 * intensity)
    gcx, gcy = (x0+x1)//2, y1
    for dy in range(-glow_r, glow_r+1):
        for dx in range(-glow_r, glow_r+1):
            px, py = gcx+dx, gcy+dy
            if not (0 <= px < W and 0 <= py < H):
                continue
            if x0 <= px <= x1 and y0 <= py <= y1:
                continue   # skip the opening itself
            dist = math.sqrt(dx*dx + (dy*0.7)**2) + 0.1
            if dist >= glow_r:
                continue
            a = max(0.0, (1-dist/glow_r)**2) * intensity * 0.28
            cur = pix[px, py]
            pix[px, py] = (
                min(255, cur[0] + int((_HEARTH_FIRE[0]-cur[0])*a)),
                min(255, cur[1] + int(30*a)),
                min(255, cur[2]),
            )


def _draw_door(
    draw: "ImageDraw.ImageDraw",
    pix: object,
    W: int, H: int,
    rect: tuple[int,int,int,int],
    *,
    time_of_day: str = "dawn",
    ajar: bool = False,
) -> None:
    """Wooden plank door with iron crossbar and handle. Light bleeds through edges."""
    x0, y0, x1, y1 = rect
    dw, dh = x1-x0, y1-y0

    # Door frame (stone arch / lintel)
    FRAME_W = max(3, dw//12)
    draw.rectangle([x0-FRAME_W, y0-FRAME_W//2, x1+FRAME_W, y1],
                   fill=_STONE_BASE, outline=_STONE_MORTAR, width=1)

    # Exterior light bleed — thin strip at door edges/bottom
    sky_top, sky_bot = _SKY.get(time_of_day, _SKY["dawn"])
    light_col = (
        (sky_top[0]+sky_bot[0])//2,
        (sky_top[1]+sky_bot[1])//2,
        (sky_top[2]+sky_bot[2])//2,
    )
    if ajar:
        gap = max(3, dw // 8)
        draw.rectangle([x0, y0, x0+gap, y1], fill=light_col)

    # Door planks
    PLANK_W = max(4, dw // 5)
    for i in range(dw // PLANK_W + 2):
        px0 = x0 + i * PLANK_W
        px1 = min(px0 + PLANK_W - 1, x1)
        if px0 > x1:
            break
        v = _nhash(i*7, 3) * 0.10 - 0.05
        pr = max(0, min(255, int(_WOOD_SHELF[0]*(1+v))))
        pg = max(0, min(255, int(_WOOD_SHELF[1]*(1+v))))
        pb = max(0, min(255, int(_WOOD_SHELF[2]*(1+v))))
        draw.rectangle([px0, y0, px1, y1], fill=(pr, pg, pb))
        draw.line([(px0, y0), (px0, y1)], fill=_WOOD_PLANK_D, width=1)

    # Iron crossbar
    bar_y = y0 + dh // 3
    draw.line([(x0, bar_y), (x1, bar_y)], fill=_IRON, width=3)
    bar_y2 = y0 + dh * 2 // 3
    draw.line([(x0, bar_y2), (x1, bar_y2)], fill=_IRON, width=3)

    # Handle (right side)
    handle_x = x1 - dw // 6
    handle_y = y0 + dh // 2
    draw.ellipse([handle_x-5, handle_y-5, handle_x+5, handle_y+5],
                 fill=_IRON_WARM, outline=_IRON, width=1)

    # Light at bottom threshold
    for dy_off in range(min(4, FRAME_W)):
        alpha = 0.15 * (1 - dy_off / 4)
        for lx in range(x0, x1+1):
            py = y1 + dy_off
            if 0 <= py < H:
                cur = pix[lx, py]
                pix[lx, py] = (
                    min(255, cur[0] + int((light_col[0]-cur[0])*alpha)),
                    min(255, cur[1] + int((light_col[1]-cur[1])*alpha)),
                    min(255, cur[2] + int((light_col[2]-cur[2])*alpha)),
                )


def _draw_shop_counter(
    draw: "ImageDraw.ImageDraw",
    W: int,
    y_top: int, y_bottom: int,
    x0: int, x1: int,
) -> None:
    """Long shop counter with thick wooden surface and paneled front face."""
    # Front face (customer-facing)
    FACE_H = max(12, (y_bottom - y_top) * 2)
    face_y0 = y_bottom
    face_y1 = min(face_y0 + FACE_H, face_y0 + 60)

    # Panel divisions on the face
    PANEL_W = (x1 - x0) // 4
    for i in range(4):
        px = x0 + i * PANEL_W
        v  = _nhash(i*3, 1) * 0.06 - 0.03
        pr = max(0, min(255, int(_WOOD_BENCH[0]*(1+v)-5)))
        pg = max(0, min(255, int(_WOOD_BENCH[1]*(1+v)-3)))
        pb = max(0, min(255, int(_WOOD_BENCH[2]*(1+v))))
        draw.rectangle([px, face_y0, min(px+PANEL_W-1, x1), face_y1],
                       fill=(pr, pg, pb))
        draw.line([(px, face_y0), (px, face_y1)],
                  fill=_WOOD_PLANK_D, width=1)

    draw.line([(x0, face_y0), (x1, face_y0)], fill=(22, 15, 7), width=2)

    # Counter top surface
    draw.rectangle([x0, y_top, x1, y_bottom], fill=_WOOD_BENCH)
    draw.line([(x0, y_top), (x1, y_top)], fill=(22, 15, 7), width=2)

    # Surface worn centre strip
    mid = (y_top + y_bottom) // 2
    draw.rectangle([x0+10, mid-2, x1-10, mid+2],
                   fill=(_WOOD_BENCH[0]+8, _WOOD_BENCH[1]+5, _WOOD_BENCH[2]+2))

    # Grain
    for gx in range(x0+6, x1, 18):
        draw.line([(gx, y_top+1), (gx+3, y_bottom-1)], fill=_WOOD_PLANK_D, width=1)

    # Items on counter: open ledger (left) + small scale (right)
    # Ledger
    led_x = x0 + (x1-x0)//5
    led_y = y_top - 4
    draw.rectangle([led_x-20, led_y-12, led_x+20, led_y],
                   fill=_PARCHMENT, outline=(80, 60, 30), width=1)
    # Scale (same as workbench but smaller)
    sc_cx = x0 + (x1-x0)*3//4
    draw.line([(sc_cx, led_y-10), (sc_cx, led_y)], fill=_IRON, width=1)
    draw.line([(sc_cx-12, led_y-6), (sc_cx+12, led_y-6)], fill=_IRON, width=1)
    draw.ellipse([sc_cx-16, led_y-10, sc_cx-8, led_y-4], fill=_IRON)
    draw.ellipse([sc_cx+8,  led_y-10, sc_cx+16, led_y-4], fill=_IRON)


def _draw_workbench(
    draw: "ImageDraw.ImageDraw",
    W: int,
    y_top: int, y_bottom: int,
    *,
    ambient_light: float = 0.0,
) -> None:
    bench_x0 = W // 12
    bench_x1 = W - W // 7

    draw.rectangle([bench_x0, y_top, bench_x1, y_bottom], fill=_WOOD_BENCH)
    draw.line([(bench_x0, y_top), (bench_x1, y_top)], fill=(22, 15, 7), width=2)

    if ambient_light > 0:
        sr = min(255, int(_WOOD_BENCH[0] + 40*ambient_light))
        sg = min(255, int(_WOOD_BENCH[1] + 25*ambient_light))
        sb = min(255, int(_WOOD_BENCH[2] + 8*ambient_light))
        draw.rectangle([bench_x0, y_top, bench_x0+(bench_x1-bench_x0)//3, y_bottom],
                       fill=(sr, sg, sb))

    for gx in range(bench_x0+8, bench_x1, 22):
        draw.line([(gx, y_top+1), (gx+5, y_bottom-1)], fill=_WOOD_PLANK_D, width=1)

    surface_y = y_top
    # Mortar + pestle
    m_cx  = bench_x0 + (bench_x1-bench_x0)//4
    m_r   = max(6, (y_bottom-y_top)//3)
    draw.ellipse([m_cx-m_r, surface_y-m_r//2, m_cx+m_r, surface_y+m_r],
                 fill=(80,70,68), outline=(30,22,18), width=1)
    draw.line([m_cx-m_r//2, surface_y-m_r, m_cx+m_r, surface_y-m_r*2],
              fill=(100,90,88), width=2)
    # Scales
    sc_cx = bench_x0 + (bench_x1-bench_x0)*2//3
    arm   = max(10, (y_bottom-y_top)//2)
    draw.line([(sc_cx, surface_y-arm), (sc_cx, surface_y+arm//2)], fill=(80,70,68), width=1)
    draw.line([(sc_cx-arm, surface_y), (sc_cx+arm, surface_y)], fill=(80,70,68), width=1)
    draw.ellipse([sc_cx-arm-5, surface_y-3, sc_cx-arm+5, surface_y+3], fill=(80,70,68))
    draw.ellipse([sc_cx+arm-5, surface_y-3, sc_cx+arm+5, surface_y+3], fill=(80,70,68))
    # Candle
    c_x  = bench_x0 + (bench_x1-bench_x0)//2 + 15
    c_w  = max(3, (y_bottom-y_top)//4)
    c_h  = max(6, (y_bottom-y_top)//2)
    draw.rectangle([c_x, surface_y-c_h, c_x+c_w, surface_y], fill=(210,200,175))
    draw.ellipse([c_x+1, surface_y-c_h-5, c_x+c_w-1, surface_y-c_h],
                 fill=(255,200,80))


def _draw_bed(
    draw: "ImageDraw.ImageDraw",
    W: int, H: int,
    bed_x0: int, bed_x1: int,
    bed_top: int, bed_bottom: int,
    *,
    rumpled: bool = False,
) -> None:
    """Wooden bed frame with linen bedding."""
    FRAME_H = max(5, (bed_bottom - bed_top) // 5)
    FRAME_W = max(4, (bed_x1 - bed_x0) // 12)

    # Headboard (back)
    draw.rectangle([bed_x0, bed_top, bed_x1, bed_top + FRAME_H*2],
                   fill=_WOOD_SHELF, outline=_WOOD_PLANK_D, width=1)
    # Footboard
    draw.rectangle([bed_x0, bed_bottom - FRAME_H, bed_x1, bed_bottom],
                   fill=_WOOD_SHELF, outline=_WOOD_PLANK_D, width=1)
    # Side rails
    draw.rectangle([bed_x0, bed_top, bed_x0+FRAME_W, bed_bottom],
                   fill=_WOOD_SHELF)
    draw.rectangle([bed_x1-FRAME_W, bed_top, bed_x1, bed_bottom],
                   fill=_WOOD_SHELF)

    # Mattress / bedding
    mat_top = bed_top + FRAME_H*2
    mat_bot = bed_bottom - FRAME_H
    draw.rectangle([bed_x0+FRAME_W, mat_top, bed_x1-FRAME_W, mat_bot],
                   fill=_BEDDING)

    if rumpled:
        # Rumpled fold lines
        for i in range(3):
            fold_y = mat_top + (mat_bot-mat_top)*(i+1)//4
            draw.arc([bed_x0+FRAME_W+5, fold_y-8, bed_x1-FRAME_W-5, fold_y+8],
                     190, 350, fill=_BEDDING_SHADE, width=2)
        # Pillow (pushed to headboard end)
        pil_h = max(8, (mat_bot-mat_top)//4)
        draw.rectangle([bed_x0+FRAME_W+6, mat_top+4,
                        bed_x1-FRAME_W-6, mat_top+pil_h],
                       fill=(215, 205, 190), outline=_BEDDING_SHADE, width=1)
    else:
        # Neat bedding
        draw.line([(bed_x0+FRAME_W+5, mat_top+(mat_bot-mat_top)//3),
                   (bed_x1-FRAME_W-5, mat_top+(mat_bot-mat_top)//3)],
                  fill=_BEDDING_SHADE, width=1)


def _draw_bookshelves(
    draw: "ImageDraw.ImageDraw",
    W: int,
    shelf_x0: int, shelf_x1: int,
    shelf_y0: int,
    tiers: int = 2,
    tier_h: int = 40,
) -> None:
    """Two-tier bookshelf with books of varying heights and colors."""
    sw = shelf_x1 - shelf_x0
    SHELF_PLANK = max(3, tier_h // 10)

    for tier in range(tiers):
        sy_bottom = shelf_y0 + (tier+1) * tier_h
        sy_top    = sy_bottom - tier_h
        # Shelf back panel
        draw.rectangle([shelf_x0, sy_top, shelf_x1, sy_bottom], fill=_WOOD_SHELF)
        draw.line([(shelf_x0, sy_bottom), (shelf_x1, sy_bottom)],
                  fill=_WOOD_PLANK_D, width=SHELF_PLANK)

        # Books
        bx = shelf_x0 + 2
        bi = tier * 12
        while bx < shelf_x1 - 6:
            bw  = max(6, int(6 + _nhash(bx, tier*100)*10))
            bh  = max(int(tier_h*0.5),
                      int(tier_h * (0.55 + _nhash(bx+1, tier*100+1)*0.35)))
            col = _BOOK_COLORS[bi % len(_BOOK_COLORS)]
            by  = sy_bottom - SHELF_PLANK - bh
            draw.rectangle([bx, by, bx+bw-1, sy_bottom-SHELF_PLANK],
                           fill=col, outline=(col[0]//2, col[1]//2, col[2]//2), width=1)
            # Spine highlight
            draw.line([(bx+1, by+2), (bx+1, by+bh-2)],
                      fill=(min(255,col[0]+30), min(255,col[1]+30), min(255,col[2]+30)),
                      width=1)
            bx += bw
            bi += 1


def _draw_writing_desk(
    draw: "ImageDraw.ImageDraw",
    W: int,
    desk_x0: int, desk_x1: int,
    desk_top: int, desk_bottom: int,
) -> None:
    """Writing desk with papers, inkwell, and quill."""
    # Desk surface
    draw.rectangle([desk_x0, desk_top, desk_x1, desk_bottom], fill=_WOOD_BENCH)
    draw.line([(desk_x0, desk_top), (desk_x1, desk_top)], fill=_WOOD_PLANK_D, width=2)

    # Papers
    p_x0 = desk_x0 + (desk_x1-desk_x0)//6
    draw.rectangle([p_x0, desk_top-10, p_x0+30, desk_top-1],
                   fill=_PARCHMENT, outline=(100,85,55), width=1)
    draw.rectangle([p_x0+4, desk_top-14, p_x0+34, desk_top-4],
                   fill=(180, 165, 115), outline=(100,85,55), width=1)

    # Inkwell
    iw_cx = desk_x0 + (desk_x1-desk_x0)*2//3
    draw.ellipse([iw_cx-6, desk_top-12, iw_cx+6, desk_top],
                 fill=(15, 10, 8), outline=_IRON, width=1)
    draw.ellipse([iw_cx-4, desk_top-10, iw_cx+4, desk_top-4],
                 fill=(8, 8, 20))  # deep blue-black ink

    # Quill (diagonal line + small curve at top)
    q_x  = iw_cx + 10
    q_y0 = desk_top - 22
    q_y1 = desk_top - 2
    draw.line([(q_x, q_y1), (q_x-8, q_y0)], fill=_PARCHMENT, width=1)
    draw.arc([q_x-12, q_y0-4, q_x, q_y0+4], 200, 350, fill=_PARCHMENT, width=1)


def _draw_meditation_platform(
    draw: "ImageDraw.ImageDraw",
    W: int, H: int,
    cx: int, cy: int,
    radius: int,
) -> None:
    """Low stone platform for meditation."""
    # Stepped: outer ring (1 step) then inner surface
    STEP_H = max(3, radius // 8)
    outer  = (34, 32, 42)
    inner  = (28, 26, 36)
    draw.ellipse([cx-radius, cy-STEP_H, cx+radius, cy+STEP_H*2],
                 fill=outer, outline=_STONE_MORTAR, width=1)
    draw.ellipse([cx-radius+STEP_H*2, cy-1, cx+radius-STEP_H*2, cy+STEP_H],
                 fill=inner)


def _draw_ko_floor_spiral(
    draw: "ImageDraw.ImageDraw",
    W: int, H: int,
    cx: int, cy: int,
    radius: int,
) -> None:
    """Faint Ko-spiral etched into the meditation room floor."""
    N_SPIRALS = 7
    b = -0.25
    for k in range(N_SPIRALS):
        base = k * (2 * math.pi / N_SPIRALS)
        pts: list[tuple[float,float]] = []
        for j in range(60):
            t = base + j * (2 * math.pi / 60)
            r = radius * 0.7 * math.exp(b * t)
            if r < 1 or r > radius * 0.75:
                continue
            pts.append((cx + r*math.cos(t), cy + r*math.sin(t)))
        if len(pts) >= 2:
            # Very faint — near-floor-colour gold trace
            draw.line(pts, fill=(32, 28, 22), width=1)


def _window_light_spill(
    pix: object, W: int, H: int,
    window_rect: tuple[int,int,int,int],
    *,
    time_of_day: str,
    floor_y: int,
) -> None:
    x0, y0, x1, y1 = window_rect
    wx, wy = (x0+x1)/2.0, (y0+y1)/2.0
    if time_of_day == "night":
        light_col, max_reach, max_alpha = (18,28,52), W*0.40, 0.08
    elif time_of_day == "dawn":
        light_col, max_reach, max_alpha = (80,65,40), W*0.50, 0.18
    else:
        light_col, max_reach, max_alpha = (200,120,40), W*0.65, 0.30

    for py in range(H):
        for px in range(W):
            if x0 <= px <= x1 and y0 <= py <= y1:
                continue
            if py >= floor_y:
                continue
            dx   = px - wx
            dy   = py - wy
            dist = math.sqrt(dx*dx + dy*dy) + 0.1
            if dist >= max_reach:
                continue
            alpha = max(0.0, (1-dist/max_reach)**1.8) * max_alpha
            cur   = pix[px, py]
            pix[px, py] = (
                min(255, cur[0] + int((light_col[0]-cur[0])*alpha)),
                min(255, cur[1] + int((light_col[1]-cur[1])*alpha)),
                min(255, cur[2] + int((light_col[2]-cur[2])*alpha)),
            )


# ── Room renderers ─────────────────────────────────────────────────────────────

def render_foyer(
    *,
    time_of_day: str = "dawn",
    width: int = 512, height: int = 384,
) -> Optional[bytes]:
    """
    The foyer — entrance and public face of the shop.

    Layout:
      Back wall with front door (left) and narrow window (right)
      Long shop counter across the room (~60 % height)
      Stone floor below the counter

    Dawn variant shows cold light bleeding through the door gap —
    used for the Fate Knocks courier arrival scene.
    """
    if not _PIL_AVAILABLE:
        return None
    W, H = width, height
    img  = Image.new("RGB", (W, H), _STONE_BASE)
    draw = ImageDraw.Draw(img)
    pix  = img.load()

    FLOOR_Y   = int(H * 0.68)

    # Door: upper-left, occupies ~22 % of width, starts from floor, extends to ~82 % height
    DOOR_X0 = int(W * 0.07)
    DOOR_X1 = int(W * 0.29)
    DOOR_Y0 = int(H * 0.12)
    DOOR_Y1 = FLOOR_Y
    door_rect = (DOOR_X0, DOOR_Y0, DOOR_X1, DOOR_Y1)

    # Narrow window above-right
    WIN_X0 = int(W * 0.70)
    WIN_Y0 = int(H * 0.10)
    WIN_X1 = int(W * 0.88)
    WIN_Y1 = int(H * 0.36)
    win_rect = (WIN_X0, WIN_Y0, WIN_X1, WIN_Y1)

    _draw_stone_wall(draw, W, H, 0, FLOOR_Y,
                     window_rect=win_rect, door_rect=door_rect,
                     ambient_light=(DOOR_X1/W*0.6, 0.2 if time_of_day != "night" else 0.0))
    _draw_window(draw, W, H, win_rect, time_of_day=time_of_day, show_mountain=False)
    _draw_door(draw, pix, W, H, door_rect, time_of_day=time_of_day, ajar=True)

    # Shop counter runs from left edge to right (~40 % to 90 % of width)
    COUNTER_TOP    = int(H * 0.56)
    COUNTER_BOTTOM = int(H * 0.62)
    COUNTER_X0     = int(W * 0.05)
    COUNTER_X1     = int(W * 0.94)
    _draw_shop_counter(draw, W, COUNTER_TOP, COUNTER_BOTTOM, COUNTER_X0, COUNTER_X1)

    _draw_stone_floor(draw, W, H, FLOOR_Y)

    _window_light_spill(pix, W, H, win_rect, time_of_day=time_of_day, floor_y=FLOOR_Y)
    draw = ImageDraw.Draw(img)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_workbench_area(
    *,
    time_of_day: str = "late_afternoon",
    width: int = 512, height: int = 384,
) -> Optional[bytes]:
    """
    The workbench area — between foyer and kitchen.
    Alchemy workspace: shelved jars, workbench, brazier.
    """
    if not _PIL_AVAILABLE:
        return None
    W, H = width, height
    img  = Image.new("RGB", (W, H), _STONE_BASE)
    draw = ImageDraw.Draw(img)
    pix  = img.load()

    FLOOR_Y = int(H * 0.72)

    WIN_X0, WIN_Y0 = int(W*0.06), int(H*0.07)
    WIN_X1, WIN_Y1 = int(W*0.28), int(H*0.38)
    win_rect = (WIN_X0, WIN_Y0, WIN_X1, WIN_Y1)

    ambient = 0.80 if time_of_day != "night" else 0.15
    _draw_stone_wall(draw, W, H, 0, FLOOR_Y,
                     window_rect=win_rect,
                     ambient_light=(WIN_X1/W*0.5, ambient))
    _draw_window(draw, W, H, win_rect, time_of_day=time_of_day)
    _draw_shelf_row(draw, W, int(H*0.42), int(H*0.46), int(W*0.32), int(W*0.94),
                    6, jar_start=0)
    _draw_shelf_row(draw, W, int(H*0.55), int(H*0.59), int(W*0.52), int(W*0.94),
                    4, jar_start=2)
    _draw_workbench(draw, W, int(H*0.60), int(H*0.66), ambient_light=ambient)
    _draw_stone_floor(draw, W, H, FLOOR_Y)
    _window_light_spill(pix, W, H, win_rect, time_of_day=time_of_day, floor_y=FLOOR_Y)
    draw = ImageDraw.Draw(img)

    BRAZIER_CX   = int(W * 0.75)
    brazier_glow = 1.0 if time_of_day == "night" else 0.72
    _draw_brazier(draw, pix, W, H, BRAZIER_CX, FLOOR_Y, intensity=brazier_glow)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_kitchen(
    *,
    time_of_day: str = "late_afternoon",
    width: int = 512, height: int = 384,
) -> Optional[bytes]:
    """
    The kitchen — stone hearth (furnace) at center-back wall,
    rough table left, food shelves right.
    """
    if not _PIL_AVAILABLE:
        return None
    W, H = width, height
    img  = Image.new("RGB", (W, H), _STONE_BASE)
    draw = ImageDraw.Draw(img)
    pix  = img.load()

    FLOOR_Y = int(H * 0.72)

    # Narrow window — left side, high
    WIN_X0, WIN_Y0 = int(W*0.04), int(H*0.08)
    WIN_X1, WIN_Y1 = int(W*0.18), int(H*0.30)
    win_rect = (WIN_X0, WIN_Y0, WIN_X1, WIN_Y1)

    # Hearth: center of back wall
    HEARTH_W = int(W * 0.32)
    HEARTH_H = int(H * 0.42)
    HEARTH_X0 = (W - HEARTH_W) // 2
    HEARTH_Y0 = int(H * 0.04)
    HEARTH_X1 = HEARTH_X0 + HEARTH_W
    HEARTH_Y1 = HEARTH_Y0 + HEARTH_H
    hearth_rect = (HEARTH_X0, HEARTH_Y0, HEARTH_X1, HEARTH_Y1)

    hearth_intensity = 1.2 if time_of_day == "night" else 0.9
    _draw_stone_wall(draw, W, H, 0, FLOOR_Y,
                     window_rect=win_rect,
                     ambient_light=(0.40, 0.15 if time_of_day != "night" else 0.0))
    _draw_window(draw, W, H, win_rect, time_of_day=time_of_day, show_mountain=False)
    _draw_hearth(draw, pix, W, H, hearth_rect, intensity=hearth_intensity)
    draw = ImageDraw.Draw(img)

    # Food shelves (right side)
    _draw_shelf_row(draw, W, int(H*0.28), int(H*0.32), int(W*0.70), int(W*0.96),
                    3, jar_start=3)

    # Rough kitchen table (left-center)
    TABLE_X0 = int(W * 0.06)
    TABLE_X1 = int(W * 0.44)
    TABLE_TOP = int(H * 0.58)
    TABLE_BOT = int(H * 0.63)
    draw.rectangle([TABLE_X0, TABLE_TOP, TABLE_X1, TABLE_BOT], fill=_WOOD_SHELF)
    draw.line([(TABLE_X0, TABLE_TOP), (TABLE_X1, TABLE_TOP)],
              fill=_WOOD_PLANK_D, width=2)
    # Table legs
    for lx in (TABLE_X0+6, TABLE_X1-6):
        draw.rectangle([lx, TABLE_BOT, lx+5, min(TABLE_BOT+int(H*0.08), FLOOR_Y)],
                       fill=_WOOD_SHELF)
    # Basket on floor
    basket_cx = int(W * 0.22)
    basket_y  = FLOOR_Y - int(H * 0.06)
    draw.ellipse([basket_cx-14, basket_y-8, basket_cx+14, basket_y+6],
                 fill=(75, 55, 25), outline=(50, 35, 12), width=1)
    draw.arc([basket_cx-14, basket_y-14, basket_cx+14, basket_y-4],
             200, 340, fill=(90,65,30), width=2)

    _draw_stone_floor(draw, W, H, FLOOR_Y)
    _window_light_spill(pix, W, H, win_rect, time_of_day=time_of_day, floor_y=FLOOR_Y)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_bedroom(
    *,
    time_of_day: str = "dawn",
    rumpled: bool = True,
    width: int = 512, height: int = 384,
) -> Optional[bytes]:
    """
    The bedroom — wooden floor, stone wall, bed against the right wall.
    Dawn variant is used for the Fate Knocks opening (player wakes up).
    rumpled=True shows slept-in bedding.
    """
    if not _PIL_AVAILABLE:
        return None
    W, H = width, height
    img  = Image.new("RGB", (W, H), _STONE_BASE)
    draw = ImageDraw.Draw(img)
    pix  = img.load()

    FLOOR_Y = int(H * 0.70)

    # Window: left side, high — shows dawn sky
    WIN_X0, WIN_Y0 = int(W*0.07), int(H*0.09)
    WIN_X1, WIN_Y1 = int(W*0.26), int(H*0.34)
    win_rect = (WIN_X0, WIN_Y0, WIN_X1, WIN_Y1)

    ambient = 0.30 if time_of_day == "dawn" else (0.75 if time_of_day == "late_afternoon" else 0.05)
    _draw_stone_wall(draw, W, H, 0, FLOOR_Y,
                     window_rect=win_rect,
                     ambient_light=(WIN_X1/W*0.4, ambient))
    _draw_window(draw, W, H, win_rect, time_of_day=time_of_day, show_mountain=True)

    # Bed against back wall, right side
    BED_X0  = int(W * 0.45)
    BED_X1  = int(W * 0.92)
    BED_TOP = int(H * 0.24)
    BED_BOT = int(H * 0.65)
    _draw_bed(draw, W, H, BED_X0, BED_X1, BED_TOP, BED_BOT, rumpled=rumpled)

    # Nightstand beside bed (left of bed)
    NS_X0 = int(W * 0.33)
    NS_X1 = int(W * 0.44)
    NS_TOP = int(H * 0.52)
    NS_BOT = int(H * 0.65)
    draw.rectangle([NS_X0, NS_TOP, NS_X1, NS_BOT], fill=_WOOD_BENCH)
    draw.line([(NS_X0, NS_TOP), (NS_X1, NS_TOP)], fill=_WOOD_PLANK_D, width=1)
    # Candle on nightstand
    c_cx = (NS_X0 + NS_X1) // 2
    draw.rectangle([c_cx-3, NS_TOP-12, c_cx+3, NS_TOP], fill=(210, 200, 175))
    draw.ellipse([c_cx-2, NS_TOP-16, c_cx+2, NS_TOP-11], fill=(255, 200, 80))

    # Coat hook right wall edge with coat
    hook_x = int(W * 0.96)
    hook_y = int(H * 0.30)
    draw.rectangle([hook_x-4, hook_y, hook_x, hook_y+4], fill=_IRON)
    draw.arc([hook_x-20, hook_y, hook_x+4, hook_y+30], 10, 170, fill=_WOOD_SHELF, width=6)

    _draw_wooden_floor(draw, W, H, FLOOR_Y)

    # Small rug under the bed (slightly lighter patch on floor)
    rug_y = FLOOR_Y + 4
    draw.rectangle([BED_X0-10, rug_y, BED_X1+10, rug_y + int(H*0.06)],
                   fill=(35, 28, 40), outline=(28, 22, 32), width=1)

    _window_light_spill(pix, W, H, win_rect, time_of_day=time_of_day, floor_y=FLOOR_Y)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_meditation_room(
    *,
    time_of_day: str = "late_afternoon",
    width: int = 512, height: int = 384,
) -> Optional[bytes]:
    """
    The meditation room — almost empty.
    Low stone platform at center. Slit window. Faint Ko spiral on floor.
    The emptiness is intentional.
    """
    if not _PIL_AVAILABLE:
        return None
    W, H = width, height
    img  = Image.new("RGB", (W, H), _STONE_BASE)
    draw = ImageDraw.Draw(img)
    pix  = img.load()

    FLOOR_Y = int(H * 0.72)

    # Slit window — very narrow, high center
    WIN_X0 = W//2 - 8
    WIN_Y0 = int(H * 0.06)
    WIN_X1 = W//2 + 8
    WIN_Y1 = int(H * 0.28)
    win_rect = (WIN_X0, WIN_Y0, WIN_X1, WIN_Y1)

    ambient = 0.20 if time_of_day != "night" else 0.0
    _draw_stone_wall(draw, W, H, 0, FLOOR_Y,
                     window_rect=win_rect,
                     ambient_light=(0.5, ambient))

    # Slit window (no mountain — too narrow)
    _draw_window(draw, W, H, win_rect, time_of_day=time_of_day, show_mountain=False)

    _draw_stone_floor(draw, W, H, FLOOR_Y)

    # Ko spiral etched in floor
    spiral_cx = W // 2
    spiral_cy = FLOOR_Y + int(H * 0.10)
    _draw_ko_floor_spiral(draw, W, H, spiral_cx, spiral_cy, radius=int(W*0.14))

    # Low meditation platform
    platform_cx = W // 2
    platform_cy = FLOOR_Y + int(H * 0.06)
    _draw_meditation_platform(draw, W, H, platform_cx, platform_cy, radius=int(W*0.10))

    # Single oil lamp on the floor (left)
    lamp_cx = int(W * 0.22)
    lamp_y  = FLOOR_Y - int(H * 0.04)
    draw.ellipse([lamp_cx-8, lamp_y-6, lamp_cx+8, lamp_y+4],
                 fill=_IRON_WARM, outline=_IRON, width=1)
    draw.ellipse([lamp_cx-4, lamp_y-10, lamp_cx+4, lamp_y-5],
                 fill=(255, 200, 80))   # flame

    _window_light_spill(pix, W, H, win_rect, time_of_day=time_of_day, floor_y=FLOOR_Y)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_study(
    *,
    time_of_day: str = "late_afternoon",
    width: int = 512, height: int = 384,
) -> Optional[bytes]:
    """
    The study — bookshelves left, writing desk under right window.
    Warm candlelight. Wooden floor.
    """
    if not _PIL_AVAILABLE:
        return None
    W, H = width, height
    img  = Image.new("RGB", (W, H), _STONE_BASE)
    draw = ImageDraw.Draw(img)
    pix  = img.load()

    FLOOR_Y = int(H * 0.70)

    # Window: right side, taller — light falls on desk
    WIN_X0 = int(W * 0.68)
    WIN_Y0 = int(H * 0.06)
    WIN_X1 = int(W * 0.88)
    WIN_Y1 = int(H * 0.42)
    win_rect = (WIN_X0, WIN_Y0, WIN_X1, WIN_Y1)

    ambient = 0.70 if time_of_day == "late_afternoon" else (0.20 if time_of_day == "dawn" else 0.05)
    _draw_stone_wall(draw, W, H, 0, FLOOR_Y,
                     window_rect=win_rect,
                     ambient_light=(WIN_X0/W, ambient))
    _draw_window(draw, W, H, win_rect, time_of_day=time_of_day, show_mountain=False)

    # Bookshelves: left portion of back wall
    SHELF_X0 = int(W * 0.04)
    SHELF_X1 = int(W * 0.58)
    SHELF_Y0 = int(H * 0.10)
    TIER_H   = int(H * 0.22)
    _draw_bookshelves(draw, W, SHELF_X0, SHELF_X1, SHELF_Y0, tiers=2, tier_h=TIER_H)

    # Writing desk under the window
    DESK_X0  = int(W * 0.58)
    DESK_X1  = int(W * 0.94)
    DESK_TOP = int(H * 0.55)
    DESK_BOT = int(H * 0.62)
    _draw_writing_desk(draw, W, DESK_X0, DESK_X1, DESK_TOP, DESK_BOT)

    # Desk chair (simple rectangular suggestion)
    CHAIR_X0 = int(W * 0.63)
    CHAIR_X1 = int(W * 0.85)
    CHAIR_TOP = int(H * 0.62)
    CHAIR_BOT = int(H * 0.68)
    draw.rectangle([CHAIR_X0, CHAIR_TOP, CHAIR_X1, CHAIR_BOT],
                   fill=_WOOD_BENCH, outline=_WOOD_PLANK_D, width=1)

    _draw_wooden_floor(draw, W, H, FLOOR_Y)
    _window_light_spill(pix, W, H, win_rect, time_of_day=time_of_day, floor_y=FLOOR_Y)

    # Candle on desk (after light spill so it's always visible)
    draw = ImageDraw.Draw(img)
    c_cx = DESK_X0 + (DESK_X1-DESK_X0)//6
    draw.rectangle([c_cx-3, DESK_TOP-14, c_cx+3, DESK_TOP], fill=(210,200,175))
    draw.ellipse([c_cx-2, DESK_TOP-18, c_cx+2, DESK_TOP-13], fill=(255,200,80))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Dispatch ──────────────────────────────────────────────────────────────────

def render_home_room(
    room: str | HomeRoom,
    *,
    time_of_day: str = "late_afternoon",
    width:  int = 512,
    height: int = 384,
    **kwargs,
) -> Optional[bytes]:
    """
    Render any room of the Wiltoll Lane home by name.

    Parameters
    ----------
    room:
        One of: ``"foyer"``, ``"workbench"``, ``"kitchen"``,
        ``"bedroom"``, ``"meditation"``, ``"study"``.
        Accepts :class:`HomeRoom` enum values or plain strings.
    time_of_day:
        ``"dawn"`` | ``"late_afternoon"`` | ``"night"``
    width, height:
        Image dimensions.  Default 512×384.
    **kwargs:
        Extra arguments forwarded to the room renderer
        (e.g. ``rumpled=True`` for bedroom).
    """
    room = HomeRoom(str(room).lower().split(".")[-1])
    dispatch = {
        HomeRoom.FOYER:      render_foyer,
        HomeRoom.WORKBENCH:  render_workbench_area,
        HomeRoom.KITCHEN:    render_kitchen,
        HomeRoom.BEDROOM:    render_bedroom,
        HomeRoom.MEDITATION: render_meditation_room,
        HomeRoom.STUDY:      render_study,
    }
    fn = dispatch[room]
    return fn(time_of_day=time_of_day, width=width, height=height, **kwargs)


# ── Backward-compatible alias ─────────────────────────────────────────────────

def render_wiltoll_lane_interior(
    *,
    time_of_day: str = "late_afternoon",
    width:  int = 512,
    height: int = 384,
) -> Optional[bytes]:
    """
    Backward-compatible alias — renders the workbench area.
    The workbench area is the room originally called 'the interior'.
    """
    return render_workbench_area(
        time_of_day=time_of_day, width=width, height=height,
    )