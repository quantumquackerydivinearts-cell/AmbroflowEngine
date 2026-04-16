"""
Dungeon Registry
================
Canonical definitions for all dungeon types in the KLGS series.

Sulphera ring traversal order: 8 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 9
  Ring 8  = Visitor's Ring (entry point; requires infernal_meditation perk)
  Rings 1–7 = Sin Rings, each locked by the previous ring's token
  Ring 9  = Royal Ring (requires all 8 prior rings cleared)

Token chain:
  infernal_meditation perk → Ring 8 (inciting token from 0009_KLST)
  Ring 8 cleared → Lucifer token → Ring 1
  Ring 1 cleared → Mammon token → Ring 2
  ... etc.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DungeonDef:
    id: str
    name: str
    realm: str                        # "sulphera" | "faewilds" | "overworld"
    dungeon_type: str                 # "sulphera_ring" | "fae" | "mine"
    floor_count: int
    encounter_density: float          # 0.0–1.0
    # Access gating
    requires_perk: Optional[str] = None
    locked_by_token: Optional[str] = None
    grants_token: Optional[str] = None
    # Ring-specific
    ring_number: Optional[int] = None
    ring_order: Optional[int] = None  # traversal position (1=first entered, 9=last)
    sin_ruler: Optional[str] = None
    sin_name: Optional[str] = None
    # Tile composition overrides (beyond defaults)
    special_tiles: list[str] = field(default_factory=list)


# ── Sulphera Rings ─────────────────────────────────────────────────────────────

RING_VISITOR = DungeonDef(
    id="sulphera_ring_visitor",
    name="Visitor's Ring",
    realm="sulphera",
    dungeon_type="sulphera_ring",
    ring_number=8,
    ring_order=1,
    floor_count=3,
    encounter_density=0.4,
    requires_perk="infernal_meditation",   # The perk IS the gate; no token needed
    grants_token="ring.visitor.token.granted",
    special_tiles=["infernal_altar"],
)

SINNERS_RINGS: list[DungeonDef] = [
    DungeonDef(
        id="sulphera_ring_pride",
        name="Ring of Pride",
        realm="sulphera",
        dungeon_type="sulphera_ring",
        ring_number=1, ring_order=2,
        sin_ruler="Lucifer", sin_name="pride",
        floor_count=5, encounter_density=0.55,
        locked_by_token="ring.visitor.token.granted",
        grants_token="ring.pride.token.granted",
        special_tiles=["throne_of_pride"],
    ),
    DungeonDef(
        id="sulphera_ring_greed",
        name="Ring of Greed",
        realm="sulphera",
        dungeon_type="sulphera_ring",
        ring_number=2, ring_order=3,
        sin_ruler="Mammon", sin_name="greed",
        floor_count=5, encounter_density=0.55,
        locked_by_token="ring.pride.token.granted",
        grants_token="ring.greed.token.granted",
        special_tiles=["vault_of_mammon"],
    ),
    DungeonDef(
        id="sulphera_ring_envy",
        name="Ring of Envy",
        realm="sulphera",
        dungeon_type="sulphera_ring",
        ring_number=3, ring_order=4,
        sin_ruler="Leviathan", sin_name="envy",
        floor_count=5, encounter_density=0.6,
        locked_by_token="ring.greed.token.granted",
        grants_token="ring.envy.token.granted",
        special_tiles=["mirror_of_leviathan"],
    ),
    DungeonDef(
        id="sulphera_ring_gluttony",
        name="Ring of Gluttony",
        realm="sulphera",
        dungeon_type="sulphera_ring",
        ring_number=4, ring_order=5,
        sin_ruler="Beelzebub", sin_name="gluttony",
        floor_count=5, encounter_density=0.65,
        locked_by_token="ring.envy.token.granted",
        grants_token="ring.gluttony.token.granted",
        special_tiles=["banquet_of_beelzebub"],
    ),
    DungeonDef(
        id="sulphera_ring_sloth",
        name="Ring of Sloth",
        realm="sulphera",
        dungeon_type="sulphera_ring",
        ring_number=5, ring_order=6,
        sin_ruler="Belphegor", sin_name="sloth",
        floor_count=5, encounter_density=0.5,
        locked_by_token="ring.gluttony.token.granted",
        grants_token="ring.sloth.token.granted",
        special_tiles=["belphegor_couch"],
    ),
    DungeonDef(
        id="sulphera_ring_wrath",
        name="Ring of Wrath",
        realm="sulphera",
        dungeon_type="sulphera_ring",
        ring_number=6, ring_order=7,
        sin_ruler="Satan", sin_name="wrath",
        floor_count=6, encounter_density=0.75,
        locked_by_token="ring.sloth.token.granted",
        grants_token="ring.wrath.token.granted",
        special_tiles=["pyre_of_satan"],
    ),
    DungeonDef(
        id="sulphera_ring_lust",
        name="Ring of Lust",
        realm="sulphera",
        dungeon_type="sulphera_ring",
        ring_number=7, ring_order=8,
        sin_ruler="Asmodeus", sin_name="lust",
        floor_count=5, encounter_density=0.6,
        locked_by_token="ring.wrath.token.granted",
        grants_token="ring.lust.token.granted",
        special_tiles=["desire_crystal", "asmodean_shrine"],
    ),
]

RING_ROYAL = DungeonDef(
    id="sulphera_ring_royal",
    name="Royal Ring",
    realm="sulphera",
    dungeon_type="sulphera_ring",
    ring_number=9, ring_order=9,
    floor_count=7, encounter_density=0.3,
    locked_by_token="ring.lust.token.granted",   # Final token; all 8 prior required
    grants_token=None,
    special_tiles=["royal_throne", "royal_audience_chamber"],
)

SULPHERA_RINGS: list[DungeonDef] = [RING_VISITOR, *SINNERS_RINGS, RING_ROYAL]

# ── Fae Dungeons ───────────────────────────────────────────────────────────────

FAE_DUNGEONS: list[DungeonDef] = [
    DungeonDef(
        id="fae_dryad_grove",
        name="Dryad Grove",
        realm="faewilds",
        dungeon_type="fae",
        floor_count=4, encounter_density=0.4,
        special_tiles=["world_tree_root", "sap_pool"],
    ),
    DungeonDef(
        id="fae_undine_deep",
        name="Undine Deep",
        realm="faewilds",
        dungeon_type="fae",
        floor_count=4, encounter_density=0.45,
        special_tiles=["current_gate", "singing_pool"],
    ),
    DungeonDef(
        id="fae_salamander_forge",
        name="Salamander Forge",
        realm="faewilds",
        dungeon_type="fae",
        floor_count=4, encounter_density=0.5,
        special_tiles=["forge", "fire_glyph"],
    ),
    DungeonDef(
        id="fae_gnome_warren",
        name="Gnome Warren",
        realm="faewilds",
        dungeon_type="fae",
        floor_count=5, encounter_density=0.35,
        special_tiles=["deep_tunnel", "gnome_hoard"],
    ),
    DungeonDef(
        id="fae_faerie_court",
        name="Faerie Court",
        realm="faewilds",
        dungeon_type="fae",
        floor_count=3, encounter_density=0.25,
        special_tiles=["court_stage", "mona_altar"],
    ),
]

# ── Mines ──────────────────────────────────────────────────────────────────────

MINES_DUNGEONS: list[DungeonDef] = [
    DungeonDef(
        id="mine_iron",
        name="Iron Mine",
        realm="overworld",
        dungeon_type="mine",
        floor_count=3, encounter_density=0.3,
        special_tiles=["ore_vein", "forge_access"],
    ),
    DungeonDef(
        id="mine_silver",
        name="Silver Mine",
        realm="overworld",
        dungeon_type="mine",
        floor_count=4, encounter_density=0.35,
        special_tiles=["silver_vein", "refining_station"],
    ),
    DungeonDef(
        id="mine_gold",
        name="Gold Mine",
        realm="overworld",
        dungeon_type="mine",
        floor_count=5, encounter_density=0.4,
        special_tiles=["gold_vein", "desire_crystal_cache"],
    ),
]

# ── Flat lookup ────────────────────────────────────────────────────────────────

DUNGEON_BY_ID: dict[str, DungeonDef] = {
    d.id: d
    for d in [*SULPHERA_RINGS, *FAE_DUNGEONS, *MINES_DUNGEONS]
}


def get_dungeon(dungeon_id: str) -> DungeonDef:
    d = DUNGEON_BY_ID.get(dungeon_id)
    if d is None:
        raise KeyError(f"Unknown dungeon: {dungeon_id!r}")
    return d


def is_accessible(dungeon: DungeonDef, unlocked_perks: list[str], held_tokens: list[str]) -> tuple[bool, str]:
    """
    Return (accessible, reason).

    Sulphera Ring 8 (Visitor's Ring) requires the infernal_meditation perk.
    All subsequent rings are locked by the previous ring's granted token.
    """
    if dungeon.requires_perk and dungeon.requires_perk not in unlocked_perks:
        return False, f"Requires perk: {dungeon.requires_perk}"
    if dungeon.locked_by_token and dungeon.locked_by_token not in held_tokens:
        return False, f"Locked — requires token: {dungeon.locked_by_token}"
    return True, "accessible"
