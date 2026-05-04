"""
ambroflow/world/ko_scene_reader.py
===================================
Native Kobra scene reader for the Ambroflow engine.

Reads a .ko scene file directly — no intermediate .scene.json required.
Returns the same dict structure as compile_scene() so the GL renderer
and interaction dispatch layer remain format-agnostic.

Usage
-----
    from ambroflow.world.ko_scene_reader import load_ko_scene

    scene = load_ko_scene(Path("productions/.../home_morning.scene.ko"))
    voxels = scene["renderer"]["scene"]["voxels"]
    nodes  = scene["nodes"]
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# ── Bootstrap: try importing the authoritative compiler from DjinnOS ──────────

_HERE = Path(__file__).resolve().parent   # ambroflow/world/
_DJINNOS_CANDIDATES = [
    _HERE.parents[2] / "DjinnOS" / "DjinnOS_Shyagzun",
    _HERE.parents[3] / "DjinnOS_Shyagzun",
    Path("C:/DjinnOS/DjinnOS_Shyagzun"),
]

_compiler_mod = None
for _candidate in _DJINNOS_CANDIDATES:
    _charters = _candidate / "shygazun" / "sanctum" / "charters"
    if _charters.is_dir():
        if str(_charters) not in sys.path:
            sys.path.insert(0, str(_charters))
        try:
            import scene_compiler as _compiler_mod  # type: ignore
            break
        except ImportError:
            sys.path.remove(str(_charters))


# ── Inline fallback (mirrors scene_compiler.py — kept in sync manually) ───────
# Active only when the DjinnOS compiler is unreachable (isolated installs).

if _compiler_mod is None:
    import json
    import re

    _ROSE = {
        "Gaoh": 0, "Ao": 1, "Ye": 2, "Ui": 3, "Shu": 4, "Kiel": 5,
        "Yeshu": 6, "Lao": 7, "Shushy": 8, "Uinshu": 9, "Kokiel": 10, "Aonkiel": 11,
    }
    _COLOR_HEX = {
        "Ot": "#8B6914", "El": "#696969", "Ru": "#8B0000",
        "Fu": "#87CEEB", "Ka": "#4B0082", "AE": "#9400D3",
        "Ki": "#3A7D44", "Na": "#C0C0C0", "Ha": "#FFFFFF", "Ga": "#1A1A1A",
    }
    _ACTION_MAP = {
        "MavoOpenAlchemyUi":      ("alchemy_bench", "open_alchemy_ui",      "Press E to use alchemy workbench"),
        "MavoExitToLapidusTown":  ("exit",          "exit_to_lapidus_town", "Press E to go outside"),
        "MavoOpenSmeltUi":        ("furnace",        "open_smelt_ui",        "Press E to use furnace"),
        "MavoMeditationTutorial": ("meditate",       "meditation_tutorial",  "Press E to meditate"),
        "MavoLoreBooks":          ("read",           "lore_books",           "Press E to read books"),
        "MavoSaveAndHeal":        ("rest",           "save_and_heal",        "Press E to rest (saves game)"),
        "MavoOpenChest":          ("storage",        "open_chest",           "Press E to open chest"),
    }

    def _rs(t: list[str], i: int) -> tuple[int, int]:
        if i >= len(t) or t[i] not in _ROSE: return 0, 0
        return _ROSE[t[i]], 1

    def _rm(t: list[str], i: int) -> tuple[int, int]:
        if i >= len(t) or t[i] not in _ROSE: return 0, 0
        v = _ROSE[t[i]]
        if i + 1 < len(t) and t[i + 1] in _ROSE: return v * 12 + _ROSE[t[i + 1]], 2
        return v, 1

    def _c3(t: list[str]) -> tuple[int, int, int, int]:
        x, nx = _rs(t, 0); y, ny = _rs(t, nx); z, nz = _rs(t, nx + ny)
        return x, y, z, nx + ny + nz

    def _mat(ts: set, ct: str) -> tuple[str, str]:
        if ct == "Ot":
            if "Shak" in ts: return "thatch_roof", "#654321"
            if "FyKo" in ts: return "books",        "#8B4513"
            if "Va"   in ts: return "wood_floor",   "#8B6914"
            return                   "wood_solid",  "#8B4513"
        if ct == "El":
            return ("metal_tool", "#B87333") if "Va" in ts else ("stone_wall", "#696969")
        if ct == "Ru":
            if "Di"   in ts: return "wood_door",  "#8B0000"
            if "Shak" in ts: return "furnace",    "#FF4500"
            if "Va"   in ts: return "metal_tool", "#B87333"
            return                   "furnace",   "#8B0000"
        if ct == "Fu": return "glass",         "#87CEEB"
        if ct == "Ka": return "cloth",         "#4B0082"
        if ct == "AE": return "cloth_cushion", "#9400D3"
        return "unknown", _COLOR_HEX.get(ct, "#888888")

    def _snake(n: str) -> str:
        s = n.removeprefix("Mavo")
        return re.sub(r"(?<=[a-z])(?=[A-Z])", "_", s).lower()

    def _specs(body: str) -> list[list[str]]:
        out, d, st = [], 0, None
        for i, ch in enumerate(body):
            if ch == "[":
                if d == 0: st = i + 1
                d += 1
            elif ch == "]":
                d -= 1
                if d == 0 and st is not None:
                    inner = body[st:i].strip()
                    if inner and not inner.startswith("TaShyMa"):
                        out.append(inner.split())
        return out

    def _sections(src: str) -> list[tuple[str, str]]:
        pat = re.compile(r"(Lo\w+)\s*:\s*Mavo\w+[^{]*\{", re.MULTILINE)
        out = []
        for m in pat.finditer(src):
            i, d = m.end(), 1
            while i < len(src) and d:
                if src[i] == "{": d += 1
                elif src[i] == "}": d -= 1
                i += 1
            out.append((m.group(1), src[m.end():i - 1]))
        return out

    def _fallback_compile(source: str, scene_id: str = "") -> dict[str, Any]:
        meta: dict[str, Any] = {}
        voxels: list[dict[str, Any]] = []
        spawn = None
        nodes: list[dict[str, Any]] = []

        for lo, body in _sections(source):
            if lo == "LoGaoh":
                for toks in _specs(body):
                    if len(toks) < 2: continue
                    k = toks[0]
                    if k == "MavoSceneId":   meta["scene_id"]  = toks[1]
                    elif k == "MavoRealm":   meta["realm_id"]  = _snake(toks[1])
                    elif k == "MavoSpawn":
                        x, y, z, _ = _c3(toks[1:])
                        meta["spawn"] = {"x": x, "y": y, "z": z}
                    elif k in ("MavoWidth","MavoDepth","MavoHeight"):
                        v, _ = _rm(toks, 1)
                        meta[k.removeprefix("Mavo").lower()] = v
                    elif k == "MavoCamera":
                        a, na = _rm(toks, 1); e, ne = _rm(toks, 1+na); z2, _ = _rm(toks, 1+na+ne)
                        meta["camera"] = {"angle": a, "elevation": e, "zoom": z2}
            elif lo in {"LoAo","LoYe","LoUi","LoShu","LoKiel"}:
                for toks in _specs(body):
                    if not toks or toks[0] not in _ROSE: continue
                    x, y, z, nc = _c3(toks)
                    prop = toks[nc:]; ts = set(prop)
                    ct = next((t for t in prop if t in _COLOR_HEX), None)
                    if ct is None: continue
                    mat, col = _mat(ts, ct)
                    v: dict[str, Any] = {
                        "x": x, "y": y, "z": z, "color": col, "color_token": ct,
                        "presence_token": "Ta" if "Ta" in ts else "",
                        "material": mat,
                        "walkable": "Va" in ts and "Vo" not in ts,
                        "solid":    "Vo" in ts,
                    }
                    if "Di" in ts: v["movable"] = True
                    if "Wu" in ts: v["opacity_token"] = "Wu"
                    voxels.append(v)
            elif lo == "LoYeshu":
                for toks in _specs(body):
                    if not toks or not toks[0].startswith("Mavo"): continue
                    nm = toks[0]; rest = toks[1:]
                    x, y, z, nc = _c3(rest); acts = rest[nc:]
                    act = next((t for t in acts if t.startswith("Mavo") and t not in ("MavoKael","MavoSy")), None)
                    if nm == "MavoSpawnPoint": spawn = {"x": x, "y": y, "z": z}; continue
                    nid = _snake(nm).removesuffix("_intr")
                    nd: dict[str, Any] = {"node_id": nid, "kind": "interaction",
                                          "x": float(x), "y": float(y), "metadata": {"z": z}}
                    if act and act in _ACTION_MAP:
                        i2, a2, p2 = _ACTION_MAP[act]
                        nd["metadata"].update({"interaction": i2, "action": a2, "prompt": p2})
                    nodes.append(nd)

        sid = meta.get("scene_id", scene_id); realm = meta.get("realm_id", "lapidus")
        name = sid.replace("_", " ").title()
        spn_node = {"node_id": "spawn_point", "kind": "spawn",
                    "x": float(spawn["x"]) if spawn else 0.0,
                    "y": float(spawn["y"]) if spawn else 0.0,
                    "metadata": {"z": spawn["z"] if spawn else 1, "placement_id": f"{sid}:spawn_point"}}
        for n in nodes: n["metadata"].setdefault("placement_id", f"{sid}:{n['node_id']}")
        return {
            "schema": "atelier.scene.content.v1", "scene_id": sid, "realm_id": realm,
            "name": name, "description": f"Player home in {realm.title()}.",
            "nodes": [spn_node] + nodes, "edges": [],
            "renderer": {"scene": {
                "scene_id": sid, "scene_name": name, "scene_type": "voxel_interior",
                "realm_id": realm,
                "dimensions": {"width": meta.get("width",12), "depth": meta.get("depth",8), "height": meta.get("height",6)},
                "spawn_point": spawn or {"x":6,"y":6,"z":1},
                "camera_default": meta.get("camera", {"angle":45,"elevation":30,"zoom":1.0}),
                "voxels": voxels,
                "ambient_music": meta.get("ambient",""),
                "time_of_day":   meta.get("time_of_day","morning"),
            }},
        }

    class _FallbackCompiler:
        @staticmethod
        def compile_scene(source: str, scene_id: str = "") -> dict[str, Any]:
            return _fallback_compile(source, scene_id)

    _compiler_mod = _FallbackCompiler()   # type: ignore


# ── Public API ─────────────────────────────────────────────────────────────────

def load_ko_scene(path: Path | str) -> dict[str, Any]:
    """
    Load and parse a .ko scene file. Returns a .scene.json-compatible dict.

    The dict has the same structure produced by scene_compiler.compile_scene(),
    so any code that reads .scene.json can consume this directly.
    """
    p      = Path(path)
    source = p.read_text(encoding="utf-8")
    sid    = p.name.replace(".scene.ko", "").replace(".ko", "")
    return _compiler_mod.compile_scene(source, sid)  # type: ignore


def iter_ko_scenes(directory: Path | str) -> "Iterator[dict[str, Any]]":
    """Yield parsed scene dicts for every .scene.ko file in a directory tree."""
    from typing import Iterator
    for ko in sorted(Path(directory).rglob("*.scene.ko")):
        yield load_ko_scene(ko)


def voxels(scene: dict[str, Any]) -> list[dict[str, Any]]:
    """Convenience accessor — extract the voxel list from a parsed scene."""
    return scene["renderer"]["scene"]["voxels"]


def interaction_nodes(scene: dict[str, Any]) -> list[dict[str, Any]]:
    """Convenience accessor — extract non-spawn interaction nodes."""
    return [n for n in scene["nodes"] if n["kind"] == "interaction"]


def spawn_point(scene: dict[str, Any]) -> dict[str, Any]:
    """Convenience accessor — return the spawn node's metadata."""
    node = next((n for n in scene["nodes"] if n["kind"] == "spawn"), None)
    return node["metadata"] if node else {"x": 0, "y": 0, "z": 1}