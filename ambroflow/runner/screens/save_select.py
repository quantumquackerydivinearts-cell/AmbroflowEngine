"""
Save / Profile Select Screen
=============================
Lists all player profiles with name, Game 7 status, last-seen time, and play
time.  NEW GAME and (if unlocked) NEW GAME+ entries appear below the profile
list.  A delete-confirmation bar replaces the navigation hint while active.

render_save_select(entries, selected_idx, ...) -> bytes (PNG)

Entry dict schema
-----------------
Profile entry:
    {"type": "profile", "player_id": str, "name": str,
     "last_seen_at": float, "game7_status": str, "play_time_seconds": float}

Action entry:
    {"type": "new_game"}
    {"type": "ng_plus"}
"""

from __future__ import annotations

import math
import time
from typing import Optional

try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False

from .common import (
    _load_font, text_size, to_png, draw_starfield,
    draw_ko_spiral, draw_rounded_rect,
)
from . import palette as P


# ── Layout constants ──────────────────────────────────────────────────────────

_CARD_H       = 88      # pixels per profile card
_ACTION_H     = 60      # pixels per new-game / ng+ action card
_CARD_GAP     = 6
_CARD_W_FRAC  = 0.62    # card width as fraction of window
_LIST_TOP     = 110     # y where the card list starts
_LIST_BOT_PAD = 80      # pixels reserved at bottom for the hint bar
_DOT_R        = 5       # status dot radius


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rel_time(ts: float) -> str:
    dt = time.time() - ts
    if dt < 60:
        return "just now"
    if dt < 3600:
        return f"{int(dt / 60)}m ago"
    if dt < 86400:
        return f"{int(dt / 3600)}h ago"
    if dt < 86400 * 7:
        return f"{int(dt / 86400)}d ago"
    if dt < 86400 * 30:
        return f"{int(dt / 86400 / 7)}w ago"
    return f"{int(dt / 86400 / 30)}mo ago"


def _fmt_playtime(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m:02d}m"


_STATUS_LABEL = {
    "not_started": "Not started",
    "in_progress":  "In progress",
    "complete":     "Complete",
}
_STATUS_COLOR = {
    "not_started": P.STATUS_IDLE,
    "in_progress":  P.STATUS_ACTIVE,
    "complete":     P.STATUS_DONE,
}


# ── Card renderers ────────────────────────────────────────────────────────────

def _draw_profile_card(
    draw:     "ImageDraw.ImageDraw",
    entry:    dict,
    x0:       int,
    y0:       int,
    w:        int,
    selected: bool,
) -> None:
    h         = _CARD_H
    bg        = P.CARD_ACTIVE if selected else P.CARD
    border    = P.BORDER_SELECT if selected else P.BORDER

    draw_rounded_rect(draw, (x0, y0, x0 + w, y0 + h), radius=4,
                      fill=bg, outline=border, width=2 if selected else 1)

    # Status dot
    status = entry.get("game7_status", "not_started")
    dot_col = _STATUS_COLOR.get(status, P.STATUS_IDLE)
    dot_cx  = x0 + 20
    dot_cy  = y0 + h // 2
    draw.ellipse([dot_cx - _DOT_R, dot_cy - _DOT_R,
                  dot_cx + _DOT_R, dot_cy + _DOT_R], fill=dot_col)

    # Name
    name_col  = P.TEXT_WHITE if selected else P.TEXT_PRIMARY
    name_font = _load_font(17)
    name_x    = x0 + 38
    name_y    = y0 + 14
    draw.text((name_x, name_y), entry.get("name", "?"), fill=name_col, font=name_font)

    # Detail row: status label + play time + last seen
    detail_font = _load_font(11)
    status_txt  = _STATUS_LABEL.get(status, status)
    playtime    = _fmt_playtime(entry.get("play_time_seconds", 0))
    last_seen   = _rel_time(entry.get("last_seen_at", time.time()))
    detail_txt  = f"Game 7  ·  {status_txt}   {playtime} played   last seen {last_seen}"
    draw.text((name_x, y0 + 40), detail_txt, fill=P.TEXT_DIM, font=detail_font)

    # Selected indicator (right edge)
    if selected:
        ind_font = _load_font(11)
        ind_txt  = "▶"
        iw, _    = text_size(draw, ind_txt, ind_font)
        draw.text((x0 + w - iw - 14, y0 + h // 2 - 6), ind_txt,
                  fill=P.KO_GOLD, font=ind_font)


def _draw_action_card(
    draw:        "ImageDraw.ImageDraw",
    label:       str,
    sublabel:    str,
    x0:          int,
    y0:          int,
    w:           int,
    selected:    bool,
    locked:      bool = False,
) -> None:
    h      = _ACTION_H
    bg     = P.CARD_ACTIVE if (selected and not locked) else P.CARD
    border = P.BORDER_SELECT if (selected and not locked) else P.BORDER

    draw_rounded_rect(draw, (x0, y0, x0 + w, y0 + h), radius=4,
                      fill=bg, outline=border, width=2 if (selected and not locked) else 1)

    lf    = _load_font(15)
    sf    = _load_font(10)
    col   = P.TEXT_DIM if locked else (P.TEXT_WHITE if selected else P.TEXT_PRIMARY)
    sub_c = (30, 28, 40) if locked else P.TEXT_DIM

    lw, lh = text_size(draw, label, lf)
    sw, _  = text_size(draw, sublabel, sf)

    total_h = lh + (8 + 12 if sublabel else 0)
    top_y   = y0 + (h - total_h) // 2

    draw.text(((x0 + x0 + w - lw) // 2, top_y), label, fill=col, font=lf)
    if sublabel:
        draw.text(((x0 + x0 + w - sw) // 2, top_y + lh + 8),
                  sublabel, fill=sub_c, font=sf)


# ── Main renderer ─────────────────────────────────────────────────────────────

def render_save_select(
    entries:             list[dict],
    selected_idx:        int,
    *,
    first_visible:       int   = 0,
    ng_plus_unlocked:    bool  = False,
    confirm_delete_name: str   = "",
    pulse:               float = 0.0,
    width:               int   = 1280,
    height:              int   = 800,
) -> Optional[bytes]:
    if not _PIL:
        return None

    W, H = width, height
    img  = Image.new("RGB", (W, H), P.VOID)
    draw_starfield(img, seed=0xB2E4, density=0.0010)
    draw = ImageDraw.Draw(img)

    # ── Header ────────────────────────────────────────────────────────────────
    # Small Ko spiral, top-left
    draw_ko_spiral(draw, cx=38, cy=38, radius=22,
                   col=P.KO_SPIRAL_DIM, turns=2.5, steps=120)

    title_font = _load_font(22)
    draw.text((72, 18), "Ko's Labyrinth", fill=P.KO_GOLD, font=title_font)

    sub_font = _load_font(11)
    draw.text((74, 46), "Select a profile or begin a new journey",
              fill=P.TEXT_DIM, font=sub_font)

    rule_x0 = 40
    rule_x1 = W - 40
    draw.line([rule_x0, 76, rule_x1, 76], fill=P.BORDER, width=1)

    # ── Card list ─────────────────────────────────────────────────────────────
    card_w    = int(W * _CARD_W_FRAC)
    card_x0   = (W - card_w) // 2
    list_bot  = H - _LIST_BOT_PAD

    # How many cards fit
    max_vis_profiles = max(1, (list_bot - _LIST_TOP) // (_CARD_H + _CARD_GAP))

    cur_y  = _LIST_TOP
    for rel_i, entry in enumerate(entries[first_visible:first_visible + max_vis_profiles]):
        abs_i    = first_visible + rel_i
        selected = (abs_i == selected_idx)
        kind     = entry.get("type", "profile")

        if kind == "profile":
            _draw_profile_card(draw, entry, card_x0, cur_y, card_w, selected)
            cur_y += _CARD_H + _CARD_GAP

        elif kind == "new_game":
            # Spacer line above action cards
            if rel_i > 0:
                draw.line([card_x0, cur_y + 2, card_x0 + card_w, cur_y + 2],
                          fill=P.BORDER, width=1)
                cur_y += 12
            _draw_action_card(draw, "New Game", "Start fresh", card_x0, cur_y,
                              card_w, selected, locked=False)
            cur_y += _ACTION_H + _CARD_GAP

        elif kind == "ng_plus":
            locked = not ng_plus_unlocked
            sub    = "Complete Game 7 to unlock" if locked else "Carry your sins forward"
            _draw_action_card(draw, "New Game +", sub, card_x0, cur_y,
                              card_w, selected, locked=locked)
            cur_y += _ACTION_H + _CARD_GAP

    # Scroll indicators
    if first_visible > 0:
        arr_font = _load_font(11)
        draw.text(((W - 60) // 2, _LIST_TOP - 16), "▲  more above",
                  fill=P.TEXT_DIM, font=arr_font)
    total_cards = len(entries)
    last_vis    = first_visible + max_vis_profiles
    if last_vis < total_cards:
        arr_font = _load_font(11)
        draw.text(((W - 60) // 2, cur_y + 4), "▼  more below",
                  fill=P.TEXT_DIM, font=arr_font)

    # ── Bottom hint bar ───────────────────────────────────────────────────────
    draw.line([rule_x0, H - _LIST_BOT_PAD + 4, rule_x1, H - _LIST_BOT_PAD + 4],
              fill=P.BORDER, width=1)

    hint_font = _load_font(11)
    hint_y    = H - _LIST_BOT_PAD + 14

    if confirm_delete_name:
        # Delete confirmation
        conf_txt = f"Delete  \"{confirm_delete_name}\"?   [DEL] confirm   [ESC] cancel"
        cw, _    = text_size(draw, conf_txt, hint_font)
        # Warm warning tint
        warn_col = (180, 80, 60)
        draw.text(((W - cw) // 2, hint_y), conf_txt, fill=warn_col, font=hint_font)
    else:
        hints = "↑ ↓  navigate     [enter]  select     [del]  delete profile     [esc]  back"
        hw, _ = text_size(draw, hints, hint_font)
        draw.text(((W - hw) // 2, hint_y), hints, fill=P.TEXT_DIM, font=hint_font)

    # Pulse highlight on selected card border (subtle gold shimmer)
    shimmer_alpha = int(30 + 20 * math.sin(pulse * math.pi * 2))
    # (cosmetic only; already handled by CARD_ACTIVE fill above)
    _ = shimmer_alpha   # reserved for future use

    return to_png(img)
