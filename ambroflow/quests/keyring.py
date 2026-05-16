"""
keyring.py — The player's key ring.

A KeyRing is a set of granted yeigo strings (Akinenwun) representing
everything the player has witnessed, done, or earned. It is the
runtime face of the key-lock system.

Validation against a KeyRegistry is optional but strongly recommended
for production use — it ensures no undeclared key ever enters the system.

Usage
-----
    from ambroflow.quests.keyring import KeyRing
    from ambroflow.quests.key_registry import global_registry

    ring = KeyRing(registry=global_registry())
    ring.grant("letter_received")        # validated, returns True (new)
    ring.grant("letter_received")        # already held, returns False
    ring.has("letter_received")          # True
    ring.satisfies(lock)                 # checks requires/excludes
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .key_registry import KeyRegistry
    from .schema import Lock


class KeyRing:
    """
    Runtime set of granted yeigo keys for one player.

    Parameters
    ----------
    keys:
        Initial set of yeigo strings already held.
    registry:
        Optional KeyRegistry for validation. If provided, grant() and
        validate_key() reject undeclared yeigo strings with ValueError.
        If None, any string is accepted (useful for tests).
    """

    def __init__(
        self,
        keys: set[str] | None = None,
        registry: Optional["KeyRegistry"] = None,
    ) -> None:
        self._keys:     set[str]                = set(keys or [])
        self._registry: Optional["KeyRegistry"] = registry

        # Validate any pre-loaded keys against the registry
        if registry and self._keys:
            for k in self._keys:
                registry.validate(k)

    # ── Core operations ───────────────────────────────────────────────────────

    def grant(self, key: str) -> bool:
        """
        Grant a key. Returns True if this was a new key, False if already held.
        Raises ValueError if the key is not declared in the registry.
        """
        if self._registry:
            self._registry.validate(key)
        if key in self._keys:
            return False
        self._keys.add(key)
        return True

    def grant_many(self, keys: list[str]) -> list[str]:
        """
        Grant multiple keys. Returns list of newly granted (previously unheld) keys.
        """
        new: list[str] = []
        for k in keys:
            if self.grant(k):
                new.append(k)
        return new

    def has(self, key: str) -> bool:
        return key in self._keys

    def revoke(self, key: str) -> bool:
        """
        Remove a key. Returns True if it was present, False if not.
        Used by Va() restoration logic when a previously held key is cleared.
        """
        if key in self._keys:
            self._keys.discard(key)
            return True
        return False

    # ── Lock evaluation ───────────────────────────────────────────────────────

    def satisfies(self, lock: "Lock") -> bool:
        """
        Return True if the current key set satisfies the given Lock —
        all requires are present and none of the excludes are present.
        Time-window checking is handled by SceneRunner, not KeyRing.
        """
        return (
            all(self.has(k) for k in lock.requires) and
            not any(self.has(k) for k in lock.excludes)
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_list(self) -> list[str]:
        """Return a sorted list of all held keys — suitable for save state."""
        return sorted(self._keys)

    def to_propagating_list(self) -> list[str]:
        """
        Return keys that are declared as propagating in the registry.
        Used when transferring state to the next game in the series.
        """
        if not self._registry:
            return self.to_list()
        return sorted(
            k for k in self._keys
            if (defn := self._registry.get(k)) and defn.dyne
        )

    @classmethod
    def from_list(
        cls,
        keys: list[str],
        registry: Optional["KeyRegistry"] = None,
    ) -> "KeyRing":
        """Restore a KeyRing from a saved list of yeigo strings."""
        return cls(keys=set(keys), registry=registry)

    # ── Introspection ─────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._keys)

    def __contains__(self, key: str) -> bool:
        return key in self._keys

    def __repr__(self) -> str:
        return f"KeyRing({len(self._keys)} keys)"
