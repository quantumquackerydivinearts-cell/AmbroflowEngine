"""Tests for the Aeralune calendar system."""

import pytest

from ambroflow.world.calendar import (
    AeraluneDate,
    WorldClock,
    TimeOfDay,
    MONTHS,
    VRWUMANE,
    DAYS_PER_MONTH,
    DAYS_PER_YEAR,
    ASTRONOMICAL_ANCHORS,
    SPRING_EQUINOX,
    SUMMER_SOLSTICE,
    AUTUMN_EQUINOX,
    WINTER_SOLSTICE,
    fountain_running,
    alzedroswune_present,
    _hour_to_time_of_day,
)


# ── Constants ─────────────────────────────────────────────────────────────────

def test_year_structure():
    assert DAYS_PER_MONTH == 32
    assert len(MONTHS) == 12
    assert DAYS_PER_YEAR == 385       # 12 × 32 + 1
    assert DAYS_PER_YEAR == 12 * DAYS_PER_MONTH + 1

def test_month_names():
    assert MONTHS[0]  == "Gaohwumane"
    assert MONTHS[1]  == "Aowumane"
    assert MONTHS[2]  == "Yewumane"
    assert MONTHS[3]  == "Uiwumane"   # Spring Equinox
    assert MONTHS[4]  == "Shuwumane"
    assert MONTHS[5]  == "Kielwumane"
    assert MONTHS[6]  == "Yeshuwumane"  # Summer Solstice / fold midpoint
    assert MONTHS[7]  == "Laowumane"
    assert MONTHS[8]  == "Shushywumane"
    assert MONTHS[9]  == "Uinshuwumane"  # Autumn Equinox
    assert MONTHS[10] == "Kokielwumane"
    assert MONTHS[11] == "Aonkielwumane"

def test_vrwumane_constant():
    assert VRWUMANE == "Vrwumane"

def test_astronomical_anchor_values():
    assert SPRING_EQUINOX  == 97
    assert SUMMER_SOLSTICE == 193
    assert AUTUMN_EQUINOX  == 289
    assert WINTER_SOLSTICE == 385
    assert ASTRONOMICAL_ANCHORS == {97, 193, 289, 385}

def test_spring_equinox_is_uiwumane_day_1():
    """Uiwumane (month 4) starts at day 97: 3 months × 32 days + 1."""
    assert SPRING_EQUINOX == 3 * DAYS_PER_MONTH + 1

def test_summer_solstice_is_yeshuwumane_day_1():
    """Yeshuwumane (month 7) starts at day 193: 6 months × 32 days + 1."""
    assert SUMMER_SOLSTICE == 6 * DAYS_PER_MONTH + 1

def test_autumn_equinox_is_uinshuwumane_day_1():
    """Uinshuwumane (month 10) starts at day 289: 9 months × 32 days + 1."""
    assert AUTUMN_EQUINOX == 9 * DAYS_PER_MONTH + 1


# ── AeraluneDate ──────────────────────────────────────────────────────────────

def test_regular_date_properties():
    d = AeraluneDate(year=1, day_of_year=1)
    assert d.is_vrwumane is False
    assert d.month_index == 1
    assert d.day_in_month == 1
    assert d.month_name == "Gaohwumane"
    assert d.is_astronomical_anchor is False

def test_month_boundary():
    # Last day of month 1
    d = AeraluneDate(year=1, day_of_year=32)
    assert d.month_index == 1
    assert d.day_in_month == 32
    # First day of month 2
    d2 = AeraluneDate(year=1, day_of_year=33)
    assert d2.month_index == 2
    assert d2.day_in_month == 1

def test_spring_equinox_date():
    d = AeraluneDate(year=1, day_of_year=SPRING_EQUINOX)
    assert d.month_name == "Uiwumane"
    assert d.day_in_month == 1
    assert d.is_astronomical_anchor is True

def test_summer_solstice_date():
    d = AeraluneDate(year=1, day_of_year=SUMMER_SOLSTICE)
    assert d.month_name == "Yeshuwumane"
    assert d.day_in_month == 1
    assert d.is_astronomical_anchor is True

def test_autumn_equinox_date():
    d = AeraluneDate(year=1, day_of_year=AUTUMN_EQUINOX)
    assert d.month_name == "Uinshuwumane"
    assert d.day_in_month == 1
    assert d.is_astronomical_anchor is True

def test_vrwumane_date():
    d = AeraluneDate(year=1, day_of_year=385)
    assert d.is_vrwumane is True
    assert d.month_index == 0
    assert d.day_in_month == 1
    assert d.month_name == "Vrwumane"
    assert d.is_astronomical_anchor is True   # Winter Solstice

def test_last_regular_day():
    d = AeraluneDate(year=1, day_of_year=384)
    assert d.month_index == 12
    assert d.month_name == "Aonkielwumane"
    assert d.day_in_month == 32
    assert d.is_vrwumane is False

def test_invalid_day_of_year():
    with pytest.raises(ValueError):
        AeraluneDate(year=1, day_of_year=0)
    with pytest.raises(ValueError):
        AeraluneDate(year=1, day_of_year=386)

def test_advance_simple():
    d = AeraluneDate(year=1, day_of_year=1)
    d2 = d.advance(1)
    assert d2.day_of_year == 2
    assert d2.year == 1

def test_advance_wraps_year():
    d = AeraluneDate(year=1, day_of_year=384)
    d2 = d.advance(2)   # 384 + 2 = 386 = year 2 day 1
    assert d2.year == 2
    assert d2.day_of_year == 1

def test_advance_to_vrwumane():
    d = AeraluneDate(year=1, day_of_year=384)
    d2 = d.advance(1)
    assert d2.day_of_year == 385
    assert d2.is_vrwumane is True

def test_advance_zero():
    d = AeraluneDate(year=5, day_of_year=100)
    assert d.advance(0) == d

def test_advance_negative_raises():
    d = AeraluneDate(year=1, day_of_year=1)
    with pytest.raises(ValueError):
        d.advance(-1)

def test_equality():
    assert AeraluneDate(1, 1) == AeraluneDate(1, 1)
    assert AeraluneDate(1, 1) != AeraluneDate(1, 2)
    assert AeraluneDate(1, 1) != AeraluneDate(2, 1)

def test_str_regular():
    d = AeraluneDate(year=3, day_of_year=SUMMER_SOLSTICE)
    assert "Yeshuwumane" in str(d)
    assert "Year 3" in str(d)

def test_str_vrwumane():
    d = AeraluneDate(year=2, day_of_year=385)
    assert str(d) == "Vrwumane, Year 2"


# ── Calendar queries ──────────────────────────────────────────────────────────

class TestFountainRunning:
    def test_runs_on_all_anchors(self):
        for doy in [SPRING_EQUINOX, SUMMER_SOLSTICE, AUTUMN_EQUINOX, WINTER_SOLSTICE]:
            assert fountain_running(AeraluneDate(1, doy)) is True

    def test_off_on_ordinary_days(self):
        for doy in [1, 50, 100, 200, 300, 384]:
            assert fountain_running(AeraluneDate(1, doy)) is False


class TestAlzedroswunePresent:
    def test_present_during_months_3_to_9(self):
        # Month 3 day 1 = day 65
        assert alzedroswune_present(AeraluneDate(1, 65)) is True
        # Month 9 day 32 = day 288
        assert alzedroswune_present(AeraluneDate(1, 288)) is True
        # Middle of summer
        assert alzedroswune_present(AeraluneDate(1, SUMMER_SOLSTICE)) is True

    def test_absent_months_1_2(self):
        assert alzedroswune_present(AeraluneDate(1, 1))  is False  # month 1 day 1
        assert alzedroswune_present(AeraluneDate(1, 64)) is False  # month 2 day 32

    def test_absent_months_10_12(self):
        assert alzedroswune_present(AeraluneDate(1, 289)) is False  # month 10 day 1
        assert alzedroswune_present(AeraluneDate(1, 384)) is False  # month 12 day 32

    def test_absent_on_vrwumane(self):
        assert alzedroswune_present(AeraluneDate(1, 385)) is False


# ── TimeOfDay ─────────────────────────────────────────────────────────────────

class TestTimeOfDay:
    def test_dawn(self):
        assert _hour_to_time_of_day(5) == TimeOfDay.DAWN
        assert _hour_to_time_of_day(6) == TimeOfDay.DAWN

    def test_morning(self):
        assert _hour_to_time_of_day(7)  == TimeOfDay.MORNING
        assert _hour_to_time_of_day(11) == TimeOfDay.MORNING

    def test_afternoon(self):
        assert _hour_to_time_of_day(12) == TimeOfDay.AFTERNOON
        assert _hour_to_time_of_day(16) == TimeOfDay.AFTERNOON

    def test_late_afternoon(self):
        assert _hour_to_time_of_day(17) == TimeOfDay.LATE_AFTERNOON
        assert _hour_to_time_of_day(18) == TimeOfDay.LATE_AFTERNOON

    def test_dusk(self):
        assert _hour_to_time_of_day(19) == TimeOfDay.DUSK
        assert _hour_to_time_of_day(20) == TimeOfDay.DUSK

    def test_night(self):
        assert _hour_to_time_of_day(0)  == TimeOfDay.NIGHT
        assert _hour_to_time_of_day(4)  == TimeOfDay.NIGHT
        assert _hour_to_time_of_day(21) == TimeOfDay.NIGHT
        assert _hour_to_time_of_day(23) == TimeOfDay.NIGHT


# ── WorldClock ────────────────────────────────────────────────────────────────

class TestWorldClock:
    def test_default_start(self):
        clk = WorldClock()
        d = clk.date
        assert d.year == 1
        assert d.day_of_year == 1
        assert clk.hour == 6
        assert clk.time_of_day == TimeOfDay.DAWN

    def test_custom_start(self):
        clk = WorldClock(year=2, day_of_year=193, hour=12)
        d = clk.date
        assert d.year == 2
        assert d.day_of_year == SUMMER_SOLSTICE
        assert clk.hour == 12
        assert clk.time_of_day == TimeOfDay.AFTERNOON

    def test_advance_hours(self):
        clk = WorldClock(year=1, day_of_year=1, hour=0)
        clk.advance(6)
        assert clk.hour == 6

    def test_advance_day(self):
        clk = WorldClock(year=1, day_of_year=1, hour=6)
        clk.advance_day()
        assert clk.date.day_of_year == 2

    def test_advance_wraps_day(self):
        clk = WorldClock(year=1, day_of_year=1, hour=23)
        clk.advance(2)   # 23 + 2 = 25 → hour 1, day 2
        assert clk.date.day_of_year == 2
        assert clk.hour == 1

    def test_advance_wraps_year(self):
        clk = WorldClock(year=1, day_of_year=385, hour=23)
        clk.advance(1)   # crosses into year 2 day 1
        assert clk.date.year == 2
        assert clk.date.day_of_year == 1

    def test_fountain_running_property(self):
        clk = WorldClock(year=1, day_of_year=SPRING_EQUINOX, hour=8)
        assert clk.fountain_running is True
        clk2 = WorldClock(year=1, day_of_year=100, hour=8)
        assert clk2.fountain_running is False

    def test_alzedroswune_present_property(self):
        clk_present = WorldClock(year=1, day_of_year=200, hour=8)
        assert clk_present.alzedroswune_present is True
        clk_absent = WorldClock(year=1, day_of_year=1, hour=8)
        assert clk_absent.alzedroswune_present is False

    def test_advance_negative_raises(self):
        clk = WorldClock()
        with pytest.raises(ValueError):
            clk.advance(-1)

    def test_breathofko_week(self):
        """Seven advance_day() calls = seven nightly recaps (quest 0016_KLST patience mechanic)."""
        clk = WorldClock(year=1, day_of_year=1, hour=6)
        for _ in range(7):
            clk.advance_day()
        assert clk.date.day_of_year == 8
        assert clk.date.year == 1

    def test_str(self):
        clk = WorldClock(year=1, day_of_year=1, hour=6)
        s = str(clk)
        assert "Year 1" in s
        assert "dawn" in s