"""
World Zone Registry
===================
Zone builders for each game / realm.  The public entry point is
`build_game7_world()` which returns a fully-assembled WorldMap for
Ko's Labyrinth (7_KLGS).
"""

from __future__ import annotations

from ..map import WorldMap
from .lapidus import build_wiltoll_lane, build_market_district


def build_game7_world() -> WorldMap:
    """
    Assemble the starter world for Ko's Labyrinth (7_KLGS).

    Zones registered:
        lapidus_wiltoll_ext  — Wiltoll Lane exterior (starting zone)
        lapidus_market       — Market district stub

    The player begins inside their home on Wiltoll Lane.
    """
    wiltoll = build_wiltoll_lane()
    market  = build_market_district()

    return WorldMap(
        zones={
            wiltoll.zone_id: wiltoll,
            market.zone_id:  market,
        },
        starting_zone_id=wiltoll.zone_id,
    )