"""
Tests for SceneRunner — lock evaluation, scene firing, key propagation,
quest tracker integration, dialogue topics.
"""

import pytest
from unittest.mock import MagicMock

from ambroflow.quests.keyring import KeyRing
from ambroflow.quests.schema import Lock, Beat, Scene, DialogueTopic, DialogueResponse, QuestScript
from ambroflow.quests.scene_runner import SceneRunner
from ambroflow.quests.tracker import QuestTracker, QuestStatus


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_tracker() -> QuestTracker:
    orrery = MagicMock()
    orrery.record = MagicMock(return_value={})
    return QuestTracker(actor_id="player", orrery=orrery)


def make_scene(
    scene_id="test_scene",
    zone="test_zone",
    lock=None,
    grants=(),
    beats=(),
    repeatable=False,
) -> Scene:
    return Scene(
        id=scene_id,
        zone=zone,
        lock=lock or Lock(),
        grants=list(grants),
        beats=list(beats),
        repeatable=repeatable,
    )


def make_script(
    quest_id="0001_KLST",
    completion_key="quest_done",
    failure_key=None,
    scenes=(),
    topics=(),
) -> QuestScript:
    return QuestScript(
        quest_id=quest_id,
        game_slug="7_KLGS",
        title="Test Quest",
        completion_key=completion_key,
        failure_key=failure_key,
        scenes=list(scenes),
        topics=list(topics),
    )


def make_runner(scripts=(), hour=12, keys=()) -> tuple[SceneRunner, KeyRing, QuestTracker]:
    ring = KeyRing(keys=set(keys))
    tracker = make_tracker()
    runner = SceneRunner(
        keyring=ring,
        quest_tracker=tracker,
        scripts=list(scripts),
        hour=hour,
    )
    return runner, ring, tracker


# ── Lock evaluation ───────────────────────────────────────────────────────────

def test_empty_lock_always_open():
    runner, ring, _ = make_runner()
    assert runner._lock_open(Lock()) is True


def test_requires_present():
    runner, ring, _ = make_runner(keys=["a"])
    assert runner._lock_open(Lock(requires=["a"])) is True


def test_requires_missing():
    runner, ring, _ = make_runner()
    assert runner._lock_open(Lock(requires=["a"])) is False


def test_excludes_absent():
    runner, ring, _ = make_runner(keys=["a"])
    assert runner._lock_open(Lock(requires=["a"], excludes=["b"])) is True


def test_excludes_present():
    runner, ring, _ = make_runner(keys=["a", "b"])
    assert runner._lock_open(Lock(requires=["a"], excludes=["b"])) is False


def test_time_window_in_range():
    runner, _, _ = make_runner(hour=14)
    assert runner._lock_open(Lock(time_window=(12, 18))) is True


def test_time_window_out_of_range():
    runner, _, _ = make_runner(hour=10)
    assert runner._lock_open(Lock(time_window=(12, 18))) is False


def test_time_window_wraps_midnight_inside():
    runner, _, _ = make_runner(hour=23)
    assert runner._lock_open(Lock(time_window=(22, 4))) is True


def test_time_window_wraps_midnight_outside():
    runner, _, _ = make_runner(hour=12)
    assert runner._lock_open(Lock(time_window=(22, 4))) is False


def test_set_hour():
    runner, _, _ = make_runner(hour=10)
    assert runner._lock_open(Lock(time_window=(12, 18))) is False
    runner.set_hour(14)
    assert runner._lock_open(Lock(time_window=(12, 18))) is True


# ── available_scenes ──────────────────────────────────────────────────────────

def test_available_scenes_zone_match():
    scene = make_scene(zone="zone_a")
    script = make_script(scenes=[scene])
    runner, _, _ = make_runner(scripts=[script])
    assert len(runner.available_scenes("zone_a")) == 1
    assert len(runner.available_scenes("zone_b")) == 0


def test_available_scenes_lock_filters():
    scene = make_scene(zone="z", lock=Lock(requires=["key_a"]))
    script = make_script(scenes=[scene])
    runner, ring, _ = make_runner(scripts=[script])
    assert runner.available_scenes("z") == []
    ring.grant("key_a")
    assert len(runner.available_scenes("z")) == 1


def test_available_scenes_fired_excluded():
    scene = make_scene(scene_id="s1", zone="z")
    script = make_script(scenes=[scene])
    runner, _, _ = make_runner(scripts=[script])
    runner.fire_scene(scene)
    assert runner.available_scenes("z") == []


def test_available_scenes_repeatable_refires():
    scene = make_scene(scene_id="s1", zone="z", repeatable=True)
    script = make_script(scenes=[scene])
    runner, _, _ = make_runner(scripts=[script])
    runner.fire_scene(scene)
    assert len(runner.available_scenes("z")) == 1


# ── fire_scene ────────────────────────────────────────────────────────────────

def test_fire_scene_grants_keys():
    scene = make_scene(grants=["k1", "k2"])
    script = make_script(scenes=[scene])
    runner, ring, _ = make_runner(scripts=[script])
    new = runner.fire_scene(scene)
    assert set(new) == {"k1", "k2"}
    assert ring.has("k1")
    assert ring.has("k2")


def test_fire_scene_marks_fired():
    scene = make_scene(scene_id="s1", zone="z")
    script = make_script(scenes=[scene])
    runner, _, _ = make_runner(scripts=[script])
    runner.fire_scene(scene)
    assert runner.is_fired("s1")


def test_fire_scene_returns_only_new_keys():
    scene = make_scene(grants=["k1", "k2"])
    script = make_script(scenes=[scene])
    runner, ring, _ = make_runner(scripts=[script], keys=["k1"])
    new = runner.fire_scene(scene)
    assert new == ["k2"]


# ── fire_beat ─────────────────────────────────────────────────────────────────

def test_fire_beat_grants_keys():
    beat = Beat(speaker="NPC", text="hello", grants=["beat_key"])
    runner, ring, _ = make_runner()
    new = runner.fire_beat(beat)
    assert new == ["beat_key"]
    assert ring.has("beat_key")


# ── fire_response ─────────────────────────────────────────────────────────────

def test_fire_response_grants_keys():
    response = DialogueResponse(text="option A", grants=["resp_key"])
    runner, ring, _ = make_runner()
    new = runner.fire_response(response)
    assert new == ["resp_key"]
    assert ring.has("resp_key")


# ── grant_key ─────────────────────────────────────────────────────────────────

def test_grant_key_new():
    runner, ring, _ = make_runner()
    assert runner.grant_key("x") is True
    assert ring.has("x")


def test_grant_key_existing():
    runner, ring, _ = make_runner(keys=["x"])
    assert runner.grant_key("x") is False


# ── Quest tracker propagation ─────────────────────────────────────────────────

def test_completion_key_completes_quest():
    script = make_script(quest_id="0001_KLST", completion_key="quest_complete")
    runner, _, tracker = make_runner(scripts=[script])
    tracker.start("0001_KLST")
    runner.grant_key("quest_complete")
    assert tracker.status("0001_KLST") == QuestStatus.COMPLETED


def test_failure_key_fails_quest():
    script = make_script(
        quest_id="0001_KLST",
        completion_key="quest_done",
        failure_key="quest_failed",
    )
    runner, _, tracker = make_runner(scripts=[script])
    tracker.start("0001_KLST")
    runner.grant_key("quest_failed")
    assert tracker.status("0001_KLST") == QuestStatus.FAILED


def test_scene_grant_propagates_completion():
    scene = make_scene(grants=["quest_complete"])
    script = make_script(
        quest_id="0001_KLST",
        completion_key="quest_complete",
        scenes=[scene],
    )
    runner, _, tracker = make_runner(scripts=[script])
    tracker.start("0001_KLST")
    runner.fire_scene(scene)
    assert tracker.status("0001_KLST") == QuestStatus.COMPLETED


# ── available_topics ─────────────────────────────────────────────────────────

def test_available_topics_char_match():
    topic = DialogueTopic(
        id="t1", char_id="0006_WTCH", prompt="hello",
        lock=Lock(),
    )
    script = make_script(topics=[topic])
    runner, _, _ = make_runner(scripts=[script])
    assert len(runner.available_topics("0006_WTCH")) == 1
    assert len(runner.available_topics("0007_WTCH")) == 0


def test_available_topics_lock_filters():
    topic = DialogueTopic(
        id="t1", char_id="0006_WTCH", prompt="hello",
        lock=Lock(requires=["alfir_met"]),
    )
    script = make_script(topics=[topic])
    runner, ring, _ = make_runner(scripts=[script])
    assert runner.available_topics("0006_WTCH") == []
    ring.grant("alfir_met")
    assert len(runner.available_topics("0006_WTCH")) == 1


# ── fired state ──────────────────────────────────────────────────────────────

def test_fired_scenes_sorted():
    runner, _, _ = make_runner()
    runner.mark_fired("b_scene")
    runner.mark_fired("a_scene")
    assert runner.fired_scenes() == ["a_scene", "b_scene"]


def test_restore_fired():
    runner, _, _ = make_runner()
    SceneRunner.restore_fired(runner, ["s1", "s2"])
    assert runner.is_fired("s1")
    assert runner.is_fired("s2")
