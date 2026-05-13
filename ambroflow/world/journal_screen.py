"""
Journal Screen
==============
PIL-based renderer for the in-game journal overlay.

Two views
---------
  list    — paginated entry list (title + kind tag + relative date).
            Up/Down to navigate cursor; Enter/Space to expand; Escape to close.
  detail  — expanded single entry (full body text with word-wrap).
            Escape or Enter returns to list view.
"""

from __future__ import annotations

import io
import textwrap
import time
from typing import Optional

_KIND_LABEL: dict[str, str] = {
    "quest_note":     "[ Quest ]",
    "lore_fragment":  "[ Lore ]",
    "character_note": "[ Character ]",
    "encounter_note": "[ Encounter ]",
    "alchemy_note":   "[ Alchemy ]",
    "dream_note":     "[ Dream ]",
    "reflection":     "[ Reflection ]",
    "observation":    "[ Observation ]",
}

_BG           = ( 20,  16,  12)
_BORDER       = ( 90,  70,  42)
_HEADER_TEXT  = (220, 185, 100)
_ENTRY_NORMAL = (180, 160, 120)
_ENTRY_SEL    = (240, 220, 160)
_KIND_COLOR   = (120, 110,  80)
_DATE_COLOR   = ( 90,  82,  60)
_BODY_COLOR   = (165, 148, 108)
_DIM          = ( 70,  60,  44)
_HINT_COLOR   = ( 90,  82,  62)
_TITLE_BG     = ( 30,  24,  18)


def _pil_font(size: int = 14):
    try:
        from PIL import ImageFont
        return ImageFont.load_default(size=size)
    except Exception:
        return None


def _age_str(ts: float) -> str:
    delta = time.time() - ts
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


class JournalScreen:
    """Stateless PIL renderer — all state lives in WorldPlay."""

    _PAGE_ENTRIES = 10   # entries per list page

    def render_list(
        self,
        entries: list,          # list[JournalEntry]
        cursor:  int,
        page:    int,
        width:   int,
        height:  int,
    ) -> bytes:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return b""

        img  = Image.new("RGB", (width, height), _BG)
        draw = ImageDraw.Draw(img)

        f14 = _pil_font(14)
        f12 = _pil_font(12)

        pad   = 48
        panel = (pad, 40, width - pad, height - 40)
        draw.rectangle(panel, outline=_BORDER, width=2)

        # Title bar
        draw.rectangle((pad, 40, width - pad, 80), fill=_TITLE_BG)
        draw.text((pad + 16, 52), "Journal", font=f14, fill=_HEADER_TEXT)
        count_str = f"{len(entries)} entries"
        draw.text((width - pad - 120, 52), count_str, font=f12, fill=_DIM)

        if not entries:
            draw.text((pad + 20, 110), "No entries yet.", font=f14, fill=_DIM)
        else:
            start = page * self._PAGE_ENTRIES
            page_entries = entries[start : start + self._PAGE_ENTRIES]
            y = 98
            for i, entry in enumerate(page_entries):
                abs_i = start + i
                sel = (abs_i == cursor)
                tc = _ENTRY_SEL if sel else _ENTRY_NORMAL

                if sel:
                    draw.rectangle((pad + 4, y - 2, width - pad - 4, y + 20), fill=(38, 30, 20))

                kind_label = _KIND_LABEL.get(
                    getattr(entry, "kind", entry.get("kind", "observation") if isinstance(entry, dict) else "observation"),
                    "[ Note ]"
                )
                title = (
                    entry.title if hasattr(entry, "title") else entry.get("title", "—")
                )
                ts = (
                    entry.timestamp if hasattr(entry, "timestamp") else entry.get("timestamp", 0.0)
                )

                draw.text((pad + 16, y), kind_label, font=f12, fill=_KIND_COLOR)
                draw.text((pad + 130, y), title, font=f12, fill=tc)
                draw.text((width - pad - 80, y), _age_str(ts), font=f12, fill=_DATE_COLOR)
                y += 26

            # Pagination hint
            total_pages = max(1, (len(entries) + self._PAGE_ENTRIES - 1) // self._PAGE_ENTRIES)
            page_str = f"page {page + 1} / {total_pages}"
            draw.text((pad + 16, height - 60), page_str, font=f12, fill=_DIM)

        # Key hint
        draw.text(
            (pad + 16, height - 42),
            "[↑↓]  Navigate    [Enter/Space]  Read    [Escape]  Close",
            font=f12, fill=_HINT_COLOR,
        )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def render_detail(
        self,
        entry,
        width: int,
        height: int,
    ) -> bytes:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return b""

        img  = Image.new("RGB", (width, height), _BG)
        draw = ImageDraw.Draw(img)

        f14 = _pil_font(14)
        f12 = _pil_font(12)

        pad   = 48
        panel = (pad, 40, width - pad, height - 40)
        draw.rectangle(panel, outline=_BORDER, width=2)
        draw.rectangle((pad, 40, width - pad, 80), fill=_TITLE_BG)

        title = entry.title if hasattr(entry, "title") else entry.get("title", "—")
        kind_raw = getattr(entry, "kind", entry.get("kind", "observation") if isinstance(entry, dict) else "observation")
        if hasattr(kind_raw, "value"):
            kind_raw = kind_raw.value
        kind_label = _KIND_LABEL.get(kind_raw, "[ Note ]")
        ts = entry.timestamp if hasattr(entry, "timestamp") else entry.get("timestamp", 0.0)

        draw.text((pad + 16, 52), f"{kind_label}  {title}", font=f14, fill=_HEADER_TEXT)
        draw.text((width - pad - 80, 52), _age_str(ts), font=f12, fill=_DATE_COLOR)

        body = entry.body if hasattr(entry, "body") else entry.get("body", "")
        usable_w = (width - pad * 2 - 32) // 7   # rough chars per line at ~7px/char
        lines = []
        for para in body.split("\n"):
            wrapped = textwrap.wrap(para, width=max(20, usable_w)) if para.strip() else [""]
            lines.extend(wrapped)

        y = 96
        line_h = 18
        for line in lines:
            if y > height - 80:
                draw.text((pad + 16, y), "…", font=f12, fill=_DIM)
                break
            draw.text((pad + 16, y), line, font=f12, fill=_BODY_COLOR)
            y += line_h

        draw.text(
            (pad + 16, height - 42),
            "[Escape / Enter]  Back to list",
            font=f12, fill=_HINT_COLOR,
        )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()