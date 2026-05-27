"""
SamosMyr ↔ Ambroflow Bridge
============================
Parses SamosMyr scene expressions into structured Python objects and
converts them to Lock instances for the key-lock system.

Grammar (extended):
    scene       ::= ident ":" coherence interior? reversible? body?
    interior    ::= "(" symbol* ")"
    reversible  ::= "[" "reversible" "]"
    body        ::= "{" entity_spec* "}"
    entity_spec ::= "[" entity_item* "]"
    entity_item ::= closure | temporal | symbol
    closure     ::= ("Ga" | "Va") "(" ident ")"
    temporal    ::= symbol "(" symbol ")"
    symbol      ::= WORD

Ga(X) — permanent closure of scene X when this scene resolves.
Va(X) — restoration of scene X (only valid if X carries [reversible]).

Cannabis entries in entity specs map to required keys in Lock.requires.
Ga/Va ops are resolved at the script level, not the single-scene level.
Cross-scene validation (Va requires [reversible] target) happens in
SamosMyrScript.validate().
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

try:
    from pathlib import Path as _Path
    from ..kobra import get_runtime as _kobra_get_rt
    _samosmyr_ko = _Path(__file__).parent / "samosmyr.ko"
    if _samosmyr_ko.exists():
        _rt = _kobra_get_rt()
        if "SamosMyr" not in _rt.units():
            _rt.load(_samosmyr_ko)
except ImportError:
    pass

if TYPE_CHECKING:
    from .key_registry import KeyRegistry
    from .schema import Lock


# ── Token types ───────────────────────────────────────────────────────────────

_DELIMS = set("[]{}();:")
_WS     = set(" \t\r\n")

CLOSURE_OPS = frozenset(("Ga", "Va"))


@dataclass
class _Token:
    kind: str   # "W" (word) | delimiter char | "EOF"
    val:  str


def _tokenise(src: str) -> list[_Token]:
    tokens: list[_Token] = []
    i = 0
    while i < len(src):
        ch = src[i]
        if ch in _WS:
            i += 1
            continue
        if ch in _DELIMS:
            tokens.append(_Token(ch, ch))
            i += 1
            continue
        j = i
        while j < len(src) and src[j] not in _WS and src[j] not in _DELIMS:
            j += 1
        tokens.append(_Token("W", src[i:j]))
        i = j
    tokens.append(_Token("EOF", ""))
    return tokens


# ── Structured parse results ──────────────────────────────────────────────────

@dataclass
class ClosureOp:
    op:     str   # "Ga" | "Va"
    target: str   # target scene ident string


@dataclass
class EntitySpec:
    words:       list[str]
    cannabis:    list[str]   # Cannabis-tongue symbols (witness gates → required keys)
    closure_ops: list[ClosureOp]


@dataclass
class SamosMyrScene:
    """
    A parsed SamosMyr scene expression.

    ident:       Rose numeral identity sequence
    coherence:   Shygazun coherence word
    interior:    interior qualification words
    reversible:  True if scene carries [reversible] — can be reopened by Va
    entity_specs: parsed entity blocks
    temporal:    TaShyMa temporal closure (operator, address, seconds) or None
    closure_ops: all Ga/Va operators across all entity specs

    cannabis:    flat list of all Cannabis entries across all entity specs
                 (= required keys in the Lock)
    """
    ident:        str
    coherence:    str
    interior:     list[str]
    reversible:   bool
    entity_specs: list[EntitySpec]
    temporal:     Optional[dict]
    closure_ops:  list[ClosureOp]

    @property
    def cannabis(self) -> list[str]:
        seen: set[str] = set()
        out:  list[str] = []
        for spec in self.entity_specs:
            for c in spec.cannabis:
                if c not in seen:
                    seen.add(c)
                    out.append(c)
        return out

    @property
    def ga_targets(self) -> list[str]:
        return [op.target for op in self.closure_ops if op.op == "Ga"]

    @property
    def va_targets(self) -> list[str]:
        return [op.target for op in self.closure_ops if op.op == "Va"]

    def to_lock(
        self,
        registry: "KeyRegistry",
        excludes: Optional[list[str]] = None,
    ) -> "Lock":
        """
        Convert this scene's Cannabis entries to a Lock.

        Cannabis entries → Lock.requires (via registry.validate_shygazun).
        excludes: additional yeigo strings to exclude (from Ga() counter-scenes
                  in the parent SamosMyrScript).
        time_window is derived from TaShyMa seconds → hour.
        """
        from .schema import Lock
        requires = [registry.validate_shygazun(c) for c in self.cannabis]
        time_window = None
        if self.temporal:
            secs = self.temporal.get("seconds", 0)
            hour = (secs // 60) % 24
            time_window = (hour, (hour + 1) % 24)
        return Lock(
            requires=requires,
            excludes=list(excludes or []),
            time_window=time_window,
        )


# ── Cannabis symbol set ───────────────────────────────────────────────────────
# Cannabis is Tongue 8 (bytes 184–213).  These are the witness-gate symbols.
# Populated lazily from the byte table if available; fallback to a known set.

def _load_cannabis_syms() -> frozenset[str]:
    try:
        import sys, pathlib
        _root = str(pathlib.Path(__file__).parent.parent.parent.parent / "DjinnOS_Shyagzun")
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from shygazun.kernel.constants.byte_table import byte_rows
        return frozenset(
            r["symbol"] if isinstance(r, dict) else r.symbol
            for r in byte_rows()
            if (r["tongue"] if isinstance(r, dict) else r.tongue) == "Cannabis"
        )
    except Exception:
        return frozenset()


_CANNABIS_SYMS: Optional[frozenset[str]] = None


def cannabis_syms() -> frozenset[str]:
    global _CANNABIS_SYMS
    if _CANNABIS_SYMS is None:
        _CANNABIS_SYMS = _load_cannabis_syms()
    return _CANNABIS_SYMS


# ── Parser ────────────────────────────────────────────────────────────────────

class _Parser:
    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._pos    = 0

    def _peek(self) -> _Token:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else _Token("EOF", "")

    def _consume(self) -> _Token:
        t = self._peek()
        self._pos += 1
        return t

    def _expect(self, kind: str) -> _Token:
        t = self._consume()
        if t.kind != kind:
            raise ValueError(f"Expected {kind!r}, got {t.kind!r} ({t.val!r})")
        return t

    def parse_scene(self) -> SamosMyrScene:
        # ident
        ident = self._peek().val if self._peek().kind == "W" else ""
        if self._peek().kind == "W":
            self._consume()
        self._expect(":")

        # coherence
        coherence = ""
        if self._peek().kind == "W":
            coherence = self._consume().val

        # interior (...)
        interior: list[str] = []
        if self._peek().kind == "(":
            self._consume()
            while self._peek().kind not in (")", "EOF"):
                if self._peek().kind == "W":
                    interior.append(self._consume().val)
                else:
                    self._consume()
            if self._peek().kind == ")":
                self._consume()

        # [reversible] modifier
        reversible = False
        if self._peek().kind == "[":
            saved = self._pos
            self._consume()
            if self._peek().kind == "W" and self._peek().val.lower() == "reversible":
                self._consume()
                if self._peek().kind == "]":
                    self._consume()
                    reversible = True
                else:
                    self._pos = saved
            else:
                self._pos = saved

        # body {...}
        entity_specs: list[EntitySpec] = []
        temporal:     Optional[dict]   = None
        all_closure:  list[ClosureOp]  = []

        if self._peek().kind == "{":
            self._consume()
            while self._peek().kind not in ("}", "EOF"):
                if self._peek().kind == "[":
                    spec, t_op, cops = self._parse_entity_spec()
                    if t_op:
                        temporal = t_op
                    all_closure.extend(cops)
                    if spec is not None:
                        entity_specs.append(spec)
                else:
                    self._consume()
            if self._peek().kind == "}":
                self._consume()

        # Validate
        ga_tgts = {op.target for op in all_closure if op.op == "Ga"}
        va_tgts = {op.target for op in all_closure if op.op == "Va"}
        if ident in ga_tgts or ident in va_tgts:
            raise ValueError(f"Closure op references own ident {ident!r} — self-reference not allowed")
        for tgt in ga_tgts:
            if tgt in va_tgts:
                raise ValueError(f"Ga({tgt}) and Va({tgt}) in same scene — contradictory")

        return SamosMyrScene(
            ident        = ident,
            coherence    = coherence,
            interior     = interior,
            reversible   = reversible,
            entity_specs = entity_specs,
            temporal     = temporal,
            closure_ops  = all_closure,
        )

    def _parse_entity_spec(self) -> tuple[Optional[EntitySpec], Optional[dict], list[ClosureOp]]:
        """
        Parse one [...] block.
        Returns (EntitySpec|None, temporal_closure|None, closure_ops).
        temporal_closure is set for TaShyMa blocks (no EntitySpec produced).
        """
        self._consume()  # "["
        words:   list[str]     = []
        cops:    list[ClosureOp] = []
        temporal: Optional[dict] = None
        is_temporal_block = False
        cset = cannabis_syms()

        while self._peek().kind not in ("]", "EOF"):
            t = self._consume()
            if t.kind == "W":
                if self._peek().kind == "(":
                    # operator(arg) — Ga/Va or TaShyMa
                    op_name = t.val
                    self._consume()  # "("
                    arg = self._peek().val if self._peek().kind == "W" else ""
                    if self._peek().kind == "W":
                        self._consume()
                    while self._peek().kind not in (")", "EOF"):
                        self._consume()
                    if self._peek().kind == ")":
                        self._consume()

                    if op_name in CLOSURE_OPS:
                        cops.append(ClosureOp(op=op_name, target=arg))
                    else:
                        # TaShyMa or other temporal operator
                        is_temporal_block = True
                        secs = _eval_temporal_address(arg)
                        temporal = {
                            "operator": op_name,
                            "address":  arg,
                            "seconds":  secs,
                        }
                else:
                    words.append(t.val)

        if self._peek().kind == "]":
            self._consume()

        if is_temporal_block:
            # Temporal blocks don't produce entity specs
            return None, temporal, cops

        if not words:
            # Closure-only blocks: ops already tracked, no entity spec needed
            return None, None, cops

        # Segment words into symbols to find Cannabis entries
        syms: list[str] = []
        for w in words:
            syms.extend(_segment(w))
        cannab = [s for s in syms if s in cset]

        spec = EntitySpec(words=words, cannabis=cannab, closure_ops=cops)
        return spec, None, cops


# ── Symbol segmentation ───────────────────────────────────────────────────────
# Mirrors the JS segmentRaw() — greedy longest-match against known symbols.

_ALL_SYMS: Optional[list[str]] = None


def _get_all_syms() -> list[str]:
    global _ALL_SYMS
    if _ALL_SYMS is None:
        try:
            import sys, pathlib
            _root = str(pathlib.Path(__file__).parent.parent.parent.parent / "DjinnOS_Shyagzun")
            if _root not in sys.path:
                sys.path.insert(0, _root)
            from shygazun.kernel.constants.byte_table import byte_rows
            syms = sorted(
                {r["symbol"] if isinstance(r, dict) else r.symbol for r in byte_rows()},
                key=lambda s: -len(s),
            )
            _ALL_SYMS = syms
        except Exception:
            _ALL_SYMS = []
    return _ALL_SYMS


def _segment(raw: str) -> list[str]:
    syms = _get_all_syms()
    out: list[str] = []
    pos = 0
    while pos < len(raw):
        matched = False
        for s in syms:
            if raw.startswith(s, pos):
                out.append(s)
                pos += len(s)
                matched = True
                break
        if not matched:
            pos += 1
    return out


def _eval_temporal_address(raw: str) -> int:
    rose_digit = {
        "Gaoh": 0, "Ao": 1, "Ye": 2, "Ui": 3, "Shu": 4, "Kiel": 5,
        "Yeshu": 6, "Lao": 7, "Shushy": 8, "Uinshu": 9, "Kokiel": 10, "Aonkiel": 11,
    }
    syms = _segment(raw)
    nums = [s for s in syms if s in rose_digit]
    result = 0
    for n in nums:
        result = result * 12 + rose_digit[n]
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def parse_scene(src: str) -> SamosMyrScene:
    """Parse a single SamosMyr scene expression."""
    tokens = _tokenise(src.strip())
    return _Parser(tokens).parse_scene()


# ── SamosMyrScript — collection of scenes with cross-scene validation ─────────

@dataclass
class SamosMyrScript:
    """
    A collection of SamosMyr scenes forming a quest or script.

    Cross-scene validation:
      - Va(X) requires X to carry [reversible]
      - Ga(X) target must exist in the script
      - Va(X) target must exist in the script
    """
    scenes: list[SamosMyrScene]

    @classmethod
    def from_text(cls, src: str) -> "SamosMyrScript":
        """
        Parse multiple scene expressions from a text block.
        Scenes are separated by blank lines or parsed greedily.
        """
        scenes = []
        # Split on blank lines between scenes
        blocks = re.split(r"\n\s*\n", src.strip())
        for block in blocks:
            block = block.strip()
            if block and not block.startswith("#"):
                try:
                    scenes.append(parse_scene(block))
                except Exception as exc:
                    raise ValueError(f"Parse error in scene block:\n{block}\n→ {exc}") from exc
        return cls(scenes=scenes)

    def validate(self) -> list[str]:
        """
        Run cross-scene validation. Returns list of error strings.
        Empty list = valid.
        """
        errors: list[str] = []
        by_ident = {s.ident: s for s in self.scenes}

        for scene in self.scenes:
            for op in scene.closure_ops:
                if op.target not in by_ident:
                    errors.append(
                        f"{scene.ident}: {op.op}({op.target}) — target not found in script"
                    )
                    continue
                if op.op == "Va":
                    target_scene = by_ident[op.target]
                    if not target_scene.reversible:
                        errors.append(
                            f"{scene.ident}: Va({op.target}) — target is not declared [reversible]"
                        )
        return errors

    def scene(self, ident: str) -> Optional[SamosMyrScene]:
        for s in self.scenes:
            if s.ident == ident:
                return s
        return None
