"""Tests for ambroflow.world.loaders."""

import json
import tempfile
from pathlib import Path

import pytest
from ambroflow.world.loaders import (
    EncounterDef,
    AudioTrack,
    load_encounter_defs,
    load_audio_tracks,
    load_quest_steps,
    select_audio,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _quest_state(witnessed=None):
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


def _enc(encounter_id="enc_01", zone_id="lapidus_town", trigger_type="always",
         entry_id="", candidate=""):
    return {
        "encounter_id": encounter_id,
        "name": "Test Encounter",
        "zone_id": zone_id,
        "trigger_type": trigger_type,
        "entry_id": entry_id,
        "candidate": candidate,
        "combatants": ["enemy_1"],
        "loot": ["item_x"],
        "xp_reward": 50,
    }


def _track(track_id="trk_01", realm_id="lapidus", condition="always",
           required_witness="", priority=0):
    return {
        "track_id": track_id,
        "name": "Lapidus Theme",
        "file": "lapidus.ogg",
        "channel": "music",
        "realm_id": realm_id,
        "quest_id": "",
        "required_witness": required_witness,
        "loop": True,
        "condition": condition,
        "priority": priority,
    }


# ── load_encounter_defs ───────────────────────────────────────────────────────

def test_load_encounter_defs_list():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "encounters.json"
        p.write_text(json.dumps([_enc(), _enc("enc_02")]), encoding="utf-8")
        defs = load_encounter_defs(p)
    assert len(defs) == 2
    assert defs[0].encounter_id == "enc_01"


def test_load_encounter_defs_envelope():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "encounters.json"
        p.write_text(
            json.dumps({"encounters": [_enc()]}), encoding="utf-8"
        )
        defs = load_encounter_defs(p)
    assert len(defs) == 1


def test_load_encounter_defs_missing():
    with pytest.raises(FileNotFoundError):
        load_encounter_defs("/nonexistent/enc.json")


# ── EncounterDef.fires ────────────────────────────────────────────────────────

def test_fires_always():
    enc = EncounterDef(
        encounter_id="e1", name="E", zone_id="z1", trigger_type="always",
        entry_id="", candidate="", combatants=(), loot=(), xp_reward=0,
    )
    assert enc.fires(_quest_state(), "z1") is True


def test_fires_wrong_zone():
    enc = EncounterDef(
        encounter_id="e1", name="E", zone_id="other_zone", trigger_type="always",
        entry_id="", candidate="", combatants=(), loot=(), xp_reward=0,
    )
    assert enc.fires(_quest_state(), "z1") is False


def test_fires_quest_witnessed_before():
    enc = EncounterDef(
        encounter_id="e1", name="E", zone_id="", trigger_type="quest_witnessed",
        entry_id="0009_KLST", candidate="", combatants=(), loot=(), xp_reward=0,
    )
    assert enc.fires(_quest_state(), "any") is False
    assert enc.fires(_quest_state(witnessed=["0009_KLST"]), "any") is True


def test_fires_quest_unwitnessed():
    enc = EncounterDef(
        encounter_id="e1", name="E", zone_id="", trigger_type="quest_unwitnessed",
        entry_id="0009_KLST", candidate="", combatants=(), loot=(), xp_reward=0,
    )
    assert enc.fires(_quest_state(), "any") is True
    assert enc.fires(_quest_state(witnessed=["0009_KLST"]), "any") is False


def test_fires_quest_witnessed_specific_candidate():
    enc = EncounterDef(
        encounter_id="e1", name="E", zone_id="", trigger_type="quest_witnessed",
        entry_id="0009_KLST", candidate="b", combatants=(), loot=(), xp_reward=0,
    )
    # Witnessed but with candidate "a" — should not fire
    state = _quest_state(witnessed=["0009_KLST"])
    assert enc.fires(state, "any") is False


# ── load_audio_tracks ─────────────────────────────────────────────────────────

def test_load_audio_tracks_list():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "audio.json"
        p.write_text(json.dumps([_track(), _track("trk_02")]), encoding="utf-8")
        tracks = load_audio_tracks(p)
    assert len(tracks) == 2
    assert tracks[0].track_id == "trk_01"
    assert tracks[0].loop is True


def test_load_audio_tracks_envelope():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "audio.json"
        p.write_text(json.dumps({"tracks": [_track()]}), encoding="utf-8")
        tracks = load_audio_tracks(p)
    assert len(tracks) == 1


def test_load_audio_tracks_missing():
    with pytest.raises(FileNotFoundError):
        load_audio_tracks("/nonexistent/audio.json")


# ── select_audio ──────────────────────────────────────────────────────────────

def test_select_audio_by_realm():
    tracks = [
        AudioTrack(track_id="t1", name="", file="", channel="music",
                   realm_id="lapidus", quest_id="", required_witness="",
                   loop=True, condition="always", priority=0),
        AudioTrack(track_id="t2", name="", file="", channel="music",
                   realm_id="sulphera", quest_id="", required_witness="",
                   loop=True, condition="always", priority=0),
    ]
    result = select_audio(tracks, _quest_state(), "lapidus")
    assert result is not None
    assert result.track_id == "t1"


def test_select_audio_higher_priority_wins():
    tracks = [
        AudioTrack(track_id="low",  name="", file="", channel="music",
                   realm_id="lapidus", quest_id="", required_witness="",
                   loop=True, condition="always", priority=0),
        AudioTrack(track_id="high", name="", file="", channel="music",
                   realm_id="lapidus", quest_id="", required_witness="",
                   loop=True, condition="always", priority=10),
    ]
    result = select_audio(tracks, _quest_state(), "lapidus")
    assert result is not None
    assert result.track_id == "high"


def test_select_audio_witnessed_condition():
    tracks = [
        AudioTrack(track_id="post", name="", file="", channel="music",
                   realm_id="lapidus", quest_id="", required_witness="0009_KLST",
                   loop=True, condition="quest_witnessed", priority=5),
        AudioTrack(track_id="base", name="", file="", channel="music",
                   realm_id="lapidus", quest_id="", required_witness="",
                   loop=True, condition="always", priority=0),
    ]
    result_before = select_audio(tracks, _quest_state(), "lapidus")
    assert result_before is not None
    assert result_before.track_id == "base"

    result_after = select_audio(tracks, _quest_state(witnessed=["0009_KLST"]), "lapidus")
    assert result_after is not None
    assert result_after.track_id == "post"


def test_select_audio_no_match():
    tracks = [
        AudioTrack(track_id="t1", name="", file="", channel="music",
                   realm_id="sulphera", quest_id="", required_witness="",
                   loop=True, condition="always", priority=0),
    ]
    result = select_audio(tracks, _quest_state(), "lapidus")
    assert result is None


# ── load_quest_steps ──────────────────────────────────────────────────────────

def test_load_quest_steps_list():
    steps = [
        {"entry_id": "0009_KLST", "cannabis_symbol": "Ha",
         "candidate_a_label": "Accept", "candidate_b_label": "Decline",
         "description": "Alfir offers the Infernal pact."},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "quest.json"
        p.write_text(json.dumps(steps), encoding="utf-8")
        loaded = load_quest_steps(p)
    assert len(loaded) == 1
    assert loaded[0]["entry_id"] == "0009_KLST"
    assert loaded[0]["candidate_a_label"] == "Accept"


def test_load_quest_steps_envelope():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "quest.json"
        p.write_text(json.dumps({
            "quest_id": "0009_KLST",
            "steps": [{"entry_id": "0009_KLST", "cannabis_symbol": "Ha",
                        "candidate_a_label": "A", "candidate_b_label": "B"}],
        }), encoding="utf-8")
        loaded = load_quest_steps(p)
    assert len(loaded) == 1


def test_load_quest_steps_missing():
    with pytest.raises(FileNotFoundError):
        load_quest_steps("/nonexistent/quest.json")