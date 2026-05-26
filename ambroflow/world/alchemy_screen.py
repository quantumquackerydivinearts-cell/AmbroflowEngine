"""
AlchemyScreen — PIL renderer for the alchemy UI.

Phases
------
  subject    — list of available subjects with inventory check
  lab_ops    — laboratory operation menu (grinding, dissolution, etc.)
               shown when LaboratorySession is active; replaces approach select
  approach   — choose presence / intuition / formula (direct path, no lab)
  result     — AlchemicalResult summary (resonance, outputs, flags)

The lab path inserts between subject and approach:
  subject → lab_ops (repeat per operation) → approach (auto from session) → result
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..alchemy.system import AlchemicalSubject, AlchemicalResult
    from ..alchemy.laboratory import OperationDef, SubstanceState, OperationResult

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
                y += 24

        phys = getattr(result, "physics_context", None)
        if phys is not None:
            _PHYS_COLORS = {
                "stable":    _GREEN,
                "active":    _WHITE,
                "chaotic":   _GOLD,
                "explosive": _RED,
            }
            phys_color = _PHYS_COLORS.get(phys.outcome, _WHITE)
            compound = f"  [{phys.compound_name}]" if phys.compound_name else ""
            draw.text(
                (pad + 24, y),
                f"Substrate:  {phys.outcome}{compound}  (KE {phys.peak_energy:.3f})",
                font=dim_font, fill=phys_color,
            )

        draw.text(
            (pad + 24, height - pad - 34),
            "[space] or [enter] to continue",
            font=dim_font, fill=_DIM,
        )
        return _to_png(img)

    def render_lab_operation_menu(
        self,
        subject_name:     str,
        all_ops:          tuple,
        available_op_ids: set,
        cursor_idx:       int,
        mode_scores:      dict,
        substance,
        history:          list,
        width:            int,
        height:           int,
    ) -> Optional[bytes]:
        """
        Laboratory operation selection screen.

        all_ops          : OPERATIONS tuple from laboratory.py
        available_op_ids : set of op_ids currently runnable (equipment + traits satisfied)
        cursor_idx       : 0 .. len(all_ops)  — len(all_ops) points to "Conclude"
        mode_scores      : accumulated engagement {mode: float}
        substance        : current SubstanceState
        history          : list of OperationResult (most recent last)
        """
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return None

        img  = Image.new("RGB", (width, height), _BG)
        draw = ImageDraw.Draw(img)

        title_font = _load_font(20)
        body_font  = _load_font(15)
        dim_font   = _load_font(13)

        pad = 40
        draw.rectangle((pad, pad, width - pad, height - pad), fill=_PANEL)

        # ── Header ────────────────────────────────────────────────────────────
        draw.text((pad + 20, pad + 14), f"Laboratory — {subject_name}",
                  font=title_font, fill=_GOLD)
        draw.line([(pad + 20, pad + 40), (width - pad - 20, pad + 40)],
                  fill=_GOLD, width=1)

        left_w  = (width - 2 * pad) * 2 // 5
        split_x = pad + left_w

        # ── Left: substance state + history ───────────────────────────────────
        y = pad + 50
        draw.text((pad + 16, y), "Substance", font=body_font, fill=_CYAN)
        y += 22
        draw.text((pad + 16, y), substance.object_id, font=dim_font, fill=_WHITE)
        y += 18

        traits = substance.trait_names() if hasattr(substance, "trait_names") else []
        for chunk_start in range(0, len(traits), 3):
            chunk = traits[chunk_start:chunk_start + 3]
            draw.text((pad + 16, y), "  ".join(chunk), font=dim_font, fill=_DIM)
            y += 16

        y += 6
        purity_bar_w = left_w - 40
        draw.text((pad + 16, y), f"Purity  {substance.purity:.0%}", font=dim_font, fill=_DIM)
        y += 16
        draw.rectangle((pad + 16, y, pad + 16 + purity_bar_w, y + 8), fill=(40, 40, 60))
        filled = int(purity_bar_w * substance.purity)
        draw.rectangle((pad + 16, y, pad + 16 + filled, y + 8), fill=_CYAN)
        y += 18

        if history:
            y += 6
            draw.text((pad + 16, y), "Done", font=body_font, fill=_CYAN)
            y += 18
            for res in history[-4:]:
                q_col = _GREEN if res.quality >= 0.65 else (_GOLD if res.quality >= 0.30 else _RED)
                op_name = res.op_id.replace("_", " ").title()
                draw.text((pad + 16, y), f"• {op_name}", font=dim_font, fill=q_col)
                draw.text((pad + 16 + left_w - 52, y), f"{res.quality:.2f}", font=dim_font, fill=q_col)
                y += 16

        # ── Mode engagement bars ───────────────────────────────────────────────
        _MODES = ["ontological", "cosmological", "narrative", "somatic"]
        _MODE_COLORS = {
            "ontological":  (100, 180, 240),
            "cosmological": (180, 140, 220),
            "narrative":    (240, 200, 100),
            "somatic":      (100, 220, 140),
        }
        bar_y = height - pad - 80
        draw.text((pad + 16, bar_y - 18), "Engagement", font=dim_font, fill=_DIM)
        for mode in _MODES:
            score = min(1.0, mode_scores.get(mode, 0.0))
            col   = _MODE_COLORS.get(mode, _WHITE)
            label = mode[:3].upper()
            draw.text((pad + 16, bar_y), label, font=dim_font, fill=col)
            bar_x0 = pad + 46
            bar_x1 = split_x - 16
            draw.rectangle((bar_x0, bar_y + 2, bar_x1, bar_y + 10), fill=(40, 40, 60))
            draw.rectangle((bar_x0, bar_y + 2, bar_x0 + int((bar_x1 - bar_x0) * score), bar_y + 10),
                           fill=col)
            bar_y += 16

        # ── Right: operation list ─────────────────────────────────────────────
        _VITRIOL_COLORS = {"V": _CYAN, "I": (140, 220, 140), "T": _GOLD,
                           "R": (200, 140, 220), "O": (220, 160, 100), "L": (200, 200, 240)}

        oy = pad + 50
        draw.text((split_x + 12, oy), "Operations", font=body_font, fill=_CYAN)
        oy += 22

        total_items = len(all_ops) + 1  # +1 for Conclude
        for i, op in enumerate(all_ops):
            available = op.op_id in available_op_ids
            is_cursor = (i == cursor_idx)
            prefix    = "▶ " if is_cursor else "  "
            color     = _WHITE if available else _DIM
            if is_cursor:
                color = _GOLD if available else (160, 130, 60)

            vit_col  = _VITRIOL_COLORS.get(op.vitriol_letter, _WHITE) if available else _DIM
            draw.text((split_x + 12, oy), prefix, font=body_font, fill=color)
            draw.text((split_x + 28, oy), f"[{op.vitriol_letter}]", font=dim_font, fill=vit_col)
            draw.text((split_x + 50, oy), op.name, font=body_font, fill=color)
            oy += 20

            if not available and is_cursor:
                missing_eq = op.required_equipment - getattr(substance, "_equipment_ref", set())
                if missing_eq:
                    eq_names = ", ".join(sorted(missing_eq))
                    draw.text((split_x + 50, oy), f"needs: {eq_names}", font=dim_font, fill=(140, 90, 60))
                    oy += 14

        # Conclude option
        is_conclude = (cursor_idx == len(all_ops))
        conclude_color = _GOLD if is_conclude else _DIM
        prefix = "▶ " if is_conclude else "  "
        draw.text((split_x + 12, oy + 4), prefix, font=body_font, fill=conclude_color)
        draw.text((split_x + 28, oy + 4), "[ Conclude Session ]", font=body_font, fill=conclude_color)

        # ── Footer ────────────────────────────────────────────────────────────
        draw.text(
            (pad + 20, height - pad - 20),
            "↑↓ navigate   [enter] perform / conclude   [esc] cancel",
            font=dim_font, fill=_DIM,
        )
        return _to_png(img)

    def render_lab_operation_result(
        self,
        result,
        subject_name: str,
        width:        int,
        height:       int,
    ) -> Optional[bytes]:
        """
        Brief flash screen shown after one laboratory operation completes.
        Displays the observation text, quality, and whether an axis was identified.
        """
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return None

        img  = Image.new("RGB", (width, height), _BG)
        draw = ImageDraw.Draw(img)

        title_font = _load_font(20)
        body_font  = _load_font(16)
        dim_font   = _load_font(14)

        pad = 60
        draw.rectangle((pad, pad, width - pad, height - pad), fill=_PANEL)

        op_name = result.op_id.replace("_", " ").title()
        heading = "Catastrophic Failure" if result.catastrophic else op_name
        h_color = _RED if result.catastrophic else _GOLD
        draw.text((pad + 24, pad + 16), f"Laboratory — {subject_name}", font=title_font, fill=_GOLD)
        draw.line([(pad + 24, pad + 44), (width - pad - 24, pad + 44)], fill=_GOLD, width=1)

        y = pad + 60
        draw.text((pad + 24, y), heading, font=body_font, fill=h_color)
        y += 30

        q = result.quality
        q_color = _GREEN if q >= 0.65 else (_GOLD if q >= 0.30 else _RED)
        draw.text((pad + 24, y), f"Quality:  {q:.2f}", font=body_font, fill=q_color)
        y += 28

        if result.axis_identified:
            draw.text((pad + 24, y), f"Axis identified:  {result.axis_identified}",
                      font=body_font, fill=_CYAN)
            y += 28

        obs_text = result.observation if not result.catastrophic else result.failure_text if hasattr(result, "failure_text") else result.observation
        if obs_text:
            words    = obs_text.split()
            line_buf = []
            for word in words:
                line_buf.append(word)
                if len(" ".join(line_buf)) > 58:
                    draw.text((pad + 24, y), " ".join(line_buf[:-1]), font=dim_font, fill=_DIM)
                    y += 18
                    line_buf = [word]
            if line_buf:
                draw.text((pad + 24, y), " ".join(line_buf), font=dim_font, fill=_DIM)

        draw.text(
            (pad + 24, height - pad - 24),
            "[any key] continue",
            font=dim_font, fill=_DIM,
        )
        return _to_png(img)