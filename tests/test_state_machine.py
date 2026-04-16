"""Tests for the game state machine."""

import pytest
from ambroflow.state.machine import GameStateMachine, GamePhase, resolve_game1_starting_city
from ambroflow.ko.breath import BreathOfKo
from ambroflow.ko.calibration import DreamCalibrationSession, CalibrationTongue


class _MockOrrery:
    def __init__(self):
        self.events = []
    def record(self, kind, payload):
        self.events.append((kind, payload))
    def record_sanity_delta(self, **kw):
        pass


def _run_calibration(resonance=0.6):
    session = DreamCalibrationSession(game_id="7_KLGS")
    for _ in range(9):   # 3 phases × 3
        session.respond(resonance)
    return session.complete()


def _make_machine(game_number=7):
    orrery = _MockOrrery()
    breath = BreathOfKo()
    machine = GameStateMachine("7_KLGS", game_number, breath, orrery)
    return machine, orrery, breath


def test_initial_phase_is_unstarted():
    machine, _, _ = _make_machine()
    assert machine.phase == GamePhase.UNSTARTED


def test_begin_dream_calibration():
    machine, _, _ = _make_machine()
    machine.begin_dream_calibration()
    assert machine.phase == GamePhase.DREAM_CALIBRATION


def test_invalid_transition_raises():
    machine, _, _ = _make_machine()
    with pytest.raises(ValueError):
        machine.begin_convergence()   # can't skip phases


def test_full_lifecycle():
    from ambroflow.ko.vitriol import assign_vitriol
    machine, orrery, breath = _make_machine()
    cal = _run_calibration()
    vitriol = assign_vitriol(cal)

    machine.begin_dream_calibration()
    machine.complete_dream_calibration(cal, vitriol)
    assert machine.phase == GamePhase.WAKING_PLAY

    machine.begin_convergence()
    assert machine.phase == GamePhase.CONVERGENCE

    machine.end_game("sovereign_path")
    assert machine.phase == GamePhase.ENDED
    assert machine.state.ended_at_phase == "sovereign_path"


def test_game1_starting_city_assigned():
    from ambroflow.ko.vitriol import assign_vitriol
    machine, _, _ = _make_machine(game_number=1)
    machine._state.game_id = "1_KLGS"
    machine._state.game_number = 1

    cal = _run_calibration()
    vitriol = assign_vitriol(cal)
    machine.begin_dream_calibration()
    machine.complete_dream_calibration(cal, vitriol, safety_axis="sovereign", sanity_axis="consonance")
    assert machine.state.starting_city == "La Paz, Peru"


def test_game1_timeline_all_four_cities():
    assert resolve_game1_starting_city("sovereign",         "consonance")  == "La Paz, Peru"
    assert resolve_game1_starting_city("sovereign",         "dissonance")  == "Kyoto"
    assert resolve_game1_starting_city("wounded_sovereign", "consonance")  == "New York"
    assert resolve_game1_starting_city("wounded_sovereign", "dissonance")  == "London"


def test_breath_integrated_on_end():
    from ambroflow.ko.vitriol import assign_vitriol
    machine, _, breath = _make_machine()
    cal = _run_calibration()
    vitriol = assign_vitriol(cal)

    machine.begin_dream_calibration()
    machine.complete_dream_calibration(cal, vitriol)
    machine.begin_convergence()
    machine.end_game("test_path")

    assert breath.snapshot()["games_played"] == 1


def test_orrery_events_fired_on_transitions():
    from ambroflow.ko.vitriol import assign_vitriol
    machine, orrery, _ = _make_machine()
    cal = _run_calibration()
    vitriol = assign_vitriol(cal)

    machine.begin_dream_calibration()
    machine.complete_dream_calibration(cal, vitriol)
    machine.begin_convergence()
    machine.end_game("test_path")

    event_kinds = [k for k, _ in orrery.events]
    assert "game.phase.dream_calibration" in event_kinds
    assert "game.phase.waking_play" in event_kinds
    assert "game.calibration.complete" in event_kinds
    assert "game.ended" in event_kinds
