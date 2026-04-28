"""
World Zone Registry
===================
Zone builders for each game / realm.  The public entry point is
`build_game7_world()` which returns a fully-assembled WorldMap for
Ko's Labyrinth (7_KLGS).
"""

from __future__ import annotations

from ..map import WorldMap
from .lapidus import (
    build_wiltoll_lane,
    build_wiltoll_home,
    build_market_interior,
    build_litleaf_thoroughfare,
    build_azonithia_slum,
    build_azonithia_market,
    build_azonithia_temple,
    build_azonithia_heartvein,
    build_azoth_approach,
    build_castle_azoth,
    build_mt_elaene_trail,
)


def build_game7_world() -> WorldMap:
    """
    Assemble the starter world for Ko's Labyrinth (7_KLGS).

    Zone chain (West → East along Azonithia Avenue):
        lapidus_castle_azoth            Castle Azoth courtyard + zodiac fountain
          ↕ N (marble sprint)
        lapidus_azoth_approach          Orchard + Azoth Sprint
        lapidus_azonithia_heartvein     Youthspring Road / silica (nobles)
        lapidus_azonithia_temple        Goldshoot Street / slate (temple)
        lapidus_azonithia_market        June Street / ceramic (market)
        lapidus_azonithia_slum          Hopefare Street / yellow brick (slums)
        lapidus_wiltoll_lane            Player home — starting zone
          ↕ N (Litleaf fork)
        lapidus_litleaf_thoroughfare    N–S connecting road
          ↕ E
        lapidus_mt_elaene_trail         Forest trail toward Mt. Elaene

    Stubs (show "(nothing that way yet)"):
        lapidus_dirt_trail              West of Castle Azoth — ocean-bound trail
        lapidus_slum_interior           Azonithia Slum (9 warrens / 13 passages)
        lapidus_market_interior         Market district interior
        lapidus_temple_interior         Temple of the Gods
        lapidus_heartvein_interior      Heartvein Heights
        lapidus_mt_elaene_summit        Mt. Elaene / Elaene desert gateway
    """
    zones_list = [
        build_wiltoll_lane(),
        build_wiltoll_home(),
        build_market_interior(),
        build_litleaf_thoroughfare(),
        build_azonithia_slum(),
        build_azonithia_market(),
        build_azonithia_temple(),
        build_azonithia_heartvein(),
        build_azoth_approach(),
        build_castle_azoth(),
        build_mt_elaene_trail(),
    ]

    return WorldMap(
        zones={z.zone_id: z for z in zones_list},
        starting_zone_id="lapidus_wiltoll_lane",
    )