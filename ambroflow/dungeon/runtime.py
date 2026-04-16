"""
Dungeon Runtime
===============
Turn-based dungeon run engine.

A DungeonRuntime governs one active dungeon run:
  - Player movement over generated layout
  - Encounter triggering
  - Void Wraith observation during play
  - Omission flushing (≥3 missed opportunities ≥3 times → Vios observation)
  - Run outcome recording to the Orrery on close

Run lifecycle:
  runtime = DungeonRuntime(dungeon_def, seed, orrery_client, player_state)
  runtime.start()
  ...
  result = runtime.move(dx, dy)   → MoveResult
  result = runtime.act(action)    → ActionResult
  runtime.defeat()   # player defeated
  runtime.abandon()  # player fled
  # OR: runtime auto-closes when last floor exit cleared
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .generator import DungeonLayout, EncounterSlot, Room, SpecialTile, TileKind, generate
from .registry import DungeonDef
from ..encounter.resolver import resolve
from ..orrery.client import OrreryClient


class RUN_OUTCOME(str, Enum):
    CLEARED  = "cleared"
    FLED     = "fled"
    DEFEATED = "defeated"


# ── Player state snapshot passed into runtime ──────────────────────────────────

@dataclass
class PlayerState:
    actor_id: str
    unlocked_perks: list[str] = field(default_factory=list)
    completed_quests: list[str] = field(default_factory=list)
    held_tokens: list[str] = field(default_factory=list)
    skill_ranks: dict[str, int] = field(default_factory=dict)


# ── Move / action results ──────────────────────────────────────────────────────

@dataclass
class MoveResult:
    ok: bool
    reason: Optional[str] = None
    tile: Optional[str] = None
    encounter_triggered: bool = False
    floor_complete: bool = False
    run_complete: bool = False


@dataclass
class ActionResult:
    ok: bool
    outcome: str
    sanity_delta: dict[str, float] = field(default_factory=dict)
    token_granted: Optional[str] = None
    loot: list[str] = field(default_factory=list)


# ── Runtime ────────────────────────────────────────────────────────────────────

class DungeonRuntime:
    """
    Turn-based dungeon run.

    Parameters
    ----------
    dungeon_def:
        Canonical DungeonDef from registry.
    seed:
        32-bit integer seed for BSP generation.
    orrery:
        OrreryClient — for recording observations and outcomes.
    player:
        Snapshot of player state at run start.
    """

    def __init__(
        self,
        dungeon_def: DungeonDef,
        seed: int,
        orrery: OrreryClient,
        player: PlayerState,
    ) -> None:
        self._def     = dungeon_def
        self._seed    = seed
        self._orrery  = orrery
        self._player  = player

        self._floor:   int = 0
        self._layout:  DungeonLayout | None = None
        self._px:      int = 0
        self._py:      int = 0
        self._outcome: RUN_OUTCOME | None = None
        self._active:  bool = False

        # Omission tracking
        self._missed_opportunities: dict[str, int] = {}
        self._vios_threshold = 3

        # Fixed-layout mode (set by from_fixed_layout factory, None = BSP mode)
        self._fixed_layout: DungeonLayout | None = None
        self._fixed_floor:  int = 0

        # Render manifest — populated by from_export_bundle, None in BSP mode
        # Keys: "compiled_pack", "stream_manifest", "prefetch_manifest"
        # Values: paths relative to the gameplay/ asset root (or absolute)
        self._render_manifest: dict[str, str | None] | None = None

    # ── Export bundle factory ─────────────────────────────────────────────────

    @classmethod
    def from_export_bundle(
        cls,
        bundle_doc: dict,
        dungeon_def: "DungeonDef",
        orrery: "OrreryClient",
        player: "PlayerState",
    ) -> "DungeonRuntime":
        """
        Build a DungeonRuntime from an Atelier export bundle
        (schema ambroflow.dungeon.export_bundle.v1).

        The bundle carries two layers:
          ``layout`` — ambroflow.dungeon.fixed_layout.v1 (gameplay: TileKind grid,
                        rooms, encounters, specials).
          ``render``  — relative paths to the compiled voxel pack and stream
                        manifests produced by the Atelier Render Lab pipeline.

        Export bundles are written to:
          ``files/exports/{game_slug}/dungeons/{dungeon_id}_floor{N}.bundle.json``

        Example
        -------
        .. code-block:: python

            bundle = json.loads(Path("...floor0.bundle.json").read_text())
            runtime = DungeonRuntime.from_export_bundle(bundle, dungeon_def, orrery, player)
            runtime.start()

            # Resolve render asset paths in the presentation layer:
            paths = runtime.resolve_render_manifest(asset_root="gameplay/")
            pack_path   = paths["compiled_pack"]    # → abs path to pack.v2.json
            stream_path = paths["stream_manifest"]  # → abs path to stream manifest
        """
        layout_doc = bundle_doc.get("layout") or {}
        instance = cls.from_fixed_layout(
            layout_doc=layout_doc,
            dungeon_def=dungeon_def,
            orrery=orrery,
            player=player,
        )
        render = bundle_doc.get("render") or {}
        instance._render_manifest = {
            "compiled_pack":     render.get("compiled_pack"),
            "stream_manifest":   render.get("stream_manifest"),
            "prefetch_manifest": render.get("prefetch_manifest"),
        }
        return instance

    # ── Fixed-layout factory ─────────────────────────────────────────────────

    @classmethod
    def from_fixed_layout(
        cls,
        layout_doc: dict,
        dungeon_def: "DungeonDef",
        orrery: "OrreryClient",
        player: "PlayerState",
    ) -> "DungeonRuntime":
        """
        Build a DungeonRuntime from an Atelier-exported fixed layout document
        (schema ambroflow.dungeon.fixed_layout.v1) instead of BSP generation.

        Exported docs live at:
          files/exports/{game_slug}/dungeons/{dungeon_id}_floor{n}.json

        Multi-floor authored dungeons require one doc per floor; floor transitions
        load the next document from the same directory by naming convention.
        """
        instance = cls(
            dungeon_def=dungeon_def,
            seed=layout_doc.get("seed", 0),
            orrery=orrery,
            player=player,
        )
        instance._fixed_layout = cls._layout_from_doc(layout_doc)
        instance._fixed_floor  = int(layout_doc.get("floor", 0))
        return instance

    @staticmethod
    def _layout_from_doc(doc: dict) -> DungeonLayout:
        """Deserialise an Atelier dungeon export doc into a DungeonLayout."""
        voxels: dict[tuple[int, int], TileKind] = {}
        for v in doc.get("voxels", []):
            x, y = int(v["x"]), int(v["y"])
            try:
                voxels[(x, y)] = TileKind(str(v["kind"]))
            except ValueError:
                voxels[(x, y)] = TileKind.FLOOR   # unknown kind → passable

        rooms = [
            Room(x=r["x"], y=r["y"], w=r["w"], h=r["h"])
            for r in doc.get("rooms", [])
        ]
        encounters = [
            EncounterSlot(
                x=e["x"], y=e["y"],
                encounter_type=e.get("encounter_type", "combat"),
                difficulty=float(e.get("difficulty", 0.4)),
            )
            for e in doc.get("encounters", [])
        ]
        specials = [
            SpecialTile(x=s["x"], y=s["y"], kind=s.get("kind", "special"))
            for s in doc.get("specials", [])
        ]
        return DungeonLayout(
            voxels=voxels,
            rooms=rooms,
            encounters=encounters,
            specials=specials,
            metadata={
                "dungeon_id": doc.get("dungeon_id", "authored"),
                "seed":       doc.get("seed", 0),
                "floor":      doc.get("floor", 0),
                "ephemeral":  False,
                "authored":   True,
            },
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._active:
            raise RuntimeError("Run already started.")
        self._active = True
        self._load_floor(0)
        self._orrery.record("dungeon.run.started", {
            "dungeon_id": self._def.id,
            "floor": self._floor,
            "seed": self._seed,
            "actor_id": self._player.actor_id,
        })

    def _load_floor(self, floor: int) -> None:
        self._floor = floor
        if self._fixed_layout is not None and floor == self._fixed_floor:
            # Use the Atelier-authored fixed layout for this floor.
            # Floors without a matching authored layout fall through to BSP.
            self._layout = self._fixed_layout
        else:
            self._layout = generate(
                dungeon_id=self._def.id,
                seed=self._seed,
                floor=floor,
                encounter_density=self._def.encounter_density,
                special_tiles=list(self._def.special_tiles),
            )
        # Place player at entry tile
        entry = self._find_tile(TileKind.ENTRY)
        if entry:
            self._px, self._py = entry

    def _find_tile(self, kind: TileKind) -> Optional[tuple[int, int]]:
        assert self._layout is not None
        for (x, y), tk in self._layout.voxels.items():
            if tk == kind:
                return x, y
        return None

    # ── Movement ──────────────────────────────────────────────────────────────

    def move(self, dx: int, dy: int) -> MoveResult:
        if not self._active:
            return MoveResult(ok=False, reason="Run not active.")
        assert self._layout is not None

        nx, ny = self._px + dx, self._py + dy
        tile = self._layout.voxels.get((nx, ny))
        if tile is None:
            return MoveResult(ok=False, reason="Wall.", tile="wall")

        self._px, self._py = nx, ny
        result = MoveResult(ok=True, tile=tile.value)

        # Check for encounter at new position
        for enc in self._layout.encounters:
            if enc.x == nx and enc.y == ny:
                result.encounter_triggered = True
                self._orrery.void_wraith_observe("encounter.trigger", {
                    "actor_id": self._player.actor_id,
                    "dungeon_id": self._def.id,
                    "floor": self._floor,
                    "encounter_type": enc.encounter_type,
                    "difficulty": enc.difficulty,
                    "position": [nx, ny],
                })
                break

        # Floor exit
        if tile == TileKind.EXIT:
            next_floor = self._floor + 1
            if next_floor >= self._def.floor_count:
                self._complete_run()
                result.run_complete = True
            else:
                self._load_floor(next_floor)
                result.floor_complete = True

        return result

    # ── Actions ───────────────────────────────────────────────────────────────

    def act(self, action: str, context: dict[str, Any] | None = None) -> ActionResult:
        """
        Resolve a player action (combat, negotiate, observe, skip, loot, etc.).
        The encounter resolver is called for non-trivial actions.
        """
        if not self._active:
            return ActionResult(ok=False, outcome="run_not_active")

        ctx = context or {}

        if action == "skip":
            opportunity_key = ctx.get("opportunity_key", "generic")
            count = self._missed_opportunities.get(opportunity_key, 0) + 1
            self._missed_opportunities[opportunity_key] = count
            if count >= self._vios_threshold:
                self._orrery.void_wraith_observe("vios.omission_pattern", {
                    "actor_id": self._player.actor_id,
                    "dungeon_id": self._def.id,
                    "opportunity_key": opportunity_key,
                    "times_missed": count,
                })
            return ActionResult(ok=True, outcome="skipped")

        result = resolve(action, self._player, self._def, ctx)

        if result.get("sanity_delta"):
            self._orrery.record_sanity_delta(
                actor_id=self._player.actor_id,
                deltas=result["sanity_delta"],
                context={"dungeon_id": self._def.id, "action": action},
            )

        return ActionResult(
            ok=True,
            outcome=result.get("outcome", "resolved"),
            sanity_delta=result.get("sanity_delta", {}),
            token_granted=result.get("token_granted"),
            loot=result.get("loot", []),
        )

    # ── Run termination ───────────────────────────────────────────────────────

    def _complete_run(self) -> None:
        self._outcome = RUN_OUTCOME.CLEARED
        self._active = False
        token = self._def.grants_token
        self._orrery.record("dungeon.run.outcome", {
            "dungeon_id": self._def.id,
            "outcome": RUN_OUTCOME.CLEARED,
            "actor_id": self._player.actor_id,
            "token_granted": token,
        })
        if token:
            self._orrery.record("ring.token.granted", {
                "token": token,
                "actor_id": self._player.actor_id,
                "dungeon_id": self._def.id,
            })

    def defeat(self) -> None:
        self._outcome = RUN_OUTCOME.DEFEATED
        self._active = False
        self._orrery.record("dungeon.run.outcome", {
            "dungeon_id": self._def.id,
            "outcome": RUN_OUTCOME.DEFEATED,
            "actor_id": self._player.actor_id,
        })

    def abandon(self) -> None:
        self._outcome = RUN_OUTCOME.FLED
        self._active = False
        self._orrery.record("dungeon.run.outcome", {
            "dungeon_id": self._def.id,
            "outcome": RUN_OUTCOME.FLED,
            "actor_id": self._player.actor_id,
        })

    # ── Inspection ────────────────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        return self._active

    @property
    def outcome(self) -> RUN_OUTCOME | None:
        return self._outcome

    @property
    def position(self) -> tuple[int, int]:
        return self._px, self._py

    @property
    def floor(self) -> int:
        return self._floor

    @property
    def layout(self) -> DungeonLayout | None:
        return self._layout

    @property
    def render_manifest(self) -> "dict[str, str | None] | None":
        """
        Render asset references populated when loaded from an export bundle.
        Keys: "compiled_pack", "stream_manifest", "prefetch_manifest".
        Values are paths relative to the gameplay/ asset root.
        Returns None for BSP-generated or plain fixed-layout runs.
        """
        return self._render_manifest

    def resolve_render_manifest(
        self, asset_root: "str | Any"
    ) -> "dict[str, str | None]":
        """
        Return absolute paths to render assets by resolving the render manifest
        against a gameplay asset root directory.

        Parameters
        ----------
        asset_root:
            The gameplay/ directory (or equivalent base) that the relative
            paths in the manifest are anchored to.

        Returns
        -------
        dict with the same keys as render_manifest; None values preserved
        for assets that were not produced by the pipeline.
        """
        from pathlib import Path as _Path
        if not self._render_manifest:
            return {}
        base = _Path(asset_root)
        result: dict[str, str | None] = {}
        for key, rel in self._render_manifest.items():
            if rel is None:
                result[key] = None
            elif _Path(rel).is_absolute():
                result[key] = rel
            else:
                result[key] = str(base / rel)
        return result
