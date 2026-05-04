"""Tests for kobra_zone_loader — TPN placement notation → Zone geometry."""
import pytest
from ambroflow.world.kobra_zone_loader import (
    load_zone_from_kobra,
    resolve_color_token,
    _parse_placement_line,
    _hue_category,
)
from ambroflow.world.map import WorldTileKind, Realm, Zone


# ── colour token resolution ───────────────────────────────────────────────────

class TestResolveColorToken:
    def test_rose_direct(self):
        r, g, b = resolve_color_token("Ki")
        assert g > r and g > b          # green dominant

    def test_aster_right_lightened(self):
        base = resolve_color_token("Ru")
        light = resolve_color_token("Ry")
        assert light[0] > base[0]       # lightened red is brighter

    def test_aster_left_darkened(self):
        base = resolve_color_token("Ru")
        dark = resolve_color_token("Ra")
        assert dark[0] < base[0]        # darkened red is dimmer

    def test_combined_akinenwun(self):
        rgb = resolve_color_token("RuOtKi")
        assert rgb is not None
        r, g, b = rgb
        assert 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255

    def test_unknown_returns_none(self):
        assert resolve_color_token("Xyz") is None

    def test_ha_is_white(self):
        r, g, b = resolve_color_token("Ha")
        assert r == 255 and g == 255 and b == 255


# ── placement line parser ─────────────────────────────────────────────────────

class TestParsePlacementLine:
    def test_basic_floor_tile(self):
        p = _parse_placement_line("ground|3,12 : [Ta Ui Ao Gaoh Ha Va]")
        assert p is not None
        assert p.x == 3
        assert p.y == 12
        assert p.presence == "Ta"
        assert p.color_token == "Ha"
        assert p.traversal == "walkable_surface"

    def test_zo_presence(self):
        p = _parse_placement_line("base|5,5 : [Zo Kiel Kiel Ha Va]")
        assert p.presence == "Zo"

    def test_wall_tile(self):
        p = _parse_placement_line("base|0,0 : [Ta Gaoh Gaoh Ka Vo]")
        assert p.traversal == "visual_unwalkable"
        assert p.color_token == "Ka"

    def test_combined_color_token(self):
        p = _parse_placement_line("base|1,1 : [Ta Ao Ao OtElKi Va]")
        assert p.color_token == "OtElKi"

    def test_aster_right_chiral(self):
        p = _parse_placement_line("base|2,3 : [Ta Ye Ui Ry Va]")
        assert p.color_token == "Ry"

    def test_aster_left_chiral(self):
        p = _parse_placement_line("base|2,3 : [Ta Ye Ui Ra Va]")
        assert p.color_token == "Ra"

    def test_npc_daisy_lo(self):
        p = _parse_placement_line("base|4,6 : [Ta Shu Yeshu Ha Va Lo 0005_TOWN]")
        assert p.daisy_type == "Lo"
        assert "0005_TOWN" in p.lex

    def test_item_daisy_to(self):
        p = _parse_placement_line("base|2,2 : [Ta Ye Ye Ha Va To 0001_KLOB 1]")
        assert p.daisy_type == "To"
        assert p.lex[0] == "0001_KLOB"

    def test_exit_daisy_ne(self):
        p = _parse_placement_line("base|3,0 : [Ta Ui Gaoh Ha Va Ne north lapidus_street 10 20]")
        assert p.daisy_type == "Ne"
        assert p.lex == ["north", "lapidus_street", "10", "20"]

    def test_skip_comment(self):
        assert _parse_placement_line("# this is a comment") is None

    def test_skip_empty(self):
        assert _parse_placement_line("   ") is None

    def test_tile_key_coordinates_take_precedence(self):
        # Tile key says x=7, y=3; Rose tokens also present
        p = _parse_placement_line("base|7,3 : [Ta Yeshu Ui Ha Va]")
        assert p.x == 7
        assert p.y == 3


# ── tile kind resolution ──────────────────────────────────────────────────────

class TestHueCategory:
    def test_ki_is_grass(self):
        assert _hue_category("Ki") == "grass"

    def test_fu_is_water(self):
        assert _hue_category("Fu") == "water"

    def test_ha_is_floor(self):
        assert _hue_category("Ha") == "floor"

    def test_combined_majority(self):
        # RuOtEl — Ru+Ot dominant → road
        assert _hue_category("RuOt") == "road"


# ── full zone loading ─────────────────────────────────────────────────────────

_SIMPLE_SOURCE = """\
# Simple 3×3 zone
base|0,0 : [Ta Gaoh Gaoh Ka Vo]
base|1,0 : [Ta Ao Gaoh Ka Vo]
base|2,0 : [Ta Ye Gaoh Ka Vo]
base|0,1 : [Ta Gaoh Ao Ka Vo]
base|1,1 : [Ta Ao Ao Ha Va]
base|2,1 : [Ta Ye Ao Ka Vo]
base|0,2 : [Ta Gaoh Ye Ka Vo]
base|1,2 : [Ta Ao Ye Ha Va]
base|2,2 : [Ta Ye Ye Ka Vo]
"""

class TestLoadZoneFromKobra:
    def test_returns_zone(self):
        z = load_zone_from_kobra(_SIMPLE_SOURCE, "test", "Test")
        assert isinstance(z, Zone)

    def test_dimensions(self):
        z = load_zone_from_kobra(_SIMPLE_SOURCE, "test", "Test")
        assert z.width == 3
        assert z.height == 3

    def test_wall_tiles(self):
        z = load_zone_from_kobra(_SIMPLE_SOURCE, "test", "Test")
        assert z.tile_at(0, 0) == WorldTileKind.WALL
        assert z.tile_at(2, 2) == WorldTileKind.WALL

    def test_floor_tiles(self):
        z = load_zone_from_kobra(_SIMPLE_SOURCE, "test", "Test")
        assert z.tile_at(1, 1) == WorldTileKind.FLOOR
        assert z.tile_at(1, 2) == WorldTileKind.FLOOR

    def test_zo_tiles_absent(self):
        src = "base|0,0 : [Ta Gaoh Gaoh Ha Va]\nbase|1,0 : [Zo Ao Gaoh Ha Va]\n"
        z = load_zone_from_kobra(src, "z", "Z")
        assert z.tile_at(0, 0) == WorldTileKind.FLOOR
        assert z.tile_at(1, 0) == WorldTileKind.VOID   # Zo → not instantiated

    def test_realm(self):
        z = load_zone_from_kobra(_SIMPLE_SOURCE, "t", "T", realm=Realm.MERCURIE)
        assert z.realm == Realm.MERCURIE

    def test_npc_spawn(self):
        src = _SIMPLE_SOURCE + "base|1,1 : [Ta Ao Ao Ha Va Lo 0005_TOWN]\n"
        z = load_zone_from_kobra(src, "t", "T")
        npc = z.npc_at(1, 1)
        assert npc is not None
        assert npc.character_id == "0005_TOWN"

    def test_item_spawn(self):
        src = _SIMPLE_SOURCE + "base|1,2 : [Ta Ao Ye Ha Va To 0001_KLOB 3]\n"
        z = load_zone_from_kobra(src, "t", "T")
        items = z.items_at(1, 2)
        assert len(items) == 1
        assert items[0].item_id == "0001_KLOB"
        assert items[0].qty == 3

    def test_zone_exit(self):
        src = _SIMPLE_SOURCE + "base|1,0 : [Ta Ao Gaoh Ha Va Ne north lapidus_street 10 5]\n"
        z = load_zone_from_kobra(src, "t", "T")
        ex = z.exit_at(1, 0, "north")
        assert ex is not None
        assert ex.target_zone == "lapidus_street"
        assert ex.target_x == 10
        assert ex.target_y == 5

    def test_grass_tiles(self):
        src = "base|0,0 : [Ta Gaoh Gaoh Ki Va]\n"
        z = load_zone_from_kobra(src, "t", "T")
        assert z.tile_at(0, 0) == WorldTileKind.GRASS

    def test_lex_tile_kind_override(self):
        src = "base|0,0 : [Ta Gaoh Gaoh Ha Va door]\n"
        z = load_zone_from_kobra(src, "t", "T")
        assert z.tile_at(0, 0) == WorldTileKind.DOOR

    def test_combined_color_road(self):
        # Tan (OtElKi) — Ot dominant → road (warm earth surface)
        src = "base|0,0 : [Ta Gaoh Gaoh OtElKi Va]\n"
        z = load_zone_from_kobra(src, "t", "T")
        assert z.tile_at(0, 0) == WorldTileKind.ROAD

    def test_aster_chiral_walkable(self):
        # Gi (light green Aster right-chiral) walkable → GRASS
        src = "base|0,0 : [Ta Gaoh Gaoh Gi Va]\n"
        z = load_zone_from_kobra(src, "t", "T")
        assert z.tile_at(0, 0) == WorldTileKind.GRASS

    def test_player_spawn_default(self):
        z = load_zone_from_kobra(_SIMPLE_SOURCE, "t", "T", player_spawn=(1, 1))
        assert z.player_spawn == (1, 1)

    def test_empty_source_returns_void_zone(self):
        z = load_zone_from_kobra("", "t", "T")
        assert z.tile_at(0, 0) == WorldTileKind.VOID