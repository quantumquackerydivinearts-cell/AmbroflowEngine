"""
Tests for the multi-room home scene renderers (scenes/location.py).

Covers:
- All six room renderers return valid PNG bytes at expected dimensions
- HomeRoom dispatch function routes correctly
- Time-of-day variants produce different images
- Backward-compatible render_wiltoll_lane_interior alias still works
- render_bedroom rumpled flag produces visible difference
"""

from __future__ import annotations

import struct
import pytest

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

pytestmark = pytest.mark.skipif(not _PIL, reason="PIL not installed")


# ── helpers ───────────────────────────────────────────────────────────────────

def _is_png(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def _png_dims(data: bytes) -> tuple[int, int]:
    w = struct.unpack(">I", data[16:20])[0]
    h = struct.unpack(">I", data[20:24])[0]
    return w, h


# ── imports ───────────────────────────────────────────────────────────────────

from ambroflow.scenes.location import (
    HomeRoom,
    render_bedroom,
    render_foyer,
    render_workbench_area,
    render_kitchen,
    render_meditation_room,
    render_study,
    render_home_room,
    render_wiltoll_lane_interior,
)


# ── individual room renderers ─────────────────────────────────────────────────

class TestRenderBedroom:
    def test_returns_png_dawn(self):
        data = render_bedroom(time_of_day="dawn", rumpled=True)
        assert data is not None
        assert _is_png(data)

    def test_returns_png_late_afternoon(self):
        data = render_bedroom(time_of_day="late_afternoon", rumpled=False)
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self):
        data = render_bedroom(time_of_day="dawn")
        w, h = _png_dims(data)
        assert w == 512
        assert h == 384

    def test_custom_dimensions(self):
        data = render_bedroom(time_of_day="dawn", width=320, height=240)
        w, h = _png_dims(data)
        assert w == 320
        assert h == 240

    def test_dawn_vs_late_afternoon_differ(self):
        dawn = render_bedroom(time_of_day="dawn", rumpled=True)
        late = render_bedroom(time_of_day="late_afternoon", rumpled=True)
        assert dawn != late

    def test_rumpled_vs_tidy_differ(self):
        rumpled = render_bedroom(time_of_day="late_afternoon", rumpled=True)
        tidy    = render_bedroom(time_of_day="late_afternoon", rumpled=False)
        assert rumpled != tidy


class TestRenderFoyer:
    def test_returns_png_dawn(self):
        data = render_foyer(time_of_day="dawn")
        assert data is not None
        assert _is_png(data)

    def test_returns_png_late_afternoon(self):
        data = render_foyer(time_of_day="late_afternoon")
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self):
        data = render_foyer(time_of_day="dawn")
        w, h = _png_dims(data)
        assert w == 512
        assert h == 384

    def test_time_of_day_variants_differ(self):
        dawn = render_foyer(time_of_day="dawn")
        late = render_foyer(time_of_day="late_afternoon")
        assert dawn != late


class TestRenderKitchen:
    def test_returns_png_dawn(self):
        data = render_kitchen(time_of_day="dawn")
        assert data is not None
        assert _is_png(data)

    def test_returns_png_late_afternoon(self):
        data = render_kitchen(time_of_day="late_afternoon")
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self):
        data = render_kitchen(time_of_day="dawn")
        w, h = _png_dims(data)
        assert w == 512
        assert h == 384

    def test_time_of_day_variants_differ(self):
        dawn = render_kitchen(time_of_day="dawn")
        late = render_kitchen(time_of_day="late_afternoon")
        assert dawn != late


class TestRenderMeditationRoom:
    def test_returns_png_dawn(self):
        data = render_meditation_room(time_of_day="dawn")
        assert data is not None
        assert _is_png(data)

    def test_returns_png_late_afternoon(self):
        data = render_meditation_room(time_of_day="late_afternoon")
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self):
        data = render_meditation_room(time_of_day="dawn")
        w, h = _png_dims(data)
        assert w == 512
        assert h == 384

    def test_time_of_day_variants_differ(self):
        dawn = render_meditation_room(time_of_day="dawn")
        late = render_meditation_room(time_of_day="late_afternoon")
        assert dawn != late


class TestRenderStudy:
    def test_returns_png_dawn(self):
        data = render_study(time_of_day="dawn")
        assert data is not None
        assert _is_png(data)

    def test_returns_png_late_afternoon(self):
        data = render_study(time_of_day="late_afternoon")
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self):
        data = render_study(time_of_day="dawn")
        w, h = _png_dims(data)
        assert w == 512
        assert h == 384

    def test_time_of_day_variants_differ(self):
        dawn = render_study(time_of_day="dawn")
        late = render_study(time_of_day="late_afternoon")
        assert dawn != late


class TestRenderWorkbench:
    def test_returns_png_dawn(self):
        data = render_workbench_area(time_of_day="dawn")
        assert data is not None
        assert _is_png(data)

    def test_returns_png_late_afternoon(self):
        data = render_workbench_area(time_of_day="late_afternoon")
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self):
        data = render_workbench_area(time_of_day="dawn")
        w, h = _png_dims(data)
        assert w == 512
        assert h == 384

    def test_time_of_day_variants_differ(self):
        dawn = render_workbench_area(time_of_day="dawn")
        late = render_workbench_area(time_of_day="late_afternoon")
        assert dawn != late


# ── HomeRoom dispatch ─────────────────────────────────────────────────────────

class TestRenderHomeRoom:
    @pytest.mark.parametrize("room", list(HomeRoom))
    def test_dispatch_all_rooms_return_png(self, room):
        data = render_home_room(room, time_of_day="late_afternoon")
        assert data is not None
        assert _is_png(data)

    def test_dispatch_bedroom_matches_direct(self):
        via_dispatch = render_home_room(HomeRoom.BEDROOM, time_of_day="dawn", rumpled=True)
        direct       = render_bedroom(time_of_day="dawn", rumpled=True)
        assert via_dispatch == direct

    def test_dispatch_foyer_matches_direct(self):
        via_dispatch = render_home_room(HomeRoom.FOYER, time_of_day="dawn")
        direct       = render_foyer(time_of_day="dawn")
        assert via_dispatch == direct

    def test_dispatch_kitchen_matches_direct(self):
        via_dispatch = render_home_room(HomeRoom.KITCHEN, time_of_day="late_afternoon")
        direct       = render_kitchen(time_of_day="late_afternoon")
        assert via_dispatch == direct

    def test_dispatch_study_matches_direct(self):
        via_dispatch = render_home_room(HomeRoom.STUDY, time_of_day="late_afternoon")
        direct       = render_study(time_of_day="late_afternoon")
        assert via_dispatch == direct

    def test_dispatch_meditation_matches_direct(self):
        via_dispatch = render_home_room(HomeRoom.MEDITATION, time_of_day="late_afternoon")
        direct       = render_meditation_room(time_of_day="late_afternoon")
        assert via_dispatch == direct

    def test_dispatch_workbench_matches_direct(self):
        via_dispatch = render_home_room(HomeRoom.WORKBENCH, time_of_day="late_afternoon")
        direct       = render_workbench_area(time_of_day="late_afternoon")
        assert via_dispatch == direct


# ── backward compatibility ────────────────────────────────────────────────────

class TestBackwardCompat:
    def test_render_wiltoll_lane_interior_returns_png(self):
        data = render_wiltoll_lane_interior(
            time_of_day="late_afternoon", width=512, height=384
        )
        assert data is not None
        assert _is_png(data)

    def test_wiltoll_matches_workbench(self):
        wiltoll   = render_wiltoll_lane_interior(
            time_of_day="late_afternoon", width=512, height=384
        )
        workbench = render_workbench_area(
            time_of_day="late_afternoon", width=512, height=384
        )
        assert wiltoll == workbench


# ── all rooms are distinct ────────────────────────────────────────────────────

class TestAllRoomsDistinct:
    def test_all_six_rooms_produce_different_output(self):
        late = "late_afternoon"
        renders = {
            HomeRoom.BEDROOM:    render_bedroom(time_of_day=late),
            HomeRoom.FOYER:      render_foyer(time_of_day=late),
            HomeRoom.KITCHEN:    render_kitchen(time_of_day=late),
            HomeRoom.MEDITATION: render_meditation_room(time_of_day=late),
            HomeRoom.STUDY:      render_study(time_of_day=late),
            HomeRoom.WORKBENCH:  render_workbench_area(time_of_day=late),
        }
        # All 6 unique
        assert len(set(renders.values())) == 6