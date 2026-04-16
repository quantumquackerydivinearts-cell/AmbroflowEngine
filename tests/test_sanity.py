"""Tests for the live sanity system."""

import pytest
from ambroflow.sanity.live import LiveSanity, SanitySnapshot, consonance_axis


class _MockOrrery:
    def __init__(self):
        self.deltas = []
    def record_sanity_delta(self, **kwargs):
        self.deltas.append(kwargs)
    def get_sanity(self):
        return {"alchemical": 0.5, "narrative": 0.5, "terrestrial": 0.5, "cosmic": 0.5}


def _make_sanity(**kwargs):
    return LiveSanity(actor_id="test", orrery=_MockOrrery(), **kwargs)


def test_default_scores_neutral():
    s = _make_sanity()
    snap = s.snapshot()
    assert snap.alchemical == 0.5
    assert snap.narrative  == 0.5
    assert snap.terrestrial == 0.5
    assert snap.cosmic == 0.5


def test_delta_applied_and_clamped():
    s = _make_sanity()
    snap = s.apply_delta({"alchemical": 0.3, "cosmic": -0.8})
    assert snap.alchemical == pytest.approx(0.8)
    assert snap.cosmic == pytest.approx(0.0)   # clamped at 0


def test_consonance_low_variance():
    snap = SanitySnapshot(alchemical=0.5, narrative=0.5, terrestrial=0.5, cosmic=0.5)
    assert consonance_axis(snap) == "consonance"


def test_dissonance_high_variance():
    snap = SanitySnapshot(alchemical=0.9, narrative=0.1, terrestrial=0.5, cosmic=0.2)
    assert consonance_axis(snap) == "dissonance"


def test_consonance_property_on_runtime():
    s = _make_sanity(initial={"alchemical": 0.5, "narrative": 0.5, "terrestrial": 0.5, "cosmic": 0.5})
    assert s.consonance() == "consonance"

    s.apply_delta({"alchemical": 0.4, "narrative": -0.4})
    assert s.consonance() == "dissonance"


def test_orrery_delta_recorded():
    orrery = _MockOrrery()
    s = LiveSanity(actor_id="test", orrery=orrery)
    s.apply_delta({"cosmic": 0.05})
    assert len(orrery.deltas) == 1
    assert orrery.deltas[0]["deltas"] == {"cosmic": 0.05}
