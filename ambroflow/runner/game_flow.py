"""
GameFlow -- In-Game Entry Sequence
==================================
Manages the full pipeline from press-enter-on-a-game through to waking play.

Phases (in order for game 7):
  NAME_ENTRY   Player types their character name
  LINEAGE      Select one of 5 lineage options (arrow keys + enter)
  KO_GENDER    Ko asks about the shape you move through the world with (arrow + enter)
  DREAM        Ko dream calibration -- 9 resonance prompts, then rendered frames
  VITRIOL      Player assigns their own VITRIOL profile against Ko's read
  WAKING       "The work begins." -- brief breath before the world opens
  FATE_KNOCKS  Interactive 0001_KLST opening: bedroom, knock, foyer, courier, letter
  DONE         Hand control back to the app

GameFlow is a pure state container.  It renders PIL frames on demand and
translates key events into state changes.  The pygame app drives it.
"""

from __future__ import annotations

import threading
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
    NAME_ENTRY  = "name_entry"
    LINEAGE     = "lineage"
    KO_GENDER   = "ko_gender"
    DREAM       = "dream"
    VITRIOL     = "vitriol"
    WAKING      = "waking"
    FATE_KNOCKS = "fate_knocks"
    DONE        = "done"


_PHASE_ORDER = [
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
        self.phase      = FlowPhase.NAME_ENTRY
        self.chargen    = ChargenState()

        # Sequence playback (DREAM phase)
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

        # Dream calibration — interactive prompt collection
        self._cal_session: Optional[DreamCalibrationSession] = None
        self._ko_profile:  Optional[VITRIOLProfile] = None
        self._dream_prompts: list[tuple[str, str]] = []  # (phase_label, text)
        self._dream_q_idx: int = 0
        self._dream_resonance: float = 0.5
        self._dream_responses: list[float] = []
        self._dream_collecting: bool = False
        self._dream_rendering:  bool = False  # True while background render runs

        # VITRIOL assignment (player's own allocation)
        self._vitriol_stat_idx = 0
        self._player_vitriol: dict[str, int] = {}

        # Fate Knocks interactive sequence
        self._fate_knocks: Optional[FateKnocksPlay] = None

    # -- Phase transitions ----------------------------------------------------

    def _next_phase(self) -> None:
        idx = _PHASE_ORDER.index(self.phase)
        if idx + 1 < len(_PHASE_ORDER):
            self.phase = _PHASE_ORDER[idx + 1]
            self._on_enter_phase()

    def _on_enter_phase(self) -> None:
        if self.phase == FlowPhase.DREAM:
            self._init_dream()
        elif self.phase == FlowPhase.VITRIOL:
            self._init_vitriol()
        elif self.phase == FlowPhase.FATE_KNOCKS:
            self._fate_knocks = FateKnocksPlay(
                player_name=self.chargen.name or "Apprentice",
                width=self.width,
                height=self.height,
            )

    # -- Dream sequence -------------------------------------------------------

    def _init_dream(self) -> None:
        """Start interactive dream calibration — collect one resonance per prompt."""
        gp = DreamCalibrationSession.GAME_PROMPTS.get(self.game_slug, {})
        dp = DreamCalibrationSession.PROMPTS
        self._dream_prompts = []
        for tongue, label in [
            ("sakura", "Sakura"),
            ("rose",   "Rose"),
            ("lotus",  "Lotus"),
        ]:
            from ..ko.calibration import CalibrationTongue
            key = CalibrationTongue(tongue)
            prompts = (gp.get(key) or dp.get(key) or [])
            for p in prompts:
                self._dream_prompts.append((label, p))
        self._dream_q_idx      = 0
        self._dream_resonance  = 0.5
        self._dream_responses  = []
        self._dream_collecting = True
        self._frames           = []
        self._frame_idx        = 0

    def _run_dream_calibration(self) -> None:
        """
        Kick off background rendering after all 9 responses are collected.
        Sets _dream_rendering True while the thread works; clears it when done.
        The main loop shows a loading screen until _dream_rendering is False.
        """
        responses = list(self._dream_responses)
        prompts   = list(self._dream_prompts)
        game_slug = self.game_slug
        size      = min(self.width, self.height)
        self._dream_rendering = True

        def _work() -> None:
            cal = DreamCalibrationSession(
                game_id=game_slug,
                active_perks=frozenset(),
            )
            for r in responses:
                cal.respond(r)
            while not cal.is_complete():
                cal.respond(0.5)

            calibration = cal.complete()
            ko_profile  = assign_vitriol(calibration)

            opening_lines = GAME_OPENING_LINES.get(game_slug, [
                "You are here.",
                "The ground has not assembled yet.",
                "The reading begins from what is already true.",
            ])
            closing_lines = GAME_CLOSING_LINES.get(game_slug, [
                "What you do with this reading is not my concern.",
                "Wake.",
            ])
            assignment_lines = {
                stat: get_assignment_line(game_slug, stat,
                                          getattr(ko_profile, stat))
                for stat in VITRIOL_STATS
            }
            prompts_display = {
                "sakura": [p for lbl, p in prompts if lbl == "Sakura"],
                "rose":   [p for lbl, p in prompts if lbl == "Rose"],
                "lotus":  [p for lbl, p in prompts if lbl == "Lotus"],
            }
            frames = render_dream_sequence(
                game_id=game_slug,
                calibration_prompts=prompts_display,
                assignment_lines=assignment_lines,
                vitriol_profile=ko_profile,
                opening_lines=opening_lines,
                closing_lines=closing_lines,
                size=size,
            )
            # Write results atomically before clearing the flag
            self._ko_profile       = ko_profile
            self._frames           = [f for f in frames if f]
            self._frame_idx        = 0
            self._dream_collecting = False
            self._dream_rendering  = False

        threading.Thread(target=_work, daemon=True).start()

    # -- Dream prompt renderer ------------------------------------------------

    # What each phase reads — shown as a subtitle under the phase label.
    _PHASE_SUBTITLES = {
        "Sakura": "Ko reads your orientation — which direction you are already facing.",
        "Rose":   "Ko reads how things land in you before you have words for them.",
        "Lotus":  "Ko reads the material character of the ground you are standing in.",
    }
    _SLIDER_LEFT  = "not at all"
    _SLIDER_RIGHT = "completely"
    _INSTRUCTION  = "How much does this land in you right now?"

    def _render_dream_prompt(self) -> Optional[bytes]:
        """
        Render a single dream calibration prompt with a resonance slider.

        Layout (top to bottom):
          header band   — "Ko is reading you." + phase name + phase subtitle
          prompt text   — the philosophical prompt, large, centered
          instruction   — "How much does this land in you right now?"
          slider        — labeled 'not at all' ... 'completely'
          hints         — key instructions
          progress      — dim, bottom-right corner
        """
        if not _PIL:
            return None
        W, H = self.width, self.height
        img  = Image.new("RGB", (W, H), P.VOID)
        draw = ImageDraw.Draw(img)
        draw_starfield(img, seed=0xCA01, density=0.0005)

        if self._dream_q_idx >= len(self._dream_prompts):
            return to_png(img)

        phase_label, prompt_text = self._dream_prompts[self._dream_q_idx]

        _PHASE_COLORS = {
            "Sakura": (200, 145, 180),
            "Rose":   (180,  80, 100),
            "Lotus":  ( 60, 110, 160),
        }
        phase_col = _PHASE_COLORS.get(phase_label, P.KO_GOLD)

        font_ko     = _load_font(11)
        font_phase  = _load_font(13)
        font_sub    = _load_font(11)
        font_prompt = _load_font(15)
        font_instr  = _load_font(12)
        font_hint   = _load_font(11)
        font_tiny   = _load_font(10)

        # Header band
        ko_line = "Ko is reading you."
        kw, _ = text_size(draw, ko_line, font_ko)
        draw.text(((W - kw) // 2, int(H * 0.06)), ko_line,
                  fill=P.TEXT_DIM, font=font_ko)

        pl_w, pl_h = text_size(draw, phase_label, font_phase)
        phase_y = int(H * 0.11)
        draw.text(((W - pl_w) // 2, phase_y), phase_label, fill=phase_col, font=font_phase)

        subtitle = self._PHASE_SUBTITLES.get(phase_label, "")
        sw, sh = text_size(draw, subtitle, font_sub)
        sub_y = phase_y + pl_h + int(H * 0.008)
        if sw < W * 0.90:
            draw.text(((W - sw) // 2, sub_y), subtitle, fill=P.TEXT_DIM, font=font_sub)
        else:
            # wrap subtitle if it overflows
            sub_cw = max(1, sw // max(1, len(subtitle)))
            sub_max = max(12, int(W * 0.82) // sub_cw)
            sub_lines: list[str] = []
            cur = ""
            for word in subtitle.split():
                cand = (cur + " " + word).strip()
                if cur and len(cand) > sub_max:
                    sub_lines.append(cur)
                    cur = word
                else:
                    cur = cand
            if cur:
                sub_lines.append(cur)
            for sl in sub_lines:
                slw, slh = text_size(draw, sl, font_sub)
                draw.text(((W - slw) // 2, sub_y), sl, fill=P.TEXT_DIM, font=font_sub)
                sub_y += slh + 2

        # Prompt text
        try:
            bbox = draw.textbbox((0, 0), "M", font=font_prompt)
            ch_w = max(1, bbox[2] - bbox[0])
            ch_h = max(1, bbox[3] - bbox[1]) + 6
        except AttributeError:
            ch_w, ch_h = 8, 21
        max_chars = max(12, int(W * 0.72) // ch_w)

        words = prompt_text.split()
        lines: list[str] = []
        cur = ""
        for word in words:
            cand = (cur + " " + word).strip()
            if cur and len(cand) > max_chars:
                lines.append(cur)
                cur = word
            else:
                cur = cand
        if cur:
            lines.append(cur)

        ty = int(H * 0.30)
        for line in lines:
            try:
                b  = draw.textbbox((0, 0), line, font=font_prompt)
                lw = b[2] - b[0]
            except AttributeError:
                lw = len(line) * ch_w
            draw.text(((W - lw) // 2, ty), line, fill=P.TEXT_PRIMARY, font=font_prompt)
            ty += ch_h

        # Instruction line
        instr_y = ty + int(H * 0.04)
        iw, _ = text_size(draw, self._INSTRUCTION, font_instr)
        draw.text(((W - iw) // 2, instr_y), self._INSTRUCTION,
                  fill=(140, 130, 115), font=font_instr)

        # Resonance slider
        slider_y  = int(H * 0.70)
        slider_x0 = int(W * 0.18)
        slider_x1 = W - int(W * 0.18)
        slider_w  = slider_x1 - slider_x0

        draw.line([(slider_x0, slider_y), (slider_x1, slider_y)],
                  fill=P.TEXT_DIM, width=1)
        for n in range(11):
            nx = slider_x0 + int(slider_w * n / 10)
            draw.line([(nx, slider_y - 3), (nx, slider_y + 3)], fill=P.TEXT_DIM, width=1)

        fill_x = slider_x0 + int(slider_w * self._dream_resonance)
        if fill_x > slider_x0:
            draw.line([(slider_x0, slider_y), (fill_x, slider_y)], fill=phase_col, width=2)

        draw.ellipse([fill_x - 6, slider_y - 6, fill_x + 6, slider_y + 6],
                     fill=phase_col, outline=P.TEXT_DIM)

        # End labels
        lbl_y = slider_y + 12
        draw.text((slider_x0, lbl_y), self._SLIDER_LEFT,
                  fill=P.TEXT_DIM, font=font_tiny)
        rw, _ = text_size(draw, self._SLIDER_RIGHT, font_tiny)
        draw.text((slider_x1 - rw, lbl_y), self._SLIDER_RIGHT,
                  fill=P.TEXT_DIM, font=font_tiny)

        # Hints
        hint_y = int(H * 0.87)
        for hint in ["[left / right]  adjust", "[space]  confirm"]:
            hw, _ = text_size(draw, hint, font_hint)
            draw.text(((W - hw) // 2, hint_y), hint, fill=P.TEXT_DIM, font=font_hint)
            hint_y += 15

        # Progress — dim, bottom-right
        total    = len(self._dream_prompts)
        progress = f"{self._dream_q_idx + 1} / {total}"
        pgw, _  = text_size(draw, progress, font_tiny)
        draw.text((W - pgw - int(W * 0.03), H - int(H * 0.04)),
                  progress, fill=P.TEXT_DIM, font=font_tiny)

        return to_png(img)

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
            if self._dream_collecting:
                return self._render_dream_prompt()
            if self._dream_rendering:
                return _render_waking_screen(self.width, self.height)
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
        K_UP        = 1073741906
        K_DOWN      = 1073741905
        K_LEFT      = 1073741904
        K_RIGHT     = 1073741903
        K_BACKSPACE = 8

        if self.phase == FlowPhase.NAME_ENTRY:
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
            if self._dream_rendering:
                return  # wait for background render to finish
            if self._dream_collecting:
                if key == K_LEFT:
                    self._dream_resonance = round(
                        max(0.0, self._dream_resonance - 0.1), 1)
                elif key == K_RIGHT:
                    self._dream_resonance = round(
                        min(1.0, self._dream_resonance + 0.1), 1)
                elif key in (K_RETURN, K_SPACE):
                    self._dream_responses.append(self._dream_resonance)
                    self._dream_q_idx    += 1
                    self._dream_resonance = 0.5
                    if self._dream_q_idx >= len(self._dream_prompts):
                        self._run_dream_calibration()
                elif key == K_ESCAPE:
                    self.phase = FlowPhase.DONE
            else:
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