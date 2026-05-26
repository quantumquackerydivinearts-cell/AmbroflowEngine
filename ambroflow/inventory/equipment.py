"""
Equipment slot manager.

Tracks what the player has equipped across five slots:
  weapon, armor, ring_1, ring_2, clothes.

Items are classified by KLIT ID.  Non-equippable items raise ValueError
on equip().  Rings fill ring_1 first, then ring_2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


WEAPON_ITEMS: frozenset[str] = frozenset({
    "0017_KLIT",  # Dagger
    "0018_KLIT",  # Sword
    "0020_KLIT",  # Bow
    "0022_KLIT",  # Staff
    "0024_KLIT",  # Angelic Spear
    "0025_KLIT",  # Angelic Gun
    "0026_KLIT",  # Demonic Irons
    "0027_KLIT",  # Hypatia's Dagger
})

ARMOR_ITEMS: frozenset[str] = frozenset({
    "0019_KLIT",  # Shield
})

RING_ITEMS: frozenset[str] = frozenset({
    "0013_KLIT",  # Necklace
    "0014_KLIT",  # Ring
})

CLOTHES_ITEMS: frozenset[str] = frozenset()

EQUIPPABLE: frozenset[str] = WEAPON_ITEMS | ARMOR_ITEMS | RING_ITEMS | CLOTHES_ITEMS

SLOT_ORDER = ("weapon", "armor", "ring_1", "ring_2", "clothes")

SLOT_LABELS: dict[str, str] = {
    "weapon":  "Weapon",
    "armor":   "Armor",
    "ring_1":  "Ring I",
    "ring_2":  "Ring II",
    "clothes": "Clothes",
}


def slot_for(item_id: str) -> Optional[str]:
    """Return the base slot name for an item, or None if not equippable."""
    if item_id in WEAPON_ITEMS:
        return "weapon"
    if item_id in ARMOR_ITEMS:
        return "armor"
    if item_id in RING_ITEMS:
        return "ring_1"
    if item_id in CLOTHES_ITEMS:
        return "clothes"
    return None


@dataclass
class EquipmentSlots:
    weapon:  Optional[str] = None
    armor:   Optional[str] = None
    ring_1:  Optional[str] = None
    ring_2:  Optional[str] = None
    clothes: Optional[str] = None

    def get(self, slot: str) -> Optional[str]:
        return getattr(self, slot, None)

    def equip(self, item_id: str) -> tuple[str, Optional[str]]:
        """
        Equip item_id into the appropriate slot.
        Returns (slot_name, displaced_item_or_None).
        Rings: fill ring_1 first; if occupied fill ring_2; if both occupied displace ring_1.
        """
        base = slot_for(item_id)
        if base is None:
            raise ValueError(f"{item_id!r} is not equippable")

        if base == "ring_1":
            if self.ring_1 is None:
                slot = "ring_1"
            elif self.ring_2 is None:
                slot = "ring_2"
            else:
                slot = "ring_1"
        else:
            slot = base

        displaced = getattr(self, slot)
        setattr(self, slot, item_id)
        return slot, displaced

    def unequip(self, slot: str) -> Optional[str]:
        """Remove and return the item in slot (None if empty)."""
        item = getattr(self, slot, None)
        if item is not None:
            setattr(self, slot, None)
        return item

    def as_dict(self) -> dict[str, Optional[str]]:
        return {s: self.get(s) for s in SLOT_ORDER}

    @classmethod
    def from_dict(cls, d: dict) -> "EquipmentSlots":
        return cls(
            weapon=d.get("weapon"),
            armor=d.get("armor"),
            ring_1=d.get("ring_1"),
            ring_2=d.get("ring_2"),
            clothes=d.get("clothes"),
        )
