"""
renderer_bridge — Ko's Labyrinth rendering contract loader.

Source of truth: DjinnOS_Shyagzun/shygazun/sanctum/renderer_bridge.ko

Reads the .ko file and extracts the structural rendering contract:
  LoYeshu  — Cannabis mode tile sizes (A / I / Y)
  LoYe     — time topology passability (Va = passable, Vo = impassable)

Colour tables (LoKiel) are pre-decoded constants mirroring the Shygazun
compound tokens in renderer_bridge.ko. Each entry is annotated with its
LoKiel origin token. Stage 2 (Kobra VM) will replace these with live
decodes of the compound colour grammar.

The DjinnOS kernel renderer (src/renderer_bridge.rs) carries the same
contract: the same pre-decoded colour constants and the same Cannabis
mode tile sizes.  Both renderers must produce identical output for
identical zone data.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


# ── Canonical .ko location ────────────────────────────────────────────────────

_KO_PATH = Path(__file__).parents[3] / "DjinnOS_Shyagzun" / "shygazun" / \
           "sanctum" / "renderer_bridge.ko"


# ── Rose numeral table ────────────────────────────────────────────────────────

_ROSE = {
    "Gaoh": 0, "Ao": 1, "Ye": 2, "Ui": 3, "Shu": 4, "Kiel": 5,
    "Yeshu": 6, "Lao": 7, "Shushy": 8, "Uinshu": 9,
    "Kokiel": 10, "Aonkiel": 11,
}


def _rose_pair(toks: list[str], i: int) -> tuple[int, int]:
    """Read one base-12 Rose numeral (1 or 2 tokens). Returns (value, consumed)."""
    if i >= len(toks) or toks[i] not in _ROSE:
        return 0, 0
    v = _ROSE[toks[i]]
    if i + 1 < len(toks) and toks[i + 1] in _ROSE:
        return v * 12 + _ROSE[toks[i + 1]], 2
    return v, 1


# ── Minimal .ko section / spec parser ────────────────────────────────────────

def _find_section(src: str, lo_name: str) -> Optional[str]:
    pat = re.compile(rf"{re.escape(lo_name)}\s*:\s*Mavo\w+[^{{]*\{{", re.MULTILINE)
    m = pat.search(src)
    if not m:
        return None
    i, depth = m.end(), 1
    while i < len(src) and depth:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return src[m.end():i - 1]


def _extract_specs(body: str) -> list[list[str]]:
    specs, depth, start = [], 0, None
    for i, ch in enumerate(body):
        if ch == "[":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0 and start is not None:
                inner = body[start:i].strip()
                if inner and "TaShyMa" not in inner:
                    specs.append(inner.split())
    return specs


# ── Cannabis mode parser (LoYeshu) ────────────────────────────────────────────

def _parse_cannabis_modes(src: str) -> dict[str, int]:
    """
    Parse Cannabis mode tile sizes from LoYeshu.
    Returns {"A": tile_px, "I": tile_px, "Y": tile_px}.

    renderer_bridge.ko LoYeshu:
      [A  MavoTile Ao Shu    MavoZScale Ao Gaoh]   → A=16
      [I  MavoTile Ao Shushy MavoZScale Shushy  ]   → I=20
      [Y  MavoTile Ao Ye     MavoZScale Yeshu   ]   → Y=14
    """
    body = _find_section(src, "LoYeshu")
    if not body:
        return {}
    result = {}
    for spec in _extract_specs(body):
        if not spec:
            continue
        mode = spec[0]
        if mode not in ("A", "I", "Y"):
            continue
        try:
            tile_pos = spec.index("MavoTile")
            val, _ = _rose_pair(spec, tile_pos + 1)
            result[mode] = val
        except (ValueError, IndexError):
            pass
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def load_renderer_bridge(ko_path: Optional[Path] = None) -> dict:
    """
    Load and parse renderer_bridge.ko.  Returns a contract dict:

      "tile_a"  — Cannabis mode A tile size in pixels  (primary world view)
      "tile_i"  — Cannabis mode I tile size in pixels  (detail view)
      "tile_y"  — Cannabis mode Y tile size in pixels  (overview)
      "zscale_a", "zscale_i", "zscale_y"  — corresponding z-scale values

    Falls back to the pre-decoded constants if the file is not found or
    cannot be parsed.
    """
    path = ko_path or _KO_PATH
    modes = {}
    try:
        src = path.read_text(encoding="utf-8")
        modes = _parse_cannabis_modes(src)
    except Exception:
        pass

    return {
        "tile_a":   modes.get("A", _TILE_A_DEFAULT),
        "tile_i":   modes.get("I", _TILE_I_DEFAULT),
        "tile_y":   modes.get("Y", _TILE_Y_DEFAULT),
        "zscale_a": 12,
        "zscale_i":  8,
        "zscale_y":  6,
    }


# ── Pre-decoded defaults (match renderer_bridge.ko Cannabis mode decode) ──────

_TILE_A_DEFAULT = 16   # renderer_bridge.ko LoYeshu: [A MavoTile Ao Shu ...]
_TILE_I_DEFAULT = 20   # renderer_bridge.ko LoYeshu: [I MavoTile Ao Shushy ...]
_TILE_Y_DEFAULT = 14   # renderer_bridge.ko LoYeshu: [Y MavoTile Ao Ye ...]

# Display scale: the GL renderer runs at 2× tile density relative to the
# DjinnOS native-resolution renderer.  Cannabis mode A = 16 → GL tile = 32.
_DISPLAY_SCALE = 2

# Tile size used by gl_world_play.py — Cannabis mode A at display scale.
TILE_SIZE: int = load_renderer_bridge()["tile_a"] * _DISPLAY_SCALE


# ── Colour constants (LoKiel pre-decode) ──────────────────────────────────────
#
# Mirrors src/renderer_bridge.rs and gl_world_play.py colour tables.
# All values are (R, G, B) matching PIL / Python convention.
#
# LoKiel decode targets (Stage 2 — Kobra VM will replace these):
#   PLAYER_FILL   ← MavoAorutakael MavoBg ZoFuMel
#   NPC_FILL      ← MavoAokitakael MavoBg KaAE
#   HUD_TEXT      ← MavoClusterTrustAuthMap Ha entry
#   HUD_ACCENT    ← MavoClusterTrustAuthMap Ko entry
#
# These match _PLAYER_FILL / _NPC_FILL / _HUD_TEXT / _HUD_ACCENT in
# gl_world_play.py exactly — single source of record.

PLAYER_FILL   = (220, 190, 100)
PLAYER_SHADOW = ( 80,  60,  20)
NPC_FILL      = (160, 160, 180)
NPC_SHADOW    = ( 60,  60,  70)
NPC_OUTLINE   = (100, 100, 120)
HUD_TEXT      = (200, 180, 130)
HUD_ACCENT    = (200, 155,  50)