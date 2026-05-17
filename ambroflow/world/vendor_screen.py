"""VendorScreen — PIL renderer for the buy-from-NPC overlay."""

from __future__ import annotations

from typing import Optional

_BG    = (12, 12, 20)
_PANEL = (28, 22, 42)
_GOLD  = (210, 175, 80)
_WHITE = (230, 225, 215)
_DIM   = (120, 115, 105)
_RED   = (190, 70, 60)
_GREEN = (80, 170, 90)
_CYAN  = (80, 190, 190)

_ITEM_NAMES: dict[str, str] = {
    # ── Botanical / consumable ingredients ────────────────────────────────────
    "0040_KLOB": "Water Flask",
    "0073_KLOB": "Herb (Common)",
    "0074_KLOB": "Herb (Restorative)",
    "0075_KLOB": "Binding Wax",
    "0076_KLOB": "Raw Desire Stone",
    "0077_KLOB": "Asmodean Essence",
    # ── Processing chemicals ──────────────────────────────────────────────────
    "1003_KLOB": "Diatom Earth",
    "1004_KLOB": "Glycerine",
    "1006_KLOB": "Saltpeter",
    "1007_KLOB": "Sulphur",
    "1008_KLOB": "Charcoal",
    "1015_KLOB": "Water",
    # ── Minerals ─────────────────────────────────────────────────────────────
    "3001_KLOB": "Granite",
    "3003_KLOB": "Chalk",
    "3005_KLOB": "Quartz",
    "3006_KLOB": "Pumice",
    # ── Lab apparatus (canonical IDs) ─────────────────────────────────────────
    "8000_KLOB": "Mortar",
    "2000_KLOB": "Pestle",
    "0001_KLOB": "Rag",
    "0002_KLOB": "Stand",
    "0003_KLOB": "Retort",
    "0004_KLOB": "Volume Flask",
    "0005_KLOB": "Reagent Bottle",
    "0006_KLOB": "Bellows",
    "0007_KLOB": "Crucible",
    "0008_KLOB": "Bottle",
    "0009_KLOB": "Jar",
    "0010_KLOB": "Crucible Tongs",
    "0020_KLOB": "Wooden Spoon",
    "0021_KLOB": "Copper Spoon",
    "0030_KLOB": "Furnace",
    # ── Metals ────────────────────────────────────────────────────────────────
    "2002_KLOB": "Iron",
    "2003_KLOB": "Gold",
    "2004_KLOB": "Copper",
    "2006_KLOB": "Silver",
    # ── KLIT currency ─────────────────────────────────────────────────────────
    "0050_KLIT": "Copper Coin",
    "0051_KLIT": "Silver Coin",
    "0052_KLIT": "Gold Coin",
}

COIN_ID  = "0050_KLIT"   # Copper Coin — base currency unit


# ── Well-stocked starting catalog ─────────────────────────────────────────────
#
# The player's home shop opens pre-stocked before the first letter arrives.
# Prices are in Copper Coins (0050_KLIT). The catalog is intentionally generous —
# the point is to let the player explore alchemy freely before the plot begins.

STARTING_CATALOG: list[tuple[str, int]] = [
    # Botanicals and consumables
    ("0073_KLOB", 2),   # Herb (Common)
    ("0074_KLOB", 4),   # Herb (Restorative)
    ("0075_KLOB", 5),   # Binding Wax
    ("0076_KLOB", 8),   # Raw Desire Stone
    ("0077_KLOB", 12),  # Asmodean Essence
    ("0040_KLOB", 1),   # Water Flask
    # Chemicals
    ("1007_KLOB", 3),   # Sulphur
    ("1008_KLOB", 2),   # Charcoal
    ("1006_KLOB", 4),   # Saltpeter
    ("1003_KLOB", 5),   # Diatom Earth
    ("1004_KLOB", 6),   # Glycerine
    ("1015_KLOB", 1),   # Water
    # Minerals
    ("3005_KLOB", 6),   # Quartz
    ("3003_KLOB", 2),   # Chalk
    ("3001_KLOB", 3),   # Granite
    ("3006_KLOB", 2),   # Pumice
    # Apparatus (for Study fine-processing setup)
    ("0005_KLOB", 4),   # Reagent Bottle
    ("0007_KLOB", 8),   # Crucible
    ("0009_KLOB", 3),   # Jar
    ("0020_KLOB", 2),   # Wooden Spoon
    ("0021_KLOB", 5),   # Copper Spoon
]


def _item_name(item_id: str) -> str:
    return _ITEM_NAMES.get(item_id, item_id)


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


class VendorScreen:
    """Stateless PIL renderer for the vendor purchase overlay."""

    def render(
        self,
        vendor_name: str,
        catalog:     list[tuple[str, int]],   # [(item_id, price), ...]
        cursor_idx:  int,
        coin_qty:    int,
        width:       int,
        height:      int,
    ) -> Optional[bytes]:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return None

        img  = Image.new("RGB", (width, height), _BG)
        draw = ImageDraw.Draw(img)

        title_font = _load_font(22)
        body_font  = _load_font(16)
        dim_font   = _load_font(14)

        pad   = 60
        panel = (pad, pad, width - pad, height - pad)
        draw.rectangle(panel, fill=_PANEL)

        draw.text((pad + 24, pad + 18), f"Trade — {vendor_name}", font=title_font, fill=_GOLD)
        draw.line([(pad + 24, pad + 48), (width - pad - 24, pad + 48)], fill=_GOLD, width=1)

        draw.text(
            (pad + 24, pad + 56),
            f"Coins: {coin_qty}",
            font=dim_font, fill=_CYAN,
        )

        y = pad + 80
        if not catalog:
            draw.text((pad + 24, y), "(nothing for sale)", font=body_font, fill=_DIM)
        else:
            for i, (item_id, price) in enumerate(catalog):
                can_afford = coin_qty >= price
                color  = _WHITE if (i == cursor_idx and can_afford) else (_DIM if not can_afford else _WHITE)
                prefix = "▶ " if i == cursor_idx else "  "
                name   = _item_name(item_id)
                draw.text(
                    (pad + 24, y),
                    f"{prefix}{name}",
                    font=body_font, fill=color,
                )
                price_color = _GREEN if can_afford else _RED
                draw.text(
                    (width - pad - 120, y),
                    f"{price} coins",
                    font=body_font, fill=price_color,
                )
                y += 36

        draw.text(
            (pad + 24, height - pad - 34),
            "↑↓ navigate   [enter] buy   [esc] leave",
            font=dim_font, fill=_DIM,
        )
        return _to_png(img)