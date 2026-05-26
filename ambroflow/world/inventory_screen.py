"""
InventoryScreen — PIL renderer for the player inventory overlay.

Two tabs:
  Items      — all carried items, sorted, qty shown.  Equippable items
               show an [E] hint; Enter equips the selected item.
  Equipment  — five slots (Weapon / Armor / Ring I / Ring II / Clothes).
               Enter unequips the selected slot back to the bag.

Names are resolved from the KLOB registry and the canonical KLIT table.
Raw IDs are never shown prominently — names only.
Tab key switches between tabs.
"""

from __future__ import annotations

from typing import Optional

_BG    = (12, 12, 20)
_PANEL = (28, 22, 42)
_GOLD  = (210, 175, 80)
_WHITE = (230, 225, 215)
_DIM   = (120, 115, 105)
_CYAN  = (80, 190, 190)
_GREEN = (80, 200, 100)
_TAB_A = (50, 44, 70)    # active tab bg
_TAB_I = (30, 26, 46)    # inactive tab bg

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

_KLOB_NOTE_CACHE: dict[str, tuple[str, str]] = {}


def _klob_info(klob_id: str) -> tuple[str, str]:
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
        return _KLIT_NAMES.get(item_id, item_id), ""
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

    _ROWS = 16

    def render(
        self,
        inv_dict:        dict[str, int],
        cursor_idx:      int,
        width:           int,
        height:          int,
        tab:             str = "items",       # "items" or "equipment"
        equipment_slots: Optional[dict] = None,
        equip_cursor:    int = 0,
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

        # ── Tab bar ───────────────────────────────────────────────────────────
        tab_y    = pad + 8
        tab_h    = 26
        tab_w    = 120
        tab_x0   = pad + 16
        tabs     = [("items", "Items"), ("equipment", "Equipment")]
        for i, (tid, tlabel) in enumerate(tabs):
            tx = tab_x0 + i * (tab_w + 4)
            bg = _TAB_A if tab == tid else _TAB_I
            draw.rectangle((tx, tab_y, tx + tab_w, tab_y + tab_h), fill=bg)
            fc = _GOLD if tab == tid else _DIM
            draw.text((tx + 10, tab_y + 5), tlabel, font=body_font, fill=fc)

        sep_y = tab_y + tab_h + 4
        draw.line([(pad + 10, sep_y), (width - pad - 10, sep_y)],
                  fill=(50, 46, 70), width=1)

        content_top = sep_y + 8

        if tab == "items":
            self._render_items(
                draw, inv_dict, cursor_idx,
                pad, content_top, width, height,
                body_font, dim_font, equipment_slots,
            )
        else:
            self._render_equipment(
                draw, equipment_slots or {}, equip_cursor,
                pad, content_top, width, height,
                title_font, body_font, dim_font,
            )

        return _to_png(img)

    # ── Items tab ─────────────────────────────────────────────────────────────

    def _render_items(self, draw, inv_dict, cursor_idx,
                      pad, top, width, height,
                      body_font, dim_font, equipment_slots):
        from ..inventory.equipment import EQUIPPABLE

        def _sort_key(item_id: str) -> tuple[int, str]:
            if item_id.endswith("_KLIT"):
                return (0, item_id)
            if item_id.endswith("_KLOB"):
                return (1, item_id)
            return (2, item_id)

        rows = sorted(inv_dict.items(), key=lambda kv: _sort_key(kv[0]))

        if not rows:
            draw.text((pad + 20, top + 10), "— nothing carried —",
                      font=body_font, fill=_DIM)
            self._footer(draw, "Tab  equipment    I / Esc  close",
                         pad, width, height, dim_font)
            return

        cursor_idx = max(0, min(cursor_idx, len(rows) - 1))

        half  = self._ROWS // 2
        v_top = max(0, cursor_idx - half)
        v_top = min(v_top, max(0, len(rows) - self._ROWS))
        v_rows = rows[v_top:v_top + self._ROWS]

        col_name = pad + 20
        col_qty  = width - pad - 60

        list_h   = height - pad - 90 - top
        row_h    = max(18, min(list_h // self._ROWS, 26))

        y = top
        for rel_i, (item_id, qty) in enumerate(v_rows):
            abs_i    = v_top + rel_i
            selected = abs_i == cursor_idx
            name, _  = _item_display(item_id)
            equippable = item_id in EQUIPPABLE

            if selected:
                draw.rectangle(
                    (pad + 10, y - 2, width - pad - 10, y + row_h - 4),
                    fill=(40, 36, 60),
                )

            fc = _WHITE if selected else _DIM
            draw.text((col_name, y), name, font=body_font, fill=fc)

            if equippable and selected:
                draw.text((col_name + 200, y), "[E]", font=dim_font, fill=_GREEN)

            qty_str = f"×{qty}" if qty > 1 else ""
            if qty_str:
                draw.text((col_qty, y), qty_str, font=body_font,
                          fill=_GOLD if selected else _DIM)
            y += row_h

        if len(rows) > self._ROWS:
            frac_top = v_top / max(1, len(rows) - self._ROWS)
            bar_h  = height - pad * 2 - 80
            bar_x  = width - pad - 14
            draw.rectangle((bar_x, top, bar_x + 4, top + bar_h), fill=(40, 40, 60))
            thumb_y = top + int(frac_top * (bar_h - 20))
            draw.rectangle((bar_x, thumb_y, bar_x + 4, thumb_y + 20), fill=_DIM)

        # Detail line for selected item
        sel_id, _ = rows[cursor_idx]
        sel_name, sel_note = _item_display(sel_id)
        detail_y = height - pad - 52
        draw.line([(pad + 20, detail_y - 6), (width - pad - 20, detail_y - 6)],
                  fill=(50, 50, 70), width=1)
        draw.text((pad + 20, detail_y), sel_name, font=body_font, fill=_WHITE)
        if sel_note:
            draw.text((pad + 20, detail_y + 18), sel_note, font=dim_font, fill=_DIM)

        hint = "↑↓  navigate    Tab  equipment    Enter  equip    I / Esc  close"
        self._footer(draw, hint, pad, width, height, dim_font)

    # ── Equipment tab ─────────────────────────────────────────────────────────

    def _render_equipment(self, draw, slots_dict, equip_cursor,
                          pad, top, width, height,
                          title_font, body_font, dim_font):
        from ..inventory.equipment import SLOT_ORDER, SLOT_LABELS

        label_x  = pad + 28
        value_x  = pad + 140
        row_h    = 34

        for i, slot in enumerate(SLOT_ORDER):
            selected = i == equip_cursor
            item_id  = slots_dict.get(slot)
            y        = top + i * row_h

            if selected:
                draw.rectangle(
                    (pad + 10, y - 2, width - pad - 10, y + row_h - 6),
                    fill=(40, 36, 60),
                )

            lc = _GOLD if selected else _DIM
            draw.text((label_x, y + 6), SLOT_LABELS[slot], font=dim_font, fill=lc)

            if item_id:
                name, _ = _item_display(item_id)
                fc = _WHITE if selected else (160, 155, 145)
                draw.text((value_x, y + 5), name, font=body_font, fill=fc)
                if selected:
                    draw.text((value_x + 200, y + 7), "[unequip]",
                              font=dim_font, fill=_DIM)
            else:
                draw.text((value_x, y + 5), "—", font=dim_font, fill=(60, 58, 72))

        # Separator
        sep_y = top + len(SLOT_ORDER) * row_h + 8
        draw.line([(pad + 20, sep_y), (width - pad - 20, sep_y)],
                  fill=(50, 50, 70), width=1)

        # Detail: show selected slot's item note if any
        sel_slot = SLOT_ORDER[equip_cursor] if equip_cursor < len(SLOT_ORDER) else None
        if sel_slot:
            item_id = slots_dict.get(sel_slot)
            if item_id:
                _, note = _item_display(item_id)
                if note:
                    draw.text((pad + 20, sep_y + 8), note,
                              font=dim_font, fill=_DIM)

        hint = "↑↓  navigate    Tab  items    Enter  unequip    I / Esc  close"
        self._footer(draw, hint, pad, width, height, dim_font)

    # ── Shared ────────────────────────────────────────────────────────────────

    @staticmethod
    def _footer(draw, text: str, pad, width, height, font) -> None:
        draw.text((pad + 20, height - pad - 18), text, font=font, fill=_DIM)
