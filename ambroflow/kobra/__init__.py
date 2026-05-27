"""
ambroflow.kobra — Kobra JIT Compiler + Runtime Shim
====================================================

Compiles Shygazun (or English) bracket compounds to the 12-layer
nested stack. The stack IS the compiled output.

Quick start:
    from ambroflow.kobra import get_runtime
    rt = get_runtime()
    rt.load("my_module.ko")
    rt.call("LoMyUnit")

See jit.py for types, runtime.py for the .ko loader shim.
kobra_jit.ko is the Kobra-native spec (replaces this shim eventually).
"""

from .jit import (
    Layer,
    GrammarRole,
    Mood,
    ByteEntry,
    CompiledToken,
    CompiledCompound,
    KobraStack,
    KobraJIT,
)
from .runtime import KobraRuntime, get_runtime

__all__ = [
    "Layer",
    "GrammarRole",
    "Mood",
    "ByteEntry",
    "CompiledToken",
    "CompiledCompound",
    "KobraStack",
    "KobraJIT",
    "KobraRuntime",
    "get_runtime",
]
