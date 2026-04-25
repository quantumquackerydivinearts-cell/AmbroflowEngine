"""Tests for ambroflow.dialogue.selector."""

import json
import tempfile
from pathlib import Path

import pytest
from ambroflow.dialogue.loader import load_from_file
from ambroflow.dialogue.selector import (
    load_paths,
    load_paths_dir,
    select,
    render_interaction,
    DialogueScreen,
    _fallback_select,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _minimal_registry():
    return {
        "characters": [
            {"id": "0006_WTCH", "name": "Alfir",           "type": "WTCH", "role": "mentor"},
            {"id": "0019_ROYL", "name": "Princess Luminyx", "type": "ROYL"},
        ],
        "quests":  [{"slug": "0009_KLST", "name": "Demons and Diamonds"}],
        "items":   [],
        "objects": [],
    }


def _minimal_bundle(tmp_dir: Path):
    reg_path = tmp_dir / "7_KLGS" / "registry.json"
    reg_path.parent.mkdir(parents=True)
    reg_path.write_text(json.dumps(_minimal_registry()), encoding="utf-8")
    return load_from_file(reg_path)


def _quest_state(witnessed=None):
    """Build a minimal quest_state dict."""
    entries = {}
    for eid in (witnessed or []):
        entries[eid] = {"witness_state": "witnessed", "witnessed_candidate": "a"}
    return {
        "quest_id": "test_quest",
        "game_id": "7_KLGS",
        "entries": entries,
        "soa_artifacts": [],
        "current_frame": "frame_0",
    }


def _paths():
    return [
        {
            "path_id": "path_default",
            "character_id": "0006_WTCH",
            "realm_id": "lapidus",
            "priority": 0,
            "required_witnesses": [],
            "blocked_witnesses": [],
            "lines": [
                {"speaker": "0006_WTCH", "text": "The path of the Infernal awaits.", "shygazun": ""},
                {"speaker": "player",     "text": "Tell me more.",                    "shygazun": ""},
            ],
            "meta": {},
        },
        {
            "path_id": "path_post_quest",
            "character_id": "0006_WTCH",
            "realm_id": "lapidus",
            "priority": 10,
            "required_witnesses": ["0009_KLST"],
            "blocked_witnesses": [],
            "lines": [
                {"speaker": "0006_WTCH", "text": "You've proven yourself. Sulphera calls.", "shygazun": ""},
            ],
            "meta": {},
        },
        {
            "path_id": "path_sulphera",
            "character_id": "0006_WTCH",
            "realm_id": "sulphera",
            "priority": 5,
            "required_witnesses": ["0009_KLST"],
            "blocked_witnesses": [],
            "lines": [
                {"speaker": "0006_WTCH", "text": "Welcome to the first ring.", "shygazun": ""},
            ],
            "meta": {},
        },
    ]


# ── load_paths ────────────────────────────────────────────────────────────────

def test_load_paths_from_list():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "dialogue_0006_WTCH.json"
        p.write_text(json.dumps(_paths()), encoding="utf-8")
        loaded = load_paths(p)
    assert len(loaded) == 3
    assert loaded[0]["path_id"] == "path_default"


def test_load_paths_from_envelope():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "dialogue_alfir.json"
        p.write_text(
            json.dumps({"character_id": "0006_WTCH", "paths": _paths()}),
            encoding="utf-8",
        )
        loaded = load_paths(p)
    assert len(loaded) == 3


def test_load_paths_missing_file():
    with pytest.raises(FileNotFoundError):
        load_paths("/nonexistent/dialogue.json")


def test_load_paths_dir():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "dialogue_0006_WTCH.json").write_text(
            json.dumps(_paths()), encoding="utf-8"
        )
        (d / "dialogue_0019_ROYL.json").write_text(
            json.dumps([{
                "path_id": "royl_default",
                "character_id": "0019_ROYL",
                "realm_id": "lapidus",
                "priority": 0,
                "required_witnesses": [],
                "blocked_witnesses": [],
                "lines": [{"speaker": "0019_ROYL", "text": "Hello.", "shygazun": ""}],
                "meta": {},
            }]),
            encoding="utf-8",
        )
        by_char = load_paths_dir(d)
    assert "0006_WTCH" in by_char
    assert "0019_ROYL" in by_char
    assert len(by_char["0006_WTCH"]) == 3


# ── fallback_select ───────────────────────────────────────────────────────────

def test_fallback_default_path():
    state = _quest_state()
    chosen = _fallback_select(state, "lapidus", "0006_WTCH", _paths())
    assert chosen is not None
    assert chosen["path_id"] == "path_default"


def test_fallback_post_quest_higher_priority():
    state = _quest_state(witnessed=["0009_KLST"])
    chosen = _fallback_select(state, "lapidus", "0006_WTCH", _paths())
    assert chosen["path_id"] == "path_post_quest"


def test_fallback_sulphera_blocked_without_gate():
    state = _quest_state()
    chosen = _fallback_select(state, "sulphera", "0006_WTCH", _paths())
    assert chosen is None


def test_fallback_sulphera_accessible_with_gate():
    state = _quest_state(witnessed=["0009_KLST"])
    chosen = _fallback_select(state, "sulphera", "0006_WTCH", _paths())
    assert chosen is not None
    assert chosen["path_id"] == "path_sulphera"


def test_fallback_blocked_witness():
    paths = [
        {
            "path_id": "blocked_path",
            "character_id": "0006_WTCH",
            "realm_id": "lapidus",
            "priority": 20,
            "required_witnesses": [],
            "blocked_witnesses": ["0009_KLST"],
            "lines": [{"speaker": "0006_WTCH", "text": "Not yet.", "shygazun": ""}],
            "meta": {},
        },
        {
            "path_id": "default_path",
            "character_id": "0006_WTCH",
            "realm_id": "lapidus",
            "priority": 0,
            "required_witnesses": [],
            "blocked_witnesses": [],
            "lines": [{"speaker": "0006_WTCH", "text": "Come in.", "shygazun": ""}],
            "meta": {},
        },
    ]
    # With 0009_KLST witnessed, blocked_path is unavailable → default wins
    state = _quest_state(witnessed=["0009_KLST"])
    chosen = _fallback_select(state, "lapidus", "0006_WTCH", paths)
    assert chosen["path_id"] == "default_path"


# ── select ────────────────────────────────────────────────────────────────────

def test_select_returns_dialogue_screen():
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _minimal_bundle(Path(tmp))
        state  = _quest_state()
        screen = select(state, "lapidus", "0006_WTCH", _paths(), bundle)
    assert screen is not None
    assert isinstance(screen, DialogueScreen)
    assert screen.character_id == "0006_WTCH"
    assert screen.name         == "Alfir"
    assert screen.char_type    == "WTCH"
    assert screen.realm_id     == "lapidus"
    assert screen.path_id      == "path_default"
    assert "Infernal" in screen.text


def test_select_choices_extracted():
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _minimal_bundle(Path(tmp))
        state  = _quest_state()
        screen = select(state, "lapidus", "0006_WTCH", _paths(), bundle)
    assert screen is not None
    assert screen.choices == ["Tell me more."]


def test_select_post_quest_path():
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _minimal_bundle(Path(tmp))
        state  = _quest_state(witnessed=["0009_KLST"])
        screen = select(state, "lapidus", "0006_WTCH", _paths(), bundle)
    assert screen is not None
    assert screen.path_id == "path_post_quest"
    assert "Sulphera" in screen.text


def test_select_no_matching_path():
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _minimal_bundle(Path(tmp))
        state  = _quest_state()
        screen = select(state, "sulphera", "0006_WTCH", _paths(), bundle)
    assert screen is None


def test_select_unknown_character():
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _minimal_bundle(Path(tmp))
        state  = _quest_state()
        paths  = [{
            "path_id": "p",
            "character_id": "9999_UNKN",
            "realm_id": "lapidus",
            "priority": 0,
            "required_witnesses": [],
            "blocked_witnesses": [],
            "lines": [{"speaker": "9999_UNKN", "text": "Who am I?", "shygazun": ""}],
            "meta": {},
        }]
        screen = select(state, "lapidus", "9999_UNKN", paths, bundle)
    assert screen is not None
    assert screen.name      == "9999_UNKN"   # falls back to id
    assert screen.char_type == "TOWN"        # default type


# ── render_interaction ────────────────────────────────────────────────────────

from ambroflow.dialogue.render import _PIL_AVAILABLE

@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_render_interaction_returns_png():
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _minimal_bundle(Path(tmp))
        state  = _quest_state()
        png    = render_interaction(state, "lapidus", "0006_WTCH", _paths(), bundle)
    assert png is not None
    assert png[:4] == b'\x89PNG'


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_render_interaction_no_match_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _minimal_bundle(Path(tmp))
        state  = _quest_state()
        result = render_interaction(state, "sulphera", "0006_WTCH", _paths(), bundle)
    assert result is None


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_dialogue_screen_render():
    with tempfile.TemporaryDirectory() as tmp:
        bundle = _minimal_bundle(Path(tmp))
        state  = _quest_state()
        screen = select(state, "lapidus", "0006_WTCH", _paths(), bundle)
    assert screen is not None
    png = screen.render()
    assert png is not None
    assert png[:4] == b'\x89PNG'