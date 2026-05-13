"""
ambroflow/world/action_handlers.py
====================================
Scene interaction action → Ambroflow system dispatch.

Every named entity in a .ko scene with tag="interaction" carries an
action_id derived from its MavoExitXxx / MavoOpenXxx token.  When the
player presses E at that entity's position, WorldPlay calls:

    result = dispatch(action_id, context)

Each handler returns an ActionResult that WorldPlay acts on.

Adding a new interaction type:
    1. Register a handler function decorated with @handler("action_id")
    2. The function receives an ActionContext and returns ActionResult

Handlers are pure functions — all state access goes through ActionContext.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class ActionResult:
    ok:          bool            = True
    kind:        str             = "none"       # none | scene_transition | ui_open | save
    scene_id:    Optional[str]   = None
    spawn_id:    Optional[str]   = None
    ui:          Optional[str]   = None         # "alchemy" | "smelt" | "inventory" | …
    message:     Optional[str]   = None

    @classmethod
    def noop(cls) -> "ActionResult":
        return cls(ok=True, kind="none")

    @classmethod
    def transition(cls, scene_id: str, spawn_id: str = "spawn_point") -> "ActionResult":
        return cls(ok=True, kind="scene_transition", scene_id=scene_id, spawn_id=spawn_id)

    @classmethod
    def open_ui(cls, ui_name: str) -> "ActionResult":
        return cls(ok=True, kind="ui_open", ui=ui_name)

    @classmethod
    def save_and_heal(cls) -> "ActionResult":
        return cls(ok=True, kind="save")

    @classmethod
    def unknown(cls, action_id: str) -> "ActionResult":
        return cls(ok=False, kind="none", message=f"unhandled action: {action_id}")


@dataclass
class ActionContext:
    """Everything a handler needs to resolve an action."""
    action_id:   str
    entity_id:   str             = ""
    player_x:    float           = 0.0
    player_y:    float           = 0.0
    player_z:    float           = 0.0
    scene_id:    str             = ""
    realm_id:    str             = "lapidus"
    world_graph: Any             = None   # WorldGraph instance
    game_state:  Any             = None   # Ambroflow game state
    systems:     Dict[str, Any]  = field(default_factory=dict)


# ── Handler registry ──────────────────────────────────────────────────────────

_HANDLERS: Dict[str, Callable[[ActionContext], ActionResult]] = {}

def handler(*action_ids: str):
    """Decorator: register a function as the handler for one or more action_ids."""
    def decorator(fn: Callable[[ActionContext], ActionResult]) -> Callable:
        for aid in action_ids:
            _HANDLERS[aid] = fn
        return fn
    return decorator


def dispatch(action_id: str, ctx: ActionContext) -> ActionResult:
    """Dispatch an action_id to its registered handler."""
    fn = _HANDLERS.get(action_id)
    if fn is not None:
        try:
            return fn(ctx)
        except Exception as exc:
            return ActionResult(ok=False, kind="none", message=str(exc))
    # Prefix fallback: exit_to_* and enter_* resolve via WorldGraph
    if action_id.startswith("exit_to_") or action_id.startswith("enter_") or action_id.startswith("exit_"):
        return _resolve_exit(action_id, ctx)
    return ActionResult.unknown(action_id)


# ── Exit handler (generic) ────────────────────────────────────────────────────

def _resolve_exit(action_id: str, ctx: ActionContext) -> ActionResult:
    if ctx.world_graph is None:
        return ActionResult(ok=False, kind="none", message="world_graph not available")
    t = ctx.world_graph.resolve_exit(action_id)
    if t is None:
        return ActionResult(ok=False, kind="none", message=f"no transition for: {action_id}")
    return ActionResult.transition(t.scene_id, t.spawn_id)


# ── Registered handlers ───────────────────────────────────────────────────────

@handler("open_alchemy_ui")
def _alchemy(ctx: ActionContext) -> ActionResult:
    return ActionResult.open_ui("alchemy")


@handler("open_smelt_ui")
def _smelt(ctx: ActionContext) -> ActionResult:
    return ActionResult.open_ui("smelt")


@handler("open_shop_ui", "manage_shop", "shop_counter")
def _shop(ctx: ActionContext) -> ActionResult:
    # Player-operated trade screen — stock is set by the player via alchemy.
    # Full WorldMode.SHOP implementation pending; stub opens the inventory
    # management screen with a shop_mode flag the UI can gate on.
    return ActionResult(ok=True, kind="ui_open", ui="shop")


@handler("open_chest")
def _chest(ctx: ActionContext) -> ActionResult:
    return ActionResult.open_ui("inventory")


@handler("save_and_heal")
def _rest(ctx: ActionContext) -> ActionResult:
    if ctx.game_state is not None and hasattr(ctx.game_state, "save"):
        ctx.game_state.save()
    player = ctx.systems.get("player")
    if player is not None and hasattr(player, "heal"):
        player.heal()
    return ActionResult.save_and_heal()


@handler("meditation_tutorial", "meditate")
def _meditate(ctx: ActionContext) -> ActionResult:
    med = ctx.systems.get("meditation")
    if med is not None and hasattr(med, "begin_tutorial"):
        med.begin_tutorial()
    return ActionResult.open_ui("meditation")


@handler("lore_books", "read")
def _read(ctx: ActionContext) -> ActionResult:
    return ActionResult.open_ui("lore_books")


@handler("read_journal")
def _read_journal(ctx: ActionContext) -> ActionResult:
    return ActionResult.open_ui("journal")


@handler("rest")
def _rest(ctx: ActionContext) -> ActionResult:
    return ActionResult.save_and_heal()


@handler("stairs_up")
def _stairs_up(ctx: ActionContext) -> ActionResult:
    return ActionResult.transition("player_home_upper", "24,7")


@handler("stairs_down")
def _stairs_down(ctx: ActionContext) -> ActionResult:
    return ActionResult.transition("lapidus_wiltoll_home", "9,3")


# Sulphera access gate
@handler("enter_sulphera", "open_sulphera_gate")
def _sulphera_gate(ctx: ActionContext) -> ActionResult:
    gs = ctx.game_state
    has_infernal = (
        gs is not None
        and hasattr(gs, "has_perk")
        and gs.has_perk("infernal_meditation")
    )
    if not has_infernal:
        return ActionResult(
            ok=False, kind="none",
            message="Infernal Meditation required to enter Sulphera."
        )
    return _resolve_exit("enter_sulphera", ctx)


# Fae dungeon access (requires Mona's acknowledgement)
@handler("enter_fae_dungeon")
def _fae_gate(ctx: ActionContext) -> ActionResult:
    return _resolve_exit("enter_fae_dungeon", ctx)


# Generic named exits — all resolved via WorldGraph
@handler(
    "exit_to_lapidus_town", "exit_to_home_morning", "exit_to_home_apothecary",
    "enter_home", "enter_apothecary",
    "enter_azonithia", "exit_wiltoll", "exit_azonithia",
    "exit_west", "exit_east", "exit_hope", "exit_serpent",
    "exit_azon_west", "exit_azon_east",
    "enter_mines", "exit_mines_surface",
    "exit_sulphera_entry", "exit_entry", "exit_pride", "exit_greed",
    "exit_envy", "exit_gluttony", "exit_sloth", "exit_wrath", "exit_lust",
    "exit_royal", "exit_dryad", "exit_undine", "exit_salamander",
    "exit_gnome", "exit_faerie",
)
def _generic_exit(ctx: ActionContext) -> ActionResult:
    return _resolve_exit(ctx.action_id, ctx)