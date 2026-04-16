"""Tests for Void Wraith entity definitions and observer."""

from ambroflow.void_wraith import VOID_WRAITHS, WRAITH_BY_ID, ObservationKind, WraithObserver


def test_three_wraiths_defined():
    assert len(VOID_WRAITHS) == 3


def test_named_wraiths():
    names = {w.name for w in VOID_WRAITHS}
    assert "Negaya" in names
    assert "Vios" in names
    assert "Haldoro" in names


def test_wraith_ids():
    assert "2001_VDWR" in WRAITH_BY_ID  # Haldoro
    assert "2002_VDWR" in WRAITH_BY_ID  # Vios
    assert "2003_VDWR" in WRAITH_BY_ID  # Negaya


def test_haldoro_observes_silence():
    haldoro = WRAITH_BY_ID["2001_VDWR"]
    assert ObservationKind.WORD_WITHHELD in haldoro.observation_kinds
    assert haldoro.domain.startswith("Silence")


def test_vios_observes_omissions():
    vios = WRAITH_BY_ID["2002_VDWR"]
    assert ObservationKind.OMISSION_PATTERN in vios.observation_kinds
    assert vios.ko_flag_id == "absence_practiced"


def test_negaya_observes_kills_and_dreams():
    negaya = WRAITH_BY_ID["2003_VDWR"]
    assert ObservationKind.LIFE_MADE_ABSENT in negaya.observation_kinds
    assert ObservationKind.DREAM_ENTRY in negaya.observation_kinds
    assert negaya.threshold_ratio == 0.0   # always fires
    assert negaya.min_repetitions == 1


# ── WraithObserver ────────────────────────────────────────────────────────────

class _MockOrrery:
    def __init__(self):
        self.void_wraith_calls = []
    def void_wraith_observe(self, observation_id, context):
        self.void_wraith_calls.append((observation_id, context))


def _make_observer():
    orrery = _MockOrrery()
    return WraithObserver(actor_id="0000_0451", orrery=orrery), orrery


def test_life_made_absent_always_fires():
    obs, orrery = _make_observer()
    obs.life_made_absent("0019_ROYL")
    assert len(orrery.void_wraith_calls) == 1
    kind, ctx = orrery.void_wraith_calls[0]
    assert kind == ObservationKind.LIFE_MADE_ABSENT
    assert ctx["target_id"] == "0019_ROYL"
    assert ctx["wraith"] == "Negaya"


def test_omission_below_threshold_no_fire():
    obs, orrery = _make_observer()
    # 2 opportunities, 0 taken — not enough repetitions yet (min=3)
    obs.opportunity("speech")
    obs.opportunity("speech")
    obs.check_omission_pattern("speech")
    assert len(orrery.void_wraith_calls) == 0


def test_omission_above_threshold_fires():
    obs, orrery = _make_observer()
    # 5 opportunities, 0 taken → 100% missed, >= 3 min repetitions
    for _ in range(5):
        obs.opportunity("speech")
    obs.check_omission_pattern("speech")
    assert len(orrery.void_wraith_calls) == 1
    kind, ctx = orrery.void_wraith_calls[0]
    assert ctx["wraith"] == "Vios"
    assert ctx["missed"] == 5


def test_omission_fires_once_per_session():
    obs, orrery = _make_observer()
    for _ in range(5):
        obs.opportunity("speech")
    obs.check_omission_pattern("speech")
    obs.check_omission_pattern("speech")   # second call — should not re-fire
    assert len(orrery.void_wraith_calls) == 1


def test_dream_entry_observation():
    obs, orrery = _make_observer()
    obs.dream_entry_observed("entry_001", "First Dream")
    assert len(orrery.void_wraith_calls) == 1
    kind, ctx = orrery.void_wraith_calls[0]
    assert kind == ObservationKind.DREAM_ENTRY
    assert ctx["wraith"] == "Negaya"
