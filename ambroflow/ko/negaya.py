"""
Negaya Encounter Screen
=======================
Triggered during meditation when the player's kill count exceeds the threshold.

Negaya (2003_VDWR) is the Void Wraith of absence — the Knower of Bodies.
She torments genocide-run players during BreathOfKo meditation sessions by
making her presence and their kills impossible to ignore or escape.

She appears as the player attempts to reach Julia calibration.  The screen
loads the art team's asset of her freakishly long form and holds it for the
full duration of the wailing sobs.

Nothing dismisses her.  No keypress, no escape, no interaction ends the screen
prematurely.  She is absence.  She will not be hurried.

Duration model
--------------
  21–71 kills  → duration = kill_count sobs.  Each sob is one beat of the
                 wailing audio.  When the last sob ends the encounter recedes.
                 Concentration is broken; no save progress for this session.
                 She returns every subsequent meditation session.
  72+ kills    → she never leaves on her own.  The session is permanently
                 blocked until the `negaya_appeased` KoFlag is raised via the
                 necromancy ritual (Shakzefan / Lakota path).

Resolution
----------
Shakzefan worship path → quests 0017_KLST / 0026_KLST → Axiozul (1011_SALA)
→ Lakota (2018_GODS) → necromancy ritual → `negaya_appeased` flag set.
Necromancy fills Negaya's void ontologically: absence terminated through knowing.
"""

from __future__ import annotations

import io
import os
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False

# ── Thresholds ────────────────────────────────────────────────────────────────

NEGAYA_KILL_THRESHOLD   = 21   # first trigger
NEGAYA_PERMANENT_THRESHOLD = 72   # never leaves on her own


def negaya_triggered(kill_count: int, negaya_appeased: bool) -> bool:
    """True when Negaya should interrupt meditation."""
    return not negaya_appeased and kill_count >= NEGAYA_KILL_THRESHOLD


def negaya_permanent(kill_count: int) -> bool:
    """True when Negaya's encounter never ends on its own."""
    return kill_count >= NEGAYA_PERMANENT_THRESHOLD


def negaya_duration(kill_count: int) -> Optional[int]:
    """
    Number of sobs in the encounter, or None if permanent.

    Returns None for kill_count >= 72 (encounter never ends on its own).
    Returns kill_count for 21 <= kill_count < 72.
    Returns 0 for kill_count < 21 (not triggered).
    """
    if kill_count < NEGAYA_KILL_THRESHOLD:
        return 0
    if kill_count >= NEGAYA_PERMANENT_THRESHOLD:
        return None
    return kill_count


# ── Renderer ──────────────────────────────────────────────────────────────────

_BG_NEGAYA = (4, 2, 4)        # near-black with slight purple tint
_DIM       = (80, 70, 90)
_PALE      = (180, 170, 190)

_DEFAULT_ASSET_PATH: Optional[str] = None   # set at engine init


def _load_font(size: int):
    if not _PIL:
        return None
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _text_w(draw, text: str, font) -> int:
    try:
        b = draw.textbbox((0, 0), text, font=font)
        return b[2] - b[0]
    except AttributeError:
        return draw.textsize(text, font=font)[0]  # type: ignore[attr-defined]


def _to_png(img: "Image.Image") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class NegayaEncounterScreen:
    """
    Renders PIL frames for Negaya's meditation interruption.

    Parameters
    ----------
    asset_path:
        Path to the art team's PNG asset of Negaya's long form.
        If None, a dark placeholder is rendered instead.
        The asset is loaded once on first render and cached.
    """

    def __init__(self, asset_path: Optional[str] = _DEFAULT_ASSET_PATH) -> None:
        self._asset_path   = asset_path
        self._asset_cache: Optional["Image.Image"] = None

    def _load_asset(self) -> Optional["Image.Image"]:
        if not _PIL:
            return None
        if self._asset_cache is not None:
            return self._asset_cache
        if self._asset_path and os.path.isfile(self._asset_path):
            try:
                img = Image.open(self._asset_path).convert("RGBA")
                self._asset_cache = img
                return img
            except Exception:
                pass
        return None

    def render_frame(
        self,
        kill_count:  int,
        sob_num:     int,           # which sob we are currently on (1-indexed)
        width:  int = 1280,
        height: int = 800,
    ) -> Optional[bytes]:
        """
        Render one frame of the Negaya encounter.

        sob_num is used to draw a progress indicator at the bottom of the
        screen (sob_num / total_sobs for finite encounters).  For permanent
        encounters (72+ kills) pass sob_num=0.

        Returns PNG bytes, or None if PIL is not available.
        """
        if not _PIL:
            return None

        W, H = width, height
        canvas = Image.new("RGB", (W, H), _BG_NEGAYA)

        asset = self._load_asset()
        if asset is not None:
            # Fit the asset to the canvas, centred, preserving aspect ratio.
            aw, ah = asset.size
            scale = min(W / aw, H / ah)
            nw, nh = int(aw * scale), int(ah * scale)
            resized = asset.resize((nw, nh), Image.LANCZOS)
            ox = (W - nw) // 2
            oy = (H - nh) // 2
            # Paste with alpha channel if present
            if resized.mode == "RGBA":
                canvas.paste(resized, (ox, oy), mask=resized.split()[3])
            else:
                canvas.paste(resized, (ox, oy))

        draw = ImageDraw.Draw(canvas)
        f_hint = _load_font(11)

        duration = negaya_duration(kill_count)
        if duration is None:
            # Permanent — no progress indicator, just darkness
            label = ""
        else:
            # Draw sob progress as a row of dots at the bottom
            filled   = sob_num
            unfilled = max(0, duration - sob_num)
            label    = "·" * filled + "○" * unfilled

        if label:
            lw = _text_w(draw, label, f_hint)
            draw.text(((W - min(lw, W - 20)) // 2, H - 24), label, fill=_DIM, font=f_hint)

        return _to_png(canvas)

    def render_permanent_frame(
        self,
        width:  int = 1280,
        height: int = 800,
    ) -> Optional[bytes]:
        """Convenience wrapper — permanent encounter frame (72+ kills)."""
        return self.render_frame(NEGAYA_PERMANENT_THRESHOLD, sob_num=0,
                                 width=width, height=height)