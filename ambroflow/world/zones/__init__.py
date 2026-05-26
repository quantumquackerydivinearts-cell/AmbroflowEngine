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
    build_market_interior,
    build_litleaf_thoroughfare,
    build_azonithia_slum,
    build_azonithia_market,
    build_azonithia_temple,
    build_azonithia_heartvein,
    build_azoth_approach,
    build_castle_azoth,
    build_mt_elaene_trail,
    build_serpents_pass,
    build_witch_forest,
    build_ocean_shore,
    build_dirt_trail,
    build_the_rocks,
    build_orebustle_road,
    build_mine_entrance,
    build_elsa_house,
    build_hypatia_house,
    # Kobra-built zones
    build_hopefare_junction,
    build_june_quarter,
    build_goldshoot_street,
    build_temple_interior,
    build_youthspring_road,
    # Castle Azoth interior floors
    build_castle_main_hall,
    build_castle_first_floor,
    build_castle_second_floor,
    build_castle_basement,
    build_castle_hypatia_tower,
    build_castle_canopy,
)
from .mercurie import (
    build_mercurie_threshold,
    build_tideglass,
    build_cindergrove,
    build_rootbloom,
    build_thornveil,
    build_dewspire,
)
from .sulphera import (
    build_visitor_ring,
    build_sulphera_ring_entries,
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
        lapidus_wiltoll_lane            Player home lane — starting zone
          ↕ N (home door cols 3-4, row 8)
        player_home_ground              Player home interior (48 × 13, Kobra-canonical)
          ↕ stair up (11, 2)
        player_home_upper               Study / Library (upper floor, 48 × 10)

    Stubs (show "(nothing that way yet)"):
        lapidus_slum_interior           Azonithia Slum (9 warrens / 13 passages)
        lapidus_market_interior         Market district interior
        lapidus_temple_interior         Temple of the Gods interior (Saffron, Lucion)
        lapidus_heartvein_interior      Heartvein Heights
        lapidus_mt_elaene_summit        Mt. Elaene / Elaene desert gateway
    """
    from ...scenes.home_zone import PLAYER_HOME_GROUND, PLAYER_HOME_UPPER
    from .warrens import build_all_warren_zones

    zones_list = [
        # Lapidus — exterior
        build_wiltoll_lane(),
        # Canonical home (Kobra-generated, replaces lapidus_wiltoll_home)
        PLAYER_HOME_GROUND,
        PLAYER_HOME_UPPER,
        # Warren district — 9 warrens + Cestii Alley + Serpent's Pass
        *build_all_warren_zones(),
        build_market_interior(),
        # Kobra-built street zones
        build_hopefare_junction(),
        build_june_quarter(),
        build_goldshoot_street(),
        build_temple_interior(),
        build_youthspring_road(),
        build_litleaf_thoroughfare(),
        build_azonithia_slum(),
        build_azonithia_market(),
        build_azonithia_temple(),
        build_azonithia_heartvein(),
        build_azoth_approach(),
        build_castle_azoth(),
        build_castle_main_hall(),
        build_castle_first_floor(),
        build_castle_second_floor(),
        build_castle_basement(),
        build_castle_hypatia_tower(),
        build_castle_canopy(),
        build_mt_elaene_trail(),
        build_serpents_pass(),
        build_witch_forest(),
        build_ocean_shore(),
        build_dirt_trail(),
        build_the_rocks(),
        build_orebustle_road(),
        build_mine_entrance(),
        build_elsa_house(),
        build_hypatia_house(),
        # Mercurie (gated by hypnotic_meditation / 0007_KLST)
        build_mercurie_threshold(),
        build_tideglass(),
        build_cindergrove(),
        build_rootbloom(),
        build_thornveil(),
        build_dewspire(),
        # Sulphera (gated by infernal_meditation / 0010_KLST)
        build_visitor_ring(),
        *build_sulphera_ring_entries(),
    ]
    return WorldMap(
        zones={z.zone_id: z for z in zones_list},
        starting_zone_id="lapidus_wiltoll_lane",
    )