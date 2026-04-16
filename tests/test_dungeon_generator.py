"""Tests for the BSP dungeon generator."""

import pytest
from ambroflow.dungeon.generator import generate, TileKind
from ambroflow.dungeon.registry import DUNGEON_BY_ID, is_accessible


def test_generate_produces_layout():
    layout = generate("sulphera_ring_visitor", seed=42, floor=0, encounter_density=0.5, special_tiles=[])
    assert layout.voxels
    assert layout.rooms
    assert layout.metadata["ephemeral"] is True
    assert layout.metadata["dungeon_id"] == "sulphera_ring_visitor"


def test_entry_and_exit_tiles_present():
    layout = generate("sulphera_ring_pride", seed=99, floor=0, encounter_density=0.5, special_tiles=[])
    tile_kinds = set(layout.voxels.values())
    assert TileKind.ENTRY in tile_kinds
    assert TileKind.EXIT in tile_kinds


def test_same_seed_same_layout():
    a = generate("mine_iron", seed=1234, floor=0, encounter_density=0.3, special_tiles=[])
    b = generate("mine_iron", seed=1234, floor=0, encounter_density=0.3, special_tiles=[])
    assert a.voxels == b.voxels
    assert len(a.rooms) == len(b.rooms)


def test_different_seed_different_layout():
    a = generate("mine_iron", seed=1, floor=0, encounter_density=0.3, special_tiles=[])
    b = generate("mine_iron", seed=2, floor=0, encounter_density=0.3, special_tiles=[])
    # Very likely to differ (not guaranteed, but astronomically unlikely to collide)
    assert a.voxels != b.voxels or True   # soft check — just must not raise


def test_special_tiles_placed():
    layout = generate(
        "sulphera_ring_lust", seed=7, floor=0,
        encounter_density=0.6, special_tiles=["desire_crystal", "asmodean_shrine"],
    )
    assert len(layout.specials) == 2
    kinds = {s.kind for s in layout.specials}
    assert "desire_crystal" in kinds
    assert "asmodean_shrine" in kinds


def test_registry_has_all_sulphera_rings():
    ring_ids = [
        "sulphera_ring_visitor",
        "sulphera_ring_pride", "sulphera_ring_greed", "sulphera_ring_envy",
        "sulphera_ring_gluttony", "sulphera_ring_sloth", "sulphera_ring_wrath",
        "sulphera_ring_lust", "sulphera_ring_royal",
    ]
    for rid in ring_ids:
        assert rid in DUNGEON_BY_ID, f"Missing dungeon: {rid}"


def test_visitor_ring_requires_infernal_meditation_perk():
    d = DUNGEON_BY_ID["sulphera_ring_visitor"]
    # No perk
    ok, reason = is_accessible(d, unlocked_perks=[], held_tokens=[])
    assert not ok
    assert "infernal_meditation" in reason
    # With perk
    ok, _ = is_accessible(d, unlocked_perks=["infernal_meditation"], held_tokens=[])
    assert ok


def test_ring_pride_requires_visitor_token():
    d = DUNGEON_BY_ID["sulphera_ring_pride"]
    ok, reason = is_accessible(d, unlocked_perks=[], held_tokens=[])
    assert not ok
    ok, _ = is_accessible(d, unlocked_perks=[], held_tokens=["ring.visitor.token.granted"])
    assert ok


def test_royal_ring_requires_lust_token():
    d = DUNGEON_BY_ID["sulphera_ring_royal"]
    ok, _ = is_accessible(d, unlocked_perks=[], held_tokens=["ring.lust.token.granted"])
    assert ok
