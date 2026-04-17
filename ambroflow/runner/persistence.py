"""
Persistence — dual-mode (hosted + local SQLite fallback)
=========================================================
The Atelier API owns the canonical database.  The engine talks to it via
OrreryClient when the API is reachable.  When it is not, a local SQLite file
provides identical schema for offline play.  On reconnect the local state is
not automatically synced — that is Atelier's responsibility.

PlayerProfile      — identity + BreathOfKo snapshot + game progress
GameProgress       — per-game status (not_started | in_progress | complete)
PersistenceBackend — protocol implemented by both modes
HostedPersistence  — wraps OrreryClient (atelier-api)
LocalPersistence   — direct SQLite via stdlib sqlite3

Usage
-----
    backend = auto_backend()          # tries hosted, falls back to local
    profile = backend.load_profile("player_id")
    backend.save_progress(profile)
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Protocol


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class GameProgress:
    game_slug:        str
    status:           str      # "not_started" | "in_progress" | "complete"
    started_at:       Optional[float] = None   # unix timestamp
    ended_at:         Optional[float] = None
    convergence_path: Optional[str]   = None
    play_time_seconds: float          = 0.0


@dataclass
class PlayerProfile:
    player_id:     str
    name:          str
    created_at:    float                    = field(default_factory=time.time)
    last_seen_at:  float                    = field(default_factory=time.time)
    breath_snapshot: Optional[dict]         = None   # serialised BreathOfKo
    game_progress:   dict[str, GameProgress] = field(default_factory=dict)

    def progress(self, slug: str) -> GameProgress:
        if slug not in self.game_progress:
            self.game_progress[slug] = GameProgress(game_slug=slug, status="not_started")
        return self.game_progress[slug]


# ── Protocol ──────────────────────────────────────────────────────────────────

class PersistenceBackend(Protocol):
    def load_profile(self, player_id: str) -> Optional[PlayerProfile]: ...
    def save_profile(self, profile: PlayerProfile) -> None: ...
    def list_profiles(self) -> list[str]: ...   # returns player_ids
    @property
    def mode(self) -> str: ...   # "hosted" | "local"


# ── Local SQLite ──────────────────────────────────────────────────────────────

_LOCAL_DIR = Path.home() / ".ambroflow"
_LOCAL_DB  = _LOCAL_DIR / "players.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    player_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  REAL NOT NULL,
    last_seen_at REAL NOT NULL,
    breath_json TEXT,
    progress_json TEXT NOT NULL DEFAULT '{}'
);
"""


class LocalPersistence:
    """Direct SQLite backend.  Lives at ~/.ambroflow/players.sqlite."""

    def __init__(self, db_path: Path = _LOCAL_DB) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @property
    def mode(self) -> str:
        return "local"

    def load_profile(self, player_id: str) -> Optional[PlayerProfile]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM players WHERE player_id = ?", (player_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    def save_profile(self, profile: PlayerProfile) -> None:
        profile.last_seen_at = time.time()
        progress_json = json.dumps({
            slug: asdict(gp) for slug, gp in profile.game_progress.items()
        })
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO players (player_id, name, created_at, last_seen_at,
                                     breath_json, progress_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    name          = excluded.name,
                    last_seen_at  = excluded.last_seen_at,
                    breath_json   = excluded.breath_json,
                    progress_json = excluded.progress_json
                """,
                (
                    profile.player_id,
                    profile.name,
                    profile.created_at,
                    profile.last_seen_at,
                    json.dumps(profile.breath_snapshot) if profile.breath_snapshot else None,
                    progress_json,
                ),
            )

    def list_profiles(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT player_id FROM players ORDER BY last_seen_at DESC"
            ).fetchall()
        return [r["player_id"] for r in rows]

    @staticmethod
    def _row_to_profile(row: sqlite3.Row) -> PlayerProfile:
        progress_raw = json.loads(row["progress_json"] or "{}")
        progress = {
            slug: GameProgress(**data)
            for slug, data in progress_raw.items()
        }
        return PlayerProfile(
            player_id      = row["player_id"],
            name           = row["name"],
            created_at     = row["created_at"],
            last_seen_at   = row["last_seen_at"],
            breath_snapshot= json.loads(row["breath_json"]) if row["breath_json"] else None,
            game_progress  = progress,
        )


# ── Hosted (via atelier-api) ──────────────────────────────────────────────────

class HostedPersistence:
    """
    Persistence via atelier-api.
    Wraps OrreryClient for write events; uses GET endpoints for reads.
    Falls back gracefully — if any request fails, the caller should catch
    and switch to LocalPersistence.
    """

    def __init__(self, base_url: str, workspace_id: str, timeout: float = 5.0) -> None:
        import httpx
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        self._workspace = workspace_id

    @property
    def mode(self) -> str:
        return "hosted"

    def _profile_url(self, player_id: str) -> str:
        return f"/v1/ambroflow/players/{player_id}"

    def load_profile(self, player_id: str) -> Optional[PlayerProfile]:
        resp = self._client.get(self._profile_url(player_id))
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._deserialize(resp.json())

    def save_profile(self, profile: PlayerProfile) -> None:
        profile.last_seen_at = time.time()
        self._client.put(
            self._profile_url(profile.player_id),
            json=self._serialize(profile),
        ).raise_for_status()

    def list_profiles(self) -> list[str]:
        resp = self._client.get("/v1/ambroflow/players")
        resp.raise_for_status()
        return [p["player_id"] for p in resp.json()]

    @staticmethod
    def _serialize(profile: PlayerProfile) -> dict:
        return {
            "player_id":      profile.player_id,
            "name":           profile.name,
            "created_at":     profile.created_at,
            "last_seen_at":   profile.last_seen_at,
            "breath_snapshot": profile.breath_snapshot,
            "game_progress":  {
                slug: asdict(gp) for slug, gp in profile.game_progress.items()
            },
        }

    @staticmethod
    def _deserialize(data: dict) -> PlayerProfile:
        progress = {
            slug: GameProgress(**gp)
            for slug, gp in data.get("game_progress", {}).items()
        }
        return PlayerProfile(
            player_id      = data["player_id"],
            name           = data["name"],
            created_at     = data["created_at"],
            last_seen_at   = data["last_seen_at"],
            breath_snapshot= data.get("breath_snapshot"),
            game_progress  = progress,
        )


# ── Auto-selection ────────────────────────────────────────────────────────────

def auto_backend(
    atelier_base_url: Optional[str] = None,
    workspace_id: str = "local",
    probe_timeout: float = 2.0,
) -> LocalPersistence | HostedPersistence:
    """
    Try hosted first (if URL is set and health check passes).
    Fall back to local SQLite silently.
    """
    url = atelier_base_url or os.getenv("ATELIER_API_URL", "")
    if url:
        try:
            import httpx
            resp = httpx.get(f"{url.rstrip('/')}/health", timeout=probe_timeout)
            if resp.status_code == 200:
                return HostedPersistence(
                    base_url=url,
                    workspace_id=workspace_id,
                    timeout=5.0,
                )
        except Exception:
            pass
    return LocalPersistence()