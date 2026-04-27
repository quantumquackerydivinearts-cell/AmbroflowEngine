"""
Map Discovery Screen
====================
Renders the Mercurie map discovery interaction — the player finds a folded
map inside Forest's journal (0007_WTCH) and can unfold it to inspect it.

States
------
  FOLDED   Initial state.  Shows mercurie_map_folded.png centred on a dark
           parchment background with a "[space]  Unfold" hint.
  UNFOLDED Shows mercurie_map_full.png with location/being annotations and
           an "[esc]  Close" hint.  The map is added to inventory on close.

The screen is PIL-rendered and returns bytes (PNG) on each render call.
No pygame dependency — purely image composition.

Asset paths
-----------
By default looks for the three map PNGs alongside the Atelier static/maps/
directory.  Pass ``maps_dir`` to override (used in tests with temp dirs).
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    _PIL = True
except ImportError:
    _PIL = False

# Default maps directory — sibling repo layout: c:\DjinnOS\ next to c:\AmbroflowEngine\
_DEFAULT_MAPS_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "DjinnOS" / "apps" / "atelier-api" / "static" / "maps"
)

ITEM_ID   = "0036_KLIT"
ITEM_NAME = "Map of Mercurie"

# Journal entry written on first discovery
_JOURNAL_TITLE = "A Map of Mercurie"
_JOURNAL_BODY  = (
    "Forest's reward at the end of The Golden Path — folded inside his journal, "
    "pressed between the pages like a letter. A hand-drawn graphite map of the "
    "Realm of Mercurie. He has marked Sophia and Chazak by name, a cluster of "
    "Nymphs to the south, Mt. Hieronymus in the highlands, and the Church of "
    "Gnome Rizz near the forest spine. The Faewilds, rendered in someone's own hand."
)

_BG_PARCHMENT = (28, 22, 18)
_TEXT_GOLD    = (200, 168, 75)
_TEXT_DIM     = (130, 120, 100)


class MapState(str, Enum):
    FOLDED   = "folded"
    UNFOLDED = "unfolded"


def _load_font(size: int) -> Optional[object]:
    if not _PIL:
        return None
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()


def _text_size(draw: "ImageDraw.ImageDraw", text: str, font) -> tuple[int, int]:
    try:
        b = draw.textbbox((0, 0), text, font=font)
        return b[2] - b[0], b[3] - b[1]
    except AttributeError:
        return draw.textsize(text, font=font)  # type: ignore[attr-defined]


def _to_png(img: "Image.Image") -> bytes:
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class MapDiscoveryScreen:
    """
    Stateless renderer for map discovery interaction.

    Parameters
    ----------
    maps_dir:
        Directory containing mercurie_map_folded.png and mercurie_map_full.png.
        Defaults to the Atelier static/maps/ directory.
    """

    def __init__(self, maps_dir: Optional[Path] = None) -> None:
        self._maps_dir = Path(maps_dir) if maps_dir else _DEFAULT_MAPS_DIR

    # ── Public render API ─────────────────────────────────────────────────────

    def render(
        self,
        state: MapState,
        width: int = 1280,
        height: int = 800,
    ) -> Optional[bytes]:
        """
        Return PNG bytes for the given state.

        Returns None if PIL is unavailable or the asset cannot be loaded.
        """
        if not _PIL:
            return None
        if state == MapState.FOLDED:
            return self._render_folded(width, height)
        return self._render_unfolded(width, height)

    # ── Internal renderers ────────────────────────────────────────────────────

    def _load_map_image(self, filename: str) -> Optional["Image.Image"]:
        path = self._maps_dir / filename
        if not path.exists():
            return None
        try:
            return Image.open(path).convert("RGB")
        except Exception:
            return None

    def _render_folded(self, W: int, H: int) -> Optional[bytes]:
        img  = Image.new("RGB", (W, H), _BG_PARCHMENT)
        draw = ImageDraw.Draw(img)

        map_img = self._load_map_image("mercurie_map_folded.png")
        if map_img is not None:
            # Scale to fit 60 % of the screen height, preserve aspect
            max_h = int(H * 0.60)
            max_w = int(W * 0.70)
            map_img.thumbnail((max_w, max_h), Image.LANCZOS)
            mx = (W - map_img.width)  // 2
            my = int(H * 0.12)
            img.paste(map_img, (mx, my))

        font_title = _load_font(16)
        font_sub   = _load_font(12)
        font_hint  = _load_font(11)

        # Title
        title = "Forest's Journal"
        tw, _ = _text_size(draw, title, font_title)
        draw.text(((W - tw) // 2, int(H * 0.04)), title,
                  fill=_TEXT_GOLD, font=font_title)

        # Subtitle
        sub = "A folded paper is tucked between the pages."
        sw, _ = _text_size(draw, sub, font_sub)
        draw.text(((W - sw) // 2, int(H * 0.08)), sub,
                  fill=_TEXT_DIM, font=font_sub)

        # Hint
        hint = "[space]  Unfold     [esc]  Leave"
        hw, _ = _text_size(draw, hint, font_hint)
        draw.text(((W - hw) // 2, int(H * 0.90)), hint,
                  fill=_TEXT_DIM, font=font_hint)

        return _to_png(img)

    def _render_unfolded(self, W: int, H: int) -> Optional[bytes]:
        img  = Image.new("RGB", (W, H), _BG_PARCHMENT)
        draw = ImageDraw.Draw(img)

        map_img = self._load_map_image("mercurie_map_full.png")
        if map_img is not None:
            max_h = int(H * 0.74)
            max_w = int(W * 0.86)
            map_img.thumbnail((max_w, max_h), Image.LANCZOS)
            mx = (W - map_img.width)  // 2
            my = int(H * 0.06)
            img.paste(map_img, (mx, my))

        font_title = _load_font(15)
        font_annot = _load_font(10)
        font_hint  = _load_font(11)

        title = "Realm of Mercurie  —  The Faewilds"
        tw, _ = _text_size(draw, title, font_title)
        draw.text(((W - tw) // 2, int(H * 0.015)), title,
                  fill=_TEXT_GOLD, font=font_title)

        # Annotation note
        note = "Sophia · Chazak · Nymphs · Mt. Hieronymus · Church of Gnome Rizz"
        nw, _ = _text_size(draw, note, font_annot)
        draw.text(((W - nw) // 2, int(H * 0.84)), note,
                  fill=_TEXT_DIM, font=font_annot)

        hint = "[esc]  Close and take the map"
        hw, _ = _text_size(draw, hint, font_hint)
        draw.text(((W - hw) // 2, int(H * 0.92)), hint,
                  fill=_TEXT_DIM, font=font_hint)

        return _to_png(img)