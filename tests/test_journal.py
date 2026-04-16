"""Tests for the journal system."""

import pytest
from ambroflow.journal.journal import Journal, EntryKind


class _MockOrrery:
    def __init__(self):
        self.events = []
        self.void_wraith_calls = []
    def record(self, kind, payload):
        self.events.append((kind, payload))
    def void_wraith_observe(self, observation_id, context):
        self.void_wraith_calls.append((observation_id, context))


def _make_journal():
    return Journal(actor_id="0000_0451", game_id="7_KLGS", orrery=_MockOrrery())


def test_write_entry():
    j = _make_journal()
    e = j.write(EntryKind.LORE_FRAGMENT, "Fragment 1", "Body text")
    assert e.title == "Fragment 1"
    assert e.kind == EntryKind.LORE_FRAGMENT
    assert j.entry_count == 1


def test_quest_note_tagged_with_quest_id():
    j = _make_journal()
    e = j.quest_note("0009_KLST", "Demons and Diamonds", "Met Alfir today.")
    assert "0009_KLST" in e.tags


def test_dream_note_fires_void_wraith():
    orrery = _MockOrrery()
    j = Journal(actor_id="0000_0451", game_id="7_KLGS", orrery=orrery)
    j.dream_note("First Dream", "Ko spoke to me.")
    assert len(orrery.void_wraith_calls) == 1
    assert orrery.void_wraith_calls[0][0] == "journal.dream.written"


def test_non_dream_note_no_void_wraith():
    orrery = _MockOrrery()
    j = Journal(actor_id="0000_0451", game_id="7_KLGS", orrery=orrery)
    j.lore_fragment("A stone speaks", "It said nothing useful.")
    assert len(orrery.void_wraith_calls) == 0


def test_entries_by_kind():
    j = _make_journal()
    j.lore_fragment("A", "a")
    j.lore_fragment("B", "b")
    j.reflection("Thought", "thinking")
    assert len(j.entries_by_kind(EntryKind.LORE_FRAGMENT)) == 2
    assert len(j.entries_by_kind(EntryKind.REFLECTION)) == 1


def test_entries_by_tag():
    j = _make_journal()
    j.character_note("0006_WTCH", "Alfir", "The witch teacher.")
    j.character_note("1018_DJNN", "Drovitth", "The Djinn, builder of the Orrery.")
    results = j.entries_by_tag("0006_WTCH")
    assert len(results) == 1
    assert results[0].title == "Alfir"


def test_orrery_event_fired_on_write():
    orrery = _MockOrrery()
    j = Journal(actor_id="0000_0451", game_id="7_KLGS", orrery=orrery)
    j.write(EntryKind.OBSERVATION, "Saw something", "Can't describe it yet.")
    assert any(kind == "journal.entry.written" for kind, _ in orrery.events)
