"""
Ambroflow Game Data Loader
==========================
Loads exported game data from the Atelier into a GameDataBundle.

Two loading strategies:

  load_from_file(bundle_json_path)
      Reads a locally-exported bundle JSON.  No network required.
      Portrait bytes are loaded from the same directory structure:
        <bundle_dir>/portraits/<char_id>.png

  load_from_api(game_slug, api_base)
      Fetches the bundle from the Atelier API at runtime.
      Fetches individual portrait PNGs on demand via load_portrait().

The Atelier exports to apps/atelier-api/atelier_api/files/exports/{game_slug}/.
During development Ambroflow can point directly at that directory.

Usage
-----
    from ambroflow.dialogue.loader import load_from_file, GameDataBundle

    bundle = load_from_file("path/to/exports/7_KLGS/registry.json")
    portrait_bytes = bundle.get_portrait("0006_WTCH")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class CharacterRecord:
    """
    A single character entry from the game registry.

    id:   e.g. "0006_WTCH"
    name: e.g. "Alfir"
    type: e.g. "WTCH"  (matches the character type codes in game7Registry.js)
    meta: any additional fields from the registry (role, note, teaches, etc.)
    """
    id:   str
    name: str
    type: str
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterRecord":
        meta = {k: v for k, v in data.items() if k not in ("id", "name", "type")}
        return cls(
            id=data.get("id") or "",
            name=data.get("name") or "Unknown",
            type=data.get("type") or "TOWN",
            meta=meta,
        )


@dataclass
class GameDataBundle:
    """
    Packaged game data ready for use by Ambroflow systems.

    characters: all CharacterRecords indexed by id
    quests:     raw quest dicts indexed by slug
    items:      raw item dicts indexed by id
    objects:    raw object dicts indexed by id
    portraits:  portrait PNG bytes indexed by char_id (populated on demand)
    _portrait_dir: local path to portrait PNG files (if loaded from file)
    _api_base:     Atelier API base URL (if loaded from API)
    _game_slug:    game slug (e.g. "7_KLGS")
    """
    game_slug:   str
    characters:  dict[str, CharacterRecord]  = field(default_factory=dict)
    quests:      dict[str, dict[str, Any]]   = field(default_factory=dict)
    items:       dict[str, dict[str, Any]]   = field(default_factory=dict)
    objects:     dict[str, dict[str, Any]]   = field(default_factory=dict)

    _portraits:    dict[str, bytes]  = field(default_factory=dict, repr=False)
    _portrait_dir: Optional[Path]    = field(default=None,         repr=False)
    _api_base:     Optional[str]     = field(default=None,         repr=False)

    def get_portrait(self, char_id: str) -> Optional[bytes]:
        """
        Return portrait PNG bytes for char_id, or None if unavailable.
        Loads from disk or API on first access, then caches.
        """
        if char_id in self._portraits:
            return self._portraits[char_id]

        # Try local file first
        if self._portrait_dir:
            safe = char_id.replace("/", "_").replace("..", "_")
            p = self._portrait_dir / f"{safe}.png"
            if p.exists():
                data = p.read_bytes()
                self._portraits[char_id] = data
                return data

        # Try API
        if self._api_base:
            api_data = _fetch_portrait_from_api(self._api_base, self.game_slug, char_id)
            if api_data is not None:
                self._portraits[char_id] = api_data
                return api_data

        return None

    def character(self, char_id: str) -> Optional[CharacterRecord]:
        return self.characters.get(char_id)

    def characters_of_type(self, type_code: str) -> list[CharacterRecord]:
        return [c for c in self.characters.values() if c.type == type_code]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_bundle(game_slug: str, registry: dict[str, Any]) -> GameDataBundle:
    chars: dict[str, CharacterRecord] = {}
    for entry in registry.get("characters", []):
        if entry.get("id"):
            rec = CharacterRecord.from_dict(entry)
            chars[rec.id] = rec

    quests: dict[str, dict] = {}
    for q in registry.get("quests", []):
        key = q.get("slug") or q.get("id") or ""
        if key:
            quests[key] = q

    items: dict[str, dict] = {}
    for it in registry.get("items", []):
        key = it.get("id") or it.get("name") or ""
        if key:
            items[key] = it

    objects: dict[str, dict] = {}
    for obj in registry.get("objects", []):
        key = obj.get("id") or obj.get("name") or ""
        if key:
            objects[key] = obj

    return GameDataBundle(
        game_slug=game_slug,
        characters=chars,
        quests=quests,
        items=items,
        objects=objects,
    )


def _fetch_portrait_from_api(
    api_base: str, game_slug: str, char_id: str
) -> Optional[bytes]:
    try:
        import httpx
        url = f"{api_base.rstrip('/')}/v1/export/portrait/{game_slug}/{char_id}"
        r = httpx.get(url, timeout=10.0)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None


# ── Public loaders ────────────────────────────────────────────────────────────

def load_from_file(registry_path: str | Path) -> GameDataBundle:
    """
    Load a GameDataBundle from a locally-exported registry JSON.

    Expected layout (produced by the Atelier export endpoint):
        <dir>/registry.json
        <dir>/portraits/<char_id>.png

    Parameters
    ----------
    registry_path:
        Path to registry.json.  Portrait PNGs are resolved relative to its
        parent directory's ``portraits/`` subdirectory.
    """
    path = Path(registry_path)
    if not path.exists():
        raise FileNotFoundError(f"Registry not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))

    # registry.json may be the raw registry dict or the bundle envelope
    registry = raw.get("registry", raw)
    game_slug = raw.get("game_slug", path.parent.name)

    bundle = _build_bundle(game_slug, registry)
    bundle._portrait_dir = path.parent / "portraits"
    return bundle


def load_from_api(game_slug: str, api_base: str = "http://127.0.0.1:9000") -> GameDataBundle:
    """
    Load a GameDataBundle from the Atelier API.

    Fetches GET /v1/export/bundle/{game_slug}.
    Portrait bytes are fetched on demand via bundle.get_portrait(char_id).

    Parameters
    ----------
    game_slug:
        e.g. "7_KLGS"
    api_base:
        Atelier API base URL.  Default: local dev server.

    Raises
    ------
    RuntimeError if httpx is not installed or the API is unreachable.
    ValueError if the game slug is not found in the API.
    """
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx is required for load_from_api()") from exc

    url = f"{api_base.rstrip('/')}/v1/export/bundle/{game_slug}"
    try:
        r = httpx.get(url, timeout=15.0)
    except httpx.RequestError as exc:
        raise RuntimeError(f"Could not reach Atelier API at {api_base}: {exc}") from exc

    if r.status_code == 404:
        raise ValueError(
            f"Game {game_slug!r} not found in Atelier export. "
            f"POST registry to /v1/export/registry/{game_slug} first."
        )
    r.raise_for_status()

    data      = r.json()
    registry  = data.get("registry", {})
    bundle    = _build_bundle(game_slug, registry)
    bundle._api_base = api_base
    return bundle
