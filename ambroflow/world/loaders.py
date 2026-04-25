"""
ambroflow/world/loaders.py
===========================
Data loaders for encounter definitions, audio tracks, and quest steps.

Consumes the JSON formats exported by the Atelier's Game Editors panel
(EncounterEditor, AudioTrackRegistry, QuestEditor).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_WITNESS_WITNESSED = "witnessed"


# ── EncounterDef ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EncounterDef:
    """
    One encounter entry from the Atelier EncounterEditor.

    trigger_type:
      "always"            — fires every time the player enters this zone
      "quest_witnessed"   — fires after entry_id is witnessed
      "quest_unwitnessed" — fires until entry_id is witnessed
    """
    encounter_id: str
    name:         str
    zone_id:      str             # "" = any zone
    trigger_type: str             # "always" | "quest_witnessed" | "quest_unwitnessed"
    entry_id:     str             # witness gate — "" means no gate
    candidate:    str             # required witnessed candidate — "" means any
    combatants:   tuple[str, ...]
    loot:         tuple[str, ...]
    xp_reward:    int

    def fires(self, quest_state: Dict[str, Any], current_zone_id: str) -> bool:
        """Return True if this encounter should trigger in the current context."""
        if self.zone_id and self.zone_id != current_zone_id:
            return False

        if self.trigger_type == "always":
            return True

        entries: Dict[str, Any] = quest_state.get("entries") or {}
        entry   = entries.get(self.entry_id) or {}
        w_state = str(entry.get("witness_state") or "unwitnessed")
        w_cand  = str(entry.get("witnessed_candidate") or "")

        if self.trigger_type == "quest_witnessed":
            if w_state != _WITNESS_WITNESSED:
                return False
            if self.candidate and w_cand != self.candidate:
                return False
            return True

        if self.trigger_type == "quest_unwitnessed":
            return w_state != _WITNESS_WITNESSED

        return False


# ── AudioTrack ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AudioTrack:
    """
    One audio track entry from the Atelier AudioTrackRegistry.

    condition:
      "always"          — always eligible when realm/quest filters pass
      "quest_witnessed" — required_witness entry must be witnessed
    """
    track_id:         str
    name:             str
    file:             str
    channel:          str   # "music" | "ambient" | "effect"
    realm_id:         str   # "" = any realm
    quest_id:         str   # "" = any quest context
    required_witness: str   # entry_id that must be witnessed — "" = none required
    loop:             bool
    condition:        str   # "always" | "quest_witnessed"
    priority:         int   = 0


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_encounter_defs(path: str | Path) -> List[EncounterDef]:
    """Load encounter definitions from an Atelier EncounterEditor export."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Encounter defs file not found: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("encounters") or [raw]
    out = []
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("encounter_id"):
            continue
        out.append(EncounterDef(
            encounter_id=str(entry.get("encounter_id") or ""),
            name=str(entry.get("name") or ""),
            zone_id=str(entry.get("zone_id") or ""),
            trigger_type=str(entry.get("trigger_type") or "always"),
            entry_id=str(entry.get("entry_id") or ""),
            candidate=str(entry.get("candidate") or ""),
            combatants=tuple(entry.get("combatants") or []),
            loot=tuple(entry.get("loot") or []),
            xp_reward=int(entry.get("xp_reward") or 0),
        ))
    return out


def load_audio_tracks(path: str | Path) -> List[AudioTrack]:
    """Load audio track definitions from an Atelier AudioTrackRegistry export."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Audio tracks file not found: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("tracks") or [raw]
    out = []
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("track_id"):
            continue
        out.append(AudioTrack(
            track_id=str(entry.get("track_id") or ""),
            name=str(entry.get("name") or ""),
            file=str(entry.get("file") or ""),
            channel=str(entry.get("channel") or "music"),
            realm_id=str(entry.get("realm_id") or ""),
            quest_id=str(entry.get("quest_id") or ""),
            required_witness=str(entry.get("required_witness") or ""),
            loop=bool(entry.get("loop", True)),
            condition=str(entry.get("condition") or "always"),
            priority=int(entry.get("priority") or 0),
        ))
    return out


def load_quest_steps(path: str | Path) -> List[Dict[str, Any]]:
    """
    Load quest step definitions from an Atelier QuestEditor export.

    Returns WitnessEntry-compatible dicts (entry_id, cannabis_symbol,
    candidate_a_label, candidate_b_label) ready for qqva.quest_engine.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Quest steps file not found: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    steps = raw.get("steps") if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    out = []
    for step in (steps or []):
        if not isinstance(step, dict) or not step.get("entry_id"):
            continue
        out.append({
            "entry_id":          str(step.get("entry_id") or ""),
            "cannabis_symbol":   str(step.get("cannabis_symbol") or ""),
            "candidate_a_label": str(step.get("candidate_a_label") or ""),
            "candidate_b_label": str(step.get("candidate_b_label") or ""),
            "description":       str(step.get("description") or ""),
        })
    return out


# ── Audio selection ───────────────────────────────────────────────────────────

def select_audio(
    tracks: List[AudioTrack],
    quest_state: Dict[str, Any],
    realm_id: str,
) -> Optional[AudioTrack]:
    """
    Return the highest-priority AudioTrack whose conditions are satisfied
    for the current realm and quest state.
    """
    entries: Dict[str, Any] = quest_state.get("entries") or {}
    current_quest = str(quest_state.get("quest_id") or "")

    eligible = []
    for track in tracks:
        if track.realm_id and track.realm_id != realm_id:
            continue
        if track.quest_id and track.quest_id != current_quest:
            continue
        if track.condition == "quest_witnessed":
            if not track.required_witness:
                continue
            entry   = entries.get(track.required_witness) or {}
            w_state = str(entry.get("witness_state") or "unwitnessed")
            if w_state != _WITNESS_WITNESSED:
                continue
        eligible.append(track)

    if not eligible:
        return None
    return max(eligible, key=lambda t: t.priority)