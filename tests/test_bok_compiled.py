"""
tests/test_bok_compiled.py
===========================
Validates the compiled Kobra BoK engine (kobra_compiled/bok_engine.py)
against the hand-written ambroflow.ko.breath.BreathOfKo implementation.

The compiled engine is the canonical output of the Kobra compiler targeting
selfspec.ko LoLao.  All mathematical functions must produce results within
floating-point tolerance of their BreathOfKo equivalents.
"""
from __future__ import annotations

import math
import pytest

from ambroflow.kobra_compiled.bok_engine import (
    azoth_lo,
    mobius_coil,
    coil_ep,
    julia_fa_ung,
    julia_fa_fy,
    azoth_shak,
    azoth_mobius_foa,
    azoth_su_foa,
    shi_bi,
    ke_shi_bi,
    shi_ke_bi,
    ko_foa_shi_ke_wu_ung,
    PufFyLoVaShy,
    puf_fy_lo_shak,
    puf_fy_lo_shi_wu_ung,
    puf_fy_lo_ke_wu_ung,
    puf_fy_lo_ep_em,
    KobraError,
    _MAX_ITER_JULIA,
)
from ambroflow.ko.breath import BreathOfKo, _gaoh_constant, _derive_azoth


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _default_densities() -> dict[int, float]:
    return {i: 0.5 for i in range(1, 25)}


def _varied_densities() -> dict[int, float]:
    """Non-uniform densities that exercise all three tongue groups."""
    d = {}
    for i in range(1, 9):    d[i] = 0.3 + i * 0.04   # Lotus: 0.34–0.62
    for i in range(9, 17):   d[i] = 0.5 + (i - 9) * 0.03   # Rose: 0.50–0.71
    for i in range(17, 25):  d[i] = 0.6 + (i - 17) * 0.02  # Sakura: 0.60–0.74
    return d


# ── azoth_lo matches _derive_azoth ───────────────────────────────────────────

class TestAzothLo:
    def test_default_densities(self):
        dens = _default_densities()
        compiled = azoth_lo(dens, 6.0, 0.0)
        reference = _derive_azoth(dens, 6.0, 0.0)
        assert abs(compiled.real - reference.real) < 1e-10
        assert abs(compiled.imag - reference.imag) < 1e-10

    def test_varied_densities(self):
        dens = _varied_densities()
        for coil in [0.0, 3.0, 6.0, 9.0, 11.9]:
            compiled  = azoth_lo(dens, coil, 0.0)
            reference = _derive_azoth(dens, coil, 0.0)
            assert abs(compiled.real - reference.real) < 1e-9, \
                f"coil={coil}: real {compiled.real} != {reference.real}"
            assert abs(compiled.imag - reference.imag) < 1e-9

    def test_flag_weight_spiral(self):
        dens = _default_densities()
        base  = azoth_lo(dens, 6.0, 0.0)
        moved = azoth_lo(dens, 6.0, 2.0)
        assert moved.real != base.real  # flag weight shifts Azoth

    def test_azoth_bounded_in_complex_plane(self):
        """Azoth must stay within |z| ≤ 3 for sensible density inputs."""
        for flag_w in [0.0, 0.5, 1.0]:
            z = azoth_lo(_default_densities(), 6.0, flag_w)
            assert abs(z) < 3.0


# ── mobius_coil matches _gaoh_constant ───────────────────────────────────────

class TestMobiusCoil:
    def test_matches_gaoh_constant(self):
        for coil in [0.0, 3.0, 6.0, 9.0, 12.0]:
            compiled  = mobius_coil(coil)
            reference = _gaoh_constant(coil)
            assert abs(compiled.real - reference.real) < 1e-12, f"coil={coil}"
            assert abs(compiled.imag - reference.imag) < 1e-12, f"coil={coil}"

    def test_mobius_pair_zero_imaginary(self):
        """At coil 0 and 12 (Möbius pair), imaginary part = 0."""
        assert abs(mobius_coil(0.0).imag)  < 1e-12
        assert abs(mobius_coil(12.0).imag) < 1e-12

    def test_real_is_gaoh_normalized(self):
        c = mobius_coil(0.0)
        assert abs(c.real - 31 / 255.0) < 1e-12

    def test_coil_3_maximum_imaginary(self):
        """Coil position 3 (π/2) gives maximum imaginary excursion = 0.1."""
        c = mobius_coil(3.0)
        assert abs(abs(c.imag) - 0.1) < 1e-10

    def test_coil_6_near_zero_imaginary(self):
        """Coil position 6 (π) — imaginary ≈ 0 (sin(π) floating-point near-zero)."""
        c = mobius_coil(6.0)
        assert abs(c.imag) < 1e-15


# ── coil_ep ───────────────────────────────────────────────────────────────────

class TestCoilEp:
    def test_advances_by_one_game(self):
        start = 6.0
        advanced = coil_ep(start)
        expected = (start + 12.0 / 31.0) % 12.0
        assert abs(advanced - expected) < 1e-12

    def test_wraps_at_12(self):
        near_end = 11.9
        result   = coil_ep(near_end)
        assert 0.0 <= result < 12.0

    def test_31_games_full_rotation(self):
        """After 31 games the coil returns to 0 (mod 12) — allow float accumulation."""
        pos = 0.0
        for _ in range(31):
            pos = coil_ep(pos)
        # Floating-point accumulation over 31 steps; result is 0 or ≈12 (same Möbius point)
        assert abs(pos) < 1e-6 or abs(pos - 12.0) < 1e-6


# ── julia_fa_ung ──────────────────────────────────────────────────────────────

class TestJuliaFaUng:
    def test_interior_returns_max_iter(self):
        """Point at origin with c≈0.12 is well inside the Julia set."""
        c      = mobius_coil(0.0)
        result = julia_fa_ung(complex(0.0, 0.0), c)
        assert result == float(_MAX_ITER_JULIA)

    def test_exterior_escapes(self):
        """Point far from origin escapes quickly."""
        c      = mobius_coil(6.0)
        result = julia_fa_ung(complex(10.0, 10.0), c)
        assert result < 10.0

    def test_smooth_not_integer_on_escape(self):
        """Smooth value should be non-integer for escaping points."""
        c      = mobius_coil(6.0)
        result = julia_fa_ung(complex(1.5, 0.5), c)
        if result < _MAX_ITER_JULIA:
            assert result != math.floor(result)

    def test_symmetric_left_right(self):
        """Julia set is symmetric across the real axis."""
        c   = mobius_coil(6.0)
        pos = julia_fa_ung(complex(0.5, 0.3), c)
        neg = julia_fa_ung(complex(0.5, -0.3), c)
        assert abs(pos - neg) < 1e-6


# ── julia_fa_fy ──────────────────────────────────────────────────────────────

class TestJuliaFaFy:
    def test_grid_shape(self):
        c    = mobius_coil(0.0)
        grid = julia_fa_fy(c, size=16)
        assert len(grid) == 16
        assert all(len(row) == 16 for row in grid)

    def test_grid_values_in_range(self):
        c    = mobius_coil(6.0)
        grid = julia_fa_fy(c, size=16)
        for row in grid:
            for val in row:
                assert 0.0 <= val <= float(_MAX_ITER_JULIA) + 1

    def test_interior_center_bounded(self):
        """Center of the grid (near z₀=0) should be interior for c≈0.122."""
        c    = mobius_coil(0.0)
        grid = julia_fa_fy(c, size=16)
        center = grid[8][8]
        assert center == float(_MAX_ITER_JULIA)


# ── PufFyLoVaShy ─────────────────────────────────────────────────────────────

class TestPufFyLoVaShy:
    def test_azoth_matches_breath_of_ko(self):
        dens = _varied_densities()
        state = PufFyLoVaShy(dens, coil_position=6.0)
        breath = BreathOfKo(layer_densities=dict(dens), coil_position=6.0)
        comp_az = state.azoth()
        ref_az  = breath.azoth()
        assert abs(comp_az.real - ref_az.real) < 1e-9
        assert abs(comp_az.imag - ref_az.imag) < 1e-9

    def test_gaoh_constant_matches_breath_of_ko(self):
        dens  = _default_densities()
        state  = PufFyLoVaShy(dens, coil_position=3.7)
        breath = BreathOfKo(layer_densities=dict(dens), coil_position=3.7)
        assert abs(state.gaoh_constant().real - breath.gaoh_constant().real) < 1e-12
        assert abs(state.gaoh_constant().imag - breath.gaoh_constant().imag) < 1e-12

    def test_boundedness_returns_valid_string(self):
        state = PufFyLoVaShy(_default_densities())
        assert state.boundedness() in ("bounded", "edge", "unbounded")

    def test_snapshot_keys(self):
        state = PufFyLoVaShy(_default_densities())
        snap  = state.snapshot()
        assert "layer_densities" in snap
        assert "coil_position"   in snap
        assert "azoth"           in snap
        assert "boundedness"     in snap

    def test_snapshot_azoth_length(self):
        state = PufFyLoVaShy(_default_densities())
        snap  = state.snapshot()
        assert len(snap["azoth"]) == 2

    def test_default_state_24_layers(self):
        state = PufFyLoVaShy()
        assert len(state.layer_densities) == 24


# ── puf_fy_lo_shak ────────────────────────────────────────────────────────────

class TestPufFyLoShak:
    def test_increments_games_played(self):
        state  = PufFyLoVaShy(games_played=0)
        state2 = puf_fy_lo_shak(state, 0.8)
        assert state2.games_played == 1

    def test_advances_coil(self):
        state  = PufFyLoVaShy(coil_position=6.0, games_played=0)
        state2 = puf_fy_lo_shak(state, 0.8)
        assert state2.coil_position != 6.0

    def test_updates_densities(self):
        state  = PufFyLoVaShy({i: 0.5 for i in range(1, 25)}, games_played=0)
        state2 = puf_fy_lo_shak(state, 0.9)
        # Rolling average: (0.5 × 0 + 0.9 × 1) / 1 = 0.9
        for v in state2.layer_densities.values():
            assert abs(v - 0.9) < 1e-4

    def test_immutable_original(self):
        state  = PufFyLoVaShy(games_played=5)
        puf_fy_lo_shak(state, 0.7)
        assert state.games_played == 5  # original unchanged


# ── puf_fy_lo_shi_wu_ung / ke_wu_ung ─────────────────────────────────────────

class TestEmissionBranches:
    def test_shi_wu_ung_returns_dict(self):
        state = PufFyLoVaShy(_default_densities())
        result = puf_fy_lo_shi_wu_ung(state)
        assert isinstance(result, dict)
        assert "boundedness" in result

    def test_ke_wu_ung_raises_kobra_error(self):
        state = PufFyLoVaShy(_default_densities())
        with pytest.raises(KobraError):
            puf_fy_lo_ke_wu_ung(state, "test error")

    def test_ep_em_returns_dict(self):
        state  = PufFyLoVaShy(_default_densities())
        result = puf_fy_lo_ep_em(state)
        assert isinstance(result, dict)


# ── Convergence modes ─────────────────────────────────────────────────────────

class TestConvergenceModes:
    def test_shi_bi_bounded(self):
        assert shi_bi(_MAX_ITER_JULIA)     == "bounded"
        assert shi_bi(_MAX_ITER_JULIA - 1) == "edge"

    def test_ke_shi_bi(self):
        assert ke_shi_bi(_MAX_ITER_JULIA)         == "edge"
        assert ke_shi_bi(_MAX_ITER_JULIA // 2)    == "edge"
        assert ke_shi_bi(_MAX_ITER_JULIA // 2 - 1) == "unbounded"

    def test_shi_ke_bi(self):
        assert shi_ke_bi(0)                        == "unbounded"
        assert shi_ke_bi(_MAX_ITER_JULIA // 2 - 1) == "unbounded"
        assert shi_ke_bi(_MAX_ITER_JULIA // 2)     == "edge"

    def test_ko_fork_kaganue_on_bounded(self):
        assert ko_foa_shi_ke_wu_ung(_MAX_ITER_JULIA)     == "Kaganue"

    def test_ko_fork_drovitth_on_edge(self):
        mid = _MAX_ITER_JULIA * 3 // 4   # above half, below max
        assert ko_foa_shi_ke_wu_ung(mid) == "Drovitth"

    def test_ko_fork_kaganue_on_unbounded(self):
        assert ko_foa_shi_ke_wu_ung(0) == "Kaganue"


# ── Compiler infrastructure smoke test ───────────────────────────────────────

class TestKobraCompilerSmoke:
    """Verify the kobra package can parse selfspec.ko without crashing."""

    @pytest.fixture(autouse=True)
    def _check_path(self):
        import pathlib
        p = pathlib.Path(r"C:\DjinnOS\DjinnOS_Shyagzun\shygazun\sanctum\charters\selfspec.ko")
        if not p.exists():
            pytest.skip("selfspec.ko not found")

    def test_parse_selfspec(self):
        import sys
        sys.path.insert(0, r"C:\DjinnOS\shygazun")
        from kobra import parse_file
        prog = parse_file(
            r"C:\DjinnOS\DjinnOS_Shyagzun\shygazun\sanctum\charters\selfspec.ko"
        )
        assert len(prog.seths) >= 1
        assert prog.seths[0].name == "SethKernel"

    def test_resolver_loads_selfspec(self):
        import sys
        sys.path.insert(0, r"C:\DjinnOS\shygazun")
        from kobra import parse_file, Resolver
        prog     = parse_file(
            r"C:\DjinnOS\DjinnOS_Shyagzun\shygazun\sanctum\charters\selfspec.ko"
        )
        resolver = Resolver()
        resolver.load_program(prog)
        # selfspec.ko defines 100+ words
        assert len(resolver.word_table) >= 50

    def test_parse_hw(self):
        import sys
        sys.path.insert(0, r"C:\DjinnOS\shygazun")
        from kobra import parse_file
        prog = parse_file(
            r"C:\DjinnOS\DjinnOS_Shyagzun\shygazun\sanctum\charters\hw.ko"
        )
        assert len(prog.seths) >= 1
        assert prog.seths[0].name == "SethHW"
