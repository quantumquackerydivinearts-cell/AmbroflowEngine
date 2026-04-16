"""
Inventory Manager
=================
Tracks item quantities for a player in a session.

Stackable items (marked with `()` prefix in game7Registry.js) are stored as
integer quantities.  Non-stackable items have quantity 1 and raise on add
if already held.

The inventory is not persisted by the engine — it is passed in at session
start from the saved state (stored in the Orrery workspace).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class ItemStack:
    item_id: str
    quantity: int
    stackable: bool


class Inventory:
    """
    In-session item inventory.

    Parameters
    ----------
    initial:
        Initial state as {item_id: quantity}.
    stackable_items:
        Set of item IDs that are stackable.  Others default to non-stackable.
    """

    def __init__(
        self,
        initial: dict[str, int] | None = None,
        stackable_items: set[str] | None = None,
    ) -> None:
        self._items: dict[str, int] = dict(initial or {})
        self._stackable = set(stackable_items or [])

    def is_stackable(self, item_id: str) -> bool:
        return item_id in self._stackable

    def quantity(self, item_id: str) -> int:
        return self._items.get(item_id, 0)

    def has(self, item_id: str, qty: int = 1) -> bool:
        return self._items.get(item_id, 0) >= qty

    def add(self, item_id: str, qty: int = 1) -> None:
        if qty <= 0:
            return
        if not self.is_stackable(item_id) and self.quantity(item_id) > 0 and qty > 0:
            raise ValueError(f"Non-stackable item already held: {item_id!r}")
        self._items[item_id] = self._items.get(item_id, 0) + qty

    def remove(self, item_id: str, qty: int = 1) -> None:
        current = self._items.get(item_id, 0)
        if current < qty:
            raise ValueError(f"Not enough {item_id!r} (have {current}, need {qty})")
        new_qty = current - qty
        if new_qty == 0:
            del self._items[item_id]
        else:
            self._items[item_id] = new_qty

    def as_dict(self) -> dict[str, int]:
        return dict(self._items)

    def __iter__(self) -> Iterator[tuple[str, int]]:
        return iter(self._items.items())

    def __len__(self) -> int:
        return len(self._items)
