"""
Tests for the canonical player home zones (home_zone.py).

Verifies zone geometry, spawn positions, exits, and structural coherence
for the 40-wide Kobra-canonical player home.
"""

from ambroflow.scenes.home_zone import (
    PLAYER_HOME_GROUND,
    PLAYER_HOME_UPPER,
    GROUND_W, GROUND_H,
    UPPER_W,  UPPER_H,
    GROUND_SPAWN,
    UPPER_SPAWN,
    BEDROOM_SPAWN,
    KNOCK_TILES,
    COURIER_TILE,
    build_ground_floor,
    build_upper_floor,
)
from ambroflow.world.map import WorldTileKind, is_passable


# ── Dimensions ────────────────────────────────────────────────────────────────

def test_ground_floor_dimensions():
    z = PLAYER_HOME_GROUND
    assert z.width  == GROUND_W
    assert z.height == GROUND_H


def test_upper_floor_dimensions():
    z = PLAYER_HOME_UPPER
    assert z.width  == UPPER_W
    assert z.height == UPPER_H


# ── Zone IDs ──────────────────────────────────────────────────────────────────

def test_ground_zone_id():
    assert PLAYER_HOME_GROUND.zone_id == "player_home_ground"


def test_upper_zone_id():
    assert PLAYER_HOME_UPPER.zone_id == "player_home_upper"


# ── Spawn positions ───────────────────────────────────────────────────────────

def test_ground_spawn_is_passable():
    x, y = GROUND_SPAWN
    tile = PLAYER_HOME_GROUND.tile_at(x, y)
    assert is_passable(tile), f"Ground spawn {GROUND_SPAWN} is not passable: {tile}"


def test_upper_spawn_is_passable():
    x, y = UPPER_SPAWN
    tile = PLAYER_HOME_UPPER.tile_at(x, y)
    assert is_passable(tile), f"Upper spawn {UPPER_SPAWN} is not passable: {tile}"


def test_bedroom_spawn_is_passable():
    x, y = BEDROOM_SPAWN
    tile = PLAYER_HOME_GROUND.tile_at(x, y)
    assert is_passable(tile), f"Bedroom spawn {BEDROOM_SPAWN} is not passable"


def test_ground_spawn_recorded():
    assert PLAYER_HOME_GROUND.player_spawn == GROUND_SPAWN


def test_upper_spawn_recorded():
    assert PLAYER_HOME_UPPER.player_spawn == UPPER_SPAWN


# ── Structural walkability ────────────────────────────────────────────────────

def test_perimeter_walls_impassable():
    g = PLAYER_HOME_GROUND
    for x in range(GROUND_W):
        assert not is_passable(g.tile_at(x, 0)),         f"north wall tile ({x},0) is passable"
    for x in range(GROUND_W):
        if x != COURIER_TILE[0]:   # front door exempt
            assert not is_passable(g.tile_at(x, GROUND_H - 1)), \
                f"south wall tile ({x},{GROUND_H-1}) is passable"
    for y in range(GROUND_H):
        assert not is_passable(g.tile_at(0, y)),          f"west wall tile (0,{y}) is passable"
        assert not is_passable(g.tile_at(GROUND_W-1, y)), f"east wall tile ({GROUND_W-1},{y}) is passable"


def test_front_door_passable():
    assert is_passable(PLAYER_HOME_GROUND.tile_at(COURIER_TILE[0], GROUND_H - 1))


def test_bedroom_floor_passable():
    g = PLAYER_HOME_GROUND
    for x in range(1, 12):     # bedroom x=1–11
        for y in range(1, 8):
            assert is_passable(g.tile_at(x, y)), f"bedroom floor ({x},{y}) is not passable"


def test_kitchen_floor_passable():
    g = PLAYER_HOME_GROUND
    for x in range(13, 29):    # kitchen x=13–28
        for y in range(1, 8):
            assert is_passable(g.tile_at(x, y)), f"kitchen floor ({x},{y}) is not passable"


def test_meditation_floor_passable():
    g = PLAYER_HOME_GROUND
    for x in range(30, 47):    # meditation x=30–46
        for y in range(1, 8):
            assert is_passable(g.tile_at(x, y)), f"meditation floor ({x},{y}) is not passable"


def test_foyer_floor_passable():
    g = PLAYER_HOME_GROUND
    for x in range(1, 47):     # foyer x=1–46
        for y in range(9, 12):
            assert is_passable(g.tile_at(x, y)), f"foyer floor ({x},{y}) is not passable"


def test_inner_wall_impassable():
    g = PLAYER_HOME_GROUND
    inner_doors = {6, 21, 38}
    for x in range(1, 47):
        if x not in inner_doors:
            assert not is_passable(g.tile_at(x, 8)), \
                f"inner wall tile ({x},8) should be impassable"


def test_inner_doors_passable():
    g = PLAYER_HOME_GROUND
    for x in (6, 21, 38):
        assert is_passable(g.tile_at(x, 8)), f"inner door ({x},8) is not passable"


def test_room_dividers_impassable():
    g = PLAYER_HOME_GROUND
    for y in range(1, 9):
        assert not is_passable(g.tile_at(12, y)), f"divider (12,{y}) should be impassable"
        assert not is_passable(g.tile_at(29, y)), f"divider (29,{y}) should be impassable"


def test_stair_up_passable():
    assert is_passable(PLAYER_HOME_GROUND.tile_at(11, 2))


def test_upper_stair_down_passable():
    assert is_passable(PLAYER_HOME_UPPER.tile_at(28, 8))


def test_upper_perimeter_walls():
    u = PLAYER_HOME_UPPER
    for x in range(UPPER_W):
        assert not is_passable(u.tile_at(x, 0))
        assert not is_passable(u.tile_at(x, UPPER_H - 1))
    for y in range(UPPER_H):
        assert not is_passable(u.tile_at(0, y))
        assert not is_passable(u.tile_at(UPPER_W - 1, y))


def test_upper_study_floor_passable():
    u = PLAYER_HOME_UPPER
    for x in range(1, UPPER_W - 1):
        for y in range(1, UPPER_H - 1):
            assert is_passable(u.tile_at(x, y)), \
                f"study floor ({x},{y}) is not passable"


# ── Exits ─────────────────────────────────────────────────────────────────────

def test_ground_has_exits():
    assert len(PLAYER_HOME_GROUND.exits) >= 2


def test_upper_has_exit():
    assert len(PLAYER_HOME_UPPER.exits) >= 1


def test_ground_stair_exit_targets_upper():
    exits = {e.target_zone: e for e in PLAYER_HOME_GROUND.exits}
    assert "player_home_upper" in exits


def test_upper_stair_exit_targets_ground():
    exits = {e.target_zone: e for e in PLAYER_HOME_UPPER.exits}
    assert "player_home_ground" in exits


def test_ground_exterior_exit():
    exits = {e.target_zone: e for e in PLAYER_HOME_GROUND.exits}
    assert "lapidus_wiltoll_lane" in exits


def test_stair_exit_spawn_coords_consistent():
    # Stair from ground → upper should land at UPPER_SPAWN
    exits = {e.target_zone: e for e in PLAYER_HOME_GROUND.exits}
    stair = exits.get("player_home_upper")
    assert stair is not None
    assert (stair.target_x, stair.target_y) == UPPER_SPAWN

    # Stair from upper → ground should land at GROUND_SPAWN
    exits_u = {e.target_zone: e for e in PLAYER_HOME_UPPER.exits}
    stair_d = exits_u.get("player_home_ground")
    assert stair_d is not None
    assert (stair_d.target_x, stair_d.target_y) == GROUND_SPAWN


# ── Beat trigger coordinates ──────────────────────────────────────────────────

def test_knock_tiles_passable():
    for (x, y) in KNOCK_TILES:
        assert is_passable(PLAYER_HOME_GROUND.tile_at(x, y)), \
            f"KNOCK_TILE ({x},{y}) is not passable"


def test_courier_tile_is_front_door():
    # COURIER_TILE must be the front door — passable and in south wall
    x, y = COURIER_TILE
    assert y == GROUND_H - 1, "COURIER_TILE should be on the south wall row"
    assert is_passable(PLAYER_HOME_GROUND.tile_at(x, y))


# ── Builder functions produce fresh instances ─────────────────────────────────

def test_build_produces_correct_id():
    g = build_ground_floor()
    u = build_upper_floor()
    assert g.zone_id == "player_home_ground"
    assert u.zone_id == "player_home_upper"


def test_singleton_and_fresh_build_agree():
    fresh = build_ground_floor()
    assert fresh.width  == PLAYER_HOME_GROUND.width
    assert fresh.height == PLAYER_HOME_GROUND.height
    assert fresh.player_spawn == PLAYER_HOME_GROUND.player_spawn
