"""Tests for Lapidus zone geography — Ko's Labyrinth (7_KLGS)."""

import pytest

from ambroflow.world.map import WorldTileKind, Realm, is_passable
from ambroflow.world.zones import build_game7_world
from ambroflow.world.zones.lapidus import (
    build_wiltoll_lane,
    build_wiltoll_home,
    build_market_interior,
    build_litleaf_thoroughfare,
    build_azonithia_slum,
    build_azonithia_market,
    build_azonithia_temple,
    build_azonithia_heartvein,
    build_azoth_approach,
    build_castle_azoth,
    build_mt_elaene_trail,
    VENDOR_CATALOGS,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def exit_targets(zone) -> set[str]:
    return {e.target_zone for e in zone.exits}

def exit_at(zone, x, y, direction):
    return zone.exit_at(x, y, direction)


# ── WorldMap assembly ─────────────────────────────────────────────────────────

def test_build_game7_world_has_all_zones():
    wm = build_game7_world()
    expected = {
        "lapidus_wiltoll_lane",
        "lapidus_litleaf_thoroughfare",
        "lapidus_azonithia_slum",
        "lapidus_azonithia_market",
        "lapidus_azonithia_temple",
        "lapidus_azonithia_heartvein",
        "lapidus_azoth_approach",
        "lapidus_castle_azoth",
        "lapidus_mt_elaene_trail",
    }
    assert expected.issubset(set(wm.zones.keys()))

def test_starting_zone_is_wiltoll():
    wm = build_game7_world()
    assert wm.starting_zone_id == "lapidus_wiltoll_lane"

def test_all_zones_are_lapidus_realm():
    wm = build_game7_world()
    for zone in wm.zones.values():
        assert zone.realm == Realm.LAPIDUS


# ── Wiltoll Lane ──────────────────────────────────────────────────────────────

class TestWiltollLane:
    @pytest.fixture(autouse=True)
    def zone(self):
        self.z = build_wiltoll_lane()

    def test_dimensions(self):
        assert self.z.width  == 60
        assert self.z.height == 22

    def test_player_spawn(self):
        x, y = self.z.player_spawn
        # player @ col 3, row 12 (south verge, facing home entrance)
        assert x == 3
        assert y == 12

    def test_spawn_tile_is_floor(self):
        x, y = self.z.player_spawn
        assert self.z.tile_at(x, y) == WorldTileKind.FLOOR

    def test_road_tiles_east_west(self):
        # Main road rows 10–11 should be ROAD across full width
        for col in range(60):
            assert self.z.tile_at(col, 10) == WorldTileKind.ROAD
            assert self.z.tile_at(col, 11) == WorldTileKind.ROAD

    def test_litleaf_fork_tiles(self):
        # Cols 11–12 on rows 0–9 should be ROAD (Litleaf fork)
        for row in range(10):
            assert self.z.tile_at(11, row) == WorldTileKind.ROAD
            assert self.z.tile_at(12, row) == WorldTileKind.ROAD

    def test_forest_south(self):
        # Rows 20–21 should be TREE
        for col in range(60):
            assert self.z.tile_at(col, 20) == WorldTileKind.TREE
            assert self.z.tile_at(col, 21) == WorldTileKind.TREE

    def test_exit_west_to_slum(self):
        ex0 = exit_at(self.z, 0, 10, "west")
        ex1 = exit_at(self.z, 0, 11, "west")
        assert ex0 is not None
        assert ex0.target_zone == "lapidus_azonithia_slum"
        assert ex1 is not None

    def test_exit_east_to_elaene(self):
        ex0 = exit_at(self.z, 59, 10, "east")
        ex1 = exit_at(self.z, 59, 11, "east")
        assert ex0 is not None
        assert ex0.target_zone == "lapidus_mt_elaene_trail"
        assert ex1 is not None

    def test_exit_north_litleaf(self):
        ex0 = exit_at(self.z, 11, 0, "north")
        ex1 = exit_at(self.z, 12, 0, "north")
        assert ex0 is not None
        assert ex0.target_zone == "lapidus_litleaf_thoroughfare"
        assert ex1 is not None


# ── Litleaf Thoroughfare ──────────────────────────────────────────────────────

class TestLitleafThoroughfare:
    @pytest.fixture(autouse=True)
    def zone(self):
        self.z = build_litleaf_thoroughfare()

    def test_dimensions(self):
        assert self.z.width  == 20
        assert self.z.height == 20

    def test_road_tiles(self):
        for row in range(20):
            assert self.z.tile_at(0, row) == WorldTileKind.ROAD
            assert self.z.tile_at(1, row) == WorldTileKind.ROAD

    def test_exit_south_to_wiltoll(self):
        ex = exit_at(self.z, 0, 19, "south")
        assert ex is not None
        assert ex.target_zone == "lapidus_wiltoll_lane"

    def test_exit_north_to_slum(self):
        ex = exit_at(self.z, 0, 0, "north")
        assert ex is not None
        assert ex.target_zone == "lapidus_slum_interior"


# ── Avenue sections ───────────────────────────────────────────────────────────

class TestAvenueCommon:
    """Shared assertions across all four Azonithia Avenue sections."""

    def _check(self, zone, inlet_kind: WorldTileKind):
        # Dimensions
        assert zone.width  == 48
        assert zone.height == 16

        # Main road rows 5–6
        for col in range(48):
            assert zone.tile_at(col, 5) == WorldTileKind.ROAD, f"col {col} row 5"
            assert zone.tile_at(col, 6) == WorldTileKind.ROAD, f"col {col} row 6"

        # Inlet at cols 22–23, rows 0–4
        for row in range(5):
            assert zone.tile_at(22, row) == inlet_kind, f"inlet col 22 row {row}"
            assert zone.tile_at(23, row) == inlet_kind, f"inlet col 23 row {row}"

        # Forest South rows 9–15
        for col in range(48):
            assert zone.tile_at(col, 9) == WorldTileKind.TREE, f"tree col {col} row 9"

        # Passability
        assert is_passable(WorldTileKind.ROAD)
        assert is_passable(inlet_kind)
        assert not is_passable(WorldTileKind.TREE)

    def test_slum_section(self):
        z = build_azonithia_slum()
        self._check(z, WorldTileKind.YELLOW_BRICK)
        assert exit_at(z, 47, 5, "east").target_zone == "lapidus_wiltoll_lane"
        assert exit_at(z, 0,  5, "west").target_zone == "lapidus_azonithia_market"
        assert exit_at(z, 22, 0, "north").target_zone == "lapidus_slum_interior"

    def test_market_section(self):
        z = build_azonithia_market()
        self._check(z, WorldTileKind.CERAMIC)
        assert exit_at(z, 47, 5, "east").target_zone == "lapidus_azonithia_slum"
        assert exit_at(z, 0,  5, "west").target_zone == "lapidus_azonithia_temple"
        assert exit_at(z, 22, 0, "north").target_zone == "lapidus_market_interior"

    def test_temple_section(self):
        z = build_azonithia_temple()
        self._check(z, WorldTileKind.SLATE)
        assert exit_at(z, 47, 5, "east").target_zone == "lapidus_azonithia_market"
        assert exit_at(z, 0,  5, "west").target_zone == "lapidus_azonithia_heartvein"
        assert exit_at(z, 22, 0, "north").target_zone == "lapidus_temple_interior"

    def test_heartvein_section(self):
        z = build_azonithia_heartvein()
        self._check(z, WorldTileKind.SILICA)
        assert exit_at(z, 47, 5, "east").target_zone == "lapidus_azonithia_temple"
        assert exit_at(z, 0,  5, "west").target_zone == "lapidus_azoth_approach"
        assert exit_at(z, 22, 0, "north").target_zone == "lapidus_heartvein_interior"


# ── Sidhal NPC spawn ──────────────────────────────────────────────────────────

def test_sidhal_spawns_in_slum_zone():
    z = build_azonithia_slum()
    cids = [n.character_id for n in z.npc_spawns]
    assert "0004_TOWN" in cids   # Sidhal: farmer/forester, quest 0003_KLST guide


# ── Azoth Approach ────────────────────────────────────────────────────────────

class TestAzothApproach:
    @pytest.fixture(autouse=True)
    def zone(self):
        self.z = build_azoth_approach()

    def test_dimensions(self):
        assert self.z.width  == 48
        assert self.z.height == 22

    def test_main_road(self):
        for col in range(48):
            assert self.z.tile_at(col, 11) == WorldTileKind.ROAD
            assert self.z.tile_at(col, 12) == WorldTileKind.ROAD

    def test_marble_sprint(self):
        for row in range(11):   # rows 0–10
            assert self.z.tile_at(22, row) == WorldTileKind.MARBLE
            assert self.z.tile_at(23, row) == WorldTileKind.MARBLE

    def test_orchard_trees(self):
        # Cols 4–20 and 25–41, rows 1–10 should be TREE
        assert self.z.tile_at(10, 5) == WorldTileKind.TREE
        assert self.z.tile_at(30, 5) == WorldTileKind.TREE

    def test_exit_east_to_heartvein(self):
        ex = exit_at(self.z, 47, 11, "east")
        assert ex is not None
        assert ex.target_zone == "lapidus_azonithia_heartvein"
        assert ex.target_y == 5   # heartvein road row

    def test_exit_west_to_dirt_trail(self):
        ex = exit_at(self.z, 0, 11, "west")
        assert ex is not None
        assert ex.target_zone == "lapidus_dirt_trail"

    def test_exit_north_to_castle(self):
        ex = exit_at(self.z, 22, 0, "north")
        assert ex is not None
        assert ex.target_zone == "lapidus_castle_azoth"


# ── Castle Azoth ──────────────────────────────────────────────────────────────

class TestCastleAzoth:
    @pytest.fixture(autouse=True)
    def zone(self):
        self.z = build_castle_azoth()

    def test_dimensions(self):
        assert self.z.width  == 40
        assert self.z.height == 20

    def test_marble_base(self):
        for col in range(40):
            assert self.z.tile_at(col, 19) == WorldTileKind.MARBLE

    def test_stone_courtyard(self):
        for col in range(40):
            assert self.z.tile_at(col, 18) == WorldTileKind.STONE

    def test_fountain_water(self):
        # Water tiles should be present in the fountain area rows 6–8
        water_found = any(
            self.z.tile_at(col, row) == WorldTileKind.WATER
            for col in range(40)
            for row in range(6, 10)
        )
        assert water_found

    def test_fountain_stone_ring(self):
        # Stone tiles in fountain surround rows 5–9
        stone_found = any(
            self.z.tile_at(col, row) == WorldTileKind.STONE
            for col in range(9, 20)
            for row in range(5, 10)
        )
        assert stone_found

    def test_alfir_npc_spawn(self):
        cids = [n.character_id for n in self.z.npc_spawns]
        assert "0006_WTCH" in cids   # Alfir: Infernal Meditation teacher

    def test_exit_south_to_approach(self):
        ex = exit_at(self.z, 18, 19, "south")
        assert ex is not None
        assert ex.target_zone == "lapidus_azoth_approach"
        assert ex.target_x == 22   # marble sprint col 22


# ── Mt. Elaene Trail ──────────────────────────────────────────────────────────

class TestElaeneTrail:
    @pytest.fixture(autouse=True)
    def zone(self):
        self.z = build_mt_elaene_trail()

    def test_dimensions(self):
        assert self.z.width  == 20
        assert self.z.height == 14

    def test_trail_open(self):
        # Cols 1–2 on rows 0–9 are passable (GRASS)
        for row in range(10):
            assert is_passable(self.z.tile_at(1, row))
            assert is_passable(self.z.tile_at(2, row))

    def test_forest_walls(self):
        # Rows 10–13 should be TREE
        for col in range(20):
            for row in range(10, 14):
                assert self.z.tile_at(col, row) == WorldTileKind.TREE

    def test_exit_west_to_wiltoll(self):
        ex = exit_at(self.z, 0, 6, "west")
        assert ex is not None
        assert ex.target_zone == "lapidus_wiltoll_lane"
        assert ex.target_x == 58
        assert ex.target_y == 10

    def test_exit_north_to_summit(self):
        ex = exit_at(self.z, 1, 0, "north")
        assert ex is not None
        assert ex.target_zone == "lapidus_mt_elaene_summit"


# ── Zone connectivity ─────────────────────────────────────────────────────────

def test_avenue_chain_is_symmetric():
    """Every East exit should be answered by a corresponding West exit in the destination."""
    wm = build_game7_world()

    pairs = [
        ("lapidus_azonithia_slum",      "east",  "lapidus_wiltoll_lane",         "west"),
        ("lapidus_azonithia_market",    "east",  "lapidus_azonithia_slum",        "west"),
        ("lapidus_azonithia_temple",    "east",  "lapidus_azonithia_market",      "west"),
        ("lapidus_azonithia_heartvein", "east",  "lapidus_azonithia_temple",      "west"),
    ]

    for src_id, src_dir, dst_id, dst_dir in pairs:
        src = wm.zones[src_id]
        dst = wm.zones[dst_id]
        # At least one exit in each direction
        src_targets = {e.target_zone for e in src.exits if e.direction == src_dir}
        dst_targets = {e.target_zone for e in dst.exits if e.direction == dst_dir}
        assert src_id in dst_targets, f"{dst_id} has no {dst_dir} exit back to {src_id}"
        assert dst_id in src_targets, f"{src_id} has no {src_dir} exit to {dst_id}"

def test_new_tile_kinds_are_passable():
    for kind in [
        WorldTileKind.MARBLE,
        WorldTileKind.YELLOW_BRICK,
        WorldTileKind.CERAMIC,
        WorldTileKind.SLATE,
        WorldTileKind.SILICA,
    ]:
        assert is_passable(kind), f"{kind} should be passable"

def test_tree_is_impassable():
    assert not is_passable(WorldTileKind.TREE)


# ── Wiltoll Home Interior ─────────────────────────────────────────────────────

class TestWiltollHome:
    @pytest.fixture(autouse=True)
    def zone(self):
        self.z = build_wiltoll_home()

    def test_dimensions(self):
        assert self.z.width  == 40
        assert self.z.height == 13

    def test_player_spawn(self):
        x, y = self.z.player_spawn
        assert x == 8
        assert y == 2

    def test_north_door_tiles(self):
        assert self.z.tile_at(20, 0) == WorldTileKind.DOOR
        assert self.z.tile_at(21, 0) == WorldTileKind.DOOR

    def test_exit_north_to_wiltoll(self):
        ex0 = exit_at(self.z, 20, 0, "north")
        ex1 = exit_at(self.z, 21, 0, "north")
        assert ex0 is not None
        assert ex0.target_zone == "lapidus_wiltoll_lane"
        assert ex0.target_x == 3
        assert ex0.target_y == 12
        assert ex1 is not None

    def test_item_spawns_present(self):
        assert len(self.z.item_spawns) == 12

    def test_apparatus_in_kitchen_spawns(self):
        ids = {s.item_id for s in self.z.item_spawns}
        assert "0001_KLOB" in ids   # Mortar
        assert "0002_KLOB" in ids   # Pestle
        assert "0010_KLOB" in ids   # Furnace
        assert "0017_KLOB" in ids   # Crucible

    def test_starter_materials_in_spawns(self):
        ids = {s.item_id for s in self.z.item_spawns}
        assert "0073_KLOB" in ids   # Herb (Common)
        assert "0040_KLOB" in ids   # Water Flask
        assert "0016_KLIT" in ids   # Coins

    def test_coin_spawn_qty(self):
        coins = [s for s in self.z.item_spawns if s.item_id == "0016_KLIT"]
        assert coins[0].qty == 50

    def test_vendor_npc_present(self):
        ids = [n.character_id for n in self.z.npc_spawns]
        assert "0005_TOWN" in ids

    def test_foyer_is_passable(self):
        for col in range(1, 39):
            assert is_passable(self.z.tile_at(col, 1))
            assert is_passable(self.z.tile_at(col, 3))


# ── Market Interior ───────────────────────────────────────────────────────────

class TestMarketInterior:
    @pytest.fixture(autouse=True)
    def zone(self):
        self.z = build_market_interior()

    def test_dimensions(self):
        assert self.z.width  == 48
        assert self.z.height == 20

    def test_vendor_npcs_present(self):
        ids = [n.character_id for n in self.z.npc_spawns]
        assert "0006_TOWN" in ids
        assert "0007_TOWN" in ids

    def test_exit_south_to_avenue(self):
        ex0 = exit_at(self.z, 10, 19, "south")
        assert ex0 is not None
        assert ex0.target_zone == "lapidus_azonithia_market"

    def test_market_floor_open(self):
        for col in range(1, 47):
            assert is_passable(self.z.tile_at(col, 10))


# ── Vendor catalogs ───────────────────────────────────────────────────────────

def test_vendor_catalogs_home_apothecary():
    assert "0005_TOWN" in VENDOR_CATALOGS
    cat = VENDOR_CATALOGS["0005_TOWN"]
    assert "0073_KLOB" in cat   # Herb (Common)
    assert "0001_KLOB" in cat   # Mortar

def test_vendor_catalogs_market_general():
    assert "0006_TOWN" in VENDOR_CATALOGS
    cat = VENDOR_CATALOGS["0006_TOWN"]
    assert "0076_KLOB" in cat   # Raw Desire Stone
    assert "0077_KLOB" in cat   # Asmodean Essence

def test_vendor_coin_prices_positive():
    for vendor_id, catalog in VENDOR_CATALOGS.items():
        for item_id, price in catalog.items():
            assert price > 0, f"{vendor_id}/{item_id} price must be positive"


# ── Wiltoll Lane home exits ───────────────────────────────────────────────────

def test_wiltoll_lane_has_home_exits():
    z = build_wiltoll_lane()
    ex0 = exit_at(z, 3, 12, "south")
    ex1 = exit_at(z, 4, 12, "south")
    assert ex0 is not None
    assert ex0.target_zone == "lapidus_wiltoll_home"
    assert ex1 is not None

def test_wiltoll_home_door_tiles():
    z = build_wiltoll_lane()
    assert z.tile_at(3, 13) == WorldTileKind.DOOR
    assert z.tile_at(4, 13) == WorldTileKind.DOOR

def test_wiltoll_lane_home_in_world_map():
    wm = build_game7_world()
    assert "lapidus_wiltoll_home" in wm.zones
    assert "lapidus_market_interior" in wm.zones