"""
Tests for TileTracer — Lotus Table attestation system.
"""

import time
from unittest.mock import MagicMock

import pytest

from ambroflow.world.tile_trace import (
    TileTracer, TileAttestation, LOTUS_TABLE,
    FY, PU, TA, ZO, SHA, KO,
)


# ── LOTUS_TABLE ───────────────────────────────────────────────────────────────

def test_lotus_table_has_24_entries():
    assert len(LOTUS_TABLE) == 24


def test_lotus_table_keys_0_to_23():
    assert set(LOTUS_TABLE.keys()) == set(range(24))


def test_mode_marker_symbols():
    assert LOTUS_TABLE[FY][0]  == "Fy"
    assert LOTUS_TABLE[PU][0]  == "Pu"
    assert LOTUS_TABLE[TA][0]  == "Ta"
    assert LOTUS_TABLE[ZO][0]  == "Zo"
    assert LOTUS_TABLE[SHA][0] == "Sha"
    assert LOTUS_TABLE[KO][0]  == "Ko"


def test_obversion_byte_addresses():
    # Ontic pairs confirmed by the language spec
    assert FY  == 4   # Air Initiator
    assert PU  == 5   # Air Terminator
    assert TA  == 9   # Active being / presence
    assert ZO  == 16  # Absence / passive non-being
    assert SHA == 15  # Intellect of spirit
    assert KO  == 19  # Experience / intuition


# ── TileAttestation ───────────────────────────────────────────────────────────

def test_attestation_empty_initially():
    att = TileAttestation(zone_id="z", x=0, y=0)
    assert att.lotus_counts == {}
    assert att.attested_bytes == frozenset()


def test_attestation_has_returns_false_for_undeposited():
    att = TileAttestation(zone_id="z", x=0, y=0)
    assert not att.has(TA)
    assert not att.has(FY)
    assert not att.has(KO)


def test_attestation_symbol():
    att = TileAttestation(zone_id="z", x=0, y=0)
    assert att.symbol(TA) == "Ta"
    assert att.symbol(KO) == "Ko"
    assert att.symbol(SHA) == "Sha"


def test_attestation_dominant_empty():
    att = TileAttestation(zone_id="z", x=0, y=0)
    assert att.dominant() == []


def test_attestation_dominant_ranking():
    att = TileAttestation(zone_id="z", x=0, y=0,
                          lotus_counts={TA: 5, FY: 2, KO: 8})
    top = att.dominant(2)
    assert top[0] == KO   # 8
    assert top[1] == TA   # 5


def test_attestation_as_dict_from_dict_round_trip():
    att = TileAttestation(zone_id="wiltoll", x=3, y=7,
                          lotus_counts={TA: 3, FY: 1},
                          first_at={TA: 100.0, FY: 200.0},
                          last_at=300.0)
    d = att.as_dict()
    r = TileAttestation.from_dict("wiltoll", 3, 7, d)
    assert r.lotus_counts == {TA: 3, FY: 1}
    assert r.first_at[TA] == 100.0
    assert r.last_at == 300.0


# ── TileTracer.deposit ────────────────────────────────────────────────────────

def test_deposit_ta_increments():
    t = TileTracer()
    t.deposit("z", 0, 0, TA)
    assert t.attestation_at("z", 0, 0).count(TA) == 1


def test_deposit_fy_increments():
    t = TileTracer()
    t.deposit("z", 0, 0, FY)
    assert t.attestation_at("z", 0, 0).count(FY) == 1


def test_deposit_ko_increments():
    t = TileTracer()
    t.deposit("z", 0, 0, KO)
    assert t.attestation_at("z", 0, 0).count(KO) == 1


def test_deposit_multiple_bytes_in_one_call():
    t = TileTracer()
    t.deposit("z", 1, 1, TA, FY, KO)
    att = t.attestation_at("z", 1, 1)
    assert att.count(TA) == 1
    assert att.count(FY) == 1
    assert att.count(KO) == 1


def test_deposit_non_mode_marker_byte():
    t = TileTracer()
    t.deposit("z", 0, 0, 0)   # Ty — Earth Initiator
    assert t.attestation_at("z", 0, 0).count(0) == 1


def test_deposit_accumulates():
    t = TileTracer()
    for _ in range(4):
        t.deposit("z", 0, 0, TA)
    assert t.attestation_at("z", 0, 0).count(TA) == 4


def test_deposit_out_of_range_raises():
    t = TileTracer()
    with pytest.raises(ValueError):
        t.deposit("z", 0, 0, 24)   # out of Lotus Table


def test_deposit_records_first_at_only_once():
    t = TileTracer()
    t.deposit("z", 0, 0, FY)
    first = t.attestation_at("z", 0, 0).first_at[FY]
    time.sleep(0.01)
    t.deposit("z", 0, 0, FY)
    assert t.attestation_at("z", 0, 0).first_at[FY] == first


def test_deposit_returns_attestation():
    t = TileTracer()
    result = t.deposit("z", 2, 3, TA)
    assert isinstance(result, TileAttestation)
    assert result.count(TA) == 1


# ── Reads ─────────────────────────────────────────────────────────────────────

def test_attested_bytes_at_empty():
    t = TileTracer()
    assert t.attested_bytes_at("z", 0, 0) == frozenset()


def test_attested_bytes_at_after_deposit():
    t = TileTracer()
    t.deposit("z", 0, 0, TA, FY)
    assert t.attested_bytes_at("z", 0, 0) == frozenset({TA, FY})


def test_attested_tiles_all():
    t = TileTracer()
    t.deposit("z", 0, 0, TA)
    t.deposit("z", 1, 1, FY)
    assert len(t.attested_tiles()) == 2


def test_attested_tiles_filtered_by_byte():
    t = TileTracer()
    t.deposit("z", 0, 0, TA)
    t.deposit("z", 1, 1, FY)
    t.deposit("z", 2, 2, KO)
    t.deposit("z", 0, 0, KO)
    assert set(t.attested_tiles(KO)) == {("z", 2, 2), ("z", 0, 0)}
    assert set(t.attested_tiles(TA)) == {("z", 0, 0)}


def test_wraith_context_unvisited():
    t = TileTracer()
    ctx = t.wraith_context("z", 99, 99)
    assert ctx["fy"] == 0
    assert ctx["ko"] == 0
    assert ctx["ta"] == 0
    assert ctx["zo"] == 0
    assert ctx["sha"] == 0
    assert ctx["pu"] == 0


def test_wraith_context_with_deposits():
    t = TileTracer()
    t.deposit("z", 0, 0, TA)
    t.deposit("z", 0, 0, TA)
    t.deposit("z", 0, 0, FY)
    t.deposit("z", 0, 0, KO)
    ctx = t.wraith_context("z", 0, 0)
    assert ctx["ta"] == 2
    assert ctx["fy"] == 1
    assert ctx["ko"] == 1
    assert ctx["zo"] == 0


def test_wraith_context_dominant():
    t = TileTracer()
    for _ in range(3):
        t.deposit("z", 0, 0, TA)
    t.deposit("z", 0, 0, FY)
    ctx = t.wraith_context("z", 0, 0)
    assert ctx["dominant"][0]["symbol"] == "Ta"
    assert ctx["dominant"][0]["count"] == 3


# ── Orrery / wraith routing ───────────────────────────────────────────────────

def test_ta_routes_to_negaya():
    orrery = MagicMock()
    t = TileTracer(orrery=orrery)
    t.deposit("z", 0, 0, TA)
    obs_call = orrery.void_wraith_observe.call_args
    assert obs_call[0][0] == "kill"
    assert obs_call[0][1]["wraith_id"] == "2003_VDWR"


def test_zo_routes_to_negaya():
    orrery = MagicMock()
    t = TileTracer(orrery=orrery)
    t.deposit("z", 0, 0, ZO)
    obs_call = orrery.void_wraith_observe.call_args
    assert obs_call[0][0] == "kill"
    assert obs_call[0][1]["wraith_id"] == "2003_VDWR"


def test_fy_routes_to_haldoro():
    orrery = MagicMock()
    t = TileTracer(orrery=orrery)
    t.deposit("z", 0, 0, FY)
    obs_call = orrery.void_wraith_observe.call_args
    assert obs_call[0][0] == "silence"
    assert obs_call[0][1]["wraith_id"] == "2001_VDWR"


def test_pu_routes_to_haldoro():
    orrery = MagicMock()
    t = TileTracer(orrery=orrery)
    t.deposit("z", 0, 0, PU)
    obs_call = orrery.void_wraith_observe.call_args
    assert obs_call[0][0] == "silence"
    assert obs_call[0][1]["wraith_id"] == "2001_VDWR"


def test_sha_routes_to_vios():
    orrery = MagicMock()
    t = TileTracer(orrery=orrery)
    t.deposit("z", 0, 0, SHA)
    obs_call = orrery.void_wraith_observe.call_args
    assert obs_call[0][0] == "omission"
    assert obs_call[0][1]["wraith_id"] == "2002_VDWR"


def test_ko_routes_to_vios():
    orrery = MagicMock()
    t = TileTracer(orrery=orrery)
    t.deposit("z", 0, 0, KO)
    obs_call = orrery.void_wraith_observe.call_args
    assert obs_call[0][0] == "omission"
    assert obs_call[0][1]["wraith_id"] == "2002_VDWR"


def test_non_routed_byte_fires_record_not_wraith():
    orrery = MagicMock()
    t = TileTracer(orrery=orrery)
    t.deposit("z", 0, 0, 0)   # Ty — no wraith route
    orrery.record.assert_called_once()
    orrery.void_wraith_observe.assert_not_called()


def test_context_forwarded_to_orrery():
    orrery = MagicMock()
    t = TileTracer(orrery=orrery)
    t.deposit("z", 0, 0, KO, context={"quest_entry": "0004_KLST"})
    payload = orrery.record.call_args[0][1]
    assert payload["quest_entry"] == "0004_KLST"


def test_no_orrery_does_not_raise():
    t = TileTracer(orrery=None)
    for b in range(24):
        t.deposit("z", 0, 0, b)


# ── Persistence ───────────────────────────────────────────────────────────────

def test_as_dict_from_dict_round_trip():
    t = TileTracer()
    t.deposit("wiltoll", 3, 5, TA, FY)
    t.deposit("wiltoll", 7, 2, KO)

    t2 = TileTracer.from_dict(t.as_dict())
    assert t2.attestation_at("wiltoll", 3, 5).count(TA) == 1
    assert t2.attestation_at("wiltoll", 3, 5).count(FY) == 1
    assert t2.attestation_at("wiltoll", 7, 2).count(KO) == 1
    assert len(t2) == 2


def test_from_dict_empty():
    assert len(TileTracer.from_dict({})) == 0


# ── WorldPlay integration ─────────────────────────────────────────────────────

def _make_play():
    from ambroflow.world.play import WorldPlay
    from ambroflow.world.map import WorldMap, Zone, Realm, WorldTileKind
    voxels = {(x, y): WorldTileKind.FLOOR for x in range(5) for y in range(5)}
    zone = Zone(
        zone_id="wiltoll", name="Wiltoll Lane", realm=Realm.LAPIDUS,
        width=5, height=5, voxels=voxels, player_spawn=(2, 2),
    )
    world = WorldMap(zones={"wiltoll": zone}, starting_zone_id="wiltoll")
    chargen = MagicMock()
    chargen.name = "Apprentice"
    return WorldPlay(chargen=chargen, world_map=world, width=320, height=200)


def test_worldplay_has_tile_tracer():
    play = _make_play()
    assert isinstance(play.tile_tracer, TileTracer)


def test_worldplay_current_tile_context_has_mode_markers():
    play = _make_play()
    ctx = play.current_tile_context()
    assert "fy" in ctx and "ko" in ctx and "ta" in ctx


def test_worldplay_advance_quest_deposits_ko():
    play = _make_play()
    play.advance_quest("0004_KLST", "golden_path_complete")
    att = play.tile_tracer.attestation_at("wiltoll", 2, 2)
    assert att is not None
    assert att.count(KO) >= 1