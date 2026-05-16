"""
quest_loader.py — Load QuestScript objects from JSON files.

Quest script files live in scripts/<game_slug>/<quest_id>.json.
Each file is a single QuestScript dict.

Usage
-----
    from ambroflow.quests.quest_loader import load_quest_scripts

    scripts = load_quest_scripts("scripts/7_KLGS", registry=reg)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .schema import QuestScript
from .key_registry import KeyRegistry


def load_quest_script(
    path: str | Path,
    registry: Optional[KeyRegistry] = None,
) -> QuestScript:
    """
    Load a single QuestScript from a JSON file.
    Optionally validates all key references against the registry.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    script = QuestScript.from_dict(data)

    if registry:
        _validate_script_keys(script, registry)

    return script


def load_quest_scripts(
    scripts_dir: str | Path,
    registry: Optional[KeyRegistry] = None,
) -> list[QuestScript]:
    """
    Load all QuestScript JSON files from scripts_dir.
    Files are loaded in sorted order.
    Returns empty list if directory does not exist.
    """
    scripts_path = Path(scripts_dir)
    if not scripts_path.exists():
        return []

    scripts: list[QuestScript] = []
    for path in sorted(scripts_path.glob("*.json")):
        scripts.append(load_quest_script(path, registry=registry))

    return scripts


def _validate_script_keys(script: QuestScript, registry: KeyRegistry) -> None:
    """
    Validate all yeigo key references in a QuestScript against the registry.
    Raises ValueError naming the first undeclared key found.
    """
    def check(keys: list[str], context: str) -> None:
        for k in keys:
            if k not in registry:
                raise ValueError(
                    f"{script.quest_id}: undeclared key {k!r} in {context}"
                )

    check([script.completion_key], "completion_key")
    if script.failure_key:
        check([script.failure_key], "failure_key")

    for scene in script.scenes:
        check(scene.lock.requires, f"scene {scene.id} lock.requires")
        check(scene.lock.excludes, f"scene {scene.id} lock.excludes")
        check(scene.grants,        f"scene {scene.id} grants")
        for beat in scene.beats:
            check(beat.grants, f"scene {scene.id} beat grants")

    for topic in script.topics:
        check(topic.lock.requires, f"topic {topic.id} lock.requires")
        check(topic.lock.excludes, f"topic {topic.id} lock.excludes")
        check(topic.grants,        f"topic {topic.id} grants")
        for response in topic.responses:
            check(response.lock.requires, f"topic {topic.id} response lock.requires")
            check(response.lock.excludes, f"topic {topic.id} response lock.excludes")
            check(response.grants,        f"topic {topic.id} response grants")
            for beat in response.beats:
                check(beat.grants, f"topic {topic.id} response beat grants")
