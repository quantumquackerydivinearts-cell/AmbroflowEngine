"""Tests for Ko dialogue renderer."""

import pytest
from ambroflow.ko.dialogue_render import (
    render_ko_portrait,
    render_dialogue_screen,
    render_calibration_screens,
    _PIL_AVAILABLE,
    _VOID,
    _GOLD,
)


# ── Ko portrait ───────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_portrait_returns_bytes():
    data = render_ko_portrait(size=64)
    assert isinstance(data, bytes)
    assert len(data) > 0


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_portrait_is_valid_png():
    data = render_ko_portrait(size=64)
    assert data[:4] == b'\x89PNG'


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_portrait_correct_size():
    from PIL import Image
    import io
    data = render_ko_portrait(size=96)
    img  = Image.open(io.BytesIO(data))
    assert img.size == (96, 96)


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_portrait_has_gold_pixels():
    """Ko's arms and ring should produce gold-ish pixels (R > G, R > B)."""
    from PIL import Image
    import io
    data    = render_ko_portrait(size=64)
    img     = Image.open(io.BytesIO(data))
    pixels  = list(img.get_flattened_data())
    # At least some pixels should be warm (red channel dominant)
    gold_ish = [p for p in pixels if p[0] > 80 and p[0] > p[2] + 30]
    assert len(gold_ish) > 10, "Portrait should have warm gold pixels"


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_portrait_has_void_interior():
    """The interior of the Ouroboros is void — pixels near (7, 0, 15)."""
    from PIL import Image
    import io
    data   = render_ko_portrait(size=64)
    img    = Image.open(io.BytesIO(data))
    pixels = list(img.get_flattened_data())
    void   = _VOID
    void_ish = [p for p in pixels if p[0] < 20 and p[1] < 10 and p[2] < 30]
    assert len(void_ish) > 50, "Portrait should have a void interior"


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_portrait_non_trivial_colors():
    """Portrait should not be a single flat color."""
    from PIL import Image
    import io
    data   = render_ko_portrait(size=64)
    img    = Image.open(io.BytesIO(data))
    pixels = list(img.get_flattened_data())
    assert len(set(pixels)) > 15


# ── Dialogue screen ───────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_screen_returns_bytes():
    data = render_dialogue_screen("Where do you begin?", "lotus", size=128)
    assert isinstance(data, bytes)
    assert len(data) > 0


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_screen_is_valid_png():
    data = render_dialogue_screen("Which way are you facing?", "sakura", size=128)
    assert data[:4] == b'\x89PNG'


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_screen_correct_size():
    from PIL import Image
    import io
    data = render_dialogue_screen("What is the quality of this?", "rose", size=256)
    img  = Image.open(io.BytesIO(data))
    assert img.size == (256, 256)


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_all_three_phases():
    """Each phase renders without error and produces distinct images."""
    images = []
    for phase, text in [
        ("sakura", "Which way are you facing?"),
        ("rose",   "What is the quality of this?"),
        ("lotus",  "Where do you begin?"),
    ]:
        data = render_dialogue_screen(text, phase, size=128)
        assert data is not None
        assert data[:4] == b'\x89PNG'
        images.append(data)
    # Different phases produce different images (different accent colors)
    assert images[0] != images[1]
    assert images[1] != images[2]


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_unknown_phase_graceful():
    """Unknown phase falls back to gold accent without crashing."""
    data = render_dialogue_screen("An unknown prompt.", "unknown_phase", size=128)
    assert isinstance(data, bytes)


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_long_text_wrapped():
    """Long text is wrapped and the renderer does not crash."""
    long_text = (
        "The ground arrives last. What is it made of? "
        "Consider the quality of your footing — not as metaphor, "
        "but as the literal substrate from which you operate."
    )
    data = render_dialogue_screen(long_text, "lotus", size=256)
    assert isinstance(data, bytes)
    assert len(data) > 0


# ── render_calibration_screens ────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_calibration_screens_structure():
    from ambroflow.ko.calibration import DreamCalibrationSession
    prompts = {
        k.value: v
        for k, v in DreamCalibrationSession.PROMPTS.items()
    }
    result = render_calibration_screens(prompts, size=64)
    assert set(result.keys()) == {"sakura", "rose", "lotus"}
    for phase, screens in result.items():
        assert len(screens) == 3
        for screen in screens:
            assert screen is not None
            assert screen[:4] == b'\x89PNG'
