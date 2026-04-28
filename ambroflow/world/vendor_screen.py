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
    # KLOB raw materials
    "0073_KLOB": "Herb (Common)",
    "0074_KLOB": "Herb (Restorative)",
    "0075_KLOB": "Binding Wax",
    "0076_KLOB": "Raw Desire Stone",
    "0077_KLOB": "Asmodean Essence",
    "0040_KLOB": "Water Flask",
    "0024_KLOB": "Sulphur Essence",
    # KLOB apparatus
    "0001_KLOB": "Mortar",
    "0002_KLOB": "Pestle",
    "0003_KLOB": "Retort Stand",
    "0004_KLOB": "Retort Stand",
    "0005_KLOB": "Retort",
    "0006_KLOB": "Reagent Bottle",
    "0007_KLOB": "Reagent Bottle",
    "0010_KLOB": "Furnace",
    "0017_KLOB": "Crucible",
    "0019_KLOB": "Jar",
    # KLIT
    "0016_KLIT": "Coin",
}

COIN_ID = "0016_KLIT"


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