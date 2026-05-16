"""
key_registry.py — Shygazun-native key registry for the key-lock system.

A YeigoLo (Yei+Go+Lo — integrating blocker segmented by identity) is the
canonical definition of a key in the key-lock system. Its primary identity
is an Akinenwun — a Shygazun word composed from phonological primitives
that enacts its meaning before the word is complete.

The KeyRegistry is the single authoritative source for all keys across all
31 games. Nothing gets granted or checked that is not pre-declared here.

Field derivations:
  yeigo     Yei(Component/Integrator) + Go(Plug/Blocker)
              — the integrating blocker; the key as structural primitive
  shakshi   Shak(Fire,AppleBlossom) + Shi(Space+·Fire,Lotus)
              — fire-clarity of relation; what the key discloses
  kaelsuy   Kael(Cluster/Fruit,Daisy) + Su(Loop time,Aster) + Y(Time+)
              — a fruit in looping Time+; game as repeatable temporal cluster
  dyne      Dy(Hence/Heretofore,Sakura) + Ne(Network/System,Daisy)
              — the network that broadcasts forward from this point
  anom      A(Mind+) + N(Seed,Daisy) + O(Mind−) + M(Water terminator)
              — Mind+ seed absorbed into Mind− carried by memory;
                unconscious transmission / spoiler as chiral awareness
  andyf     A(Mind+) + N(Seed) + Dy(Hence) + F(Air initiator,Lotus)
              — Mind+ seed reaching hence toward thought;
                reversibility as indeterminate forward reach
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class YeigoLo:
    yeigo:    str            # Akinenwun — canonical Shygazun identity
    shakshi:  str            # meaning — English gloss derived from composition
    kaelsuy:  str            # game_slug — e.g. "7_KLGS"
    dyne:     bool = False   # propagates — broadcasts forward across games
    anom:     bool = False   # spoiler — unconscious transmission / chiral awareness
    andyf:    bool = False   # reversible — indeterminate forward reach via Va

    @classmethod
    def from_dict(cls, d: dict) -> "YeigoLo":
        return cls(
            yeigo   = d["yeigo"],
            shakshi = d["shakshi"],
            kaelsuy = d["kaelsuy"],
            dyne    = d.get("dyne",  False),
            anom    = d.get("anom",  False),
            andyf   = d.get("andyf", False),
        )

    def to_dict(self) -> dict:
        return {
            "yeigo":   self.yeigo,
            "shakshi": self.shakshi,
            "kaelsuy": self.kaelsuy,
            "dyne":    self.dyne,
            "anom":    self.anom,
            "andyf":   self.andyf,
        }


# ── KeyRegistry ───────────────────────────────────────────────────────────────

class KeyRegistry:
    """
    Single authoritative source for all YeigoLo across all 31 games.

    Keys are indexed by their Akinenwun (yeigo field).
    Validation rejects any key not pre-declared here.
    """

    def __init__(self) -> None:
        self._keys: dict[str, YeigoLo] = {}

    def register(self, defn: YeigoLo) -> None:
        if defn.yeigo in self._keys:
            raise ValueError(
                f"Duplicate Akinenwun: {defn.yeigo!r} "
                f"(already registered for {self._keys[defn.yeigo].kaelsuy})"
            )
        self._keys[defn.yeigo] = defn

    def validate(self, yeigo: str) -> str:
        """Validate an Akinenwun. Raises if not registered. Returns yeigo."""
        if yeigo not in self._keys:
            raise ValueError(
                f"Undeclared Akinenwun: {yeigo!r} — "
                f"register it in keys/ before use"
            )
        return yeigo

    def get(self, yeigo: str) -> Optional[YeigoLo]:
        return self._keys.get(yeigo)

    def keys_for_game(self, kaelsuy: str) -> list[YeigoLo]:
        return [d for d in self._keys.values() if d.kaelsuy == kaelsuy]

    def propagating(self) -> list[YeigoLo]:
        return [d for d in self._keys.values() if d.dyne]

    def reversible(self) -> list[YeigoLo]:
        return [d for d in self._keys.values() if d.andyf]

    def __len__(self) -> int:
        return len(self._keys)

    def __contains__(self, yeigo: str) -> bool:
        return yeigo in self._keys


# ── Loader ────────────────────────────────────────────────────────────────────

def load_registry(keys_dir: str | Path) -> KeyRegistry:
    """
    Load all YeigoLo from *.json files in keys_dir.

    Each file is a JSON array of YeigoLo dicts.
    Files are loaded in sorted order so load sequence is deterministic.
    Duplicate Akinenwun across files raises immediately.
    """
    registry = KeyRegistry()
    keys_path = Path(keys_dir)

    if not keys_path.exists():
        return registry

    for path in sorted(keys_path.glob("*.json")):
        entries = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            raise ValueError(f"{path}: expected JSON array, got {type(entries).__name__}")
        for entry in entries:
            registry.register(YeigoLo.from_dict(entry))

    return registry


# ── Global instance ───────────────────────────────────────────────────────────
# Populated by calling load_registry() at engine startup.
# Tests may construct their own KeyRegistry directly.

_REGISTRY: Optional[KeyRegistry] = None


def global_registry() -> KeyRegistry:
    """Return the global registry. Raises if not yet loaded."""
    if _REGISTRY is None:
        raise RuntimeError(
            "KeyRegistry not loaded — call init_registry() at startup"
        )
    return _REGISTRY


def init_registry(keys_dir: str | Path) -> KeyRegistry:
    """Load and install the global registry from keys_dir."""
    global _REGISTRY
    _REGISTRY = load_registry(keys_dir)
    return _REGISTRY
