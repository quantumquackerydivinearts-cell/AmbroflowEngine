"""
GameFlow -- In-Game Entry Sequence
==================================
Manages the full pipeline from press-enter-on-a-game through to waking play.

Phases (in order for game 7):
  OPENING      Fate Knocks cinematic -- 5 PIL frames, advance with space/enter
  NAME_ENTRY   Player types their character name
  LINEAGE      Select one of 5 lineage options (arrow keys + enter)
  KO_GENDER    Ko asks about the shape you move through the world with (arrow + enter)
  DREAM        Ko dream calibration -- 22 pre-rendered PIL frames, advance with space/enter
  VITRIOL      Player assigns their own VITRIOL profile against Ko's read
  WAKING       "The work begins." -- brief breath before the world opens
  FATE_KNOCKS  Interactive 0001_KLST opening: bedroom, knock, foyer, courier, letter
  DONE         Hand control back to the app

GameFlow is a pure state container.  It renders PIL frames on demand and
translates key events into state changes.  The pygame app drives it.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from ..chargen.data import (
    LINEAGE_OPTIONS, GENDER_OPTIONS, ChargenState,
    LineageOption, GenderOption,
)
from ..chargen.screens import (
    render_name_screen, render_lineage_screen,
    render_ko_gender_question, render_vitriol_assignment_sheet,
)
from ..ko.vitriol import VITRIOLProfile, VITRIOL_STATS, assign_vitriol
from ..ko.calibration import (
    DreamCalibrationSession, DreamCalibration,
    get_assignment_line,
)

# These are class attributes on DreamCalibrationSession, not module-level
GAME_OPENING_LINES = DreamCalibrationSession.GAME_OPENING_LINES
GAME_CLOSING_LINES = DreamCalibrationSession.GAME_CLOSING_LINES

from ..ko.dream_scene import render_dream_sequence
from ..scenes.opening import render_fate_knocks_sequence
from .screens.common import _load_font, text_size, to_png, draw_starfield
from .screens import palette as P
from .fate_knocks_play import FateKnocksPlay

try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False


# -- Phases -------------------------------------------------------------------

class FlowPhase(str, Enum):
    OPENING     = "opening"
    NAME_ENTRY  = "name_entry"
    LINEAGE     = "lineage"
    KO_GENDER   = "ko_gender"
    DREAM       = "dream"
    VITRIOL     = "vitriol"
    WAKING      = "waking"
    FATE_KNOCKS = "fate_knocks"
    DONE        = "done"


_PHASE_ORDER = [
    FlowPhase.OPENING,
    FlowPhase.NAME_ENTRY,
    FlowPhase.LINEAGE,
    FlowPhase.KO_GENDER,
    FlowPhase.DREAM,
    FlowPhase.VITRIOL,
    FlowPhase.WAKING,
    FlowPhase.FATE_KNOCKS,
    FlowPhase.DONE,
]

_BUDGET   = 31
_STAT_MIN = 1
_STAT_MAX = 10


# -- Waking placeholder screen ------------------------------------------------

def _render_waking_screen(width: int = 1280, height: int = 800) -> Optional[bytes]:
    if not _PIL:
        return None
    W, H = width, height
    img  = Image.new("RGB", (W, H), P.VOID)
    draw = ImageDraw.Draw(img)
    draw_starfield(img, seed=0xD4F1, density=0.0008)

    font_main = _load_font(22)
    font_sub  = _load_font(13)
    font_hint = _load_font(11)

    line1 = "The work begins."
    w1, h1 = text_size(draw, line1, font_main)
    draw.text(((W - w1) // 2, H // 2 - 40), line1,
              fill=P.KO_GOLD, font=font_main)

    line2 = "Wiltoll Lane is waiting."
    w2, h2 = text_size(draw, line2, font_sub)
    draw.text(((W - w2) // 2, H // 2 + 10), line2,
              fill=P.TEXT_DIM, font=font_sub)

    hint = "[space]  Enter"
    hw, _ = text_size(draw, hint, font_hint)
    draw.text(((W - hw) // 2, int(H * 0.88)), hint,
              fill=P.TEXT_DIM, font=font_hint)

    return to_png(img)


# -- GameFlow -----------------------------------------------------------------

class GameFlow:
    """
    Drives the full in-game entry sequence for a single game run.

    Parameters
    ----------
    game_slug : str
        e.g. "7_KLGS"
    width, height : int
        Render dimensions (should match the window).
    """

    def __init__(
        self,
        game_slug: str,
        width:  int = 1280,
        height: int = 800,
    ) -> None:
        self.game_slug  = game_slug
        self.width      = width
        self.height     = height
        self.phase      = FlowPhase.OPENING
        self.chargen    = ChargenState()

        # Sequence playback (OPENING and DREAM phases)
        self._frames:    list[bytes] = []
        self._frame_idx: int = 0

        # Name entry
        self._name_buf   = ""
        self._cursor_vis = True

        # Lineage selection
        self._lineage_opts = list(LINEAGE_OPTIONS)
        self._lineage_idx  = 0

        # Gender selection
        self._gender_opts = list(GENDER_OPTIONS)
        self._gender_idx  = 0

        # Dream calibration
        self._cal_session: Optional[DreamCalibrationSession] = None
        self._ko_profile:  Optional[VITRIOLProfile] = None

        # VITRIOL assignment (player's own allocation)
        self._vitriol_stat_idx = 0
        self._player_vitriol: dict[str, int] = {}

        # Fate Knocks interactive sequence
        self._fate_knocks: Optional[FateKnocksPlay] = None

        # Pre-render opening frames immediately
        self._load_opening()

    # -- Phase transitions ----------------------------------------------------

    def _next_phase(self) -> None:
        idx = _PHASE_ORDER.index(self.phase)
        if idx + 1 < len(_PHASE_ORDER):
            self.phase = _PHASE_ORDER[idx + 1]
            self._on_enter_phase()

    def _on_enter_phase(self) -> None:
        if self.phase == FlowPhase.DREAM:
            self._load_dream()
        elif self.phase == FlowPhase.VITRIOL:
            self._init_vitriol()
        elif self.phase == FlowPhase.FATE_KNOCKS:
            self._fate_knocks = FateKnocksPlay(
                player_name=self.chargen.name or "Apprentice",
                width=self.width,
                height=self.height,
            )

    # -- Opening sequence -----------------------------------------------------

    def _load_opening(self) -> None:
        frames = render_fate_knocks_sequence(
            scene_width=self.width,
            scene_height=int(self.height * 0.75),
            screen_size=min(self.width, self.height),
        )
        self._frames    = [f for f in frames if f]
        self._frame_idx = 0

    # -- Dream sequence -------------------------------------------------------

    def _load_dream(self) -> None:
        self._cal_session = DreamCalibrationSession(
            game_id=self.game_slug,
            has_depth_meditation=False,
        )
        while not self._cal_session.is_complete():
            self._cal_session.respond(0.5)

        calibration      = self._cal_session.complete()
        self._ko_profile = assign_vitriol(calibration)

        opening_lines = GAME_OPENING_LINES.get(self.game_slug, [
            "You are here.",
            "The ground has not assembled yet.",
            "The reading begins from what is already true.",
        ])
        closing_lines = GAME_CLOSING_LINES.get(self.game_slug, [
            "What you do with this reading is not my concern.",
            "Wake.",
        ])
        assignment_lines = {
            stat: get_assignment_line(self.game_slug, stat,
                                      getattr(self._ko_profile, stat))
            for stat in VITRIOL_STATS
        }
        prompts = {
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
        frames = render_dream_sequence(
            game_id=self.game_slug,
            calibration_prompts=prompts,
            assignment_lines=assignment_lines,
            vitriol_profile=self._ko_profile,
            opening_lines=opening_lines,
            closing_lines=closing_lines,
            size=min(self.width, self.height),
        )
        self._frames    = [f for f in frames if f]
        self._frame_idx = 0

    # -- VITRIOL init ---------------------------------------------------------

    def _init_vitriol(self) -> None:
        if self._ko_profile is None:
            self._ko_profile = VITRIOLProfile(
                vitality=5, introspection=5, tactility=5,
                reflectivity=5, ingenuity=4, ostentation=4, levity=3,
            )
        self._player_vitriol = {s: getattr(self._ko_profile, s) for s in VITRIOL_STATS}
        # Clamp to exactly 31 points
        while sum(self._player_vitriol.values()) > _BUDGET:
            for s in reversed(VITRIOL_STATS):
                if sum(self._player_vitriol.values()) <= _BUDGET:
                    break
                if self._player_vitriol[s] > _STAT_MIN:
                    self._player_vitriol[s] -= 1
        while sum(self._player_vitriol.values()) < _BUDGET:
            for s in VITRIOL_STATS:
                if sum(self._player_vitriol.values()) >= _BUDGET:
                    break
                if self._player_vitriol[s] < _STAT_MAX:
                    self._player_vitriol[s] += 1
        self._vitriol_stat_idx = 0

    @property
    def _vitriol_budget_remaining(self) -> int:
        return _BUDGET - sum(self._player_vitriol.values())

    @property
    def _active_stat(self) -> str:
        return VITRIOL_STATS[self._vitriol_stat_idx]

    # -- Current frame --------------------------------------------------------

    def current_frame(self) -> Optional[bytes]:
        W, H = self.width, self.height

        if self.phase == FlowPhase.OPENING:
            if self._frames and self._frame_idx < len(self._frames):
                return self._frames[self._frame_idx]
            return None

        if self.phase == FlowPhase.NAME_ENTRY:
            return render_name_screen(self._name_buf, size=min(W, H))

        if self.phase == FlowPhase.LINEAGE:
            return render_lineage_screen(
                self._lineage_opts,
                selected_idx=self._lineage_idx,
                size=min(W, H),
            )

        if self.phase == FlowPhase.KO_GENDER:
            return render_ko_gender_question(
                self._gender_opts,
                selected_idx=self._gender_idx,
                size=min(W, H),
            )

        if self.phase == FlowPhase.DREAM:
            if self._frames and self._frame_idx < len(self._frames):
                return self._frames[self._frame_idx]
            return None

        if self.phase == FlowPhase.VITRIOL:
            return render_vitriol_assignment_sheet(
                self._ko_profile,
                self._player_vitriol,
                self._vitriol_budget_remaining,
                active_stat=self._active_stat,
                size=min(W, H),
            )

        if self.phase == FlowPhase.WAKING:
            return _render_waking_screen(W, H)

        if self.phase == FlowPhase.FATE_KNOCKS:
            if self._fate_knocks is not None:
                frame = self._fate_knocks.current_frame()
                if frame is not None:
                    return frame
            return None

        return None

    def is_done(self) -> bool:
        return self.phase == FlowPhase.DONE

    # -- Key event handling ---------------------------------------------------

    def on_key(self, key: int, unicode: str = "") -> None:
        """
        Feed a pygame key constant.  Returns nothing; check phase / is_done().
        Key constants passed as raw ints to avoid importing pygame here.
        """
        K_RETURN    = 13
        K_SPACE     = 32
        K_ESCAPE    = 27
        K_UP        = 273
        K_DOWN      = 274
        K_LEFT      = 276
        K_RIGHT     = 275
        K_BACKSPACE = 8

        if self.phase == FlowPhase.OPENING:
            if key in (K_RETURN, K_SPACE):
                if self._frame_idx < len(self._frames) - 1:
                    self._frame_idx += 1
                else:
                    self._next_phase()
            elif key == K_ESCAPE:
                self.phase = FlowPhase.DONE

        elif self.phase == FlowPhase.NAME_ENTRY:
            if key == K_RETURN:
                name = self._name_buf.strip()
                if name:
                    self.chargen.name = name
                    self._next_phase()
            elif key == K_BACKSPACE:
                self._name_buf = self._name_buf[:-1]
            elif key == K_ESCAPE:
                self.phase = FlowPhase.DONE
            elif unicode and len(self._name_buf) < 24:
                self._name_buf += unicode

        elif self.phase == FlowPhase.LINEAGE:
            if key == K_DOWN:
                self._lineage_idx = (self._lineage_idx + 1) % len(self._lineage_opts)
            elif key == K_UP:
                self._lineage_idx = (self._lineage_idx - 1) % len(self._lineage_opts)
            elif key == K_RETURN:
                self.chargen.lineage_id = self._lineage_opts[self._lineage_idx].id
                self._next_phase()
            elif key == K_ESCAPE:
                self.phase = FlowPhase.DONE

        elif self.phase == FlowPhase.KO_GENDER:
            if key == K_DOWN:
                self._gender_idx = (self._gender_idx + 1) % len(self._gender_opts)
            elif key == K_UP:
                self._gender_idx = (self._gender_idx - 1) % len(self._gender_opts)
            elif key == K_RETURN:
                self.chargen.gender_id = self._gender_opts[self._gender_idx].id
                self._next_phase()
            elif key == K_ESCAPE:
                self.phase = FlowPhase.DONE

        elif self.phase == FlowPhase.DREAM:
            if key in (K_RETURN, K_SPACE):
                if self._frame_idx < len(self._frames) - 1:
                    self._frame_idx += 1
                else:
                    self._next_phase()
            elif key == K_ESCAPE:
                self.phase = FlowPhase.DONE

        elif self.phase == FlowPhase.VITRIOL:
            if key == K_DOWN:
                self._vitriol_stat_idx = (
                    (self._vitriol_stat_idx + 1) % len(VITRIOL_STATS)
                )
            elif key == K_UP:
                self._vitriol_stat_idx = (
                    (self._vitriol_stat_idx - 1) % len(VITRIOL_STATS)
                )
            elif key == K_RIGHT:
                stat = self._active_stat
                cur  = self._player_vitriol.get(stat, 1)
                if cur < _STAT_MAX and self._vitriol_budget_remaining > 0:
                    self._player_vitriol[stat] = cur + 1
            elif key == K_LEFT:
                stat = self._active_stat
                cur  = self._player_vitriol.get(stat, 1)
                if cur > _STAT_MIN:
                    self._player_vitriol[stat] = cur - 1
            elif key == K_RETURN:
                if self._vitriol_budget_remaining == 0:
                    self.chargen.player_vitriol = dict(self._player_vitriol)
                    self._next_phase()
            elif key == K_ESCAPE:
                self.phase = FlowPhase.DONE

        elif self.phase == FlowPhase.WAKING:
            if key == K_ESCAPE:
                self.phase = FlowPhase.DONE
            elif key in (K_RETURN, K_SPACE):
                self._next_phase()   # advance to FATE_KNOCKS

        elif self.phase == FlowPhase.FATE_KNOCKS:
            if self._fate_knocks is not None:
                self._fate_knocks.on_key(key, unicode)
                if self._fate_knocks.is_done():
                    self._fate_knocks = None
                    self._next_phase()   # advance to DONE