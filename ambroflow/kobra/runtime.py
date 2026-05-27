"""
ambroflow.kobra.runtime — .ko file loader and executor (SHIM)
=============================================================
Parses Kobra .ko source files, resolves Lo units, and executes
bracket compounds against the 12-layer DB via KobraJIT.

THIS IS A SHIM. Once the runtime is self-hosting, replace this
with a call to the Kobra bootstrap in kobra_jit.ko.

Public interface:
    rt = KobraRuntime()
    rt.load("path/to/file.ko")
    rt.call("LoName", ["token", "list"])   # compile + write to stack
    rt.read(Layer.FUNCTION)                # read from stack
    rt.snapshot()                          # full stack dump
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .jit import (
    GrammarRole, Mood, Layer,
    ByteEntry, CompiledToken, CompiledCompound,
    KobraStack, KobraJIT,
)


# ---------------------------------------------------------------------------
# .ko parser — minimal, handles the subset we actually write
# ---------------------------------------------------------------------------

# Lo<Name> : <type> { ... }
_LO_HEADER = re.compile(
    r'^Lo(\w+)\s*:\s*([^{]+?)\s*\{',
    re.MULTILINE,
)
# [token token token]
_COMPOUND = re.compile(r'\[([^\]]+)\]')
# Strip inline comments and meaning annotations (— ...)
_COMMENT   = re.compile(r'#[^\n]*')
_MEANING   = re.compile(r'\s*—.*')


def _strip(src: str) -> str:
    src = _COMMENT.sub('', src)
    src = _MEANING.sub('', src)
    return src


def _extract_body(src: str, start: int) -> tuple[str, int]:
    """
    Extract the content of a { } block starting at `start` (the opening {).
    Returns (body_text, index_after_closing_brace).
    Handles nested braces correctly.
    """
    depth = 0
    body_chars: list[str] = []
    i = start
    while i < len(src):
        ch = src[i]
        if ch == '{':
            if depth > 0:
                body_chars.append(ch)
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return ''.join(body_chars), i + 1
            body_chars.append(ch)
        else:
            if depth > 0:
                body_chars.append(ch)
        i += 1
    return ''.join(body_chars), i


def _parse_ko(src: str) -> dict[str, list[list[str]]]:
    """Parse .ko source into {lo_name: [[tokens], ...]} mapping."""
    units: dict[str, list[list[str]]] = {}
    clean = _strip(src)
    pos = 0
    while True:
        m = _LO_HEADER.search(clean, pos)
        if not m:
            break
        name = m.group(1)
        brace_start = m.end() - 1  # points at the `{`
        body, pos = _extract_body(clean, brace_start)
        compounds: list[list[str]] = []
        for match in _COMPOUND.finditer(body):
            raw = match.group(1).strip()
            tokens = [t for t in raw.split() if t]
            if tokens:
                compounds.append(tokens)
        units[name] = compounds
    return units


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

class KobraRuntime:
    """
    Thin shim: loads .ko files, compiles their Lo units on demand,
    writes to and reads from the shared 12-layer KobraStack.
    """

    def __init__(self) -> None:
        self._jit = KobraJIT()
        self._units: dict[str, list[list[str]]] = {}   # name → raw token lists
        self._cache: dict[str, list[CompiledCompound]] = {}  # name → compiled

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, path: str | Path) -> "KobraRuntime":
        """Parse a .ko file and register its Lo units. Chainable."""
        src = Path(path).read_text(encoding="utf-8")
        parsed = _parse_ko(src)
        self._units.update(parsed)
        # Invalidate cache for reloaded names
        for name in parsed:
            self._cache.pop(name, None)
        return self

    def load_str(self, src: str, label: str = "<inline>") -> "KobraRuntime":
        """Parse a .ko string directly. Useful for inline declarations."""
        parsed = _parse_ko(src)
        self._units.update(parsed)
        for name in parsed:
            self._cache.pop(name, None)
        return self

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def call(
        self,
        lo_name: str,
        tokens: Optional[list[str]] = None,
    ) -> list[CompiledCompound]:
        """
        Execute a Lo unit by name.
        If tokens is provided, compile that single compound instead of
        running all compounds in the Lo block.
        Returns the list of compiled compounds written to the stack.
        """
        if tokens is not None:
            compound = self._jit.compile_and_write(tokens, source=lo_name)
            return [compound]

        if lo_name not in self._units:
            raise KeyError(f"Lo unit not found: {lo_name!r}")

        if lo_name in self._cache:
            return self._cache[lo_name]

        results: list[CompiledCompound] = []
        for token_list in self._units[lo_name]:
            compound = self._jit.compile_and_write(token_list, source=lo_name)
            results.append(compound)
        self._cache[lo_name] = results
        return results

    def compile(self, tokens: list[str]) -> CompiledCompound:
        """Compile a token list to a CompiledCompound without writing to stack."""
        return self._jit.compile_compound(tokens)

    # ------------------------------------------------------------------
    # Stack access
    # ------------------------------------------------------------------

    def read(self, layer: Layer) -> list[CompiledCompound]:
        return self._jit.stack.read(layer)

    def snapshot(self) -> dict[int, list[str]]:
        return self._jit.stack.snapshot()

    def flush(self, layer: Layer) -> None:
        self._jit.stack.flush(layer)

    @property
    def stack(self) -> KobraStack:
        return self._jit.stack

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def units(self) -> list[str]:
        """List all loaded Lo unit names."""
        return list(self._units.keys())

    def __repr__(self) -> str:
        return f"KobraRuntime(units={len(self._units)}, stack={self.snapshot()})"


# ---------------------------------------------------------------------------
# Module-level singleton — both repos import this
# ---------------------------------------------------------------------------

_runtime: Optional[KobraRuntime] = None


def get_runtime() -> KobraRuntime:
    """Return the shared runtime instance, loading kobra_jit.ko on first call."""
    global _runtime
    if _runtime is None:
        _runtime = KobraRuntime()
        _ko_root = Path(__file__).parent
        jit_ko = _ko_root / "kobra_jit.ko"
        if jit_ko.exists():
            _runtime.load(jit_ko)
    return _runtime
