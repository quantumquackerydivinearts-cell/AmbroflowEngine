"""Tests for character dialogue renderer and game data loader."""

import json
import tempfile
from pathlib import Path

import pytest
from ambroflow.dialogue.loader import (
    GameDataBundle,
    CharacterRecord,
    load_from_file,
)
from ambroflow.dialogue.render import (
    render_character_dialogue,
    render_character_portrait_placeholder,
    _PIL_AVAILABLE,
)


# ── CharacterRecord ───────────────────────────────────────────────────────────

def test_character_record_from_dict():
    rec = CharacterRecord.from_dict({
        "id":    "0006_WTCH",
        "name":  "Alfir",
        "type":  "WTCH",
        "role":  "mentor",
        "teaches": "infernal_meditation",
    })
    assert rec.id   == "0006_WTCH"
    assert rec.name == "Alfir"
    assert rec.type == "WTCH"
    assert rec.meta["role"] == "mentor"
    assert rec.meta["teaches"] == "infernal_meditation"


def test_character_record_missing_id():
    rec = CharacterRecord.from_dict({"name": "Unknown", "type": "TOWN"})
    assert rec.id == ""


# ── GameDataBundle ────────────────────────────────────────────────────────────

def _minimal_registry() -> dict:
    return {
        "characters": [
            {"id": "0006_WTCH", "name": "Alfir",           "type": "WTCH"},
            {"id": "0019_ROYL", "name": "Princess Luminyx", "type": "ROYL"},
            {"id": "2001_VDWR", "name": "Haldoro",          "type": "VDWR"},
        ],
        "quests": [
            {"slug": "0009_KLST", "name": "Demons and Diamonds"},
        ],
        "items":  [{"id": "0028_KLIT", "name": "Herb (Common)"}],
        "objects": [{"id": "0001_KLOB", "name": "Mortar"}],
    }


def test_bundle_load_from_file():
    reg = _minimal_registry()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "7_KLGS" / "registry.json"
        path.parent.mkdir()
        path.write_text(json.dumps(reg), encoding="utf-8")

        bundle = load_from_file(path)

    assert bundle.game_slug == "7_KLGS"
    assert "0006_WTCH" in bundle.characters
    assert bundle.characters["0006_WTCH"].name == "Alfir"
    assert "0009_KLST" in bundle.quests
    assert "0028_KLIT"  in bundle.items
    assert "0001_KLOB" in bundle.objects


def test_bundle_character_lookup():
    reg = _minimal_registry()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "7_KLGS" / "registry.json"
        path.parent.mkdir()
        path.write_text(json.dumps(reg), encoding="utf-8")
        bundle = load_from_file(path)

    char = bundle.character("0019_ROYL")
    assert char is not None
    assert char.name == "Princess Luminyx"
    assert bundle.character("nonexistent") is None


def test_bundle_characters_of_type():
    reg = _minimal_registry()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "7_KLGS" / "registry.json"
        path.parent.mkdir()
        path.write_text(json.dumps(reg), encoding="utf-8")
        bundle = load_from_file(path)

    witches = bundle.characters_of_type("WTCH")
    assert len(witches) == 1
    assert witches[0].id == "0006_WTCH"


def test_bundle_portrait_from_file():
    """Portraits stored as PNG files next to registry.json are loaded."""
    reg = _minimal_registry()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "7_KLGS"
        base.mkdir()
        (base / "registry.json").write_text(json.dumps(reg), encoding="utf-8")

        # Write a minimal valid PNG (1×1 pixel)
        import io, struct, zlib
        def tiny_png(r, g, b):
            def chunk(tag, data):
                c = zlib.crc32(tag + data) & 0xFFFFFFFF
                return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", c)
            raw = b'\x89PNG\r\n\x1a\n'
            raw += chunk(b'IHDR', struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            scanline = b'\x00' + bytes([r, g, b])
            compressed = zlib.compress(scanline)
            raw += chunk(b'IDAT', compressed)
            raw += chunk(b'IEND', b'')
            return raw

        portrait_dir = base / "portraits"
        portrait_dir.mkdir()
        (portrait_dir / "0006_WTCH.png").write_bytes(tiny_png(80, 140, 130))

        bundle = load_from_file(base / "registry.json")
        portrait = bundle.get_portrait("0006_WTCH")

    assert portrait is not None
    assert portrait[:4] == b'\x89PNG'


def test_bundle_missing_portrait_returns_none():
    reg = _minimal_registry()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "7_KLGS" / "registry.json"
        path.parent.mkdir()
        path.write_text(json.dumps(reg), encoding="utf-8")
        bundle = load_from_file(path)
    assert bundle.get_portrait("0006_WTCH") is None


def test_load_from_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_from_file("/nonexistent/path/registry.json")


# ── Portrait placeholder ──────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_placeholder_returns_png():
    data = render_character_portrait_placeholder("WTCH")
    assert data is not None
    assert data[:4] == b'\x89PNG'


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_placeholder_correct_size():
    from PIL import Image
    import io
    data = render_character_portrait_placeholder("ROYL", width=100, height=120)
    img  = Image.open(io.BytesIO(data))
    assert img.size == (100, 120)


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_placeholder_all_types():
    types = ["GODS","ANMU","PRIM","VDWR","DJNN","DMON","DEMI",
             "DRYA","NYMP","UNDI","SALA","GNOM","ROYL","WTCH",
             "PRST","ASSN","SOLD","TOWN"]
    for t in types:
        data = render_character_portrait_placeholder(t)
        assert data is not None, f"Failed for type {t}"


# ── Dialogue screen ───────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_screen_no_portrait():
    data = render_character_dialogue(
        "Alfir", "WTCH",
        "The Infernal perk is yours. Use it carefully.",
    )
    assert data is not None
    assert data[:4] == b'\x89PNG'


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_screen_correct_size():
    from PIL import Image
    import io
    data = render_character_dialogue("Wells", "TOWN", "Good morning.", width=512, height=256)
    img  = Image.open(io.BytesIO(data))
    assert img.size == (512, 256)


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_screen_with_choices():
    data = render_character_dialogue(
        "Princess Luminyx", "ROYL",
        "What brings you to the palace?",
        choices=["I seek an audience with the King.", "I am lost.", "Nevermind."],
    )
    assert data is not None
    assert data[:4] == b'\x89PNG'


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_all_types_render():
    """All character types render without crashing."""
    types = ["GODS","ANMU","PRIM","VDWR","DJNN","DMON","DEMI",
             "DRYA","NYMP","UNDI","SALA","GNOM","ROYL","WTCH",
             "PRST","ASSN","SOLD","TOWN"]
    for t in types:
        data = render_character_dialogue("Name", t, "Some text.", width=256, height=128)
        assert data is not None, f"Failed for type {t}"


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_with_portrait_bytes():
    """When portrait_bytes is supplied it is used instead of the placeholder."""
    from ambroflow.ko.dialogue_render import render_ko_portrait
    portrait = render_ko_portrait(size=64)
    data = render_character_dialogue(
        "Ko", "GODS", "The coil advances.",
        portrait_bytes=portrait,
    )
    assert data is not None
    assert data[:4] == b'\x89PNG'

    # Screen with portrait should differ from one without
    no_portrait = render_character_dialogue("Ko", "GODS", "The coil advances.")
    assert data != no_portrait


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_long_text():
    long_text = (
        "The lottery is not a game of chance. The Orrery has already read the weights. "
        "Your role is not to win but to understand why the result was always going to be this. "
        "Begin with the Infernal Meditation and Alfir will explain the rest."
    )
    data = render_character_dialogue("Drovitth", "DJNN", long_text, width=512, height=256)
    assert data is not None
