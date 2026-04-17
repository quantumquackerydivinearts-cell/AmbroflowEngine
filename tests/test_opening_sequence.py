"""
Tests for the Fate Knocks opening sequence (scenes/opening.py).

Covers:
- render_hypatia_letter returns valid parchment PNG
- render_stage_direction returns valid dark-screen PNG
- render_fate_knocks_sequence returns exactly 5 frames in order
- Canonical text constants are present and non-empty
- Letter dimensions match requested size
- Stage direction handles long text without error
"""

from __future__ import annotations

import struct
import pytest

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

pytestmark = pytest.mark.skipif(not _PIL, reason="PIL not installed")


# ── helpers ───────────────────────────────────────────────────────────────────

def _is_png(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def _png_dims(data: bytes) -> tuple[int, int]:
    w = struct.unpack(">I", data[16:20])[0]
    h = struct.unpack(">I", data[20:24])[0]
    return w, h


# ── imports ───────────────────────────────────────────────────────────────────

from ambroflow.scenes.opening import (
    render_hypatia_letter,
    render_stage_direction,
    render_fate_knocks_sequence,
    COURIER_LINE,
    HYPATIA_LETTER_LINES,
    DOOR_KNOCK_TEXT,
)


# ── canonical text ────────────────────────────────────────────────────────────

class TestCanonicalText:
    def test_courier_line_non_empty(self):
        assert COURIER_LINE.strip()

    def test_courier_line_mentions_castle_azoth(self):
        assert "Castle Azoth" in COURIER_LINE

    def test_courier_line_mentions_sealed_letter(self):
        assert "sealed letter" in COURIER_LINE.lower()

    def test_hypatia_letter_lines_non_empty(self):
        non_blank = [l for l in HYPATIA_LETTER_LINES if l.strip()]
        assert len(non_blank) >= 5

    def test_hypatia_letter_signed_h(self):
        # The signature line must be present
        assert any("H." in line for line in HYPATIA_LETTER_LINES)

    def test_hypatia_letter_mentions_royal_lottery(self):
        full_text = "\n".join(HYPATIA_LETTER_LINES)
        assert "Royal Lottery" in full_text

    def test_hypatia_letter_mentions_wiltoll_lane(self):
        full_text = "\n".join(HYPATIA_LETTER_LINES)
        assert "Wiltoll Lane" in full_text

    def test_door_knock_text_non_empty(self):
        assert DOOR_KNOCK_TEXT.strip()

    def test_door_knock_three_strikes(self):
        assert "Three" in DOOR_KNOCK_TEXT or "three" in DOOR_KNOCK_TEXT.lower()


# ── render_hypatia_letter ─────────────────────────────────────────────────────

class TestRenderHypatiaLetter:
    def test_returns_png(self):
        data = render_hypatia_letter()
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self):
        data = render_hypatia_letter()
        w, h = _png_dims(data)
        assert w == 512
        assert h == 512

    def test_custom_dimensions(self):
        data = render_hypatia_letter(width=400, height=600)
        w, h = _png_dims(data)
        assert w == 400
        assert h == 600

    def test_parchment_is_not_black(self):
        """Parchment should be a warm cream, not a dark background."""
        from PIL import Image
        import io
        data = render_hypatia_letter(width=64, height=64)
        img  = Image.open(io.BytesIO(data)).convert("RGB")
        pixels = list(img.getdata())
        avg_r = sum(p[0] for p in pixels) / len(pixels)
        avg_g = sum(p[1] for p in pixels) / len(pixels)
        # Parchment background is warm cream (r ~185, g ~168) — well above 80
        assert avg_r > 80
        assert avg_g > 80

    def test_wax_seal_adds_red_tones(self):
        """The wax seal (SEAL_RED ~135,28,22) should contribute red to the image."""
        from PIL import Image
        import io
        data = render_hypatia_letter(width=256, height=256)
        img  = Image.open(io.BytesIO(data)).convert("RGB")
        pixels = list(img.getdata())
        # At least some pixels should be strongly red-dominant (r > g+b combined)
        red_dominant = sum(1 for p in pixels if p[0] > p[1] + p[2])
        assert red_dominant > 0


# ── render_stage_direction ────────────────────────────────────────────────────

class TestRenderStageDirection:
    def test_returns_png(self):
        data = render_stage_direction(DOOR_KNOCK_TEXT)
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self):
        data = render_stage_direction(DOOR_KNOCK_TEXT)
        w, h = _png_dims(data)
        assert w == 512
        assert h == 512

    def test_custom_dimensions(self):
        data = render_stage_direction("test text", width=320, height=240)
        w, h = _png_dims(data)
        assert w == 320
        assert h == 240

    def test_dark_background(self):
        """Stage direction screen has a very dark near-black background."""
        from PIL import Image
        import io
        data = render_stage_direction("A knock.", width=64, height=64)
        img  = Image.open(io.BytesIO(data)).convert("RGB")
        pixels = list(img.getdata())
        avg_r = sum(p[0] for p in pixels) / len(pixels)
        avg_b = sum(p[2] for p in pixels) / len(pixels)
        assert avg_r < 60
        assert avg_b < 60

    def test_long_text_wraps_without_error(self):
        long_text = " ".join(["word"] * 100)
        data = render_stage_direction(long_text)
        assert _is_png(data)

    def test_different_texts_produce_different_images(self):
        a = render_stage_direction("Text A.")
        b = render_stage_direction("Text B.")
        assert a != b


# ── render_fate_knocks_sequence ───────────────────────────────────────────────

class TestRenderFateKnocksSequence:
    def test_returns_five_frames(self):
        frames = render_fate_knocks_sequence()
        assert len(frames) == 5

    def test_all_frames_are_png(self):
        frames = render_fate_knocks_sequence()
        for i, f in enumerate(frames):
            assert _is_png(f), f"Frame {i} is not a valid PNG"

    def test_frame_dimensions(self):
        """
        Frames 0, 2 are location scenes (scene_width x scene_height).
        Frames 1, 4 are full-screen (screen_size x screen_size).
        Frame 3 (courier dialogue) is screen_size x screen_size//2.
        """
        sw, sh, ss = 512, 384, 512
        frames = render_fate_knocks_sequence(
            scene_width=sw, scene_height=sh, screen_size=ss
        )
        w0, h0 = _png_dims(frames[0])  # bedroom
        w1, h1 = _png_dims(frames[1])  # stage direction knock
        w2, h2 = _png_dims(frames[2])  # foyer
        w3, h3 = _png_dims(frames[3])  # courier dialogue
        w4, h4 = _png_dims(frames[4])  # letter

        assert (w0, h0) == (sw, sh)
        assert (w1, h1) == (ss, ss)
        assert (w2, h2) == (sw, sh)
        assert (w3, h3) == (ss, ss // 2)
        assert (w4, h4) == (ss, ss)

    def test_custom_dimensions(self):
        frames = render_fate_knocks_sequence(
            scene_width=320, scene_height=240, screen_size=256
        )
        assert len(frames) == 5
        for f in frames:
            assert _is_png(f)

    def test_all_frames_are_distinct(self):
        frames = render_fate_knocks_sequence()
        assert len(set(frames)) == 5, "Some frames are identical"

    def test_letter_frame_is_largest(self):
        """Parchment letter has texture noise — should be the largest frame by byte size."""
        frames = render_fate_knocks_sequence()
        letter_size    = len(frames[4])
        other_max_size = max(len(f) for f in frames[:4])
        assert letter_size > other_max_size