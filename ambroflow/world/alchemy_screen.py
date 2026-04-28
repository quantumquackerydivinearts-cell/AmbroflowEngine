"""
AlchemyScreen — PIL renderer for the three-phase alchemy UI.

Phases
------
  subject   — list of available subjects with inventory check
  approach  — choose presence / intuition / formula for the selected subject
  result    — AlchemicalResult summary (resonance, outputs, flags)
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..alchemy.system import AlchemicalSubject, AlchemicalResult

_BG    = (12, 12, 20)
_PANEL = (28, 22, 42)
_GOLD  = (210, 175, 80)
_WHITE = (230, 225, 215)
_DIM   = (120, 115, 105)
_RED   = (190, 70, 60)
_GREEN = (80, 170, 90)
_CYAN  = (80, 190, 190)

_APPROACH_LABELS = {
    "presence":  "Presence  — full diagnostic (1.00×)",
    "intuition": "Intuition — pattern read  (0.75×)",
    "formula":   "Formula   — mechanistic   (0.40×)",
}
_APPROACHES = list(_APPROACH_LABELS.keys())


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


class AlchemyScreen:
    """Stateless PIL renderer for the alchemy overlay."""

    def render_subject_select(
        self,
        subjects,
        cursor_idx: int,
        inv_dict: dict,
        width: int,
        height: int,
        season_note: str = "",
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

        draw.text((pad + 24, pad + 18), "Alchemy — Choose Subject", font=title_font, fill=_GOLD)
        draw.line([(pad + 24, pad + 48), (width - pad - 24, pad + 48)], fill=_GOLD, width=1)

        y = pad + 56
        if season_note:
            draw.text((pad + 24, y), season_note, font=dim_font, fill=_CYAN)
            y += 22
        y += 6
        for i, subj in enumerate(subjects):
            has_mats = all(inv_dict.get(k, 0) >= v for k, v in subj.required_materials.items())
            has_objs = all(inv_dict.get(oid, 0) >= 1 for oid in subj.required_objects)
            ready    = has_mats and has_objs
            color    = _WHITE if ready else _DIM
            prefix   = "▶ " if i == cursor_idx else "  "
            mat_str  = ", ".join(f"{k}×{v}" for k, v in subj.required_materials.items()) or "none"
            obj_str  = "  [needs: " + ", ".join(sorted(subj.required_objects)) + "]" if not has_objs else ""
            draw.text((pad + 24, y),      f"{prefix}{subj.name}", font=body_font, fill=color)
            draw.text((pad + 48, y + 20), mat_str + obj_str,       font=dim_font,  fill=_DIM)
            y += 52

        draw.text(
            (pad + 24, height - pad - 34),
            "↑↓ navigate   [enter] select   [esc] cancel",
            font=dim_font, fill=_DIM,
        )
        return _to_png(img)

    def render_approach_select(
        self,
        subject,
        cursor_idx: int,
        width: int,
        height: int,
        formula_bonus: float = 0.0,
        peak_axis: str | None = None,
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

        draw.text((pad + 24, pad + 18), f"Alchemy — {subject.name}", font=title_font, fill=_GOLD)
        draw.line([(pad + 24, pad + 48), (width - pad - 24, pad + 48)], fill=_GOLD, width=1)

        draw.text((pad + 24, pad + 60), subject.lore, font=dim_font, fill=_DIM)

        # Seasonal axis note
        axes = set()
        try:
            axes = subject.field.axes()
        except Exception:
            pass
        y = pad + 90
        if peak_axis and peak_axis in axes:
            draw.text((pad + 24, y), f"Season favours this field's {peak_axis} axis.", font=dim_font, fill=_CYAN)
            y += 18

        y += 8
        for i, mode in enumerate(_APPROACHES):
            color  = _WHITE if i == cursor_idx else _DIM
            prefix = "▶ " if i == cursor_idx else "  "
            label  = _APPROACH_LABELS[mode]
            if mode == "formula" and formula_bonus > 0.0:
                effective = 0.40 + formula_bonus
                label = f"Formula   — mechanistic  ({effective:.2f}×)  [navigators]"
            draw.text((pad + 24, y), f"{prefix}{label}", font=body_font, fill=color)
            y += 38

        draw.text(
            (pad + 24, height - pad - 34),
            "↑↓ navigate   [enter] treat   [esc] back",
            font=dim_font, fill=_DIM,
        )
        return _to_png(img)

    def render_result(
        self,
        result,
        subject_name: str,
        width: int,
        height: int,
    ) -> Optional[bytes]:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return None

        img  = Image.new("RGB", (width, height), _BG)
        draw = ImageDraw.Draw(img)

        title_font = _load_font(22)
        body_font  = _load_font(17)
        dim_font   = _load_font(14)

        pad   = 60
        panel = (pad, pad, width - pad, height - pad)
        draw.rectangle(panel, fill=_PANEL)

        heading = "Epiphany" if result.epiphanic else "Result"
        draw.text((pad + 24, pad + 18), f"Alchemy — {heading}", font=title_font, fill=_GOLD)
        draw.line([(pad + 24, pad + 48), (width - pad - 24, pad + 48)], fill=_GOLD, width=1)

        y = pad + 64
        draw.text((pad + 24, y), f"Subject:    {subject_name}",          font=body_font, fill=_WHITE)
        y += 30
        q = result.resonance_quality
        q_color = _GREEN if q >= 0.65 else (_GOLD if q >= 0.40 else _RED)
        draw.text((pad + 24, y), f"Resonance:  {q:.2f}",                 font=body_font, fill=q_color)
        y += 30

        if result.outputs:
            outs = ", ".join(f"{k}×{v}" for k, v in result.outputs.items())
            draw.text((pad + 24, y), f"Outputs:    {outs}",              font=body_font, fill=_WHITE)
            y += 30

        if result.recipe_discovered:
            draw.text((pad + 24, y), "Recipe discovered.",               font=body_font, fill=_CYAN)
            y += 30

        if result.epiphanic:
            draw.text((pad + 24, y), "Epiphanic result.",                font=body_font, fill=_GOLD)
            y += 30

        sd = getattr(result, "sanity_delta", None)
        if sd:
            parts = [f"{k} {'+' if v >= 0 else ''}{v:.2f}" for k, v in sd.items() if v]
            if parts:
                draw.text((pad + 24, y), "Sanity:  " + "  ".join(parts), font=dim_font, fill=_DIM)

        draw.text(
            (pad + 24, height - pad - 34),
            "[space] or [enter] to continue",
            font=dim_font, fill=_DIM,
        )
        return _to_png(img)