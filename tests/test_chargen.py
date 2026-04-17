"""
Tests for character creation data and screens (chargen/data.py, chargen/screens.py).

Covers:
- LineageOption and GenderOption data integrity
- ChargenState.is_complete() logic
- All screen renderers return valid PNG bytes
- Screen dimensions
- Gender screen selection state
- Lineage screen selection state
- VITRIOL sheet budget display
- chargen_sequence produces exactly 4 frames
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

from ambroflow.chargen.data import (
    LineageOption,
    GenderOption,
    ChargenState,
    LINEAGE_OPTIONS,
    LINEAGE_BY_ID,
    GENDER_OPTIONS,
    GENDER_BY_ID,
    KO_GENDER_PROMPT,
)
from ambroflow.chargen.screens import (
    render_ko_gender_question,
    render_name_screen,
    render_lineage_screen,
    render_vitriol_assignment_sheet,
    render_chargen_sequence,
)
from ambroflow.ko.vitriol import VITRIOLProfile, VITRIOL_STATS


# ── canonical data ────────────────────────────────────────────────────────────

class TestLineageData:
    def test_five_lineage_options(self):
        assert len(LINEAGE_OPTIONS) == 5

    def test_all_have_unique_ids(self):
        ids = [l.id for l in LINEAGE_OPTIONS]
        assert len(ids) == len(set(ids))

    def test_all_have_name_and_description(self):
        for l in LINEAGE_OPTIONS:
            assert l.name.strip()
            assert l.description.strip()
            assert l.ko_note.strip()

    def test_by_id_lookup(self):
        assert LINEAGE_BY_ID["scholars_house"].name == "Scholar's House"
        assert LINEAGE_BY_ID["lapidus_touched"].id  == "lapidus_touched"

    def test_lapidus_has_quartz(self):
        lap = LINEAGE_BY_ID["lapidus_touched"]
        assert any("Quartz" in item for item in lap.starting_items)

    def test_lapidus_starting_items_are_balanced(self):
        """Lapidus-Touched should not give Desire Crystals or other Asmodean materials."""
        lap = LINEAGE_BY_ID["lapidus_touched"]
        for item in lap.starting_items:
            assert "Desire Crystal" not in item, (
                "Desire Crystal is Asmodean and grants Sulphera bypass — not a valid starting item"
            )

    def test_merchant_has_gold(self):
        mer = LINEAGE_BY_ID["merchant_family"]
        assert any("Gold" in item for item in mer.starting_items)

    def test_all_have_unlocks(self):
        for l in LINEAGE_OPTIONS:
            assert len(l.unlocks) >= 1


class TestGenderData:
    def test_seven_or_more_gender_options(self):
        assert len(GENDER_OPTIONS) >= 7

    def test_all_have_unique_ids(self):
        ids = [g.id for g in GENDER_OPTIONS]
        assert len(ids) == len(set(ids))

    def test_all_have_label_and_ko_phrasing(self):
        for g in GENDER_OPTIONS:
            assert g.label.strip()
            assert g.ko_phrasing.strip()
            assert g.pronoun_set.strip()

    def test_woman_man_have_binary_pronouns(self):
        assert GENDER_BY_ID["woman"].pronoun_set == "she/her"
        assert GENDER_BY_ID["man"].pronoun_set   == "he/him"

    def test_non_binary_options_use_they_them(self):
        non_binary = ["neither", "both", "fluid", "void_form", "unnamed"]
        for gid in non_binary:
            assert GENDER_BY_ID[gid].pronoun_set == "they/them"

    def test_ko_gender_prompt_is_canonical(self):
        assert KO_GENDER_PROMPT == "The shape you move through the world with."

    def test_ko_phrasing_not_performative(self):
        forbidden = ["you have", "i give", "i assign", "you receive"]
        for g in GENDER_OPTIONS:
            for phrase in forbidden:
                assert phrase not in g.ko_phrasing.lower(), (
                    f"Gender '{g.id}' ko_phrasing contains forbidden phrase '{phrase}'"
                )


class TestChargenState:
    def _complete_vitriol(self):
        return {s: 4 for s in VITRIOL_STATS}

    def test_incomplete_by_default(self):
        state = ChargenState()
        assert not state.is_complete()

    def test_complete_when_all_fields_set(self):
        state = ChargenState(
            name="Meridian",
            gender_id="woman",
            lineage_id="scholars_house",
            player_vitriol=self._complete_vitriol(),
        )
        assert state.is_complete()

    def test_incomplete_without_name(self):
        state = ChargenState(
            name="",
            gender_id="woman",
            lineage_id="scholars_house",
            player_vitriol=self._complete_vitriol(),
        )
        assert not state.is_complete()

    def test_incomplete_without_gender(self):
        state = ChargenState(
            name="Meridian",
            gender_id="",
            lineage_id="scholars_house",
            player_vitriol=self._complete_vitriol(),
        )
        assert not state.is_complete()

    def test_incomplete_without_lineage(self):
        state = ChargenState(
            name="Meridian",
            gender_id="woman",
            lineage_id="",
            player_vitriol=self._complete_vitriol(),
        )
        assert not state.is_complete()

    def test_incomplete_with_missing_vitriol_stats(self):
        partial = {s: 4 for s in list(VITRIOL_STATS)[:3]}
        state = ChargenState(
            name="Meridian",
            gender_id="woman",
            lineage_id="scholars_house",
            player_vitriol=partial,
        )
        assert not state.is_complete()

    def test_lineage_property_returns_option(self):
        state = ChargenState(lineage_id="scholars_house")
        assert state.lineage is not None
        assert state.lineage.name == "Scholar's House"

    def test_gender_property_returns_option(self):
        state = ChargenState(gender_id="neither")
        assert state.gender is not None
        assert state.gender.pronoun_set == "they/them"

    def test_whitespace_name_incomplete(self):
        state = ChargenState(
            name="   ",
            gender_id="woman",
            lineage_id="scholars_house",
            player_vitriol=self._complete_vitriol(),
        )
        assert not state.is_complete()


# ── screen renderers ──────────────────────────────────────────────────────────

@pytest.fixture
def ko_profile():
    return VITRIOLProfile(
        vitality=6, introspection=7, tactility=5,
        reflectivity=6, ingenuity=4, ostentation=5, levity=8,
    )


class TestRenderKoGenderQuestion:
    def test_returns_png(self):
        data = render_ko_gender_question()
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self):
        data = render_ko_gender_question()
        w, h = _png_dims(data)
        assert w == 512
        assert h == 512

    def test_custom_size(self):
        data = render_ko_gender_question(size=256)
        w, h = _png_dims(data)
        assert w == 256
        assert h == 256

    def test_with_options_and_selection(self):
        data = render_ko_gender_question(list(GENDER_OPTIONS), selected_idx=2)
        assert data is not None
        assert _is_png(data)

    def test_different_selections_differ(self):
        a = render_ko_gender_question(list(GENDER_OPTIONS), selected_idx=0)
        b = render_ko_gender_question(list(GENDER_OPTIONS), selected_idx=1)
        assert a != b

    def test_unselected_differs_from_selected(self):
        a = render_ko_gender_question(list(GENDER_OPTIONS), selected_idx=None)
        b = render_ko_gender_question(list(GENDER_OPTIONS), selected_idx=0)
        assert a != b


class TestRenderNameScreen:
    def test_returns_png(self):
        data = render_name_screen()
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self):
        data = render_name_screen()
        w, h = _png_dims(data)
        assert w == 512
        assert h == 512

    def test_with_name(self):
        data = render_name_screen("Meridian")
        assert data is not None
        assert _is_png(data)

    def test_empty_name_differs_from_filled(self):
        empty  = render_name_screen("")
        filled = render_name_screen("Meridian")
        assert empty != filled


class TestRenderLineageScreen:
    def test_returns_png(self):
        data = render_lineage_screen()
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self):
        data = render_lineage_screen()
        w, h = _png_dims(data)
        assert w == 512
        assert h == 512

    def test_with_options_and_selection(self):
        data = render_lineage_screen(list(LINEAGE_OPTIONS), selected_idx=0)
        assert data is not None
        assert _is_png(data)

    def test_different_selections_differ(self):
        a = render_lineage_screen(list(LINEAGE_OPTIONS), selected_idx=0)
        b = render_lineage_screen(list(LINEAGE_OPTIONS), selected_idx=3)
        assert a != b

    def test_all_lineage_selections_render(self):
        for idx in range(len(LINEAGE_OPTIONS)):
            data = render_lineage_screen(list(LINEAGE_OPTIONS), selected_idx=idx)
            assert _is_png(data)


class TestRenderVITRIOLSheet:
    def test_returns_png(self, ko_profile):
        player = {s: getattr(ko_profile, s) for s in VITRIOL_STATS}
        data = render_vitriol_assignment_sheet(ko_profile, player, 0)
        assert data is not None
        assert _is_png(data)

    def test_default_dimensions(self, ko_profile):
        player = {s: getattr(ko_profile, s) for s in VITRIOL_STATS}
        data = render_vitriol_assignment_sheet(ko_profile, player, 0)
        w, h = _png_dims(data)
        assert w == 512
        assert h == 512

    def test_active_stat_differs_from_inactive(self, ko_profile):
        player = {s: getattr(ko_profile, s) for s in VITRIOL_STATS}
        no_active = render_vitriol_assignment_sheet(ko_profile, player, 0)
        active    = render_vitriol_assignment_sheet(
            ko_profile, player, 0, active_stat="vitality"
        )
        assert no_active != active

    def test_each_active_stat_differs(self, ko_profile):
        player = {s: getattr(ko_profile, s) for s in VITRIOL_STATS}
        renders = [
            render_vitriol_assignment_sheet(ko_profile, player, 0, active_stat=s)
            for s in VITRIOL_STATS
        ]
        assert len(set(renders)) == len(VITRIOL_STATS)

    def test_different_budgets_differ(self, ko_profile):
        player = {s: getattr(ko_profile, s) for s in VITRIOL_STATS}
        data0  = render_vitriol_assignment_sheet(ko_profile, player, 0)
        data5  = render_vitriol_assignment_sheet(ko_profile, player, 5)
        assert data0 != data5

    def test_player_divergence_from_ko_renders(self, ko_profile):
        player = {s: max(1, getattr(ko_profile, s) - 2) for s in VITRIOL_STATS}
        data = render_vitriol_assignment_sheet(ko_profile, player, 2)
        assert _is_png(data)


class TestRenderChargenSequence:
    def test_produces_four_frames(self, ko_profile):
        state = ChargenState(
            name="Meridian",
            gender_id="woman",
            lineage_id="scholars_house",
            player_vitriol={},
        )
        frames = render_chargen_sequence(ko_profile, state)
        assert len(frames) == 4

    def test_all_frames_are_png(self, ko_profile):
        state = ChargenState(
            name="",
            gender_id="",
            lineage_id="",
            player_vitriol={},
        )
        frames = render_chargen_sequence(ko_profile, state)
        for i, f in enumerate(frames):
            assert _is_png(f), f"Frame {i} is not a valid PNG"

    def test_frames_have_consistent_size(self, ko_profile):
        state = ChargenState(
            name="Meridian",
            gender_id="man",
            lineage_id="no_fixed_past",
            player_vitriol={},
        )
        size   = 384
        frames = render_chargen_sequence(ko_profile, state, size=size)
        for i, f in enumerate(frames):
            w, h = _png_dims(f)
            assert w == size and h == size, (
                f"Frame {i} has wrong size {w}x{h}, expected {size}x{size}"
            )

    def test_frames_are_all_distinct(self, ko_profile):
        state = ChargenState(
            name="Meridian",
            gender_id="woman",
            lineage_id="scholars_house",
            player_vitriol={},
        )
        frames = render_chargen_sequence(ko_profile, state)
        assert len(set(frames)) == 4, "Some frames are identical"