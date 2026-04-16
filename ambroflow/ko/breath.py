"""
Breath of Ko — Cross-Game Save State
=====================================
The Breath of Ko is the living measure of experiential accumulation
across the entire 31-game anthology.

It is not a save file. It is not an achievement system.
It is the player's ontological state — their actual density of correspondence
across all 24 layers, accumulated across every game played.

The Breath of Ko is rendered as a Mandelbrot image.

    Azoth² + Gaoh = f(x)

  Azoth  — the player's accumulated experiential state as complex number.
           Derived from the 24 layer densities, flagged states, and coil position.
  Gaoh   — the constant (31 — Number 12/0, the Möbius zero point, Rose tongue).
           Every iteration folds the player's state through the Möbius pair.

What the image means:
  Bounded (within the set):   Integrated experience — coherent under measurement
  Boundary (Mandelbrot edge): Living philosophical inquiry — most alive work
  Unbounded (escaping):       Accumulation without comprehension

The most philosophically interesting work produces the most beautiful save files.

coil_position [0.0–12.0]: current position on the Möbius coil.
  0.0 and 12.0 are the same point (Gaoh/Wu-Yl boundary).
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass, field
from typing import Optional

from .calibration import DreamCalibration
from .flags import FlagState


# ── Gaoh constant ─────────────────────────────────────────────────────────────
# Gaoh = 31 (Rose, Number 12/0). Used as the c parameter in Mandelbrot iteration.
# Normalized to complex plane: real part = 31/255, imaginary part derived from coil position.

_GAOH_DECIMAL = 31


def _gaoh_constant(coil_position: float) -> complex:
    """
    Gaoh as a complex constant for the Mandelbrot iteration.
    Real part: Gaoh normalized (31/255 ≈ 0.122)
    Imaginary part: encodes coil position as a Möbius-aware value.
    At coil positions 0 and 12 (the Möbius pair), imaginary part = 0.
    """
    real = _GAOH_DECIMAL / 255.0
    # Möbius fold: position 6 = maximum imaginary excursion
    theta = (coil_position / 12.0) * 2 * math.pi
    imag  = math.sin(theta) * 0.1
    return complex(real, imag)


# ── Azoth derivation ──────────────────────────────────────────────────────────

def _derive_azoth(layer_densities: dict[int, float], coil_position: float, flag_weight: float) -> complex:
    """
    Derive Azoth (the player's experiential state) as a complex number.

    Real part: mean density across Lotus layers (1–8) — material ground
    Imaginary part: mean density across Rose layers (9–16) — relational state
    Both modulated by Sakura layers (17–24) as orientation scale factor.
    Flag weight adds a spiral contribution (bounded).
    """
    lotus_vals  = [layer_densities.get(i, 0.5) for i in range(1, 9)]
    rose_vals   = [layer_densities.get(i, 0.5) for i in range(9, 17)]
    sakura_vals = [layer_densities.get(i, 0.5) for i in range(17, 25)]

    lotus_mean  = statistics.mean(lotus_vals)
    rose_mean   = statistics.mean(rose_vals)
    sakura_mean = statistics.mean(sakura_vals)

    # Scale both axes by orientation (sakura)
    real = lotus_mean * sakura_mean * 4.0 - 2.0   # map to [-2, 2]
    imag = rose_mean  * sakura_mean * 4.0 - 2.0

    # Flag weight adds a bounded spiral offset
    spiral = flag_weight * 0.05
    return complex(real + spiral, imag + spiral)


# ── Mandelbrot iteration ──────────────────────────────────────────────────────

_MAX_ITERATIONS = 256


def _mandelbrot_iterations(z0: complex, c: complex, max_iter: int = _MAX_ITERATIONS) -> int:
    """
    Standard Mandelbrot iteration: z_{n+1} = z_n² + c, starting at z₀ = Azoth.
    Returns iteration count before escape (or max_iter if bounded).
    """
    z = z0
    for n in range(max_iter):
        if abs(z) > 2.0:
            return n
        z = z * z + c
    return max_iter


def _orbit_signature(z0: complex, c: complex, max_iter: int = _MAX_ITERATIONS) -> str:
    """
    Hash of the iteration trajectory (orbit) starting from z₀.
    Samples early iterations and periodic checkpoints — two players who reach
    the same boundedness through different paths produce different signatures.
    """
    z = z0
    escaped = False
    escape_iter = max_iter
    samples: list[tuple[int, float, float]] = []
    for n in range(max_iter):
        if abs(z) > 2.0:
            escaped = True
            escape_iter = n
            break
        if n < 16 or n % 32 == 0:
            samples.append((n, round(z.real, 6), round(z.imag, 6)))
        z = z * z + c
    samples.append((escape_iter, round(z.real, 6), round(z.imag, 6)))
    payload = json.dumps(
        {"samples": samples, "escaped": escaped, "escape_iter": escape_iter},
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _render_mandelbrot(azoth: complex, gaoh_c: complex, size: int = 32) -> list[list[int]]:
    """
    Render a size×size grid around the player's Azoth position.
    Returns a 2D list of iteration counts (0–256).
    This is the raw data; visual rendering is a UI concern.
    """
    grid: list[list[int]] = []
    step = 0.1
    for row in range(size):
        line: list[int] = []
        for col in range(size):
            # Sample a small neighbourhood around Azoth
            z0 = complex(
                azoth.real + (col - size // 2) * step,
                azoth.imag + (row - size // 2) * step,
            )
            line.append(_mandelbrot_iterations(z0, gaoh_c))
        grid.append(line)
    return grid


# ── BreathOfKo ────────────────────────────────────────────────────────────────

@dataclass
class BreathOfKo:
    """
    The player's cross-game ontological state.

    Parameters
    ----------
    layer_densities:
        24-layer correspondence densities [0.0–1.0].
    flagged_states:
        Active KoFlag IDs (via FlagState.active_flags()).
    dream_calibrations:
        One DreamCalibration per game played.
    coil_position:
        Current position on the Möbius coil [0.0–12.0].
    flag_state:
        Live FlagState tracker.
    """
    layer_densities:    dict[int, float]             = field(default_factory=lambda: {i: 0.5 for i in range(1, 25)})
    dream_calibrations: list[DreamCalibration]       = field(default_factory=list)
    coil_position:      float                        = 6.0
    flag_state:         FlagState                    = field(default_factory=FlagState)
    # Last known patron of kills and patron of deaths — cosmologically significant
    # entity IDs; None until at least one game session has been integrated.
    kill_patron_id:     Optional[str]                = None
    death_patron_id:    Optional[str]                = None

    def azoth(self) -> complex:
        return _derive_azoth(
            self.layer_densities,
            self.coil_position,
            self.flag_state.modification_weight(len(self.dream_calibrations)),
        )

    def gaoh_constant(self) -> complex:
        return _gaoh_constant(self.coil_position)

    def mandelbrot_grid(self, size: int = 32) -> list[list[int]]:
        """Render the save-state Mandelbrot grid. Same inputs = same image."""
        return _render_mandelbrot(self.azoth(), self.gaoh_constant(), size)

    def boundedness(self) -> str:
        """
        Interpret the player's Azoth position:
          bounded    — integrated experience, coherent
          edge       — living philosophical inquiry (most beautiful saves here)
          unbounded  — accumulation without comprehension
        """
        iters = _mandelbrot_iterations(self.azoth(), self.gaoh_constant())
        if iters >= _MAX_ITERATIONS:
            return "bounded"
        elif iters >= _MAX_ITERATIONS // 2:
            return "edge"
        else:
            return "unbounded"

    def integrate_calibration(
        self,
        calibration: DreamCalibration,
        *,
        kill_patron_id: Optional[str] = None,
        death_patron_id: Optional[str] = None,
    ) -> None:
        """
        Merge a new DreamCalibration into the BreathOfKo.
        Updates layer densities as a rolling average.
        Advances coil position by one game increment.

        Parameters
        ----------
        kill_patron_id:
            Entity ID of the patron of this game's kills (e.g. "negaya").
            Overwrites if provided — the most recent game's patron persists.
        death_patron_id:
            Entity ID of the patron of this game's deaths (e.g. "ohadame").
            Overwrites if provided.
        """
        self.dream_calibrations.append(calibration)

        # Rolling average of layer densities
        n = len(self.dream_calibrations)
        for idx, density in calibration.layer_densities.items():
            current = self.layer_densities.get(idx, 0.5)
            self.layer_densities[idx] = round((current * (n - 1) + density) / n, 4)

        # Advance coil position
        self.coil_position = (self.coil_position + 12.0 / 31.0) % 12.0

        # Update patron fields if provided
        if kill_patron_id is not None:
            self.kill_patron_id = kill_patron_id
        if death_patron_id is not None:
            self.death_patron_id = death_patron_id

    def apply_game_decay(self) -> None:
        """Call at the end of each game to decay temporary flags."""
        self.flag_state.decay()

    def orbit_signature(self) -> str:
        """Trajectory hash of the current Azoth iteration — path-sensitive."""
        return _orbit_signature(self.azoth(), self.gaoh_constant())

    def snapshot(self) -> dict:
        return {
            "layer_densities":  dict(self.layer_densities),
            "coil_position":    self.coil_position,
            "games_played":     len(self.dream_calibrations),
            "active_flags":     self.flag_state.active_flags(),
            "boundedness":      self.boundedness(),
            "azoth":            [self.azoth().real, self.azoth().imag],
            "orbit_signature":  self.orbit_signature(),
            "kill_patron_id":   self.kill_patron_id,
            "death_patron_id":  self.death_patron_id,
        }
