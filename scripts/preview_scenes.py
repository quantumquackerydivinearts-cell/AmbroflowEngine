"""
preview_scenes.py
=================
Render all visual screens to PNG files for inspection.

Usage
-----
  python scripts/preview_scenes.py                   # render everything
  python scripts/preview_scenes.py --room bedroom    # one room, all tod variants
  python scripts/preview_scenes.py --tod dawn        # all rooms at dawn
  python scripts/preview_scenes.py --group opening   # Fate Knocks sequence only
  python scripts/preview_scenes.py --group chargen   # character creation screens only
  python scripts/preview_scenes.py --group dream     # Ko dream sequence only

Output is written to a temp directory; the path is printed for each file.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import tempfile
from pathlib import Path
from typing import Optional

# -- ensure repo root on path --
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# -- helpers --

def _save(data: bytes, dest_dir: Path, name: str) -> Path:
    p = dest_dir / f"{name}.png"
    p.write_bytes(data)
    return p


def _png_dims(data: bytes) -> tuple[int, int]:
    """Parse width x height from PNG IHDR (bytes 16--23)."""
    w = struct.unpack(">I", data[16:20])[0]
    h = struct.unpack(">I", data[20:24])[0]
    return w, h


def _report(path: Path, data: bytes) -> None:
    w, h = _png_dims(data)
    kb = len(data) / 1024
    print(f"  {path.name:50s}  {w}x{h}  {kb:.1f} kB  - {path}")


# -- room previews --

_ROOM_FUNCS: dict[str, dict] = {
    "bedroom":    {"dawn": {"rumpled": True},  "late_afternoon": {"rumpled": False}},
    "foyer":      {"dawn": {},                  "late_afternoon": {}},
    "workbench":  {"dawn": {},                  "late_afternoon": {}},
    "kitchen":    {"dawn": {},                  "late_afternoon": {}},
    "meditation": {"dawn": {},                  "late_afternoon": {}},
    "study":      {"dawn": {},                  "late_afternoon": {}},
}

_TOD_ALL = ("dawn", "late_afternoon")


def preview_rooms(
    dest_dir: Path,
    room_filter: Optional[str] = None,
    tod_filter: Optional[str] = None,
) -> None:
    from ambroflow.scenes.location import (
        render_bedroom, render_foyer, render_workbench_area,
        render_kitchen, render_meditation_room, render_study,
    )
    _renderers = {
        "bedroom":    render_bedroom,
        "foyer":      render_foyer,
        "workbench":  render_workbench_area,
        "kitchen":    render_kitchen,
        "meditation": render_meditation_room,
        "study":      render_study,
    }

    rooms = [room_filter] if room_filter else list(_ROOM_FUNCS)
    tods  = [tod_filter]  if tod_filter  else list(_TOD_ALL)

    print("\n-- Home Rooms ----------------------------------------------------------")
    for room in rooms:
        fn    = _renderers[room]
        extra = _ROOM_FUNCS.get(room, {})
        for tod in tods:
            kw = extra.get(tod, {})
            data = fn(time_of_day=tod, **kw)
            if data:
                name = f"room_{room}_{tod.replace('_','')}"
                p    = _save(data, dest_dir, name)
                _report(p, data)


# -- opening / Fate Knocks --

def preview_opening(dest_dir: Path) -> None:
    from ambroflow.scenes.opening import render_fate_knocks_sequence

    print("\n-- Fate Knocks (Quest 0001_KLST) --")
    frames = render_fate_knocks_sequence()
    labels = ["00_bedroom_dawn", "01_knock_stage_dir", "02_foyer_dawn",
              "03_courier_dialogue", "04_hypatia_letter"]
    for i, (data, label) in enumerate(zip(frames, labels)):
        name = f"opening_{label}"
        p    = _save(data, dest_dir, name)
        _report(p, data)


# -- character creation --

def preview_chargen(dest_dir: Path) -> None:
    from ambroflow.chargen.screens import render_chargen_sequence
    from ambroflow.chargen.data import LINEAGE_OPTIONS, GENDER_OPTIONS, ChargenState
    from ambroflow.ko.vitriol import VITRIOLProfile

    ko_profile = VITRIOLProfile(
        vitality=6, introspection=7, tactility=5,
        reflectivity=6, ingenuity=4, ostentation=5, levity=8,
    )
    state = ChargenState(
        name="Meridian",
        gender_id="woman",
        lineage_id="scholars_house",
        player_vitriol={},
    )

    print("\n-- Character Creation --")
    frames = render_chargen_sequence(ko_profile, state)
    labels = ["00_ko_gender_question", "01_name_screen",
              "02_lineage_screen", "03_vitriol_sheet"]
    for data, label in zip(frames, labels):
        name = f"chargen_{label}"
        p    = _save(data, dest_dir, name)
        _report(p, data)

    # Extra: gender screen with selection cycling
    from ambroflow.chargen.screens import render_ko_gender_question
    for idx in range(min(3, len(GENDER_OPTIONS))):
        data = render_ko_gender_question(list(GENDER_OPTIONS), selected_idx=idx)
        if data:
            name = f"chargen_00_gender_sel{idx}"
            p    = _save(data, dest_dir, name)
            _report(p, data)

    # Extra: lineage with each option highlighted
    from ambroflow.chargen.screens import render_lineage_screen
    for idx in range(len(LINEAGE_OPTIONS)):
        data = render_lineage_screen(list(LINEAGE_OPTIONS), selected_idx=idx)
        if data:
            name = f"chargen_02_lineage_sel{idx}"
            p    = _save(data, dest_dir, name)
            _report(p, data)

    # Extra: VITRIOL sheet with each stat active
    from ambroflow.chargen.screens import render_vitriol_assignment_sheet
    from ambroflow.ko.vitriol import VITRIOL_STATS
    player_vals = {s: getattr(ko_profile, s) for s in VITRIOL_STATS}
    for stat in VITRIOL_STATS:
        spent   = sum(player_vals.values())
        budget  = 31 - spent
        data = render_vitriol_assignment_sheet(
            ko_profile, player_vals, budget, active_stat=stat
        )
        if data:
            name = f"chargen_03_vitriol_active_{stat}"
            p    = _save(data, dest_dir, name)
            _report(p, data)


# -- Ko dream sequence --

def preview_dream(dest_dir: Path) -> None:
    from ambroflow.ko.dream_scene import render_dream_sequence
    from ambroflow.ko.calibration import DreamCalibration
    from ambroflow.ko.vitriol import VITRIOLProfile, VITRIOL_STATS

    ko_profile = VITRIOLProfile(
        vitality=6, introspection=7, tactility=5,
        reflectivity=6, ingenuity=4, ostentation=5, levity=8,
    )

    # Minimal calibration prompts (9 -- one per KLGS calibration beat)
    calibration_prompts = {
        "sakura": [
            "A shape that cannot be named.",
            "The sensation of being watched from inside.",
            "A door that opens onto the same room.",
        ],
        "rose": [
            "The weight of a word before it is spoken.",
            "A color that does not exist in waking.",
            "The moment before the moment.",
        ],
        "lotus": [
            "A mirror that shows something other than a reflection.",
            "The sound a shadow makes.",
            "The edge where the known ends.",
        ],
    }

    from ambroflow.ko.calibration import get_assignment_line

    opening_lines_7 = [
        "You are here.",
        "The ground has not assembled yet. Stay in that.",
        "The reading begins from what is already true. "
        "The questions are not the reading -- you are.",
    ]
    closing_lines_7 = [
        "What you do with this reading is not my concern.",
        "The distance between what I see and what you choose to carry -- "
        "that is where you will be living.",
        "Wake.",
    ]

    assignment_lines = {
        stat: get_assignment_line("7_KLGS", stat, getattr(ko_profile, stat))
        for stat in VITRIOL_STATS
    }

    cal = DreamCalibration(
        sakura_density=0.6,
        rose_density=0.7,
        lotus_density=0.5,
        layer_densities=[0.5] * 24,
        game_id="7_KLGS",
        depth_meditated=0,
    )

    print("\n-- Ko Dream Calibration Sequence --")
    frames = render_dream_sequence(
        game_id="7_KLGS",
        calibration_prompts=calibration_prompts,
        assignment_lines=assignment_lines,
        vitriol_profile=ko_profile,
        opening_lines=opening_lines_7,
        closing_lines=closing_lines_7,
    )
    print(f"  Total frames: {len(frames)}")
    for i, data in enumerate(frames):
        name = f"dream_frame_{i:02d}"
        p    = _save(data, dest_dir, name)
        _report(p, data)


# -- runner screens (title, game select, name entry) --

def preview_runner(dest_dir: Path) -> None:
    from ambroflow.runner.screens import (
        render_title_screen, render_game_select, render_name_entry,
    )

    print("\n-- Startup / Game Selection ----------------------------------------")

    # Title screen -- two pulse states
    for pulse, label in [(0.0, "00_title_pulse0"), (0.5, "01_title_pulse50")]:
        data = render_title_screen(1280, 800, pulse=pulse)
        if data:
            p = _save(data, dest_dir, f"runner_{label}")
            _report(p, data)

    # Name entry -- with and without cursor
    for cvis, label in [(True, "02_name_cursor"), (False, "03_name_nocursor")]:
        data = render_name_entry("Meridian", cursor_visible=cvis, width=1280, height=800)
        if data:
            p = _save(data, dest_dir, f"runner_{label}")
            _report(p, data)

    # Game select -- various selections
    statuses = {
        "7_KLGS":  "in_progress",
        "1_KLGS":  "complete",
        "5_KLGS":  "complete",
    }
    for idx, label in [
        (0,  "04_select_game1"),
        (6,  "05_select_game7"),
        (16, "06_select_game17"),
        (30, "07_select_game31"),
    ]:
        data = render_game_select(
            statuses, selected_idx=idx, player_name="Meridian",
            width=1280, height=800,
        )
        if data:
            p = _save(data, dest_dir, f"runner_{label}")
            _report(p, data)


# -- entry point --

def main() -> None:
    parser = argparse.ArgumentParser(description="Preview Ambroflow rendered screens.")
    parser.add_argument("--room",  default=None,
                        choices=list(_ROOM_FUNCS), help="Render a single room")
    parser.add_argument("--tod",   default=None,
                        choices=list(_TOD_ALL), help="Restrict to one time-of-day")
    parser.add_argument("--group", default=None,
                        choices=["rooms", "opening", "chargen", "dream", "runner"],
                        help="Render one group only")
    parser.add_argument("--out",   default=None,
                        help="Output directory (default: system temp)")
    args = parser.parse_args()

    dest_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="ambroflow_preview_"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {dest_dir}\n")

    grp = args.group

    if grp in (None, "rooms"):
        preview_rooms(dest_dir, room_filter=args.room, tod_filter=args.tod)

    if grp in (None, "opening") and not args.room:
        preview_opening(dest_dir)

    if grp in (None, "chargen") and not args.room:
        preview_chargen(dest_dir)

    if grp in (None, "dream") and not args.room:
        preview_dream(dest_dir)

    if grp in (None, "runner") and not args.room:
        preview_runner(dest_dir)

    print(f"\nDone. {len(list(dest_dir.glob('*.png')))} PNGs in {dest_dir}")


if __name__ == "__main__":
    main()