"""Tests for skill registry and runtime."""

import pytest
from ambroflow.skills.registry import SKILL_BY_ID, PERK_BY_ID, ALL_PERKS


def test_all_meditation_perks_present():
    perk_ids = [
        "breathwork_meditation",
        "alchemical_meditation",
        "hypnotic_meditation",
        "infernal_meditation",
        "depth_meditation",
        "transcendental_meditation",
        "zen_meditation",
    ]
    for pid in perk_ids:
        assert pid in PERK_BY_ID, f"Missing perk: {pid}"


def test_infernal_meditation_quest_gate():
    p = PERK_BY_ID["infernal_meditation"]
    assert p.required_quest == "0009_KLST", "Demons and Diamonds = 0009_KLST"
    assert p.gates == {"sulphera_access": True}


def test_alchemical_meditation_quest_gate():
    p = PERK_BY_ID["alchemical_meditation"]
    assert p.required_quest == "0008_KLST"   # Bunsen For Hire


def test_hypnotic_meditation_quest_gate():
    p = PERK_BY_ID["hypnotic_meditation"]
    assert p.required_quest == "0007_KLST"   # Dream of Glass


def test_zen_meditation_quest_gate():
    p = PERK_BY_ID["zen_meditation"]
    assert p.required_quest == "0026_KLST"   # Good Grief


def test_breathwork_has_no_quest_gate():
    p = PERK_BY_ID["breathwork_meditation"]
    assert p.required_quest is None


def test_all_meditation_perks_have_no_perk_prerequisites():
    for pid in [
        "breathwork_meditation", "alchemical_meditation", "hypnotic_meditation",
        "infernal_meditation", "depth_meditation", "transcendental_meditation",
        "zen_meditation",
    ]:
        p = PERK_BY_ID[pid]
        assert p.required_perks == (), f"{pid} should have no perk prerequisites"


def test_meditation_skill_exists():
    assert "meditation" in SKILL_BY_ID
    assert SKILL_BY_ID["meditation"].vitriol_affinity == "I"
    assert SKILL_BY_ID["meditation"].sanity_dimension == "cosmic"


def test_19_skills_defined():
    assert len(SKILL_BY_ID) == 19


def test_alchemy_skill_reflectivity():
    s = SKILL_BY_ID["alchemy"]
    assert s.vitriol_affinity == "R"


# ── SkillRuntime tests (no Orrery calls — mock client) ────────────────────────

class _MockOrrery:
    def __init__(self):
        self.events = []
    def record(self, kind, payload):
        self.events.append((kind, payload))
    def record_sanity_delta(self, **kwargs):
        self.events.append(("sanity_delta", kwargs))


def _make_runtime(**kwargs):
    from ambroflow.skills.runtime import SkillRuntime
    return SkillRuntime(actor_id="test_actor", orrery=_MockOrrery(), **kwargs)


def test_unlock_perk_no_skill():
    rt = _make_runtime()
    result = rt.unlock_perk("breathwork_meditation")
    assert not result.success
    assert "meditation" in result.reason


def test_unlock_breathwork_with_skill():
    rt = _make_runtime(skill_ranks={"meditation": 1})
    result = rt.unlock_perk("breathwork_meditation")
    assert result.success
    assert rt.has_perk("breathwork_meditation")


def test_unlock_infernal_requires_quest():
    rt = _make_runtime(skill_ranks={"meditation": 1})
    result = rt.unlock_perk("infernal_meditation")
    assert not result.success
    assert "0009_KLST" in result.reason

    # Complete quest then unlock
    rt.complete_quest("0009_KLST")
    result = rt.unlock_perk("infernal_meditation")
    assert result.success
    assert rt.has_sulphera_access()


def test_double_unlock_fails():
    rt = _make_runtime(skill_ranks={"meditation": 3}, unlocked_perks=["breathwork_meditation"])
    result = rt.unlock_perk("breathwork_meditation")
    assert not result.success
    assert "Already" in result.reason
