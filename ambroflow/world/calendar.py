"""
Aeralune Calendar
=================
The Shygazun calendar for Aeralune (Kepler-452b), used across the KLGS series.

Structure
---------
  12 months × 32 days = 384 days
  + 1 intercalary festival day (Vrwumane) = 385 days

  Month names are Rose numeral roots + the WuMaNe suffix:
    Wu (byte 45) = Process / Way
    Ma (byte 86) = Web / Interchange
    Ne (byte 88) = Network / System
    WuMaNe = "the way of web-interchange through network" — the fabric of
    counted time.  Each month name is [numeral] + wumane = that numeral's
    weave of the fabric.

  Vrwumane:
    Vr (byte 94) = Rotor / Tensor
    = "The rotor of the fabric of counted time" — the pivot mechanism that
    turns one year into the next.  Falls as day 385.  Also the Winter
    Solstice.  Castle Azoth ceremonial fountain runs.

Astronomical anchors (equal 96-day quarters from Vrwumane):
  Day 385/0  — Vrwumane          — Winter Solstice   (Castle Azoth fountain)
  Day  97    — Uiwumane day 1    — Spring Equinox     (Castle Azoth fountain)
  Day 193    — Yeshuwumane day 1 — Summer Solstice    (Castle Azoth fountain)
  Day 289    — Uinshuwumane day 1— Autumn Equinox     (Castle Azoth fountain)
"""

from __future__ import annotations

import math as _math
from dataclasses import dataclass as _dc
from enum import Enum


# ── Month names (Rose numeral roots + wumane suffix) ──────────────────────────

MONTHS: tuple[str, ...] = (
    "Gaohwumane",      # month  1  — Rose 0/12 (Möbius origin, both endpoints)
    "Aowumane",        # month  2  — Rose 1
    "Yewumane",        # month  3  — Rose 2
    "Uiwumane",        # month  4  — Rose 3  ← Spring Equinox day 97
    "Shuwumane",       # month  5  — Rose 4
    "Kielwumane",      # month  6  — Rose 5
    "Yeshuwumane",     # month  7  — Rose 6 (Ye+Shu fold midpoint)  ← Summer Solstice day 193
    "Laowumane",       # month  8  — Rose 7
    "Shushywumane",    # month  9  — Rose 8 (Shu+Shy grid artifact)
    "Uinshuwumane",    # month 10  — Rose 9 (Ui+Shu grid artifact)  ← Autumn Equinox day 289
    "Kokielwumane",    # month 11  — Rose 10 (Ko+Kiel grid artifact)
    "Aonkielwumane",   # month 12  — Rose 11 (Ao+Kiel grid artifact)
)

VRWUMANE: str = "Vrwumane"

DAYS_PER_MONTH:  int = 32
MONTHS_PER_YEAR: int = 12
DAYS_PER_YEAR:   int = 385  # 12 × 32 + 1

# Day-of-year for each astronomical anchor
SPRING_EQUINOX:  int = 97   # Uiwumane day 1    (months 1–3 = 96 days)
SUMMER_SOLSTICE: int = 193  # Yeshuwumane day 1 (months 1–6 = 192 days)
AUTUMN_EQUINOX:  int = 289  # Uinshuwumane day 1(months 1–9 = 288 days)
WINTER_SOLSTICE: int = 385  # Vrwumane

ASTRONOMICAL_ANCHORS: frozenset[int] = frozenset({
    SPRING_EQUINOX,
    SUMMER_SOLSTICE,
    AUTUMN_EQUINOX,
    WINTER_SOLSTICE,
})

# Alzedroswune seasonal presence on Hieronymus Plateau: months 3–9 (days 65–288)
_ALZEDROSWUNE_FIRST: int = (3 - 1) * DAYS_PER_MONTH + 1  # 65  (month 3, day 1)
_ALZEDROSWUNE_LAST:  int = 9 * DAYS_PER_MONTH              # 288 (month 9, day 32)


# ── Time of day ───────────────────────────────────────────────────────────────

class TimeOfDay(str, Enum):
    DAWN           = "dawn"            # hours 5–6
    MORNING        = "morning"         # hours 7–11
    AFTERNOON      = "afternoon"       # hours 12–16
    LATE_AFTERNOON = "late_afternoon"  # hours 17–18
    DUSK           = "dusk"            # hours 19–20
    NIGHT          = "night"           # hours 21–4


HOURS_PER_DAY: int = 24


def _hour_to_time_of_day(hour: int) -> TimeOfDay:
    h = hour % HOURS_PER_DAY
    if h in (5, 6):
        return TimeOfDay.DAWN
    if 7 <= h <= 11:
        return TimeOfDay.MORNING
    if 12 <= h <= 16:
        return TimeOfDay.AFTERNOON
    if h in (17, 18):
        return TimeOfDay.LATE_AFTERNOON
    if h in (19, 20):
        return TimeOfDay.DUSK
    return TimeOfDay.NIGHT


# ── AeraluneDate ─────────────────────────────────────────────────────────────

class AeraluneDate:
    """
    A specific day in the Aeralune calendar.

    day_of_year is 1–385:
      1–384  = regular months (months 1–12, days 1–32 each)
      385    = Vrwumane (intercalary festival day / Winter Solstice)

    year is 1-indexed from the calendar epoch.
    """

    __slots__ = ("year", "day_of_year")

    def __init__(self, year: int, day_of_year: int) -> None:
        if not (1 <= day_of_year <= DAYS_PER_YEAR):
            raise ValueError(
                f"day_of_year must be 1–{DAYS_PER_YEAR}, got {day_of_year}"
            )
        self.year        = year
        self.day_of_year = day_of_year

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_vrwumane(self) -> bool:
        return self.day_of_year == DAYS_PER_YEAR

    @property
    def month_index(self) -> int:
        """1-based month number, or 0 for Vrwumane."""
        if self.is_vrwumane:
            return 0
        return (self.day_of_year - 1) // DAYS_PER_MONTH + 1

    @property
    def day_in_month(self) -> int:
        """Day within the month (1–32), or 1 for Vrwumane."""
        if self.is_vrwumane:
            return 1
        return (self.day_of_year - 1) % DAYS_PER_MONTH + 1

    @property
    def month_name(self) -> str:
        """Shygazun month name, or 'Vrwumane' for the intercalary day."""
        if self.is_vrwumane:
            return VRWUMANE
        return MONTHS[self.month_index - 1]

    @property
    def is_astronomical_anchor(self) -> bool:
        """True on the four days Castle Azoth's ceremonial fountain runs."""
        return self.day_of_year in ASTRONOMICAL_ANCHORS

    # ── Navigation ────────────────────────────────────────────────────────────

    def advance(self, days: int) -> "AeraluneDate":
        """Return a new date *days* later, wrapping across year boundaries."""
        if days < 0:
            raise ValueError("advance() requires a non-negative day count")
        total     = self.day_of_year - 1 + days
        new_year  = self.year + total // DAYS_PER_YEAR
        new_doy   = total % DAYS_PER_YEAR + 1
        return AeraluneDate(year=new_year, day_of_year=new_doy)

    # ── Comparison ────────────────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AeraluneDate):
            return NotImplemented
        return self.year == other.year and self.day_of_year == other.day_of_year

    def __hash__(self) -> int:
        return hash((self.year, self.day_of_year))

    def __repr__(self) -> str:
        return f"AeraluneDate(year={self.year}, day_of_year={self.day_of_year})"

    def __str__(self) -> str:
        if self.is_vrwumane:
            return f"Vrwumane, Year {self.year}"
        return f"{self.month_name} {self.day_in_month}, Year {self.year}"


# ── Calendar queries ──────────────────────────────────────────────────────────

def fountain_running(date: AeraluneDate) -> bool:
    """Castle Azoth ceremonial fountain — runs only on the four astronomical anchors."""
    return date.is_astronomical_anchor


def alzedroswune_present(date: AeraluneDate) -> bool:
    """
    Whether the Alzedroswune nomadic encampment is present on Hieronymus Plateau.

    They dislike the plateau and prefer the Elaene desert; they come for
    economic survival months 3–9, accepting Azonithian coin.  They are the
    shipwrights for quest 0016_KLST.
    """
    if date.is_vrwumane:
        return False
    return _ALZEDROSWUNE_FIRST <= date.day_of_year <= _ALZEDROSWUNE_LAST


# ── WorldClock ────────────────────────────────────────────────────────────────

class WorldClock:
    """
    Tracks in-game time as a running total of hours from the calendar epoch.

    The canonical time unit for world events is the hour.  The BreathOfKo
    nightly recap fires once per in-game day (HOURS_PER_DAY hour-ticks).
    """

    __slots__ = ("_total_hours",)

    def __init__(
        self,
        year:        int = 1,
        day_of_year: int = 1,
        hour:        int = 6,   # dawn default
    ) -> None:
        self._total_hours: int = (
            (year - 1) * DAYS_PER_YEAR * HOURS_PER_DAY
            + (day_of_year - 1) * HOURS_PER_DAY
            + hour
        )

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def total_hours(self) -> int:
        return self._total_hours

    @property
    def hour(self) -> int:
        return self._total_hours % HOURS_PER_DAY

    @property
    def time_of_day(self) -> TimeOfDay:
        return _hour_to_time_of_day(self.hour)

    @property
    def date(self) -> AeraluneDate:
        total_days  = self._total_hours // HOURS_PER_DAY
        year        = total_days // DAYS_PER_YEAR + 1
        day_of_year = total_days % DAYS_PER_YEAR + 1
        return AeraluneDate(year=year, day_of_year=day_of_year)

    # ── Mutation ──────────────────────────────────────────────────────────────

    def advance(self, hours: int = 1) -> None:
        """Advance the clock by *hours* in-game hours."""
        if hours < 0:
            raise ValueError("advance() requires a non-negative hour count")
        self._total_hours += hours

    def advance_day(self) -> None:
        """Advance by exactly one full in-game day (HOURS_PER_DAY ticks)."""
        self._total_hours += HOURS_PER_DAY

    # ── Convenience ───────────────────────────────────────────────────────────

    @property
    def fountain_running(self) -> bool:
        """Castle Azoth fountain status at the current clock date."""
        return fountain_running(self.date)

    @property
    def alzedroswune_present(self) -> bool:
        """Alzedroswune encampment presence at the current clock date."""
        return alzedroswune_present(self.date)

    def __str__(self) -> str:
        return f"{self.date}, {self.time_of_day.value} (hour {self.hour})"

    def __repr__(self) -> str:
        d = self.date
        return (
            f"WorldClock(year={d.year}, day_of_year={d.day_of_year}, "
            f"hour={self.hour})"
        )


# ── Alchemy calendar context ──────────────────────────────────────────────────

@_dc(frozen=True)
class AlchemyCalendarContext:
    """
    Temporal modifiers for an alchemy session, derived from the Aeralune calendar.

    The four Great Work seasons map to the year's field-axis hierarchy:
      Nigredo    (days   1– 96)  temporal — the old year's residue ferments in the dark
      Albedo     (days  97–192)  mental   — spring's clarity whitens the field
      Citrinitas (days 193–288)  spatial  — the golden expansion; Alzedroswune encamped
      Rubedo     (days 289–384)  temporal — the red crystallisation completes the work
      Vrwumane   (day  385)      all axes — the Rotor folds the year; the Great Work

    axis_bonus             — additive resonance bonus per field axis (includes anchor proximity)
    epiphany_threshold     — overrides 0.85; falls toward 0.60 approaching anchor days
    charge_multiplier      — multiplier on epiphanic_charge accumulation this session
    formula_approach_bonus — added to formula mode modifier (Alzedroswune navigator effect)
    locked_subject_ids     — subjects unavailable this season
    season_note            — short display string for the UI
    """
    season_name:            str
    peak_axis:              str | None
    axis_bonus:             dict[str, float]
    epiphany_threshold:     float
    charge_multiplier:      float
    formula_approach_bonus: float
    alzedroswune_present:   bool
    locked_subject_ids:     frozenset[str]
    season_note:            str


def _anchor_proximity(doy: int) -> float:
    """
    Returns 0.0–1.0: how close doy is to the nearest astronomical anchor.
    1.0 on an anchor day, fading to 0.0 at 14 days away (cosine falloff).
    """
    min_dist = min(abs(doy - a) for a in [SPRING_EQUINOX, SUMMER_SOLSTICE, AUTUMN_EQUINOX, WINTER_SOLSTICE])
    if min_dist == 0:
        return 1.0
    if min_dist <= 14:
        return _math.cos(min_dist / 14.0 * _math.pi / 2.0)
    return 0.0


def get_alchemy_calendar_context(date: AeraluneDate) -> "AlchemyCalendarContext":
    """
    Derive alchemy session modifiers from the current Aeralune date.

    Called by WorldPlay at the start of each alchemy session.
    """
    doy  = date.day_of_year
    alz  = alzedroswune_present(date)
    prox = _anchor_proximity(doy)

    # ── Season and peak axis ──────────────────────────────────────────────────
    if date.is_vrwumane:
        season_name, peak_axis = "vrwumane", None
    elif doy < SPRING_EQUINOX:
        season_name, peak_axis = "nigredo",    "temporal"
    elif doy < SUMMER_SOLSTICE:
        season_name, peak_axis = "albedo",     "mental"
    elif doy < AUTUMN_EQUINOX:
        season_name, peak_axis = "citrinitas", "spatial"
    else:
        season_name, peak_axis = "rubedo",     "temporal"

    # ── Base axis bonuses by season ───────────────────────────────────────────
    _BASE: dict[str, dict[str, float]] = {
        "nigredo":    {"temporal": +0.15, "mental": -0.05, "spatial":  0.00},
        "albedo":     {"mental":   +0.15, "temporal": -0.05, "spatial": 0.00},
        "citrinitas": {"spatial":  +0.20, "temporal":  0.00, "mental":  0.00},
        "rubedo":     {"temporal": +0.15, "spatial":  -0.05, "mental":  0.00},
        "vrwumane":   {"temporal": +0.15, "mental":   +0.15, "spatial": +0.15},
    }
    axis_bonus = dict(_BASE[season_name])

    # ── Anchor proximity amplifies the peak axis ──────────────────────────────
    anchor_bonus = prox * 0.10
    if peak_axis is not None:
        axis_bonus[peak_axis] = axis_bonus.get(peak_axis, 0.0) + anchor_bonus
    else:
        for ax in ("temporal", "mental", "spatial"):
            axis_bonus[ax] = axis_bonus.get(ax, 0.0) + anchor_bonus

    # ── Alzedroswune: spatial bonus + formula lift ────────────────────────────
    if alz:
        axis_bonus["spatial"] = axis_bonus.get("spatial", 0.0) + 0.10

    # ── Epiphany threshold ────────────────────────────────────────────────────
    if date.is_vrwumane:
        epiphany_threshold = 0.60
    else:
        # 0.85 on ordinary days; falls toward 0.70 as proximity → 1.0
        epiphany_threshold = 0.85 - prox * 0.15

    # ── Charge multiplier ─────────────────────────────────────────────────────
    if date.is_vrwumane:
        charge_multiplier = 3.0
    else:
        charge_multiplier = 1.0 + prox * 1.0   # up to 2.0 on anchor days

    # ── Formula approach bonus ────────────────────────────────────────────────
    formula_approach_bonus = 0.10 if alz else 0.0

    # ── Locked subjects ───────────────────────────────────────────────────────
    # desire_crystal_fragment and angelic_revival_salve require the Alzedroswune
    # window (days 65–288) OR Vrwumane — the one fold-day.
    locked: set[str] = set()
    if not alz and not date.is_vrwumane:
        locked.add("0036_KLIT")
        locked.add("0038_KLIT")

    # ── Season note ───────────────────────────────────────────────────────────
    _NOTES: dict[str, str] = {
        "nigredo":    "Nigredo — the old year ferments. Temporal work deepens in the dark.",
        "albedo":     "Albedo — spring's clarity whitens the field. Mental work ascends.",
        "citrinitas": "Citrinitas — the golden expansion. Spatial work reaches its zenith.",
        "rubedo":     "Rubedo — the red crystallisation. Temporal work completes itself.",
        "vrwumane":   "Vrwumane — the Rotor folds the year. All axes open. The Great Work.",
    }
    note = _NOTES[season_name]
    if alz and season_name in ("nigredo", "albedo", "citrinitas"):
        note += " The Alzedroswune are encamped."

    return AlchemyCalendarContext(
        season_name=season_name,
        peak_axis=peak_axis,
        axis_bonus=axis_bonus,
        epiphany_threshold=epiphany_threshold,
        charge_multiplier=charge_multiplier,
        formula_approach_bonus=formula_approach_bonus,
        alzedroswune_present=alz,
        locked_subject_ids=frozenset(locked),
        season_note=note,
    )