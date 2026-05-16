"""
Tests for the YeigoLo key registry.
"""

import json
import pytest
from pathlib import Path

from ambroflow.quests.key_registry import (
    YeigoLo, KeyRegistry, load_registry, init_registry, global_registry,
)


# ── YeigoLo construction ──────────────────────────────────────────────────────

def test_yeigolo_required_fields():
    k = YeigoLo(yeigo="Tafly", shakshi="active presence in thought", kaelsuy="7_KLGS")
    assert k.yeigo   == "Tafly"
    assert k.shakshi == "active presence in thought"
    assert k.kaelsuy == "7_KLGS"


def test_yeigolo_defaults():
    k = YeigoLo(yeigo="Tafly", shakshi="active presence in thought", kaelsuy="7_KLGS")
    assert k.dyne  is False
    assert k.anom  is False
    assert k.andyf is False


def test_yeigolo_flags():
    k = YeigoLo(
        yeigo="AmeliaMuZu", shakshi="maternal continuity severed",
        kaelsuy="7_KLGS", dyne=True, andyf=True,
    )
    assert k.dyne  is True
    assert k.andyf is True
    assert k.anom  is False


def test_yeigolo_frozen():
    k = YeigoLo(yeigo="Tafly", shakshi="x", kaelsuy="7_KLGS")
    with pytest.raises(Exception):
        k.yeigo = "other"


def test_yeigolo_from_dict():
    d = {
        "yeigo":   "Tafly",
        "shakshi": "active presence",
        "kaelsuy": "7_KLGS",
        "dyne":    True,
        "anom":    False,
        "andyf":   True,
    }
    k = YeigoLo.from_dict(d)
    assert k.yeigo   == "Tafly"
    assert k.dyne    is True
    assert k.andyf   is True


def test_yeigolo_from_dict_defaults():
    k = YeigoLo.from_dict({"yeigo": "X", "shakshi": "y", "kaelsuy": "1_KLGS"})
    assert k.dyne  is False
    assert k.anom  is False
    assert k.andyf is False


def test_yeigolo_to_dict_roundtrip():
    k = YeigoLo(yeigo="Tafly", shakshi="x", kaelsuy="7_KLGS", dyne=True)
    assert YeigoLo.from_dict(k.to_dict()) == k


# ── KeyRegistry ───────────────────────────────────────────────────────────────

def test_registry_register_and_get():
    reg = KeyRegistry()
    k = YeigoLo(yeigo="Tafly", shakshi="x", kaelsuy="7_KLGS")
    reg.register(k)
    assert reg.get("Tafly") == k


def test_registry_duplicate_raises():
    reg = KeyRegistry()
    reg.register(YeigoLo(yeigo="Tafly", shakshi="x", kaelsuy="7_KLGS"))
    with pytest.raises(ValueError, match="Duplicate"):
        reg.register(YeigoLo(yeigo="Tafly", shakshi="y", kaelsuy="7_KLGS"))


def test_registry_validate_passes():
    reg = KeyRegistry()
    reg.register(YeigoLo(yeigo="Tafly", shakshi="x", kaelsuy="7_KLGS"))
    assert reg.validate("Tafly") == "Tafly"


def test_registry_validate_fails():
    reg = KeyRegistry()
    with pytest.raises(ValueError, match="Undeclared"):
        reg.validate("Nonexistent")


def test_registry_contains():
    reg = KeyRegistry()
    reg.register(YeigoLo(yeigo="Tafly", shakshi="x", kaelsuy="7_KLGS"))
    assert "Tafly" in reg
    assert "Other" not in reg


def test_registry_len():
    reg = KeyRegistry()
    assert len(reg) == 0
    reg.register(YeigoLo(yeigo="A", shakshi="x", kaelsuy="7_KLGS"))
    reg.register(YeigoLo(yeigo="B", shakshi="y", kaelsuy="7_KLGS"))
    assert len(reg) == 2


def test_registry_keys_for_game():
    reg = KeyRegistry()
    reg.register(YeigoLo(yeigo="A", shakshi="x", kaelsuy="7_KLGS"))
    reg.register(YeigoLo(yeigo="B", shakshi="y", kaelsuy="1_KLGS"))
    reg.register(YeigoLo(yeigo="C", shakshi="z", kaelsuy="7_KLGS"))
    result = reg.keys_for_game("7_KLGS")
    assert len(result) == 2
    assert all(k.kaelsuy == "7_KLGS" for k in result)


def test_registry_propagating():
    reg = KeyRegistry()
    reg.register(YeigoLo(yeigo="A", shakshi="x", kaelsuy="7_KLGS", dyne=True))
    reg.register(YeigoLo(yeigo="B", shakshi="y", kaelsuy="7_KLGS", dyne=False))
    assert len(reg.propagating()) == 1
    assert reg.propagating()[0].yeigo == "A"


def test_registry_reversible():
    reg = KeyRegistry()
    reg.register(YeigoLo(yeigo="A", shakshi="x", kaelsuy="7_KLGS", andyf=True))
    reg.register(YeigoLo(yeigo="B", shakshi="y", kaelsuy="7_KLGS", andyf=False))
    assert len(reg.reversible()) == 1
    assert reg.reversible()[0].yeigo == "A"


# ── Loader ────────────────────────────────────────────────────────────────────

def test_load_registry_empty_dir(tmp_path):
    reg = load_registry(tmp_path)
    assert len(reg) == 0


def test_load_registry_missing_dir(tmp_path):
    reg = load_registry(tmp_path / "nonexistent")
    assert len(reg) == 0


def test_load_registry_from_file(tmp_path):
    data = [
        {"yeigo": "A", "shakshi": "x", "kaelsuy": "7_KLGS", "dyne": True},
        {"yeigo": "B", "shakshi": "y", "kaelsuy": "7_KLGS"},
    ]
    (tmp_path / "7_KLGS.json").write_text(json.dumps(data), encoding="utf-8")
    reg = load_registry(tmp_path)
    assert len(reg) == 2
    assert "A" in reg
    assert reg.get("A").dyne is True


def test_load_registry_multiple_files(tmp_path):
    (tmp_path / "7_KLGS.json").write_text(
        json.dumps([{"yeigo": "A", "shakshi": "x", "kaelsuy": "7_KLGS"}]),
        encoding="utf-8",
    )
    (tmp_path / "1_KLGS.json").write_text(
        json.dumps([{"yeigo": "B", "shakshi": "y", "kaelsuy": "1_KLGS"}]),
        encoding="utf-8",
    )
    reg = load_registry(tmp_path)
    assert len(reg) == 2
    assert reg.get("A").kaelsuy == "7_KLGS"
    assert reg.get("B").kaelsuy == "1_KLGS"


def test_load_registry_duplicate_across_files_raises(tmp_path):
    (tmp_path / "7_KLGS.json").write_text(
        json.dumps([{"yeigo": "A", "shakshi": "x", "kaelsuy": "7_KLGS"}]),
        encoding="utf-8",
    )
    (tmp_path / "8_KLGS.json").write_text(
        json.dumps([{"yeigo": "A", "shakshi": "y", "kaelsuy": "8_KLGS"}]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate"):
        load_registry(tmp_path)


def test_load_registry_non_array_raises(tmp_path):
    (tmp_path / "bad.json").write_text(
        json.dumps({"yeigo": "A", "shakshi": "x", "kaelsuy": "7_KLGS"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected JSON array"):
        load_registry(tmp_path)


# ── Global registry ───────────────────────────────────────────────────────────

def test_global_registry_unloaded_raises(monkeypatch):
    import ambroflow.quests.key_registry as kr
    monkeypatch.setattr(kr, "_REGISTRY", None)
    with pytest.raises(RuntimeError, match="not loaded"):
        global_registry()


def test_init_registry(tmp_path, monkeypatch):
    import ambroflow.quests.key_registry as kr
    monkeypatch.setattr(kr, "_REGISTRY", None)
    data = [{"yeigo": "X", "shakshi": "z", "kaelsuy": "7_KLGS"}]
    (tmp_path / "7_KLGS.json").write_text(json.dumps(data), encoding="utf-8")
    reg = init_registry(tmp_path)
    assert "X" in reg
    assert global_registry() is reg
