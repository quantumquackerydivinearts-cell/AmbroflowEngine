"""
Tile Tracer
===========
Records Lotus attestations on tiles as the player moves through the world.

Each tile accumulates a count per Lotus byte (0–23) — the full material
vocabulary of the Shygazun Lotus tongue.  Three byte-pairs are the
canonical mode markers, identified by their ontic separation rather than
their byte-address adjacency:

    Fy  / Pu   (bytes  4 /  5)  Air Initiator / Air Terminator
                                 thought toward / stasis
    Ta  / Zo   (bytes  9 / 16)  Active being   / Absence
                                 presence       / passive non-being
    Sha / Ko   (bytes 15 / 19)  Intellect of spirit / Experience / intuition

These three pairs are the ones with Void Wraith routes.  All other Lotus
bytes (0–3, 6–8, 10–14, 17–18, 20–23) fire a general ``tile.attested``
Orrery record with no wraith routing.

Wraith routing
--------------
    Fy / Pu   → Haldoro  2001_VDWR  "silence"   Knower of Minds
    Ta / Zo   → Negaya   2003_VDWR  "kill"       Knower of Bodies
    Sha / Ko  → Vios     2002_VDWR  "omission"   Knower of Souls

Persistence
-----------
``as_dict()`` / ``from_dict()`` round-trip for inclusion in Orrery workspace.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

# ── Lotus Table (bytes 0–23) ──────────────────────────────────────────────────

LOTUS_TABLE: dict[int, tuple[str, str]] = {
    0:  ("Ty",  "Earth Initiator / material beginning"),
    1:  ("Zu",  "Earth Terminator / empirical closure"),
    2:  ("Ly",  "Water Initiator / feeling toward"),
    3:  ("Mu",  "Water Terminator / memory from"),
    4:  ("Fy",  "Air Initiator / thought toward"),
    5:  ("Pu",  "Air Terminator / stasis / stuck"),
    6:  ("Shy", "Fire Initiator / pattern toward"),
    7:  ("Ku",  "Fire Terminator / death / end"),
    8:  ("Ti",  "Here / near presence"),
    9:  ("Ta",  "Active being / presence"),
    10: ("Li",  "New / odd"),
    11: ("La",  "Tense / excited"),
    12: ("Fi",  "Known / context-sensitive"),
    13: ("Fa",  "Complex / old"),
    14: ("Shi", "Related / clear"),
    15: ("Sha", "Intellect of spirit"),
    16: ("Zo",  "Absence / passive non-being"),
    17: ("Mo",  "Relaxed / silent"),
    18: ("Po",  "Simple / new"),
    19: ("Ko",  "Experience / intuition"),
    20: ("Ze",  "There / far"),
    21: ("Me",  "Familiar / home"),
    22: ("Pe",  "Unknown / insensitive"),
    23: ("Ke",  "Incoherent / ill"),
}

# Byte-address constants for the three obversion pairs with wraith routes
FY:  int = 4   # Air Initiator / thought toward
PU:  int = 5   # Air Terminator / stasis
TA:  int = 9   # Active being / presence
ZO:  int = 16  # Absence / passive non-being
SHA: int = 15  # Intellect of spirit
KO:  int = 19  # Experience / intuition

# ── Wraith routing ────────────────────────────────────────────────────────────
# Only the three obversion pairs have wraith routes.
# (wraith_id, orrery_observation_key)

_WRAITH_ROUTES: dict[int, tuple[str, str]] = {
    FY:  ("2001_VDWR", "silence"),    # Fy  → Haldoro
    PU:  ("2001_VDWR", "silence"),    # Pu  → Haldoro
    TA:  ("2003_VDWR", "kill"),       # Ta  → Negaya
    ZO:  ("2003_VDWR", "kill"),       # Zo  → Negaya
    SHA: ("2002_VDWR", "omission"),   # Sha → Vios
    KO:  ("2002_VDWR", "omission"),   # Ko  → Vios
}


# ── Data ──────────────────────────────────────────────────────────────────────

@dataclass
class TileAttestation:
    zone_id:      str
    x:            int
    y:            int
    lotus_counts: dict[int, int]   = field(default_factory=dict)
    first_at:     dict[int, float] = field(default_factory=dict)
    last_at:      float            = 0.0

    # ── Queries ───────────────────────────────────────────────────────────────

    def count(self, byte_addr: int) -> int:
        return self.lotus_counts.get(byte_addr, 0)

    def has(self, byte_addr: int) -> bool:
        return self.lotus_counts.get(byte_addr, 0) > 0

    @property
    def attested_bytes(self) -> frozenset[int]:
        return frozenset(k for k, v in self.lotus_counts.items() if v > 0)

    def dominant(self, n: int = 3) -> list[int]:
        """Return the top-n most-attested Lotus byte addresses."""
        return sorted(
            self.lotus_counts,
            key=lambda b: self.lotus_counts[b],
            reverse=True,
        )[:n]

    def symbol(self, byte_addr: int) -> str:
        return LOTUS_TABLE[byte_addr][0] if byte_addr in LOTUS_TABLE else "?"

    # ── Persistence ───────────────────────────────────────────────────────────

    def as_dict(self) -> dict:
        return {
            "lotus":    {str(k): v for k, v in self.lotus_counts.items()},
            "first_at": {str(k): v for k, v in self.first_at.items()},
            "last_at":  self.last_at,
        }

    @classmethod
    def from_dict(cls, zone_id: str, x: int, y: int, d: dict) -> "TileAttestation":
        return cls(
            zone_id=zone_id, x=x, y=y,
            lotus_counts={int(k): v for k, v in d.get("lotus", {}).items()},
            first_at=    {int(k): v for k, v in d.get("first_at", {}).items()},
            last_at=     d.get("last_at", 0.0),
        )


# ── Tracer ────────────────────────────────────────────────────────────────────

class TileTracer:
    """
    Accumulates Lotus attestations per tile and routes to the Orrery.

    Parameters
    ----------
    orrery:
        OrreryClient.  When provided, each deposit fires:
          - ``tile.attested``        — general record (every byte)
          - ``void_wraith_observe``  — only for the 6 wraith-routed bytes
    """

    def __init__(self, orrery: object = None) -> None:
        self._tiles:  dict[tuple[str, int, int], TileAttestation] = {}
        self._orrery = orrery

    # ── Deposit ───────────────────────────────────────────────────────────────

    def deposit(
        self,
        zone_id: str,
        x: int,
        y: int,
        *byte_addrs: int,
        context: Optional[dict] = None,
    ) -> TileAttestation:
        """
        Deposit one or more Lotus byte attestations on a tile.

        Parameters
        ----------
        *byte_addrs:
            One or more Lotus byte addresses (0–23).
        context:
            Optional extra data attached to the Orrery event.
        """
        for b in byte_addrs:
            if b not in LOTUS_TABLE:
                raise ValueError(
                    f"Byte address {b} is not in the Lotus Table (0–23).")

        key = (zone_id, x, y)
        att = self._tiles.get(key)
        if att is None:
            att = TileAttestation(zone_id=zone_id, x=x, y=y)
            self._tiles[key] = att

        now = time.time()
        att.last_at = now

        for b in byte_addrs:
            prev = att.lotus_counts.get(b, 0)
            att.lotus_counts[b] = prev + 1
            if prev == 0:
                att.first_at[b] = now

            symbol, meaning = LOTUS_TABLE[b]
            payload = {
                "zone_id": zone_id,
                "x":       x,
                "y":       y,
                "byte":    b,
                "symbol":  symbol,
                "meaning": meaning,
                "count":   att.lotus_counts[b],
                **(context or {}),
            }

            if self._orrery is not None:
                try:
                    self._orrery.record("tile.attested", payload)
                    route = _WRAITH_ROUTES.get(b)
                    if route is not None:
                        wraith_id, obs_key = route
                        self._orrery.void_wraith_observe(
                            obs_key, {**payload, "wraith_id": wraith_id})
                except Exception:
                    pass

        return att

    # ── Reads ─────────────────────────────────────────────────────────────────

    def attestation_at(self, zone_id: str, x: int, y: int) -> Optional[TileAttestation]:
        return self._tiles.get((zone_id, x, y))

    def attested_bytes_at(self, zone_id: str, x: int, y: int) -> frozenset[int]:
        att = self._tiles.get((zone_id, x, y))
        return att.attested_bytes if att else frozenset()

    def attested_tiles(self, byte_addr: Optional[int] = None) -> list[tuple[str, int, int]]:
        if byte_addr is None:
            return list(self._tiles.keys())
        return [k for k, v in self._tiles.items() if v.has(byte_addr)]

    def wraith_context(self, zone_id: str, x: int, y: int) -> dict:
        """
        Full Lotus signature of a tile for the dialogue selector.

        Returns counts for the three mode-marker pairs (Fy/Pu, Ta/Zo, Sha/Ko),
        the dominant bytes, and the complete lotus_counts dict.
        """
        att = self._tiles.get((zone_id, x, y))
        if att is None:
            return {
                "lotus":   {},
                "dominant": [],
                "fy": 0, "pu": 0,
                "ta": 0, "zo": 0,
                "sha": 0, "ko": 0,
            }
        return {
            "lotus":   dict(att.lotus_counts),
            "dominant": [
                {"byte": b, "symbol": LOTUS_TABLE[b][0], "count": att.lotus_counts[b]}
                for b in att.dominant(3)
            ],
            "fy":  att.count(FY),
            "pu":  att.count(PU),
            "ta":  att.count(TA),
            "zo":  att.count(ZO),
            "sha": att.count(SHA),
            "ko":  att.count(KO),
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def as_dict(self) -> dict:
        return {
            f"{zone_id}:{x},{y}": att.as_dict()
            for (zone_id, x, y), att in self._tiles.items()
        }

    @classmethod
    def from_dict(cls, data: dict, orrery: object = None) -> "TileTracer":
        tracer = cls(orrery=orrery)
        for key_str, vals in data.items():
            zone_id, coords = key_str.split(":", 1)
            x_str, y_str   = coords.split(",", 1)
            tracer._tiles[(zone_id, int(x_str), int(y_str))] = (
                TileAttestation.from_dict(zone_id, int(x_str), int(y_str), vals)
            )
        return tracer

    def kill_count(self) -> int:
        """Total ZO (absence) deposits across all tiles.  Each player kill deposits one ZO."""
        return sum(att.lotus_counts.get(ZO, 0) for att in self._tiles.values())

    def __len__(self) -> int:
        return len(self._tiles)