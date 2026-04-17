"""
Session
========
Orchestrates a player session — profile management, game lifecycle,
and the bridge between persistence and the GameStateMachine.

A Session is created once at startup and lives for the lifetime of the
application window.  It holds the active PlayerProfile and the currently
running GameStateMachine (if any).

Usage
-----
    session = Session(backend=auto_backend())
    session.load_or_create_profile("player_id", name="Meridian")

    machine = session.start_game("7_KLGS")   # or resume_game
    machine.begin_dream_calibration()
    # ... engine runs ...
    machine.end_game("primary_convergence")
    session.record_game_ended("7_KLGS", machine)
    session.save()
"""

from __future__ import annotations

import time
import uuid
from typing import Optional, Any

from .persistence import PersistenceBackend, PlayerProfile, GameProgress, auto_backend
from .registry import GAME_BY_SLUG, GAMES, GameEntry
from ..state.machine import GameStateMachine, GamePhase
from ..ko.breath import BreathOfKo
from ..ko.flags import FlagState
from ..orrery.client import OrreryClient


# ── Null Orrery for offline/local sessions ────────────────────────────────────

class _NullOrrery:
    """Drop-in for OrreryClient when no API is reachable."""
    def record(self, event_kind: str, payload: dict) -> dict:
        return {}
    def query(self, *args, **kwargs) -> dict:
        return {}


# ── Session ───────────────────────────────────────────────────────────────────

class Session:
    """
    Manages the active player session.

    Parameters
    ----------
    backend:
        A PersistenceBackend (LocalPersistence or HostedPersistence).
        If None, auto_backend() is called.
    orrery_url:
        Base URL of the atelier-api for Orrery events.
        If None or unreachable, a null orrery is used silently.
    """

    def __init__(
        self,
        backend: Optional[PersistenceBackend] = None,
        orrery_url: Optional[str] = None,
    ) -> None:
        self._backend  = backend or auto_backend()
        self._profile:  Optional[PlayerProfile] = None
        self._machine:  Optional[GameStateMachine] = None
        self._active_slug: Optional[str] = None
        self._orrery   = self._init_orrery(orrery_url)

    def _init_orrery(self, url: Optional[str]) -> Any:
        if url:
            try:
                import httpx
                resp = httpx.get(f"{url.rstrip('/')}/health", timeout=2.0)
                if resp.status_code == 200:
                    return OrreryClient(
                        workspace_id=self._profile.player_id if self._profile else "local",
                        game_id="none",
                        base_url=url,
                    )
            except Exception:
                pass
        return _NullOrrery()

    # ── Profile ───────────────────────────────────────────────────────────────

    @property
    def profile(self) -> Optional[PlayerProfile]:
        return self._profile

    @property
    def backend_mode(self) -> str:
        return self._backend.mode

    def load_profile(self, player_id: str) -> Optional[PlayerProfile]:
        """Load an existing profile by ID.  Returns None if not found."""
        self._profile = self._backend.load_profile(player_id)
        return self._profile

    def create_profile(self, name: str, player_id: Optional[str] = None) -> PlayerProfile:
        """Create a new player profile with a fresh BreathOfKo."""
        pid = player_id or str(uuid.uuid4())
        self._profile = PlayerProfile(
            player_id=pid,
            name=name.strip(),
            breath_snapshot=None,
            game_progress={},
        )
        self._backend.save_profile(self._profile)
        return self._profile

    def load_or_create_profile(self, player_id: str, name: str = "Player") -> PlayerProfile:
        """Load existing or create new."""
        profile = self.load_profile(player_id)
        if profile is None:
            profile = self.create_profile(name=name, player_id=player_id)
        return profile

    def list_profiles(self) -> list[str]:
        return self._backend.list_profiles()

    def save(self) -> None:
        if self._profile:
            self._backend.save_profile(self._profile)

    # ── BreathOfKo ────────────────────────────────────────────────────────────

    def breath(self) -> BreathOfKo:
        """Return the player's BreathOfKo, initialised from snapshot if available."""
        assert self._profile, "No profile loaded"
        snap = self._profile.breath_snapshot
        if snap:
            return BreathOfKo.from_snapshot(snap)
        return BreathOfKo(
            layer_densities={i: 0.5 for i in range(1, 25)},
            coil_position=0.0,
            flag_state=FlagState(),
        )

    # ── Game lifecycle ────────────────────────────────────────────────────────

    def game_status(self, slug: str) -> str:
        """Return "not_started" | "in_progress" | "complete"."""
        if not self._profile:
            return "not_started"
        return self._profile.progress(slug).status

    def all_game_statuses(self) -> dict[str, str]:
        return {g.slug: self.game_status(g.slug) for g in GAMES}

    def start_game(self, slug: str) -> GameStateMachine:
        """
        Begin a new run of the given game.
        Replaces any currently running machine.
        """
        assert self._profile, "No profile loaded"
        entry = GAME_BY_SLUG.get(slug)
        if entry is None:
            raise ValueError(f"Unknown game slug: {slug!r}")

        breath = self.breath()
        machine = GameStateMachine(
            game_id=slug,
            game_number=entry.number,
            breath=breath,
            orrery=self._orrery,
        )
        machine.begin_dream_calibration()

        progress = self._profile.progress(slug)
        progress.status     = "in_progress"
        progress.started_at = time.time()

        self._machine     = machine
        self._active_slug = slug
        self.save()
        return machine

    def resume_game(self, slug: str) -> Optional[GameStateMachine]:
        """
        Resume an in-progress game if one exists.
        Returns None if the game is not in-progress.
        """
        if self.game_status(slug) != "in_progress":
            return None
        # Re-entry: rebuild machine in WAKING_PLAY phase
        assert self._profile
        entry = GAME_BY_SLUG[slug]
        breath = self.breath()
        machine = GameStateMachine(
            game_id=slug,
            game_number=entry.number,
            breath=breath,
            orrery=self._orrery,
        )
        # Manually advance to waking_play without re-running calibration
        machine._state.phase = GamePhase.WAKING_PLAY
        self._machine     = machine
        self._active_slug = slug
        return machine

    def record_game_ended(self, slug: str, machine: GameStateMachine) -> None:
        """Call after machine.end_game() to persist the outcome."""
        assert self._profile
        progress = self._profile.progress(slug)
        progress.status           = "complete"
        progress.ended_at         = time.time()
        progress.convergence_path = machine.state.ended_at_phase
        if progress.started_at:
            progress.play_time_seconds += time.time() - progress.started_at

        # Persist breath snapshot
        self._profile.breath_snapshot = machine._breath.snapshot()
        self._machine     = None
        self._active_slug = None
        self.save()

    @property
    def active_machine(self) -> Optional[GameStateMachine]:
        return self._machine

    @property
    def active_slug(self) -> Optional[str]:
        return self._active_slug