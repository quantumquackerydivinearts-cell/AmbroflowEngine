"""
Tests for free world combat system.
"""

from unittest.mock import MagicMock

import pytest

from ambroflow.world.combat import (
    CombatResult, CombatScreen, CombatLoop,
    resolve_combat, npc_difficulty,
    begin_combat_loop, execute_round, to_result,
    player_health_from_vitality, npc_hits_to_kill, npc_damage_per_hit,
    endurance_reduction,
    AMMO_GOLD_ROUNDS, WEAPON_ANGELIC_SPEAR, _IMMUNE_TYPES, _RESISTANT_TYPES,
)
from ambroflow.world.tile_trace import FY, PU, ZO


# ── npc_difficulty ────────────────────────────────────────────────────────────

def test_difficulty_wtch():
    assert npc_difficulty("0007_WTCH") == 0.45


def test_difficulty_assn():
    assert npc_difficulty("0012_ASSN") == 0.65


def test_difficulty_gods():
    assert npc_difficulty("0001_GODS") == 0.98


def test_difficulty_unknown_type():
    assert npc_difficulty("9999_UNKN") == 0.50


def test_difficulty_from_id_without_type():
    assert npc_difficulty("forest") == 0.50


# ── resolve_combat ────────────────────────────────────────────────────────────

def test_resolve_returns_combat_result():
    result = resolve_combat("0007_WTCH", "Forest", {"melee_weapons": 3})
    assert isinstance(result, CombatResult)
    assert result.outcome in ("player_wins", "player_flees", "npc_wins")


def test_resolve_high_skill_vs_easy_npc_wins():
    # rank 50 / 50 = 1.0 >= TOWN difficulty 0.25 — always wins
    r = resolve_combat("0001_TOWN", "Townsperson", {"melee_weapons": 50})
    assert r.outcome == "player_wins"


def test_resolve_zero_skill_vs_gods_always_loses():
    # rank 0 / 50 = 0.0 < GODS 0.98 * 0.5 = 0.49 — always npc_wins
    r = resolve_combat("0001_GODS", "God", {})
    assert r.outcome == "npc_wins"


def test_resolve_mid_skill_vs_hard_npc_flees():
    # ASSN difficulty 0.65 (human, no resistance); flee band: 0.325 <= effective < 0.65
    # rank 20 / 50 = 0.40 → in flee band
    r = resolve_combat("0012_ASSN", "Assassin", {"melee_weapons": 20})
    assert r.outcome == "player_flees"


def test_resolve_npc_id_and_name_in_result():
    r = resolve_combat("0007_WTCH", "Forest", {"unarmed": 2})
    assert r.npc_id   == "0007_WTCH"
    assert r.npc_name == "Forest"


def test_resolve_sanity_delta_present():
    r = resolve_combat("0007_WTCH", "Forest", {"melee_weapons": 3})
    assert isinstance(r.sanity_delta, dict)
    assert len(r.sanity_delta) > 0


def test_resolve_win_has_narrative_penalty():
    # rank 50 vs TOWN — deterministic win
    r = resolve_combat("0001_TOWN", "Townsperson", {"melee_weapons": 50})
    assert r.outcome == "player_wins"
    assert r.sanity_delta.get("narrative", 0) < 0


# ── immunity and resistance ───────────────────────────────────────────────────

def test_immune_type_without_gold_rounds_always_loses():
    # DMON is immune — max skill still loses without Gold rounds
    r = resolve_combat("0001_DMON", "Demon", {"melee_weapons": 50})
    assert r.outcome == "npc_wins"


def test_immune_type_with_gold_rounds_resolves_normally():
    # rank 50 vs DMON difficulty 0.80 → 1.0 >= 0.80 → wins
    r = resolve_combat("0001_DMON", "Demon", {"melee_weapons": 50}, equipped=AMMO_GOLD_ROUNDS)
    assert r.outcome == "player_wins"


def test_all_immune_types_blocked_without_ammo():
    for ctype in _IMMUNE_TYPES:
        r = resolve_combat(f"0001_{ctype}", ctype, {"melee_weapons": 50})
        assert r.outcome == "npc_wins", f"{ctype} should be immune without Gold rounds"


def test_all_immune_types_reachable_with_gold_rounds():
    for ctype in _IMMUNE_TYPES:
        r = resolve_combat(f"0001_{ctype}", ctype, {"melee_weapons": 50}, equipped=AMMO_GOLD_ROUNDS)
        # rank 50 / 50 = 1.0 — beats any difficulty including GODS 0.98
        assert r.outcome == "player_wins", f"{ctype} should be reachable with Gold rounds at rank 50"


def test_wtch_resistance_doubles_difficulty():
    # WTCH base difficulty 0.45; doubled = 0.90
    # rank 44 / 50 = 0.88 < 0.90 → cannot win conventionally
    r = resolve_combat("0007_WTCH", "Forest", {"melee_weapons": 44})
    assert r.outcome != "player_wins"


def test_wtch_resistance_beatable_at_high_rank():
    # rank 45 / 50 = 0.90 >= 0.90 (doubled WTCH difficulty) → wins
    r = resolve_combat("0007_WTCH", "Forest", {"melee_weapons": 45})
    assert r.outcome == "player_wins"


def test_wtch_gold_rounds_use_base_difficulty():
    # with Gold rounds, WTCH difficulty stays 0.45; rank 23 / 50 = 0.46 → wins
    r = resolve_combat("0007_WTCH", "Forest", {"melee_weapons": 23}, equipped=AMMO_GOLD_ROUNDS)
    assert r.outcome == "player_wins"


def test_human_types_unaffected_by_ammo():
    # TOWN / PRST / ASSN / ROYL / SOLD — equipped gear makes no difference
    for ctype in ("TOWN", "PRST", "ASSN", "ROYL", "SOLD"):
        r_none  = resolve_combat(f"0001_{ctype}", ctype, {"melee_weapons": 50})
        r_gold  = resolve_combat(f"0001_{ctype}", ctype, {"melee_weapons": 50}, equipped=AMMO_GOLD_ROUNDS)
        r_spear = resolve_combat(f"0001_{ctype}", ctype, {"melee_weapons": 50}, equipped=WEAPON_ANGELIC_SPEAR)
        assert r_none.outcome == r_gold.outcome == r_spear.outcome == "player_wins"


# ── Angelic Spear ─────────────────────────────────────────────────────────────

def test_angelic_spear_bypasses_immunity():
    # Spear should unlock immune types just like Gold rounds
    r = resolve_combat("0001_DMON", "Demon", {"melee_weapons": 50}, equipped=WEAPON_ANGELIC_SPEAR)
    assert r.outcome == "player_wins"


def test_all_immune_types_reachable_with_spear():
    for ctype in _IMMUNE_TYPES:
        r = resolve_combat(f"0001_{ctype}", ctype, {"melee_weapons": 50}, equipped=WEAPON_ANGELIC_SPEAR)
        assert r.outcome == "player_wins", f"{ctype} should be reachable with Angelic Spear at rank 50"


def test_angelic_spear_bypasses_wtch_resistance():
    # rank 23 / 50 = 0.46 >= base WTCH 0.45 → wins with spear (no doubling)
    r = resolve_combat("0007_WTCH", "Forest", {"melee_weapons": 23}, equipped=WEAPON_ANGELIC_SPEAR)
    assert r.outcome == "player_wins"


def test_spear_and_gold_rounds_equivalent_vs_immune():
    # Both angelic gear items produce identical outcomes at the same rank
    for ctype in _IMMUNE_TYPES:
        r_gold  = resolve_combat(f"0001_{ctype}", ctype, {"melee_weapons": 50}, equipped=AMMO_GOLD_ROUNDS)
        r_spear = resolve_combat(f"0001_{ctype}", ctype, {"melee_weapons": 50}, equipped=WEAPON_ANGELIC_SPEAR)
        assert r_gold.outcome == r_spear.outcome


# ── CombatScreen ─────────────────────────────────────────────────────────────

def test_render_prompt_returns_png():
    pytest.importorskip("PIL")
    screen = CombatScreen()
    result = screen.render_prompt("Forest", "0007_WTCH", 320, 200)
    assert result is not None
    assert result[:4] == b"\x89PNG"


def test_render_result_win_returns_png():
    pytest.importorskip("PIL")
    screen = CombatScreen()
    r = CombatResult(
        outcome="player_wins", npc_id="0007_WTCH",
        npc_name="Forest", sanity_delta={"narrative": -0.03})
    result = screen.render_result(r, 320, 200)
    assert result is not None
    assert result[:4] == b"\x89PNG"


def test_render_result_flee_returns_png():
    pytest.importorskip("PIL")
    screen = CombatScreen()
    r = CombatResult(
        outcome="player_flees", npc_id="0007_WTCH",
        npc_name="Forest", sanity_delta={})
    result = screen.render_result(r, 320, 200)
    assert result is not None


def test_render_result_loss_returns_png():
    pytest.importorskip("PIL")
    screen = CombatScreen()
    r = CombatResult(
        outcome="npc_wins", npc_id="0007_WTCH",
        npc_name="Forest", sanity_delta={"terrestrial": -0.05})
    result = screen.render_result(r, 320, 200)
    assert result is not None


# ── WorldPlay integration ─────────────────────────────────────────────────────

def _make_play_with_npc():
    from ambroflow.world.play import WorldPlay, WorldMode
    from ambroflow.world.map import WorldMap, Zone, Realm, WorldTileKind, NPCSpawn

    voxels = {(x, y): WorldTileKind.FLOOR for x in range(5) for y in range(5)}
    npc = NPCSpawn(x=2, y=1, character_id="0007_WTCH")
    zone = Zone(
        zone_id="wiltoll", name="Wiltoll Lane", realm=Realm.LAPIDUS,
        width=5, height=5, voxels=voxels, player_spawn=(2, 2),
        npc_spawns=[npc],
    )
    world = WorldMap(zones={"wiltoll": zone}, starting_zone_id="wiltoll")
    chargen = MagicMock()
    chargen.name = "Apprentice"
    chargen.skill_ranks = {"melee_weapons": 45}
    chargen.vitality    = 5
    chargen.tactility   = 5
    return WorldPlay(chargen=chargen, world_map=world, width=320, height=200)


def test_worldplay_has_dead_npcs_set():
    play = _make_play_with_npc()
    assert hasattr(play, "_dead_npcs")
    assert isinstance(play._dead_npcs, set)


def test_worldplay_begin_combat_enters_mode():
    from ambroflow.world.play import WorldMode
    pytest.importorskip("PIL")
    play = _make_play_with_npc()
    npc = play._zone.npc_spawns[0]
    play._begin_combat(npc)
    assert play._mode == WorldMode.COMBAT
    assert play._combat_result is None
    assert play._combat_loop is not None
    assert play._combat_bytes is not None


def test_worldplay_begin_combat_deposits_fy():
    pytest.importorskip("PIL")
    play = _make_play_with_npc()
    npc = play._zone.npc_spawns[0]
    play._begin_combat(npc)
    att = play.tile_tracer.attestation_at("wiltoll", 2, 2)
    assert att is not None
    assert att.count(FY) >= 1


def test_worldplay_abort_combat_returns_to_world():
    from ambroflow.world.play import WorldMode
    pytest.importorskip("PIL")
    play = _make_play_with_npc()
    npc = play._zone.npc_spawns[0]
    play._begin_combat(npc)
    play._abort_combat()
    assert play._mode == WorldMode.WORLD
    assert play._combat_npc is None


def _run_to_completion(play, action: str = "attack") -> None:
    """Drive the combat loop with a repeated action until the loop ends."""
    while play._combat_loop is not None and not play._combat_loop.is_over:
        play._process_round(action)


def test_worldplay_kill_marks_npc_dead():
    pytest.importorskip("PIL")
    play = _make_play_with_npc()
    # rank 45 / 50 = 0.90 >= doubled WTCH difficulty 0.90 → hits every round
    npc = play._zone.npc_spawns[0]
    play._begin_combat(npc)
    _run_to_completion(play)
    play._end_combat()
    assert "0007_WTCH" in play._dead_npcs


def test_worldplay_kill_deposits_zo():
    pytest.importorskip("PIL")
    play = _make_play_with_npc()
    npc = play._zone.npc_spawns[0]
    play._begin_combat(npc)
    _run_to_completion(play)
    play._end_combat()
    att = play.tile_tracer.attestation_at("wiltoll", 2, 2)
    assert att.count(ZO) >= 1   # absence — Negaya observes


def test_worldplay_flee_deposits_pu():
    pytest.importorskip("PIL")
    play = _make_play_with_npc()
    play._chargen.skill_ranks = {"melee_weapons": 23}
    npc = play._zone.npc_spawns[0]
    play._begin_combat(npc)
    play._process_round("flee")
    play._end_combat()
    att = play.tile_tracer.attestation_at("wiltoll", 2, 2)
    assert att.count(PU) >= 1


def test_worldplay_loop_fy_deposits_per_round():
    pytest.importorskip("PIL")
    play = _make_play_with_npc()
    npc = play._zone.npc_spawns[0]
    play._begin_combat(npc)
    rounds = play._combat_loop.npc_hits_max  # exact rounds to kill
    _run_to_completion(play)
    att = play.tile_tracer.attestation_at("wiltoll", 2, 2)
    # FY deposited on initiation + once per round
    assert att.count(FY) >= rounds + 1


def test_worldplay_permadeath_enters_dead_mode():
    from ambroflow.world.play import WorldMode
    pytest.importorskip("PIL")
    play = _make_play_with_npc()
    # Zero skill, high-damage NPC: force player dead by attacking until health gone
    play._chargen.skill_ranks = {}
    npc = play._zone.npc_spawns[0]
    play._begin_combat(npc)
    # Drive rounds until player_dead (can't kill WTCH without angelic gear anyway)
    for _ in range(100):
        if play._combat_loop is None or play._combat_loop.is_over:
            break
        play._process_round("attack")
    assert play._combat_loop.outcome == "player_dead"
    play._end_combat()
    assert play._mode == WorldMode.DEAD


def test_worldplay_dead_npc_not_interactable():
    pytest.importorskip("PIL")
    play = _make_play_with_npc()
    play._dead_npcs.add("0007_WTCH")
    # _interact should not enter dialogue for a dead NPC
    from ambroflow.world.play import WorldMode
    play._interact()
    assert play._mode == WorldMode.WORLD   # stayed in world, no dialogue