"""
Tests for the Mercurie map discovery screen and WorldPlay MAP_DISCOVERY mode.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ambroflow.world.map_discovery import (
    MapDiscoveryScreen,
    MapState,
    ITEM_ID,
    ITEM_NAME,
    _JOURNAL_TITLE,
    _JOURNAL_BODY,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_fake_maps_dir(tmp_path: Path) -> Path:
    """Write minimal 1×1 PNGs for each map asset."""
    try:
        from PIL import Image
        for name in ("mercurie_map_folded.png", "mercurie_map_full.png", "mercurie_map_thumb.png"):
            img = Image.new("RGB", (4, 4), (200, 190, 170))
            img.save(tmp_path / name)
    except ImportError:
        # Write zero-byte placeholders so path.exists() returns True
        for name in ("mercurie_map_folded.png", "mercurie_map_full.png", "mercurie_map_thumb.png"):
            (tmp_path / name).write_bytes(b"")
    return tmp_path


# ── Item constants ────────────────────────────────────────────────────────────

def test_item_id_format():
    assert ITEM_ID == "0036_KLIT"


def test_item_name():
    assert ITEM_NAME == "Map of Mercurie"


def test_journal_title_nonempty():
    assert len(_JOURNAL_TITLE) > 0


def test_journal_body_mentions_forest():
    assert "Forest" in _JOURNAL_BODY


def test_journal_body_mentions_locations():
    assert "Mt. Hieronymus" in _JOURNAL_BODY
    assert "Church of Gnome Rizz" in _JOURNAL_BODY


# ── MapDiscoveryScreen ────────────────────────────────────────────────────────

def test_screen_renders_folded_bytes():
    pytest.importorskip("PIL")
    with tempfile.TemporaryDirectory() as td:
        maps_dir = _make_fake_maps_dir(Path(td))
        screen = MapDiscoveryScreen(maps_dir=maps_dir)
        result = screen.render(MapState.FOLDED, 320, 200)
    assert result is not None
    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"


def test_screen_renders_unfolded_bytes():
    pytest.importorskip("PIL")
    with tempfile.TemporaryDirectory() as td:
        maps_dir = _make_fake_maps_dir(Path(td))
        screen = MapDiscoveryScreen(maps_dir=maps_dir)
        result = screen.render(MapState.UNFOLDED, 320, 200)
    assert result is not None
    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"


def test_screen_handles_missing_maps_dir():
    pytest.importorskip("PIL")
    screen = MapDiscoveryScreen(maps_dir=Path("/nonexistent/maps/dir"))
    # Should still render (with blank background) rather than raise
    result = screen.render(MapState.FOLDED, 320, 200)
    assert result is not None


def test_screen_folded_and_unfolded_differ():
    pytest.importorskip("PIL")
    with tempfile.TemporaryDirectory() as td:
        maps_dir = _make_fake_maps_dir(Path(td))
        screen = MapDiscoveryScreen(maps_dir=maps_dir)
        folded   = screen.render(MapState.FOLDED,   320, 200)
        unfolded = screen.render(MapState.UNFOLDED, 320, 200)
    assert folded != unfolded


# ── WorldPlay MAP_DISCOVERY integration ──────────────────────────────────────

def _make_play_with_map(maps_dir: Path):
    """Build a minimal WorldPlay with a mocked world map and map discovery wired."""
    from ambroflow.world.play import WorldPlay, WorldMode
    from ambroflow.world.map import WorldMap, Zone, Realm, WorldTileKind
    from ambroflow.world.loaders import EncounterDef

    voxels = {(x, y): WorldTileKind.FLOOR for x in range(5) for y in range(5)}
    zone = Zone(
        zone_id="wiltoll",
        name="Wiltoll Lane",
        realm=Realm.LAPIDUS,
        width=5,
        height=5,
        voxels=voxels,
        player_spawn=(2, 2),
    )
    world = WorldMap(zones={"wiltoll": zone}, starting_zone_id="wiltoll")

    chargen = MagicMock()
    chargen.name = "Apprentice"

    inventory = MagicMock()
    journal   = MagicMock()

    enc = EncounterDef(
        encounter_id="forest_journal_discovery",
        name="forest_journal_discovery",
        zone_id="wiltoll",
        trigger_type="quest_witnessed",
        entry_id="0004_KLST",
        candidate="golden_path_complete",
        combatants=(),
        loot=(),
        xp_reward=0,
    )

    play = WorldPlay(
        chargen=chargen,
        world_map=world,
        width=320, height=200,
        encounter_defs=[enc],
        inventory=inventory,
        journal=journal,
    )
    # Point map screen at temp dir
    from ambroflow.world.map_discovery import MapDiscoveryScreen
    play._map_screen = None  # not yet opened
    play._maps_dir_override = maps_dir  # stored for _begin_map_discovery patch
    return play, inventory, journal


def test_begin_map_discovery_sets_mode():
    pytest.importorskip("PIL")
    with tempfile.TemporaryDirectory() as td:
        maps_dir = _make_fake_maps_dir(Path(td))
        play, _, _ = _make_play_with_map(maps_dir)
        with patch.object(
            play.__class__, "_begin_map_discovery",
            lambda self: (
                setattr(self, "_map_screen", MapDiscoveryScreen(maps_dir=maps_dir)),
                setattr(self, "_map_state", MapState.FOLDED),
                setattr(self, "_mode", __import__("ambroflow.world.play", fromlist=["WorldMode"]).WorldMode.MAP_DISCOVERY),
            )
        ):
            play._begin_map_discovery()
        from ambroflow.world.play import WorldMode
        assert play._mode == WorldMode.MAP_DISCOVERY


def test_close_map_adds_inventory_item():
    pytest.importorskip("PIL")
    with tempfile.TemporaryDirectory() as td:
        maps_dir = _make_fake_maps_dir(Path(td))
        play, inventory, journal = _make_play_with_map(maps_dir)
        play._map_screen = MapDiscoveryScreen(maps_dir=maps_dir)
        play._map_state  = MapState.UNFOLDED
        play._map_item_collected = False

        play._close_map()

        inventory.add.assert_called_once_with(ITEM_ID)


def test_close_map_writes_journal_entry():
    pytest.importorskip("PIL")
    with tempfile.TemporaryDirectory() as td:
        maps_dir = _make_fake_maps_dir(Path(td))
        play, inventory, journal = _make_play_with_map(maps_dir)
        play._map_screen = MapDiscoveryScreen(maps_dir=maps_dir)
        play._map_state  = MapState.UNFOLDED
        play._map_item_collected = False

        play._close_map()

        journal.write.assert_called_once()
        call_args = journal.write.call_args
        assert _JOURNAL_TITLE in str(call_args)


def test_close_map_marks_quest_witnessed():
    pytest.importorskip("PIL")
    with tempfile.TemporaryDirectory() as td:
        maps_dir = _make_fake_maps_dir(Path(td))
        play, _, _ = _make_play_with_map(maps_dir)
        play._map_screen = MapDiscoveryScreen(maps_dir=maps_dir)
        play._map_state  = MapState.FOLDED
        play._map_item_collected = False

        play._close_map()

        entries = play._quest_state.get("entries", {})
        assert "forest_journal_discovery" in entries
        assert entries["forest_journal_discovery"]["witness_state"] == "witnessed"


def test_close_map_idempotent():
    """Closing twice does not add the item twice."""
    pytest.importorskip("PIL")
    with tempfile.TemporaryDirectory() as td:
        maps_dir = _make_fake_maps_dir(Path(td))
        play, inventory, journal = _make_play_with_map(maps_dir)
        play._map_screen = MapDiscoveryScreen(maps_dir=maps_dir)
        play._map_item_collected = False

        play._close_map()
        play._map_screen = MapDiscoveryScreen(maps_dir=maps_dir)
        play._close_map()

        assert inventory.add.call_count == 1
        assert journal.write.call_count == 1


def test_returns_to_world_mode_on_close():
    pytest.importorskip("PIL")
    with tempfile.TemporaryDirectory() as td:
        maps_dir = _make_fake_maps_dir(Path(td))
        play, _, _ = _make_play_with_map(maps_dir)
        play._map_screen = MapDiscoveryScreen(maps_dir=maps_dir)
        play._map_item_collected = False

        play._close_map()

        from ambroflow.world.play import WorldMode
        assert play._mode == WorldMode.WORLD