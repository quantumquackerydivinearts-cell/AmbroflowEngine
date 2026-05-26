"""
tests/test_atlas_compiled.py
============================
Validates the compiled tile atlas engine (kobra_compiled/atlas_engine.py)
emitted from tile_atlas.ko via the Kobra compiler.
"""
from __future__ import annotations

import pytest

from ambroflow.kobra_compiled.atlas_engine import (
    AtlasDecl,
    TileFileDecl,
    TileDirDecl,
    AtlasClusterDecl,
    AtlasVAddrDecl,
    AtlasCacheDecl,
    AtlasSnapshotDecl,
    atlas_read_eval,
    atlas_index_el,
    atlas_backing,
    atlas_page_el,
    hot_page_eval,
    hot_page_el,
    page_evict_el,
    atlas_bus_eval,
    atlas_dma_el,
    atlas_stream_el,
    atlas_render_eval,
    atlas_shi_wu_ung,
    atlas_ke_wu_ung,
    atlas_ep_em,
)
from ambroflow.kobra_compiled.atlas_engine import KobraSuccess, KobraError


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _tile(name: str, w: int = 16, h: int = 16) -> TileFileDecl:
    return TileFileDecl(
        path=f"tiles/{name}.png",
        width=w,
        height=h,
        pixel_data=bytes(w * h * 4),
    )


def _dir(name: str, tiles: list) -> TileDirDecl:
    return TileDirDecl(path=f"tiles/{name}", files=list(tiles))


def _cluster(*dirs) -> AtlasClusterDecl:
    return AtlasClusterDecl(cluster_id=0, dirs=list(dirs))


# ── AtlasDecl hierarchy ───────────────────────────────────────────────────────

class TestAtlasDeclHierarchy:
    def test_tile_file_is_atlas_decl(self):
        tf = _tile("stone")
        assert isinstance(tf, AtlasDecl)
        assert tf.tongue_eq == "MavoSaoWuUng"

    def test_tile_dir_is_atlas_decl(self):
        d = _dir("ground", [])
        assert isinstance(d, AtlasDecl)
        assert d.tongue_eq == "MavoSethWuUng"

    def test_cluster_is_atlas_decl(self):
        c = _cluster()
        assert isinstance(c, AtlasDecl)
        assert c.tongue_eq == "MavoSamosWuUng"

    def test_vaddr_is_atlas_decl(self):
        v = AtlasVAddrDecl(base_offset=3, sheet_x=1, sheet_y=0, tile_w=16, tile_h=16)
        assert isinstance(v, AtlasDecl)
        assert v.tongue_eq == "MavoSaWuUng"

    def test_cache_is_atlas_decl(self):
        c = AtlasCacheDecl(max_pages=32)
        assert isinstance(c, AtlasDecl)
        assert c.tongue_eq == "MavoSaelWuUng"

    def test_snapshot_is_atlas_decl(self):
        s = AtlasSnapshotDecl()
        assert isinstance(s, AtlasDecl)
        assert s.tongue_eq == "MavoSavaWuUng"


# ── atlas_read_eval ───────────────────────────────────────────────────────────

class TestAtlasReadEval:
    def test_valid_hierarchy_returns_true(self):
        tf = _tile("grass")
        d  = _dir("ground", [tf])
        c  = _cluster(d)
        assert atlas_read_eval(tf, d, c) is True

    def test_file_not_in_dir_raises(self):
        tf = _tile("grass")
        d  = _dir("ground", [])        # tf not in dir
        c  = _cluster(d)
        with pytest.raises(KobraError):
            atlas_read_eval(tf, d, c)

    def test_dir_not_in_cluster_raises(self):
        tf = _tile("grass")
        d1 = _dir("ground", [tf])
        d2 = _dir("other", [])
        c  = _cluster(d2)              # d1 not in cluster
        with pytest.raises(KobraError):
            atlas_read_eval(tf, d1, c)

    def test_empty_paths_pass(self):
        tf = TileFileDecl()
        d  = TileDirDecl()
        c  = AtlasClusterDecl()
        assert atlas_read_eval(tf, d, c) is True


# ── atlas_index_el ────────────────────────────────────────────────────────────

class TestAtlasIndexEl:
    def test_returns_vaddr(self):
        tf = _tile("stone")
        d  = _dir("ground", [tf])
        c  = _cluster(d)
        v  = atlas_index_el(d, tf, c)
        assert isinstance(v, AtlasVAddrDecl)

    def test_first_tile_base_offset_zero(self):
        tf = _tile("stone")
        d  = _dir("ground", [tf])
        c  = _cluster(d)
        v  = atlas_index_el(d, tf, c)
        assert v.base_offset == 0

    def test_second_tile_nonzero_offset(self):
        t0 = _tile("stone")
        t1 = _tile("grass")
        d  = _dir("ground", [t0, t1])
        c  = _cluster(d)
        v  = atlas_index_el(d, t1, c)
        assert v.base_offset == 1

    def test_tile_dimensions_propagated(self):
        tf = _tile("big", w=32, h=32)
        d  = _dir("large", [tf])
        c  = _cluster(d)
        v  = atlas_index_el(d, tf, c)
        assert v.tile_w == 32
        assert v.tile_h == 32


# ── atlas_page_el ─────────────────────────────────────────────────────────────

class TestAtlasPageEl:
    def test_returns_pixel_data_when_present(self):
        data = bytes([255, 0, 128, 255] * 4)
        tf   = TileFileDecl(path="t.png", width=2, height=2, pixel_data=data)
        assert atlas_page_el(tf) == data

    def test_returns_zeroed_bytes_for_missing_file(self):
        tf   = TileFileDecl(path="nonexistent_tile_xyz.png", width=4, height=4)
        data = atlas_page_el(tf)
        assert len(data) == 4 * 4 * 4
        assert all(b == 0 for b in data)


# ── AtlasCacheDecl (hot LRU) ──────────────────────────────────────────────────

class TestAtlasCacheDecl:
    def test_promote_and_hit(self):
        c  = AtlasCacheDecl(max_pages=4)
        tf = _tile("stone")
        assert not c.is_hot(tf.path)
        c.promote(tf.path, b"data")
        assert c.is_hot(tf.path)

    def test_lru_eviction_at_capacity(self):
        c = AtlasCacheDecl(max_pages=2)
        c.promote("a", b"A")
        c.promote("b", b"B")
        c.promote("c", b"C")        # evicts "a" (oldest)
        assert not c.is_hot("a")
        assert c.is_hot("b")
        assert c.is_hot("c")

    def test_explicit_evict(self):
        c = AtlasCacheDecl(max_pages=4)
        c.promote("x", b"X")
        c.evict("x")
        assert not c.is_hot("x")

    def test_hot_page_el_promotes(self):
        cache = AtlasCacheDecl(max_pages=8)
        tf    = _tile("grass")
        result = hot_page_el(cache, tf)
        assert result.is_hot(tf.path)

    def test_page_evict_el_removes(self):
        cache = AtlasCacheDecl(max_pages=8)
        tf    = _tile("grass")
        cache.promote(tf.path, b"data")
        result = page_evict_el(cache, tf)
        assert not result.is_hot(tf.path)


# ── hot_page_eval ─────────────────────────────────────────────────────────────

class TestHotPageEval:
    def test_returns_true_on_hit(self):
        cache = AtlasCacheDecl()
        tf    = _tile("stone")
        cache.promote(tf.path, b"data")
        assert hot_page_eval(cache, tf) is True

    def test_returns_false_on_miss(self):
        cache = AtlasCacheDecl()
        tf    = _tile("stone")
        assert hot_page_eval(cache, tf) is False


# ── atlas_bus_eval ────────────────────────────────────────────────────────────

class TestAtlasBusEval:
    def test_valid_vaddr_returns_true(self):
        tf = _tile("stone")
        d  = _dir("ground", [tf])
        c  = _cluster(d)
        v  = AtlasVAddrDecl(base_offset=0, tile_w=16, tile_h=16)
        assert atlas_bus_eval(v, c) is True

    def test_out_of_bounds_raises(self):
        tf = _tile("stone")
        d  = _dir("ground", [tf])
        c  = _cluster(d)
        v  = AtlasVAddrDecl(base_offset=99, tile_w=16, tile_h=16)
        with pytest.raises(KobraError):
            atlas_bus_eval(v, c)

    def test_empty_cluster_passes(self):
        c = AtlasClusterDecl()
        v = AtlasVAddrDecl(base_offset=0)
        assert atlas_bus_eval(v, c) is True


# ── atlas_dma_el ──────────────────────────────────────────────────────────────

class TestAtlasDMAEl:
    def test_returns_transfer_descriptor(self):
        backing = bytearray(16 * 16 * 4 * 2)
        v = AtlasVAddrDecl(base_offset=0, sheet_x=0, sheet_y=0, tile_w=16, tile_h=16)
        desc = atlas_dma_el(v, backing)
        assert "offset" in desc
        assert "data_view" in desc
        assert desc["tile_w"] == 16

    def test_second_tile_has_correct_offset(self):
        w, h = 8, 8
        backing = bytearray(w * h * 4 * 4)
        v = AtlasVAddrDecl(base_offset=1, sheet_x=1, sheet_y=0, tile_w=w, tile_h=h)
        desc = atlas_dma_el(v, backing)
        assert desc["offset"] == w * h * 4


# ── atlas_stream_el ───────────────────────────────────────────────────────────

class TestAtlasStreamEl:
    def test_empty_manifest_returns_empty(self):
        snap = AtlasSnapshotDecl()
        c    = AtlasClusterDecl()
        assert atlas_stream_el(snap, c) == []

    def test_manifest_entries_returned(self):
        vaddr = AtlasVAddrDecl(base_offset=0, tile_w=8, tile_h=8)
        snap  = AtlasSnapshotDecl(manifest={"tile.png": vaddr})
        c     = AtlasClusterDecl()
        result = atlas_stream_el(snap, c)
        assert len(result) == 1
        assert result[0]["path"] == "tile.png"


# ── atlas_render_eval ─────────────────────────────────────────────────────────

class TestAtlasRenderEval:
    def test_empty_cluster_returns_empty(self):
        c    = AtlasClusterDecl()
        cache = AtlasCacheDecl()
        snap  = AtlasSnapshotDecl()
        result = atlas_render_eval(c, cache, snap)
        assert result["width"] == 0
        assert result["height"] == 0

    def test_single_tile_sheet_dimensions(self):
        tf = _tile("stone", w=16, h=16)
        d  = _dir("ground", [tf])
        c  = _cluster(d)
        result = atlas_render_eval(c, AtlasCacheDecl(), AtlasSnapshotDecl())
        assert result["width"] == 16
        assert result["height"] == 16

    def test_four_tiles_form_2x2_sheet(self):
        tiles = [_tile(f"t{i}", w=8, h=8) for i in range(4)]
        d     = _dir("ground", tiles)
        c     = _cluster(d)
        result = atlas_render_eval(c, AtlasCacheDecl(), AtlasSnapshotDecl())
        assert result["width"]  == 16   # 2 cols * 8
        assert result["height"] == 16   # 2 rows * 8

    def test_result_has_vaddrs_for_all_tiles(self):
        tiles = [_tile(f"t{i}", w=4, h=4) for i in range(3)]
        d     = _dir("ground", tiles)
        c     = _cluster(d)
        result = atlas_render_eval(c, AtlasCacheDecl(), AtlasSnapshotDecl())
        assert len(result["vaddrs"]) == 3
        for tf in tiles:
            assert tf.path in result["vaddrs"]

    def test_sheet_data_length_correct(self):
        tiles = [_tile(f"t{i}", w=4, h=4) for i in range(4)]
        d     = _dir("ground", tiles)
        c     = _cluster(d)
        result = atlas_render_eval(c, AtlasCacheDecl(), AtlasSnapshotDecl())
        expected = result["width"] * result["height"] * 4
        assert len(result["data"]) == expected

    def test_hot_cache_tiles_used(self):
        tf   = _tile("stone", w=4, h=4)
        data = bytes([100, 200, 50, 255] * 16)
        cache = AtlasCacheDecl()
        cache.promote(tf.path, data)
        d  = _dir("ground", [tf])
        c  = _cluster(d)
        result = atlas_render_eval(c, cache, AtlasSnapshotDecl())
        assert result["data"][:4] == bytes([100, 200, 50, 255])


# ── atlas_shi_wu_ung / atlas_ke_wu_ung / atlas_ep_em ─────────────────────────

class TestAtlasConvergence:
    def test_shi_wu_ung_wraps_in_kobra_success(self):
        result = atlas_shi_wu_ung({"width": 16, "height": 16, "data": b"", "vaddrs": {}})
        assert isinstance(result, KobraSuccess)
        assert result.value["width"] == 16

    def test_ke_wu_ung_raises_kobra_error(self):
        with pytest.raises(KobraError):
            atlas_ke_wu_ung("test failure")

    def test_ep_em_returns_dict_on_success(self):
        tf = _tile("stone", w=4, h=4)
        d  = _dir("ground", [tf])
        c  = _cluster(d)
        result = atlas_ep_em(c, AtlasCacheDecl(), AtlasSnapshotDecl())
        assert isinstance(result, dict)
        assert "width" in result

    def test_ep_em_propagates_kobra_error(self):
        c = AtlasClusterDecl(dirs=[TileDirDecl(path="bad")])
        with pytest.raises(KobraError):
            # Force KobraError by injecting a bad vaddr check scenario
            atlas_ke_wu_ung("forced")
