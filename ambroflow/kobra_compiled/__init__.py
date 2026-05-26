"""ambroflow/kobra_compiled — Compiled Kobra modules.

This package contains Python modules emitted by the Kobra compiler
(shygazun/kobra/) from the canonical .ko source files in DjinnOS.

The BoK engine (bok_engine.py) is compiled from:
    selfspec.ko  LoLao  — BreathOfKo mathematics
    selfspec.ko  LoYeshu — Julia set topology
"""
from .bok_engine import (
    azoth_lo,
    mobius_coil,
    coil_ep,
    julia_fa_ung,
    julia_fa_fy,
    azoth_shak,
    azoth_mobius_foa,
    azoth_su_foa,
    shi_bi,
    ke_shi_bi,
    shi_ke_bi,
    ko_foa_shi_ke_wu_ung,
    PufFyLoVaShy,
    puf_fy_lo_shak,
    puf_fy_lo_shi_wu_ung,
    puf_fy_lo_ke_wu_ung,
    puf_fy_lo_ep_em,
)

__all__ = [
    "azoth_lo",
    "mobius_coil",
    "coil_ep",
    "julia_fa_ung",
    "julia_fa_fy",
    "azoth_shak",
    "azoth_mobius_foa",
    "azoth_su_foa",
    "shi_bi",
    "ke_shi_bi",
    "shi_ke_bi",
    "ko_foa_shi_ke_wu_ung",
    "PufFyLoVaShy",
    "puf_fy_lo_shak",
    "puf_fy_lo_shi_wu_ung",
    "puf_fy_lo_ke_wu_ung",
    "puf_fy_lo_ep_em",
]
