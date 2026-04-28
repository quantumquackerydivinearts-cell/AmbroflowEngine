"""
Free World Combat
=================
Handles player-initiated combat against any NPC in the waking world.

Unlike dungeon encounters (which are scripted), free combat can be
initiated against any NPC the player is facing — including quest-critical
characters.  There are no guard rails.

Resolution uses the same skill-rank logic as the dungeon encounter resolver:
the player's best combat skill (melee_weapons / guns / unarmed) vs. a
per-NPC difficulty derived from character type.

Combat is turn-based.  Each round the player chooses attack or flee.
The NPC always counterattacks — even on rounds the player lands a hit.
Death is permadeath; the only recovery is loading a BreathOfKo save.

Health pool:   Vitality × 10   (10–100 HP)
NPC hits:      round(difficulty × 10)   (1–10 hits to kill)
NPC damage:    round(difficulty × 20) per round   (5–20)
Endurance:     bell curve on Tactility; peaks at T=6 (50% reduction)

Tile Tracer deposits:
  Attack initiated  → Fy  (4)   thought toward   (each round re-committed)
  Player wins       → Ku  (7)   death / end  +  Zo (16) absence
  Player flees      → Pu  (5)   stasis / stuck
  Player dead       → La  (11)  tense / excited

NPC type difficulty table
-------------------------
  TOWN  0.25   WTCH  0.45   PRST  0.35   ASSN  0.65
  ROYL  0.40   GNOM  0.30   NYMP  0.35   UNDI  0.55
  SALA  0.60   DRYA  0.40   DJNN  0.70   VDWR  0.90
  DMON  0.80   DEMI  0.85   SOLD  0.55   GODS  0.98
  PRIM  0.95   ANMU  0.75
  default 0.50
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False

# ── NPC difficulty by character type ─────────────────────────────────────────

_TYPE_DIFFICULTY: dict[str, float] = {
    "TOWN": 0.25, "WTCH": 0.45, "PRST": 0.35, "ASSN": 0.65,
    "ROYL": 0.40, "GNOM": 0.30, "NYMP": 0.35, "UNDI": 0.55,
    "SALA": 0.60, "DRYA": 0.40, "DJNN": 0.70, "VDWR": 0.90,
    "DMON": 0.80, "DEMI": 0.85, "SOLD": 0.55, "GODS": 0.98,
    "PRIM": 0.95, "ANMU": 0.75,
}

# Fully immune to conventional weapons — Gold rounds required
_IMMUNE_TYPES: frozenset[str] = frozenset({
    "GNOM", "NYMP", "UNDI", "SALA", "DRYA", "DJNN",
    "VDWR", "DMON", "DEMI", "GODS", "PRIM", "ANMU",
})

# Metaphysical resistance — conventional difficulty is doubled
_RESISTANT_TYPES: frozenset[str] = frozenset({"WTCH"})
_RESISTANCE_MULTIPLIER = 2.0

AMMO_GOLD_ROUNDS    = "0040_KLIT"
WEAPON_ANGELIC_SPEAR = "0024_KLIT"

# Either item bypasses supernatural immunity and witch resistance
_ANGELIC_GEAR: frozenset[str] = frozenset({AMMO_GOLD_ROUNDS, WEAPON_ANGELIC_SPEAR})

_BG   = (18, 14, 12)
_GOLD = (200, 168, 75)
_RED  = (180,  60,  60)
_DIM  = (120, 110,  95)
_TEXT = (220, 215, 200)


def npc_difficulty(character_id: str) -> float:
    """Derive difficulty from the type suffix of a character ID (e.g. '0007_WTCH')."""
    parts = character_id.split("_", 1)
    ctype = parts[1] if len(parts) == 2 else ""
    return _TYPE_DIFFICULTY.get(ctype, 0.50)


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class CombatResult:
    outcome:      str              # "player_wins" | "player_flees" | "npc_wins"
    npc_id:       str
    npc_name:     str
    sanity_delta: dict[str, float]


def resolve_combat(
    npc_id:      str,
    npc_name:    str,
    skill_ranks: dict[str, int],
    equipped:    str | None = None,
) -> CombatResult:
    """
    Resolve a single free-combat exchange.

    Uses the player's best combat skill rank (1–50) against npc_difficulty().
    Outcome is deterministic — same inputs always produce the same result.

    Supernatural types (_IMMUNE_TYPES) require angelic gear (Gold rounds or
    Angelic Spear) to hit at all.  Witches (_RESISTANT_TYPES) double the
    effective difficulty for conventional weapons; angelic gear bypasses this.
    """
    parts = npc_id.split("_", 1)
    ctype = parts[1] if len(parts) == 2 else ""

    has_angelic = (equipped in _ANGELIC_GEAR)

    if ctype in _IMMUNE_TYPES and not has_angelic:
        return CombatResult(
            outcome="npc_wins",
            npc_id=npc_id,
            npc_name=npc_name,
            sanity_delta={"terrestrial": -0.05, "alchemical": -0.02},
        )

    difficulty = npc_difficulty(npc_id)
    if ctype in _RESISTANT_TYPES and not has_angelic:
        difficulty *= _RESISTANCE_MULTIPLIER

    rank = max(
        skill_ranks.get("melee_weapons", 0),
        skill_ranks.get("guns",          0),
        skill_ranks.get("unarmed",       0),
    )
    effective = rank / 50.0

    if effective >= difficulty:
        return CombatResult(
            outcome="player_wins",
            npc_id=npc_id,
            npc_name=npc_name,
            sanity_delta={"terrestrial": 0.01, "narrative": -0.03},
        )
    elif effective >= difficulty * 0.5:
        return CombatResult(
            outcome="player_flees",
            npc_id=npc_id,
            npc_name=npc_name,
            sanity_delta={"terrestrial": -0.01},
        )
    else:
        return CombatResult(
            outcome="npc_wins",
            npc_id=npc_id,
            npc_name=npc_name,
            sanity_delta={"terrestrial": -0.05, "alchemical": -0.02},
        )


# ── Turn-based loop ───────────────────────────────────────────────────────────

def player_health_from_vitality(vitality: int) -> int:
    """Health pool: Vitality × 10  (range 10–100)."""
    return vitality * 10


def npc_hits_to_kill(difficulty: float) -> int:
    """How many player hits the NPC absorbs before dying (3–10)."""
    return max(1, round(difficulty * 10))


def npc_damage_per_hit(difficulty: float) -> int:
    """Raw damage the NPC deals each round before endurance reduction (5–20)."""
    return max(1, round(difficulty * 20))


def endurance_reduction(tactility: int) -> float:
    """
    Damage reduction fraction from Tactility (1–10).
    Bell curve peaking at T=6 (0.50 = 50% reduction).
    T=1 → ~0.07, T=10 → ~0.21.
    """
    return 0.5 * math.exp(-((tactility - 6.0) ** 2) / 8.0)


def _add_sanity(delta: dict[str, float], key: str, amount: float) -> None:
    delta[key] = delta.get(key, 0.0) + amount


@dataclass
class CombatLoop:
    """Mutable state for one turn-based combat encounter."""
    npc_id:         str
    npc_name:       str
    equipped:       str | None
    player_health:  int
    player_max:     int
    npc_hits_left:  int
    npc_hits_max:   int
    effective:      float          # rank / 50.0
    eff_difficulty: float          # difficulty after resistance modifier
    npc_damage:     int            # raw damage per round
    reduction:      float          # endurance reduction fraction
    round_num:      int                    = 0
    outcome:        str | None             = None   # None = ongoing
    sanity_delta:   dict[str, float]       = field(default_factory=dict)
    log:            list[str]              = field(default_factory=list)

    @property
    def is_over(self) -> bool:
        return self.outcome is not None


def begin_combat_loop(
    npc_id:      str,
    npc_name:    str,
    skill_ranks: dict[str, int],
    vitality:    int,
    tactility:   int,
    equipped:    str | None = None,
) -> CombatLoop:
    """Initialise a CombatLoop.  No rounds are executed yet."""
    parts = npc_id.split("_", 1)
    ctype = parts[1] if len(parts) == 2 else ""
    has_angelic = equipped in _ANGELIC_GEAR

    rank = max(
        skill_ranks.get("melee_weapons", 0),
        skill_ranks.get("guns",          0),
        skill_ranks.get("unarmed",       0),
    )
    effective = rank / 50.0

    base_diff    = npc_difficulty(npc_id)
    eff_diff     = base_diff
    if ctype in _RESISTANT_TYPES and not has_angelic:
        eff_diff *= _RESISTANCE_MULTIPLIER

    return CombatLoop(
        npc_id=npc_id,
        npc_name=npc_name,
        equipped=equipped,
        player_health=player_health_from_vitality(vitality),
        player_max=player_health_from_vitality(vitality),
        npc_hits_left=npc_hits_to_kill(base_diff),
        npc_hits_max=npc_hits_to_kill(base_diff),
        effective=effective,
        eff_difficulty=eff_diff,
        npc_damage=npc_damage_per_hit(base_diff),
        reduction=endurance_reduction(tactility),
    )


def execute_round(loop: CombatLoop, action: str) -> CombatLoop:
    """
    Process one round in-place.  action is 'attack' or 'flee'.
    Sanity accumulates across rounds; outcome is set when the loop ends.
    """
    if loop.is_over:
        return loop

    parts = loop.npc_id.split("_", 1)
    ctype = parts[1] if len(parts) == 2 else ""
    has_angelic = loop.equipped in _ANGELIC_GEAR
    actual_npc_dmg = max(1, round(loop.npc_damage * (1.0 - loop.reduction)))

    loop.round_num += 1
    entry = f"Round {loop.round_num}: "

    if action == "flee":
        loop.player_health -= actual_npc_dmg
        entry += f"You flee. {loop.npc_name} strikes as you run ({actual_npc_dmg} dmg)."
        loop.log.append(entry)
        _add_sanity(loop.sanity_delta, "terrestrial", -0.01)
        loop.outcome = "player_dead" if loop.player_health <= 0 else "player_flees"
        return loop

    # Immune without angelic gear — can't land a blow
    if ctype in _IMMUNE_TYPES and not has_angelic:
        loop.player_health -= actual_npc_dmg
        entry += f"Your attack has no effect. {loop.npc_name} strikes ({actual_npc_dmg} dmg)."
        loop.log.append(entry)
        if loop.player_health <= 0:
            loop.outcome = "player_dead"
        return loop

    # Player attacks
    if loop.effective >= loop.eff_difficulty:
        loop.npc_hits_left -= 1
        entry += f"You hit {loop.npc_name}. "
        _add_sanity(loop.sanity_delta, "narrative", -0.01)
    else:
        entry += "Your attack is deflected. "

    # NPC always counterattacks
    loop.player_health -= actual_npc_dmg
    entry += f"{loop.npc_name} strikes back ({actual_npc_dmg} dmg)."

    if loop.npc_hits_left <= 0:
        loop.outcome = "player_wins"
        entry += f" {loop.npc_name} falls."
        _add_sanity(loop.sanity_delta, "terrestrial",  0.01)
        _add_sanity(loop.sanity_delta, "narrative",   -0.03)
    elif loop.player_health <= 0:
        loop.outcome = "player_dead"
        entry += " You collapse."

    loop.log.append(entry)
    return loop


def to_result(loop: CombatLoop) -> CombatResult:
    """Convert a finished CombatLoop to a CombatResult for downstream processing."""
    return CombatResult(
        outcome=loop.outcome or "npc_wins",
        npc_id=loop.npc_id,
        npc_name=loop.npc_name,
        sanity_delta=dict(loop.sanity_delta),
    )


# ── Screen renderer ───────────────────────────────────────────────────────────

def _load_font(size: int):
    if not _PIL:
        return None
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _text_w(draw, text: str, font) -> int:
    try:
        b = draw.textbbox((0, 0), text, font=font)
        return b[2] - b[0]
    except AttributeError:
        return draw.textsize(text, font=font)[0]  # type: ignore[attr-defined]


def _to_png(img: "Image.Image") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class CombatScreen:
    """
    Renders PIL frames for the turn-based combat modal:
      prompt      — "Attack <Name>?" confirmation
      round       — live health bars + last round log
      result      — outcome after loop ends (win / flee)
      dead        — permadeath screen
    """

    def render_prompt(
        self,
        npc_name:     str,
        npc_id:       str,
        width:  int = 1280,
        height: int = 800,
    ) -> Optional[bytes]:
        if not _PIL:
            return None
        W, H = width, height
        img  = Image.new("RGB", (W, H), _BG)
        draw = ImageDraw.Draw(img)

        f_title = _load_font(18)
        f_sub   = _load_font(13)
        f_hint  = _load_font(11)
        f_diff  = _load_font(10)

        title = f"Attack {npc_name}?"
        tw = _text_w(draw, title, f_title)
        draw.text(((W - tw) // 2, int(H * 0.38)), title, fill=_RED, font=f_title)

        diff = npc_difficulty(npc_id)
        diff_label = f"Threat level: {'low' if diff < 0.4 else 'moderate' if diff < 0.7 else 'high' if diff < 0.9 else 'extreme'}"
        dw = _text_w(draw, diff_label, f_diff)
        draw.text(((W - dw) // 2, int(H * 0.50)), diff_label, fill=_DIM, font=f_diff)

        hint = "[f]  Attack     [esc]  Back"
        hw = _text_w(draw, hint, f_hint)
        draw.text(((W - hw) // 2, int(H * 0.88)), hint, fill=_DIM, font=f_hint)

        return _to_png(img)

    def render_result(
        self,
        result: CombatResult,
        width:  int = 1280,
        height: int = 800,
    ) -> Optional[bytes]:
        if not _PIL:
            return None
        W, H = width, height
        img  = Image.new("RGB", (W, H), _BG)
        draw = ImageDraw.Draw(img)

        f_title = _load_font(18)
        f_body  = _load_font(13)
        f_hint  = _load_font(11)

        if result.outcome == "player_wins":
            title = f"{result.npc_name} is dead."
            color = _RED
        elif result.outcome == "player_flees":
            title = "You flee."
            color = _DIM
        else:
            title = f"{result.npc_name} drives you back."
            color = _GOLD

        tw = _text_w(draw, title, f_title)
        draw.text(((W - tw) // 2, int(H * 0.40)), title, fill=color, font=f_title)

        hint = "[space]  Continue"
        hw = _text_w(draw, hint, f_hint)
        draw.text(((W - hw) // 2, int(H * 0.88)), hint, fill=_DIM, font=f_hint)

        return _to_png(img)

    def render_round(
        self,
        loop:   CombatLoop,
        width:  int = 1280,
        height: int = 800,
    ) -> Optional[bytes]:
        if not _PIL:
            return None
        W, H = width, height
        img  = Image.new("RGB", (W, H), _BG)
        draw = ImageDraw.Draw(img)

        f_title = _load_font(16)
        f_body  = _load_font(13)
        f_hint  = _load_font(11)

        # NPC name + hit indicators
        npc_label = f"{loop.npc_name}"
        nw = _text_w(draw, npc_label, f_title)
        draw.text(((W - nw) // 2, int(H * 0.10)), npc_label, fill=_RED, font=f_title)

        hits_str = "◆" * loop.npc_hits_left + "◇" * (loop.npc_hits_max - loop.npc_hits_left)
        hw2 = _text_w(draw, hits_str, f_body)
        draw.text(((W - hw2) // 2, int(H * 0.20)), hits_str, fill=_RED, font=f_body)

        # Player HP bar
        hp_label = f"HP  {loop.player_health} / {loop.player_max}"
        hp_pct   = max(0.0, loop.player_health / loop.player_max)
        bar_w    = int(W * 0.4)
        bar_x    = (W - bar_w) // 2
        bar_y    = int(H * 0.32)
        draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 10], fill=_DIM)
        draw.rectangle([bar_x, bar_y, bar_x + int(bar_w * hp_pct), bar_y + 10],
                       fill=(80, 180, 80) if hp_pct > 0.5 else _GOLD if hp_pct > 0.25 else _RED)
        hl = _text_w(draw, hp_label, f_body)
        draw.text(((W - hl) // 2, bar_y + 16), hp_label, fill=_TEXT, font=f_body)

        # Last log entry
        if loop.log:
            log_line = loop.log[-1]
            lw = _text_w(draw, log_line, f_body)
            draw.text(((W - min(lw, W - 40)) // 2, int(H * 0.55)), log_line,
                      fill=_TEXT, font=f_body)

        hint = "[f]  Attack     [esc]  Flee"
        hw3 = _text_w(draw, hint, f_hint)
        draw.text(((W - hw3) // 2, int(H * 0.88)), hint, fill=_DIM, font=f_hint)

        return _to_png(img)

    def render_dead(
        self,
        loop:   CombatLoop,
        width:  int = 1280,
        height: int = 800,
    ) -> Optional[bytes]:
        if not _PIL:
            return None
        W, H = width, height
        img  = Image.new("RGB", (W, H), _BG)
        draw = ImageDraw.Draw(img)

        f_title = _load_font(22)
        f_body  = _load_font(13)
        f_hint  = _load_font(11)

        title = "YOU ARE DEAD."
        tw = _text_w(draw, title, f_title)
        draw.text(((W - tw) // 2, int(H * 0.35)), title, fill=_RED, font=f_title)

        sub = f"Killed by {loop.npc_name}."
        sw = _text_w(draw, sub, f_body)
        draw.text(((W - sw) // 2, int(H * 0.50)), sub, fill=_DIM, font=f_body)

        hint = "[space]  Load save"
        hw = _text_w(draw, hint, f_hint)
        draw.text(((W - hw) // 2, int(H * 0.88)), hint, fill=_DIM, font=f_hint)

        return _to_png(img)