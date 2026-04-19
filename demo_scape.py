"""
Demo Scape — Wiltoll Lane (Lapidus)
====================================
A playable preview of the HD-2D render pipeline.

What this shows
---------------
  • Octopath-style fixed-pitch perspective camera (35° down, 35° FOV)
  • Tiled ground plane in 3-D world space — multiple tile kinds painted
    from a PIL-generated atlas (stone path, grass verge, dirt, water, wall)
  • Y-locked billboard sprites: two townsfolk silhouettes + a tree
  • Smooth exponential-lerp camera follow (WASD to move the player marker)
  • Depth-of-field — near tiles and far tiles soften, midground sharp
  • Lapidus color grade — warm amber highlights, violet shadow, vignette
  • PIL dialogue panel rendered live each frame as a GL texture

Controls
--------
  WASD / Arrow keys  move player
  ESC                quit

Run from repo root:
    python demo_scape.py
"""

import sys
import math
import time

import glm
import numpy as np
from OpenGL import GL

sys.path.insert(0, str(__file__).replace("demo_scape.py", ""))

from ambroflow.engine.window      import Window, InputEvent
from ambroflow.engine.camera      import Camera
from ambroflow.engine.framebuffer import Framebuffer
from ambroflow.engine.texture     import Texture
from ambroflow.render.world       import WorldRenderer
from ambroflow.render.sprite      import SpriteRenderer
from ambroflow.render.post        import PostProcessor
from ambroflow.render.ui          import UIRenderer

from ambroflow.world.map import (
    Zone, Realm, WorldTileKind, build_zone_from_ascii
)

from PIL import Image, ImageDraw


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1.  TILE ATLAS  — PIL-generated 512×512, 8 columns × 1 row  (64×64 px / tile)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TILE_PX   = 64          # pixels per tile
ATLAS_COLS = 8
ATLAS_ROWS = 1
ATLAS_W   = TILE_PX * ATLAS_COLS
ATLAS_H   = TILE_PX * ATLAS_ROWS

def _tile(r, g, b, style="flat", seed=0):
    img  = Image.new("RGBA", (TILE_PX, TILE_PX), (r, g, b, 255))
    draw = ImageDraw.Draw(img)
    if style == "mortar":
        # Stone floor — grey base + mortar grid lines
        for i in range(0, TILE_PX, 16):
            draw.line([(i, 0), (i, TILE_PX)], fill=(r-20, g-20, b-20, 255), width=2)
            draw.line([(0, i), (TILE_PX, i)], fill=(r-20, g-20, b-20, 255), width=2)
        # Slight per-stone colour variation
        for ty in range(0, TILE_PX, 16):
            for tx in range(0, TILE_PX, 16):
                v = (tx * 7 + ty * 13 + seed * 31) % 20 - 10
                draw.rectangle([tx+2, ty+2, tx+13, ty+13],
                                fill=(r+v, g+v, b+v, 255))
    elif style == "grass":
        # Grass — green base + darker blades
        import random; rng = random.Random(seed)
        for _ in range(60):
            x = rng.randint(0, TILE_PX - 1)
            y = rng.randint(0, TILE_PX - 1)
            v = rng.randint(-15, 15)
            draw.point((x, y), fill=(r+v, g+v+5, b+v, 255))
    elif style == "water":
        # Water — blue base + lighter ripple lines
        for i in range(0, TILE_PX, 8):
            alpha = 200 + (i % 3) * 18
            draw.line([(0, i), (TILE_PX, i)],
                      fill=(r-10, g, b+20, alpha), width=1)
    elif style == "dirt":
        # Dirt — warm brown + small pebbles
        import random; rng = random.Random(seed + 99)
        for _ in range(30):
            x = rng.randint(0, TILE_PX - 3)
            y = rng.randint(0, TILE_PX - 3)
            draw.ellipse([x, y, x+3, y+3], fill=(r+20, g+10, b, 255))
    elif style == "wall":
        # Wall top — dark stone with highlight edge
        draw.rectangle([0, 0, TILE_PX-1, 3],
                        fill=(r+30, g+30, b+30, 255))   # top highlight
        draw.rectangle([0, TILE_PX-4, TILE_PX-1, TILE_PX-1],
                        fill=(r-20, g-20, b-20, 255))   # bottom shadow
        for i in range(0, TILE_PX, 16):
            draw.line([(i, 0), (i, TILE_PX)], fill=(r-15, g-15, b-15, 255), width=1)
    elif style == "void":
        # Void — transparent black (won't be rendered if alpha=0)
        img.putalpha(0)
    elif style == "bridge":
        # Bridge / wood planks
        for i in range(0, TILE_PX, 8):
            v = 10 if (i // 8) % 2 == 0 else -5
            draw.rectangle([0, i, TILE_PX, i+7], fill=(r+v, g+v, b+v, 255))
    return img


def make_atlas() -> Image.Image:
    atlas = Image.new("RGBA", (ATLAS_W, ATLAS_H))
    tiles = [
        # idx  r    g    b    style      seed
        (0,  148, 140, 130, "mortar",   1),   # stone floor
        (1,   70, 110,  55, "grass",    2),   # grass
        (2,  120,  90,  60, "dirt",     3),   # dirt / road
        (3,   60,  55,  70, "wall",     4),   # wall top
        (4,   50,  80, 140, "water",    5),   # water
        (5,  130, 122, 115, "mortar",  17),   # stone plaza (lighter)
        (6,    0,   0,   0, "void",     0),   # void
        (7,  140, 100,  60, "bridge",   8),   # bridge / wood
    ]
    for idx, r, g, b, style, seed in tiles:
        tile_img = _tile(r, g, b, style=style, seed=seed)
        atlas.paste(tile_img, (idx * TILE_PX, 0))
    return atlas


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2.  SPRITE ATLAS  — PIL-generated silhouettes (256×64 px, 4 frames × 64px)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SPR_PX = 64

def _figure(r, g, b, hat_col=(80, 60, 40)):
    """Simple humanoid silhouette: head + body + legs."""
    img  = Image.new("RGBA", (SPR_PX, SPR_PX * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    W, H = SPR_PX, SPR_PX * 2
    # Legs
    draw.rectangle([W//2-7, H-24, W//2-2,  H-2],  fill=(r-20, g-20, b-20, 255))
    draw.rectangle([W//2+2, H-24, W//2+7,  H-2],  fill=(r-20, g-20, b-20, 255))
    # Body
    draw.rectangle([W//2-10, H//2+6, W//2+10, H-24], fill=(r, g, b, 255))
    # Arms
    draw.rectangle([W//2-16, H//2+8, W//2-10, H//2+28], fill=(r, g, b, 255))
    draw.rectangle([W//2+10, H//2+8, W//2+16, H//2+28], fill=(r, g, b, 255))
    # Head
    draw.ellipse([W//2-9, H//2-8, W//2+9, H//2+8],   fill=(210, 175, 130, 255))
    # Hat
    draw.rectangle([W//2-10, H//2-14, W//2+10, H//2-6], fill=hat_col)
    draw.rectangle([W//2-13, H//2-8,  W//2+13, H//2-4], fill=hat_col)
    return img


def _tree():
    img  = Image.new("RGBA", (SPR_PX, SPR_PX * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    W, H = SPR_PX, SPR_PX * 2
    # Trunk
    draw.rectangle([W//2-5, H-32, W//2+5, H-2], fill=(90, 60, 30, 255))
    # Canopy — three overlapping ellipses for depth
    draw.ellipse([W//2-22, H//2-30, W//2+22, H//2+20], fill=(45, 90, 40, 220))
    draw.ellipse([W//2-16, H//2-48, W//2+16, H//2+0],  fill=(55, 110, 45, 230))
    draw.ellipse([W//2-10, H//2-60, W//2+10, H//2-16], fill=(65, 130, 50, 255))
    return img


def make_sprite_atlas() -> Image.Image:
    # 4 sprites side by side in one 256×128 atlas
    atlas = Image.new("RGBA", (SPR_PX * 4, SPR_PX * 2), (0, 0, 0, 0))
    sprites = [
        (0, _figure(80,  90, 130, hat_col=(60, 40, 80))),   # townsfolk A (blue-grey)
        (1, _figure(160, 100, 70, hat_col=(100, 70, 30))),  # townsfolk B (warm brown)
        (2, _tree()),                                         # tree
        (3, _figure(50,  50,  60, hat_col=(30, 30, 40))),   # guard (dark)
    ]
    for idx, spr in sprites:
        atlas.paste(spr, (idx * SPR_PX, 0))
    return atlas


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3.  ZONE MAP  — Wiltoll Lane preview (not canonical, for scape framing only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_MAP = [
    "###################",
    "#,,,,,,,,,,,,,,,,,#",
    "#,,,S,S,S,S,S,,,,,#",
    "#,,S.,.,.,.,S,,,,~#",
    "#,,S.,.,@,.,S,,,,~#",
    "#,,S.,.,.,.,S,,,,~#",
    "#,,S.,=,=,.,S,,,,,#",
    "#,,,,,=,=,,,,,,,,,#",
    "#,,,D,=,=,D,,,,,,,#",
    "#,,,D,=,=,D,,,,,,,#",
    "#,,,D,=,=,D,,,,,,,#",
    "#,,,,,,,,,,,,,,,,,#",
    "###################",
]

_ZONE = build_zone_from_ascii(
    zone_id="wiltoll_preview",
    realm=Realm.LAPIDUS,
    name="Wiltoll Lane",
    rows=_MAP,
)

# Sprite world positions (x, z) — placed in the scene manually
_SPRITE_PLACEMENTS = [
    # (world_x, world_z, sprite_idx, label)
    (6.5,  2.5, 0, "townsfolk A"),   # near the plaza
    (11.5, 4.0, 1, "townsfolk B"),   # east side
    (14.5, 3.5, 2, "tree"),           # corner
    (2.5,  9.5, 3, "guard"),          # southern road
]

# Sprite atlas UV layout: 4 sprites, each 1/4 of atlas width, full height
_ATLAS_SPRITE_COLS = 4
_ATLAS_SPRITE_ROWS = 1


def _sprite_frame(idx: int):
    fw = 1.0 / _ATLAS_SPRITE_COLS
    fh = 1.0 / _ATLAS_SPRITE_ROWS
    return idx * fw, 0.0, fw, fh


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4.  DIALOGUE PANEL  (rebuilt each frame so text can update)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_PANEL_W, _PANEL_H = 900, 130

def build_dialogue(text: str, speaker: str = "") -> Image.Image:
    img  = Image.new("RGBA", (_PANEL_W, _PANEL_H), (14, 12, 22, 215))
    draw = ImageDraw.Draw(img)
    # Border
    draw.rectangle([3, 3, _PANEL_W-4, _PANEL_H-4],
                    outline=(140, 110, 190, 255), width=2)
    draw.rectangle([6, 6, _PANEL_W-7, _PANEL_H-7],
                    outline=(80, 60, 120, 120), width=1)
    if speaker:
        draw.text((18, 10), speaker, fill=(200, 170, 255, 255))
        draw.text((18, 34), text,    fill=(220, 215, 240, 255))
    else:
        draw.text((18, 22), text,    fill=(220, 215, 240, 255))
    return img


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5.  MAIN LOOP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> None:
    win = Window("Ko's Labyrinth — Wiltoll Lane (demo scape)", 1280, 720)
    win.make_current()

    W, H = win.width, win.height

    # ── Textures ────────────────────────────────────────────────────────────
    tile_atlas_img  = make_atlas()
    tile_atlas      = Texture.from_pil(tile_atlas_img)

    spr_atlas_img   = make_sprite_atlas()
    spr_atlas       = Texture.from_pil(spr_atlas_img)

    dialogue_tex    = Texture.from_pil(
        build_dialogue("Wiltoll Lane — HD-2D render demo", "[ Lapidus ]")
    )

    # ── Renderers ───────────────────────────────────────────────────────────
    world_r  = WorldRenderer.for_lapidus(tile_atlas,
                                          atlas_cols=ATLAS_COLS,
                                          atlas_rows=ATLAS_ROWS)
    world_r.load_zone(_ZONE)

    sprite_r = SpriteRenderer.default(spr_atlas)

    post     = PostProcessor(W, H, realm="lapidus",
                              focus_dist=12.0, focus_range=5.0, max_blur=14.0)
    ui       = UIRenderer()

    fbo      = Framebuffer(W, H)
    cam      = Camera(aspect=W / H,
                      fov_deg=35.0, pitch_deg=35.0, distance=18.0,
                      follow_speed=5.0)

    # ── Player state ─────────────────────────────────────────────────────────
    spawn_x, spawn_y = _ZONE.player_spawn
    px, pz = float(spawn_x), float(spawn_y)
    cam.target = glm.vec3(px, 0.0, pz)

    MOVE_SPEED = 4.0   # tiles per second

    t0 = time.perf_counter()
    dialogue_tex_dirty = False
    frames = 0

    # ── Dialogue lines — cycle every few seconds ─────────────────────────────
    _LINES = [
        ("[ Lapidus ]",   "Wiltoll Lane.  The stone road runs south to the Lottery Square."),
        ("[ Engine ]",    "Octopath HD-2D  •  OpenGL 4.1  •  PIL action layer  •  DoF post"),
        ("[ Controls ]",  "WASD / Arrows to move.  Camera follows via exponential lerp."),
        ("[ Scape ]",     "Tile atlas: PIL-generated.  Sprites: Y-locked billboards."),
    ]
    line_idx  = 0
    line_time = t0

    while not win.should_close():
        dt      = win.begin_frame()
        elapsed = time.perf_counter() - t0
        events  = win.consume_events()

        for ev in events:
            if ev == InputEvent.CANCEL:
                _shutdown(win, fbo, post, ui, world_r, sprite_r,
                          tile_atlas, spr_atlas, dialogue_tex)
                return

        # ── Player movement ───────────────────────────────────────────────
        move = glm.vec2(0.0, 0.0)
        if InputEvent.MOVE_NORTH in events: move.y -= 1.0
        if InputEvent.MOVE_SOUTH in events: move.y += 1.0
        if InputEvent.MOVE_EAST  in events: move.x += 1.0
        if InputEvent.MOVE_WEST  in events: move.x -= 1.0

        # Continuous key state isn't tracked yet — re-check held keys
        # via raw glfw state (temporary until InputState helper is added)
        import glfw
        h = win._handle
        if glfw.get_key(h, glfw.KEY_W) or glfw.get_key(h, glfw.KEY_UP):
            move.y -= 1.0
        if glfw.get_key(h, glfw.KEY_S) or glfw.get_key(h, glfw.KEY_DOWN):
            move.y += 1.0
        if glfw.get_key(h, glfw.KEY_A) or glfw.get_key(h, glfw.KEY_LEFT):
            move.x -= 1.0
        if glfw.get_key(h, glfw.KEY_D) or glfw.get_key(h, glfw.KEY_RIGHT):
            move.x += 1.0

        if glm.length(move) > 0.01:
            move = glm.normalize(move) * MOVE_SPEED * dt
            nx = max(1.0, min(float(_ZONE.width  - 2), px + move.x))
            nz = max(1.0, min(float(_ZONE.height - 2), pz + move.y))
            dest_kind = _ZONE.tile_at(int(nx), int(nz))
            from ambroflow.world.map import is_passable
            if is_passable(dest_kind):
                px, pz = nx, nz
            cam.target = glm.vec3(px, 0.0, pz)

        # ── Resize ────────────────────────────────────────────────────────
        nW, nH = win.width, win.height
        if nW != W or nH != H:
            W, H = nW, nH
            fbo.resize(W, H)
            post.resize(W, H)
            cam.resize(W / H)
            GL.glViewport(0, 0, W, H)

        # ── Dialogue rotation ─────────────────────────────────────────────
        if elapsed - (line_time - t0) > 4.0:
            line_idx  = (line_idx + 1) % len(_LINES)
            line_time = elapsed + t0
            speaker, text = _LINES[line_idx]
            dialogue_tex.update_pil(build_dialogue(text, speaker))

        cam.update(dt)

        # ── Scene → FBO ──────────────────────────────────────────────────
        fbo.bind()
        GL.glClearColor(0.12, 0.10, 0.20, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_DEPTH_TEST)

        world_r.draw(cam, time=elapsed)

        # Billboard sprites
        sprite_r.begin()
        for wx, wz, spr_idx, _label in _SPRITE_PLACEMENTS:
            fu, fv, fw, fh = _sprite_frame(spr_idx)
            sprite_r.add(
                world_pos=(wx, 0.0, wz),
                size=(0.9, 1.8),
                frame_u=fu, frame_v=fv, frame_w=fw, frame_h=fh,
            )
        # Player marker
        sprite_r.add(
            world_pos=(px, 0.0, pz),
            size=(0.9, 1.8),
            frame_u=0.0, frame_v=0.0,
            frame_w=1.0 / _ATLAS_SPRITE_COLS,
            frame_h=1.0,
        )
        sprite_r.end()
        sprite_r.draw(cam)

        fbo.unbind()

        # ── Post ─────────────────────────────────────────────────────────
        post.process(fbo, time=elapsed)
        post.blit_to_screen()

        # ── UI overlay ────────────────────────────────────────────────────
        GL.glViewport(0, 0, W, H)
        ui.add(dialogue_tex,
               ndc_rect=(-0.70, -1.0, 0.70, -0.60),
               opacity=0.94)
        ui.draw()
        ui.clear()

        win.end_frame()
        frames += 1

    elapsed_total = time.perf_counter() - t0
    print(f"[demo_scape] {frames} frames  {elapsed_total:.1f}s  "
          f"~{frames/elapsed_total:.0f} fps")
    _shutdown(win, fbo, post, ui, world_r, sprite_r, tile_atlas, spr_atlas, dialogue_tex)


def _shutdown(win, fbo, post, ui, world_r, sprite_r, tile_atlas, spr_atlas, dlg_tex):
    dlg_tex.delete()
    spr_atlas.delete()
    tile_atlas.delete()
    ui.delete()
    sprite_r.delete()
    world_r.delete()
    post.delete()
    fbo.delete()
    win.destroy()


if __name__ == "__main__":
    main()