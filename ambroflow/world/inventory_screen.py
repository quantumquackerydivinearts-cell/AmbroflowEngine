"""
InventoryScreen — PIL renderer for the player inventory overlay.

Shows all held items grouped and sorted by ID, with KLOB names resolved
from the object registry and KLIT names from the canonical 7_KLGS table.
Cursor navigates with ↑↓; selected item shows its note/description.
"""

from __future__ import annotations

from typing import Optional

_BG    = (12, 12, 20)
_PANEL = (28, 22, 42)
_GOLD  = (210, 175, 80)
_WHITE = (230, 225, 215)
_DIM   = (120, 115, 105)
_CYAN  = (80, 190, 190)
_GREEN = (80, 170, 90)

# ── Canonical KLIT name table (mirrors game7Registry.js ITEMS) ────────────────

_KLIT_NAMES: dict[str, str] = {
    "0001_KLIT": "Cherry",               "0002_KLIT": "Apple",
    "0003_KLIT": "Pomegranate",          "0004_KLIT": "Barley",
    "0005_KLIT": "Pine Needle",          "0006_KLIT": "Acorn",
    "0007_KLIT": "Lotus Flower",         "0008_KLIT": "Lotus Seed",
    "0009_KLIT": "Pine Nut",             "0010_KLIT": "Necklace",
    "0011_KLIT": "Ring",                 "0012_KLIT": "Ingot",
    "0013_KLIT": "Coin",                 "0014_KLIT": "Dagger",
    "0015_KLIT": "Sword",                "0016_KLIT": "Shield",
    "0017_KLIT": "Bow",                  "0018_KLIT": "Arrow",
    "0019_KLIT": "Staff",                "0021_KLIT": "Desire Crystal",
    "0022_KLIT": "Hypatia's Dagger",     "0023_KLIT": "Absinthe",
    "0024_KLIT": "Wormwood",             "0025_KLIT": "Anise",
    "0026_KLIT": "Fennel",               "0027_KLIT": "White Wine",
    "0028_KLIT": "Aqua Vitae",           "0029_KLIT": "Angelic Spear",
    "0030_KLIT": "Angelic Gun",          "0031_KLIT": "Demonic Irons",
    "0034_KLIT": "Basic Tincture",       "0035_KLIT": "Health Potion",
    "0036_KLIT": "Map of Mercurie",      "0037_KLIT": "Infernal Salve",
    "0038_KLIT": "Angelic Revival Salve","0040_KLIT": "Iron Ingot",
    "0041_KLIT": "Copper Ingot",         "0042_KLIT": "Gold Ingot",
    "0043_KLIT": "Silver Ingot",         "0044_KLIT": "Lead Ingot",
    "0045_KLIT": "Tin Ingot",            "0046_KLIT": "Nickel Ingot",
    "0050_KLIT": "Gold Coin",            "0051_KLIT": "Silver Coin",
    "0052_KLIT": "Copper Coin",          "0060_KLIT": "Gold Bullet",
    "0061_KLIT": "Iron Arrow",           "0062_KLIT": "Flint Arrow",
    "0070_KLIT": "Gunpowder",            "0081_KLIT": "Receiver",
    "0082_KLIT": "Transmitter",          "0083_KLIT": "Radio",
}

_KLOB_NOTE_CACHE: dict[str, tuple[str, str]] = {}   # id → (name, note)


def _klob_info(klob_id: str) -> tuple[str, str]:
    """Return (name, note) for a KLOB ID, cached after first lookup."""
    if klob_id not in _KLOB_NOTE_CACHE:
        try:
            from ..klob.registry import klob_registry
            obj = klob_registry().get(klob_id)
            if obj:
                _KLOB_NOTE_CACHE[klob_id] = (obj.name, obj.note or "")
            else:
                _KLOB_NOTE_CACHE[klob_id] = (klob_id, "")
        except Exception:
            _KLOB_NOTE_CACHE[klob_id] = (klob_id, "")
    return _KLOB_NOTE_CACHE[klob_id]


def _item_display(item_id: str) -> tuple[str, str]:
    """Return (display_name, note) for any item ID."""
    if item_id.endswith("_KLOB"):
        return _klob_info(item_id)
    if item_id.endswith("_KLIT"):
        name = _KLIT_NAMES.get(item_id, item_id)
        return name, ""
    return item_id, ""


def _load_font(size: int):
    try:
        from PIL import ImageFont
        return ImageFont.load_default(size=size)
    except Exception:
        from PIL import ImageFont
        return ImageFont.load_default()


def _to_png(img) -> bytes:
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class InventoryScreen:
    """Stateless PIL renderer for the inventory overlay."""

    _ROWS = 16   # visible rows in the list

    def render(
        self,
        inv_dict:   dict[str, int],
        cursor_idx: int,
        width:      int,
        height:     int,
    ) -> Optional[bytes]:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return None

        img  = Image.new("RGB", (width, height), _BG)
        draw = ImageDraw.Draw(img)

        title_font = _load_font(20)
        body_font  = _load_font(15)
        dim_font   = _load_font(13)

        pad = 48
        draw.rectangle((pad, pad, width - pad, height - pad), fill=_PANEL)

        # ── Header ────────────────────────────────────────────────────────────
        total = sum(inv_dict.values())
        draw.text((pad + 20, pad + 14), "Inventory",
                  font=title_font, fill=_GOLD)
        draw.text((width - pad - 120, pad + 16),
                  f"{len(inv_dict)} types  {total} total",
                  font=dim_font, fill=_DIM)
        draw.line([(pad + 20, pad + 40), (width - pad - 20, pad + 40)],
                  fill=_GOLD, width=1)

        # ── Build sorted item rows ────────────────────────────────────────────
        # Sort: KLIT first (carried items), then KLOB (apparatus/materials)
        def _sort_key(item_id: str) -> tuple[int, str]:
            if item_id.endswith("_KLIT"):
                return (0, item_id)
            if item_id.endswith("_KLOB"):
                return (1, item_id)
            return (2, item_id)

        rows = sorted(inv_dict.items(), key=lambda kv: _sort_key(kv[0]))

        if not rows:
            draw.text((pad + 20, pad + 60), "— empty —",
                      font=body_font, fill=_DIM)
            draw.text((pad + 20, height - pad - 20),
                      "Esc  close",
                      font=dim_font, fill=_DIM)
            return _to_png(img)

        cursor_idx = max(0, min(cursor_idx, len(rows) - 1))

        # Viewport window
        half   = self._ROWS // 2
        v_top  = max(0, cursor_idx - half)
        v_top  = min(v_top, max(0, len(rows) - self._ROWS))
        v_rows = rows[v_top:v_top + self._ROWS]

        # ── Item list ─────────────────────────────────────────────────────────
        col_id   = pad + 20
        col_name = pad + 160
        col_qty  = width - pad - 60

        y = pad + 52
        row_h = (height - pad - 90 - y) // self._ROWS
        row_h = max(18, min(row_h, 26))

        for rel_i, (item_id, qty) in enumerate(v_rows):
            abs_i   = v_top + rel_i
            selected = abs_i == cursor_idx
            name, _ = _item_display(item_id)

            if selected:
                draw.rectangle(
                    (pad + 10, y - 2, width - pad - 10, y + row_h - 4),
                    fill=(40, 36, 60),
                )
            color = _WHITE if selected else _DIM
            id_color = _CYAN if selected else (60, 120, 140)

            draw.text((col_id,   y), item_id, font=dim_font, fill=id_color)
            draw.text((col_name, y), name,    font=body_font, fill=color)
            qty_str = f"×{qty}"
            draw.text((col_qty, y), qty_str, font=body_font,
                      fill=_GOLD if selected else _DIM)
            y += row_h

        # Scroll indicator
        if len(rows) > self._ROWS:
            frac_top = v_top / max(1, len(rows) - self._ROWS)
            bar_h    = height - pad * 2 - 80
            bar_x    = width - pad - 14
            draw.rectangle((bar_x, pad + 50, bar_x + 4, pad + 50 + bar_h),
                           fill=(40, 40, 60))
            thumb_y = pad + 50 + int(frac_top * (bar_h - 20))
            draw.rectangle((bar_x, thumb_y, bar_x + 4, thumb_y + 20),
                           fill=_DIM)

        # ── Selected item detail ───────────────────────────────────────────────
        sel_id, sel_qty = rows[cursor_idx]
        sel_name, sel_note = _item_display(sel_id)
        detail_y = height - pad - 52
        draw.line([(pad + 20, detail_y - 6), (width - pad - 20, detail_y - 6)],
                  fill=(50, 50, 70), width=1)
        draw.text((pad + 20, detail_y), sel_name,
                  font=body_font, fill=_WHITE)
        if sel_note:
            draw.text((pad + 20, detail_y + 18), sel_note,
                      font=dim_font, fill=_DIM)

        # ── Footer ────────────────────────────────────────────────────────────
        draw.text((pad + 20, height - pad - 18),
                  "↑↓  navigate    I / Esc  close",
                  font=dim_font, fill=_DIM)

        return _to_png(img)
