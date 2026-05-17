"""
Tests for the divine encounter system (Ko + Moshize Jabiru altar encounters).
"""

import pytest
from ambroflow.ko.divine_encounter import (
    encounter_ko,
    encounter_moshize_jabiru,
    altar_encounter,
    DivineEncounterKind,
    ALTAR_ENTITIES,
    ALTAR_ENTITY_LABELS,
    KO_EXCHANGES,
    MOSHIZE_JABIRU_EXCHANGES,
)


# ── Ko encounters ─────────────────────────────────────────────────────────────

def test_ko_encounter_returns_result():
    result = encounter_ko(
        ko_weight=0.0,
        sanity_avg=0.7,
        active_perks=frozenset(),
        letter_arrived=False,
    )
    assert result.entity == DivineEncounterKind.KO
    assert len(result.lines) >= 1
    assert result.sanity_delta


def test_ko_encounter_early_game_fresh():
    result = encounter_ko(
        ko_weight=0.0,
        sanity_avg=0.7,
        active_perks=frozenset(),
        letter_arrived=False,
    )
    assert result.exchange_key == "early_game_fresh"


def test_ko_encounter_breathwork_perk_prioritised():
    result = encounter_ko(
        ko_weight=0.0,
        sanity_avg=0.7,
        active_perks=frozenset({"breathwork_meditation"}),
        letter_arrived=False,
    )
    assert result.exchange_key == "breathwork_active"


def test_ko_encounter_high_ko_weight():
    result = encounter_ko(
        ko_weight=0.8,
        sanity_avg=0.7,
        active_perks=frozenset(),
        letter_arrived=True,   # letter arrived, so not early_game_fresh
    )
    assert result.exchange_key == "high_ko_weight"


def test_ko_encounter_low_sanity():
    result = encounter_ko(
        ko_weight=0.1,
        sanity_avg=0.3,
        active_perks=frozenset(),
        letter_arrived=True,
    )
    assert result.exchange_key == "low_sanity"


def test_ko_encounter_always_fallback():
    result = encounter_ko(
        ko_weight=0.1,
        sanity_avg=0.7,
        active_perks=frozenset(),
        letter_arrived=True,   # not early_game_fresh
    )
    assert result.exchange_key == "always"


# ── Moshize Jabiru encounters ─────────────────────────────────────────────────

def test_jabiru_encounter_returns_result():
    result = encounter_moshize_jabiru(
        ko_weight=0.0,
        sanity_avg=0.7,
        active_perks=frozenset(),
        letter_arrived=False,
    )
    assert result.entity == DivineEncounterKind.MOSHIZE_JABIRU
    assert len(result.lines) >= 1
    assert result.sanity_delta


def test_jabiru_encounter_early_game():
    result = encounter_moshize_jabiru(
        ko_weight=0.0,
        sanity_avg=0.7,
        active_perks=frozenset(),
        letter_arrived=False,
    )
    assert result.exchange_key == "early_game_fresh"


def test_jabiru_encounter_breathwork():
    result = encounter_moshize_jabiru(
        ko_weight=0.0,
        sanity_avg=0.7,
        active_perks=frozenset({"breathwork_meditation"}),
        letter_arrived=False,
    )
    assert result.exchange_key == "breathwork_active"


# ── Altar dispatch ────────────────────────────────────────────────────────────

def test_altar_dispatch_ko():
    result = altar_encounter(
        entity=DivineEncounterKind.KO,
        ko_weight=0.0,
        sanity_avg=0.7,
        active_perks=frozenset(),
    )
    assert result is not None
    assert result.entity == DivineEncounterKind.KO


def test_altar_dispatch_jabiru():
    result = altar_encounter(
        entity=DivineEncounterKind.MOSHIZE_JABIRU,
        ko_weight=0.0,
        sanity_avg=0.7,
        active_perks=frozenset(),
    )
    assert result is not None
    assert result.entity == DivineEncounterKind.MOSHIZE_JABIRU


def test_altar_dispatch_unknown_entity():
    result = altar_encounter(
        entity="nonexistent_god",
        ko_weight=0.0,
        sanity_avg=0.7,
        active_perks=frozenset(),
    )
    assert result is None


def test_altar_entities_registered():
    assert DivineEncounterKind.KO in ALTAR_ENTITIES
    assert DivineEncounterKind.MOSHIZE_JABIRU in ALTAR_ENTITIES


def test_altar_entity_labels():
    assert ALTAR_ENTITY_LABELS[DivineEncounterKind.KO] == "Ko"
    assert ALTAR_ENTITY_LABELS[DivineEncounterKind.MOSHIZE_JABIRU] == "Moshize Jabiru"


# ── Sanity deltas are non-empty ───────────────────────────────────────────────

def test_all_ko_exchanges_have_sanity_delta():
    for exchange in KO_EXCHANGES:
        assert exchange.sanity_delta, f"Ko exchange {exchange.condition_key!r} has no sanity delta"


def test_all_jabiru_exchanges_have_sanity_delta():
    for exchange in MOSHIZE_JABIRU_EXCHANGES:
        assert exchange.sanity_delta, \
            f"Jabiru exchange {exchange.condition_key!r} has no sanity delta"


# ── Orrery recording (null orrery) ────────────────────────────────────────────

class _NullOrrery:
    def __init__(self):
        self.events = []
    def record(self, kind, payload):
        self.events.append((kind, payload))


def test_ko_records_to_orrery():
    orrery = _NullOrrery()
    encounter_ko(0.0, 0.7, frozenset(), orrery=orrery, actor_id="test_player")
    assert any(kind == "divine_encounter.ko" for kind, _ in orrery.events)


def test_jabiru_records_to_orrery():
    orrery = _NullOrrery()
    encounter_moshize_jabiru(0.0, 0.7, frozenset(), orrery=orrery, actor_id="test_player")
    assert any(kind == "divine_encounter.moshize_jabiru" for kind, _ in orrery.events)
