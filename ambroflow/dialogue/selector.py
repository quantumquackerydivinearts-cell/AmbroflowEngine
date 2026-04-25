"""
ambroflow/dialogue/selector.py
================================
Bridge between the qqva dialogue_runtime and the existing Ambroflow
dialogue loader and renderer.

Responsibilities
----------------
  load_paths(path)
      Load a DialoguePath JSON file produced by the Atelier's Dialogue
      Tree Editor.  Returns a list of path dicts ready for select_path().

  select(quest_state, realm_id, character_id, paths, bundle)
      Select the appropriate dialogue path for a character given the
      current quest witness state, then return a DialogueScreen ready
      to pass to render_character_dialogue().

  render_interaction(quest_state, realm_id, character_id, paths, bundle)
      Convenience: select + render in one call.  Returns PNG bytes or
      None if Pillow is unavailable.

qqva fallback
-------------
The qqva package is an optional dependency from the DjinnOS monorepo.
If it is not on the path the selector falls back to a structural
match (priority sort + required/blocked witness evaluation against the
raw quest_state dict) so the engine remains runnable in standalone mode.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .loader import GameDataBundle
from .render import render_character_dialogue

# ── qqva import (graceful fallback) ──────────────────────────────────────────

try:
    from qqva.dialogue_runtime import (  # type: ignore
        select_path as _qqva_select_path,
        WITNESS_WITNESSED,
    )
    _HAS_QQVA = True
except Exception:
    _qqva_select_path = None
    WITNESS_WITNESSED = "witnessed"
    _HAS_QQVA = False


# ── DialogueScreen ────────────────────────────────────────────────────────────

@dataclass
class DialogueScreen:
    """
    The resolved output of a select() call.

    character_id  — e.g. "0006_WTCH"
    name          — display name
    char_type     — e.g. "WTCH"
    text          — the selected dialogue line (first line of the path)
    choices       — optional player response choices (subsequent lines where
                    the speaker is "player" or "0000_0451")
    path_id       — which path was selected
    portrait_bytes— PNG bytes from bundle.get_portrait(), or None
    realm_id      — the realm in which this interaction occurs
    """
    character_id:   str
    name:           str
    char_type:      str
    text:           str
    choices:        List[str]
    path_id:        str
    portrait_bytes: Optional[bytes]
    realm_id:       str

    def render(self, width: int = 512, height: int = 256) -> Optional[bytes]:
        """Render to PNG bytes via the character dialogue renderer."""
        return render_character_dialogue(
            name=self.name,
            char_type=self.char_type,
            text=self.text,
            portrait_bytes=self.portrait_bytes,
            choices=self.choices or None,
            width=width,
            height=height,
        )


# ── Path loading ──────────────────────────────────────────────────────────────

def load_paths(path: str | Path) -> List[Dict[str, Any]]:
    """
    Load DialoguePath records from a JSON file exported by the Atelier's
    Dialogue Tree Editor.

    Accepts two shapes:
      { "character_id": "...", "paths": [ ... ] }   — single character export
      [ { "path_id": "...", ... }, ... ]             — bare list

    Returns a list of path dicts.  Invalid entries are skipped silently.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dialogue paths file not found: {p}")

    raw = json.loads(p.read_text(encoding="utf-8"))

    if isinstance(raw, list):
        paths = raw
    elif isinstance(raw, dict):
        paths = raw.get("paths", [])
    else:
        return []

    return [entry for entry in paths if isinstance(entry, dict) and entry.get("path_id")]


def load_paths_dir(directory: str | Path) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load all `dialogue_*.json` files from a directory.

    Returns a dict mapping character_id → list of path dicts.
    Paths without a character_id are stored under the empty string key.
    """
    d = Path(directory)
    result: Dict[str, List[Dict[str, Any]]] = {}
    for f in sorted(d.glob("dialogue_*.json")):
        try:
            paths = load_paths(f)
        except Exception:
            continue
        for path_dict in paths:
            char_id = str(path_dict.get("character_id") or "")
            result.setdefault(char_id, []).append(path_dict)
    return result


# ── Fallback selection (no qqva) ──────────────────────────────────────────────

def _fallback_select(
    quest_state: Dict[str, Any],
    realm_id: str,
    character_id: str,
    paths: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Structural path selection when qqva is unavailable.
    Mirrors dialogue_runtime.select_path() without importing it.
    """
    entries: Dict[str, str] = {}
    raw_entries = quest_state.get("entries") or {}
    for eid, entry in raw_entries.items():
        if isinstance(entry, dict):
            entries[eid] = str(entry.get("witness_state") or "unwitnessed")

    # Sulphera gate
    if realm_id == "sulphera":
        gate = entries.get("0009_KLST", "unwitnessed")
        if gate != WITNESS_WITNESSED:
            return None

    candidates = [
        p for p in paths
        if p.get("character_id") == character_id
        and p.get("realm_id") == realm_id
    ]

    available = []
    for p in candidates:
        required = p.get("required_witnesses") or []
        blocked  = p.get("blocked_witnesses")  or []
        if any(entries.get(r) != WITNESS_WITNESSED for r in required):
            continue
        if any(entries.get(b) == WITNESS_WITNESSED for b in blocked):
            continue
        available.append(p)

    if not available:
        return None
    return max(available, key=lambda p: int(p.get("priority") or 0))


# ── Core select ───────────────────────────────────────────────────────────────

def select(
    quest_state: Dict[str, Any],
    realm_id: str,
    character_id: str,
    paths: List[Dict[str, Any]],
    bundle: GameDataBundle,
) -> Optional[DialogueScreen]:
    """
    Select the appropriate dialogue path and return a DialogueScreen.

    Parameters
    ----------
    quest_state   : QuestState dict from qqva.quest_engine (or equivalent)
    realm_id      : "lapidus" | "mercurie" | "sulphera"
    character_id  : e.g. "0006_WTCH"
    paths         : loaded DialoguePath dicts (from load_paths())
    bundle        : GameDataBundle for name, type, and portrait lookup

    Returns None if no path is available for this state/realm/character.
    """
    # Select path
    if _HAS_QQVA and _qqva_select_path is not None:
        result = _qqva_select_path(quest_state, realm_id, character_id, paths)
        if not result.get("matched"):
            return None
        chosen = result.get("path")
    else:
        chosen = _fallback_select(quest_state, realm_id, character_id, paths)

    if not chosen:
        return None

    # Resolve character
    char = bundle.character(character_id)
    name      = char.name      if char else character_id
    char_type = char.type      if char else "TOWN"
    portrait  = bundle.get_portrait(character_id)

    # Extract text and choices from lines
    lines = chosen.get("lines") or []
    player_ids = {"player", "0000_0451"}

    npc_lines    = [ln for ln in lines if str(ln.get("speaker") or "") not in player_ids]
    choice_lines = [ln for ln in lines if str(ln.get("speaker") or "") in player_ids]

    text    = npc_lines[0]["text"]    if npc_lines    else ""
    choices = [ln["text"] for ln in choice_lines] if choice_lines else []

    return DialogueScreen(
        character_id=character_id,
        name=name,
        char_type=char_type,
        text=text,
        choices=choices,
        path_id=str(chosen.get("path_id") or ""),
        portrait_bytes=portrait,
        realm_id=realm_id,
    )


# ── Convenience: select + render ──────────────────────────────────────────────

def render_interaction(
    quest_state: Dict[str, Any],
    realm_id: str,
    character_id: str,
    paths: List[Dict[str, Any]],
    bundle: GameDataBundle,
    width:  int = 512,
    height: int = 256,
) -> Optional[bytes]:
    """
    Select the dialogue path and render to PNG bytes in one call.

    Returns None if no path matches or Pillow is unavailable.
    """
    screen = select(quest_state, realm_id, character_id, paths, bundle)
    if screen is None:
        return None
    return screen.render(width=width, height=height)