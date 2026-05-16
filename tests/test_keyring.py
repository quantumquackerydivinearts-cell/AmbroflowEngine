"""
Tests for KeyRing — grant, revoke, satisfies, serialisation, registry validation.
"""

import pytest
from ambroflow.quests.keyring import KeyRing
from ambroflow.quests.key_registry import KeyRegistry, YeigoLo


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_registry(*yeigos: str) -> KeyRegistry:
    reg = KeyRegistry()
    for y in yeigos:
        reg.register(YeigoLo(yeigo=y, shakshi="test", kaelsuy="7_KLGS"))
    return reg


def make_lock(requires=(), excludes=()):
    from ambroflow.quests.schema import Lock
    return Lock(requires=list(requires), excludes=list(excludes))


# ── Construction ──────────────────────────────────────────────────────────────

def test_empty_ring():
    ring = KeyRing()
    assert len(ring) == 0


def test_initial_keys():
    ring = KeyRing(keys={"a", "b"})
    assert ring.has("a")
    assert ring.has("b")
    assert not ring.has("c")


def test_initial_keys_validated_against_registry():
    reg = make_registry("a", "b")
    ring = KeyRing(keys={"a", "b"}, registry=reg)
    assert ring.has("a")


def test_initial_undeclared_key_raises():
    reg = make_registry("a")
    with pytest.raises(ValueError, match="Undeclared"):
        KeyRing(keys={"undeclared"}, registry=reg)


# ── grant ─────────────────────────────────────────────────────────────────────

def test_grant_new_returns_true():
    ring = KeyRing()
    assert ring.grant("x") is True


def test_grant_existing_returns_false():
    ring = KeyRing()
    ring.grant("x")
    assert ring.grant("x") is False


def test_grant_validates_against_registry():
    reg = make_registry("a")
    ring = KeyRing(registry=reg)
    with pytest.raises(ValueError, match="Undeclared"):
        ring.grant("undeclared")


def test_grant_no_registry_accepts_any():
    ring = KeyRing()
    assert ring.grant("anything") is True


def test_grant_many_returns_new_only():
    ring = KeyRing()
    ring.grant("a")
    new = ring.grant_many(["a", "b", "c"])
    assert set(new) == {"b", "c"}


# ── has / contains ────────────────────────────────────────────────────────────

def test_has_after_grant():
    ring = KeyRing()
    ring.grant("x")
    assert ring.has("x")


def test_not_has_before_grant():
    ring = KeyRing()
    assert not ring.has("x")


def test_contains_operator():
    ring = KeyRing()
    ring.grant("x")
    assert "x" in ring
    assert "y" not in ring


# ── revoke ────────────────────────────────────────────────────────────────────

def test_revoke_present_returns_true():
    ring = KeyRing()
    ring.grant("x")
    assert ring.revoke("x") is True
    assert not ring.has("x")


def test_revoke_absent_returns_false():
    ring = KeyRing()
    assert ring.revoke("x") is False


# ── satisfies ─────────────────────────────────────────────────────────────────

def test_satisfies_empty_lock():
    ring = KeyRing()
    lock = make_lock()
    assert ring.satisfies(lock) is True


def test_satisfies_requires_present():
    ring = KeyRing()
    ring.grant("a")
    ring.grant("b")
    lock = make_lock(requires=["a", "b"])
    assert ring.satisfies(lock) is True


def test_satisfies_requires_missing():
    ring = KeyRing()
    ring.grant("a")
    lock = make_lock(requires=["a", "b"])
    assert ring.satisfies(lock) is False


def test_satisfies_excludes_absent():
    ring = KeyRing()
    ring.grant("a")
    lock = make_lock(requires=["a"], excludes=["b"])
    assert ring.satisfies(lock) is True


def test_satisfies_excludes_present():
    ring = KeyRing()
    ring.grant("a")
    ring.grant("b")
    lock = make_lock(requires=["a"], excludes=["b"])
    assert ring.satisfies(lock) is False


def test_satisfies_empty_requires_excludes_present():
    ring = KeyRing()
    ring.grant("b")
    lock = make_lock(excludes=["b"])
    assert ring.satisfies(lock) is False


# ── serialisation ─────────────────────────────────────────────────────────────

def test_to_list_sorted():
    ring = KeyRing()
    ring.grant("c")
    ring.grant("a")
    ring.grant("b")
    assert ring.to_list() == ["a", "b", "c"]


def test_from_list_roundtrip():
    ring = KeyRing()
    ring.grant("x")
    ring.grant("y")
    restored = KeyRing.from_list(ring.to_list())
    assert restored.has("x")
    assert restored.has("y")


def test_to_propagating_list():
    reg = KeyRegistry()
    reg.register(YeigoLo(yeigo="prop", shakshi="x", kaelsuy="7_KLGS", dyne=True))
    reg.register(YeigoLo(yeigo="local", shakshi="y", kaelsuy="7_KLGS", dyne=False))
    ring = KeyRing(registry=reg)
    ring.grant("prop")
    ring.grant("local")
    assert ring.to_propagating_list() == ["prop"]


def test_to_propagating_list_no_registry():
    ring = KeyRing()
    ring.grant("a")
    ring.grant("b")
    assert set(ring.to_propagating_list()) == {"a", "b"}


# ── repr / len ────────────────────────────────────────────────────────────────

def test_len():
    ring = KeyRing()
    ring.grant("a")
    ring.grant("b")
    assert len(ring) == 2


def test_repr():
    ring = KeyRing()
    ring.grant("a")
    assert "1 keys" in repr(ring)
