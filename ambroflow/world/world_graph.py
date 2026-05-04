"""
ambroflow/world/world_graph.py
==============================
WorldGraph — scene stitching layer for Ko's Labyrinth.

Reads kos_labyrinth_scenes.ko (or its compiled scene_graph.json)
and provides transition lookups: given an action_id fired at a scene
exit, return (target_scene_id, target_spawn_id).

The graph is loaded once and cached.  Transitions are O(1) lookups.

Usage
-----
    from ambroflow.world.world_graph import WorldGraph

    graph = WorldGraph.load()
    target = graph.resolve_exit("exit_to_lapidus_town")
    # → Transition(scene_id="lapidus/wiltoll_lane", spawn_id="spawn_wiltoll_home_end")
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Transition:
    action_id:  str
    scene_id:   str
    spawn_id:   str

    def __repr__(self) -> str:
        return f"Transition({self.action_id!r} → {self.scene_id!r}@{self.spawn_id!r})"


@dataclass
class SceneNode:
    scene_id:    str
    realm_id:    str
    exits:       List[Transition]  = field(default_factory=list)
    akinen:      str               = ""


@dataclass
class WorldGraph:
    scenes:    Dict[str, SceneNode]      = field(default_factory=dict)
    exit_map:  Dict[str, Transition]     = field(default_factory=dict)

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, source: Optional[Path | str] = None) -> "WorldGraph":
        """
        Load the world graph from a .ko manifest or pre-compiled .json.
        Auto-discovers the canonical location if source is None.
        """
        resolved = _resolve_source(source)
        if resolved is None:
            return cls()
        if resolved.suffix == ".json":
            return cls._from_json(resolved)
        return cls._from_ko(resolved)

    @classmethod
    def _from_json(cls, path: Path) -> "WorldGraph":
        data = json.loads(path.read_text(encoding="utf-8"))
        g = cls()
        for entry in data.get("scenes", []):
            node = SceneNode(
                scene_id = entry["scene_id"],
                realm_id = entry.get("realm_id", "lapidus"),
                akinen   = entry.get("akinen", ""),
                exits    = [
                    Transition(t["action_id"], t["scene_id"], t["spawn_id"])
                    for t in entry.get("exits", [])
                ],
            )
            g.scenes[node.scene_id] = node
            for ex in node.exits:
                g.exit_map[ex.action_id] = ex
        return g

    @classmethod
    def _from_ko(cls, path: Path) -> "WorldGraph":
        source = path.read_text(encoding="utf-8")
        return _parse_ko_graph(source)

    # ── Public API ────────────────────────────────────────────────────────────

    def resolve_exit(self, action_id: str) -> Optional[Transition]:
        """Return the Transition for a scene exit action, or None if unknown."""
        return self.exit_map.get(action_id)

    def get_scene(self, scene_id: str) -> Optional[SceneNode]:
        return self.scenes.get(scene_id)

    def list_scenes(self, realm_id: Optional[str] = None) -> List[str]:
        if realm_id is None:
            return list(self.scenes.keys())
        return [sid for sid, n in self.scenes.items() if n.realm_id == realm_id]

    def to_json(self) -> dict:
        return {
            "scenes": [
                {
                    "scene_id": n.scene_id,
                    "realm_id": n.realm_id,
                    "akinen":   n.akinen,
                    "exits":    [{"action_id": e.action_id, "scene_id": e.scene_id, "spawn_id": e.spawn_id}
                                 for e in n.exits],
                }
                for n in self.scenes.values()
            ]
        }

    def compile_to_json(self, dest: "Path | str") -> None:
        Path(dest).write_text(json.dumps(self.to_json(), indent=2), encoding="utf-8")


# ── Ko manifest parser ────────────────────────────────────────────────────────

def _mavo_to_action(name: str) -> str:
    """MavoExitToLapidusTown → exit_to_lapidus_town"""
    s = name.removeprefix("Mavo")
    return re.sub(r"(?<=[a-z])(?=[A-Z])", "_", s).lower()

def _extract_specs(body: str) -> list[list[str]]:
    specs, depth, start = [], 0, None
    for i, ch in enumerate(body):
        if ch == "[":
            if depth == 0: start = i + 1
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0 and start is not None:
                inner = body[start:i].strip()
                if inner and not inner.startswith("TaShyMa"):
                    specs.append(inner.split())
    return specs

def _extract_sections(source: str) -> list[tuple[str, str]]:
    pat = re.compile(r"(Lo\w+)\s*:\s*Mavo\w+[^{]*\{", re.MULTILINE)
    out = []
    for m in pat.finditer(source):
        i, d = m.end(), 1
        while i < len(source) and d:
            if source[i] == "{": d += 1
            elif source[i] == "}": d -= 1
            i += 1
        out.append((m.group(1), source[m.end():i - 1]))
    return out

_REALM_TOKENS = {"MavoLapidus": "lapidus", "MavoMercurie": "mercurie", "MavoSulphera": "sulphera"}
_SHYGAZUN_COLOR = {"Zot", "Mel", "Puf", "Shak", "Ki", "Fu", "El", "Ka", "Ru", "Ot", "AE",
                   "Na", "Ha", "Ga", "Ung", "Wu", "MelZot", "TaVa", "Di", "Va", "Vo", "At",
                   "An", "Ar", "Azr", "Av", "At", "Yzr", "Af", "Yf", "Ne", "Ry", "Soa", "FyKo"}

def _parse_ko_graph(source: str) -> WorldGraph:
    g = WorldGraph()
    for lo, body in _extract_sections(source):
        if lo == "LoGaoh":
            continue
        for toks in _extract_specs(body):
            if not toks or toks[0].startswith("TaShyMa"):
                continue
            # First token = Mavo scene name, second = scene_id path
            if len(toks) < 3 or not toks[0].startswith("Mavo"):
                continue
            mavo_name  = toks[0]
            scene_id   = toks[1]  # e.g. "lapidus/home_morning"
            realm_tok  = toks[2] if len(toks) > 2 else ""
            realm_id   = _REALM_TOKENS.get(realm_tok, "lapidus")

            exits: list[Transition] = []
            akinen_parts: list[str] = []
            i = 3
            while i < len(toks):
                t = toks[i]
                if t in ("MavoKael", "MavoSy"):
                    i += 1
                    continue
                if t.startswith("Mavo") and i + 2 < len(toks) and "/" in toks[i + 1]:
                    # MavoExitFoo  target/scene  spawn_id
                    action_id = _mavo_to_action(t)
                    target_scene = toks[i + 1]
                    spawn_id     = toks[i + 2]
                    exits.append(Transition(action_id, target_scene, spawn_id))
                    i += 3
                    continue
                if t in _SHYGAZUN_COLOR or any(t == s for s in _SHYGAZUN_COLOR):
                    akinen_parts.append(t)
                i += 1

            node = SceneNode(
                scene_id = scene_id,
                realm_id = realm_id,
                exits    = exits,
                akinen   = " ".join(akinen_parts),
            )
            g.scenes[scene_id] = node
            for ex in exits:
                g.exit_map[ex.action_id] = ex

    return g


# ── Source discovery ──────────────────────────────────────────────────────────

_CANDIDATES = [
    Path("C:/DjinnOS/DjinnOS_Shyagzun/shygazun/sanctum/kos_labyrinth_scenes.ko"),
    Path(__file__).parents[2] / "productions" / "kos-labyrnth" / "scene_graph.json",
    Path(__file__).parents[3] / "DjinnOS" / "DjinnOS_Shyagzun" / "shygazun" / "sanctum" / "kos_labyrinth_scenes.ko",
]

def _resolve_source(source: Optional[Path | str]) -> Optional[Path]:
    if source is not None:
        p = Path(source)
        return p if p.exists() else None
    for c in _CANDIDATES:
        if c.exists():
            return c
    return None


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Compile kos_labyrinth_scenes.ko → scene_graph.json")
    ap.add_argument("--ko",  default=str(_CANDIDATES[0]), help="source .ko manifest")
    ap.add_argument("--out", default="scene_graph.json",  help="output JSON")
    args = ap.parse_args()
    g = WorldGraph.load(args.ko)
    out = Path(args.out)
    g.compile_to_json(out)
    print(f"Compiled {len(g.scenes)} scenes, {len(g.exit_map)} exits → {out}")

if __name__ == "__main__":
    main()