"""
OrreryClient
============
Thin synchronous HTTP client for the Atelier API orrery endpoints.

The Ambroflow Engine never writes directly to the multiverse stack —
all persistence flows through this client, which talks to atelier-api
(default: https://atelier-api.quantumquackery.com/).

All methods raise httpx.HTTPStatusError on non-2xx responses.
Callers are responsible for deciding whether to suppress or propagate.
"""

from __future__ import annotations

import httpx
from typing import Any


_DEFAULT_BASE = "https://atelier-api.quantumquackery.com/"


class OrreryClient:
    """
    Synchronous Orrery client.  Instantiate once per engine session and
    pass it into subsystems that need to record events.

    Parameters
    ----------
    base_url:
        https://atelier-api.quantumquackery.com/.  Defaults to https://atelier-api.quantumquackery.com/.
    workspace_id:
        Player workspace identifier — written into every event payload.
    game_id:
        Active game slug (e.g. "7_KLGS").
    timeout:
        Request timeout in seconds.
    """

    def __init__(
        self,
        workspace_id: str,
        game_id: str,
        base_url: str = _DEFAULT_BASE,
        timeout: float = 10.0,
    ) -> None:
        self.workspace_id = workspace_id
        self.game_id = game_id
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    # ── Orrery record ─────────────────────────────────────────────────────────

    def record(self, event_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /v1/orrery/record"""
        body = {
            "workspace_id": self.workspace_id,
            "game_id": self.game_id,
            "event_kind": event_kind,
            "payload": payload,
        }
        r = self._client.post("/v1/orrery/record", json=body)
        r.raise_for_status()
        return r.json()

    # ── Void Wraith observation ───────────────────────────────────────────────

    def void_wraith_observe(self, observation_id: str, context: dict[str, Any]) -> dict[str, Any]:
        """POST /v1/orrery/void_wraith"""
        body = {
            "workspace_id": self.workspace_id,
            "game_id": self.game_id,
            "observation_id": observation_id,
            "context": context,
        }
        r = self._client.post("/v1/orrery/void_wraith", json=body)
        r.raise_for_status()
        return r.json()

    # ── Live sanity ───────────────────────────────────────────────────────────

    def record_sanity_delta(
        self,
        actor_id: str,
        deltas: dict[str, float],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST /v1/orrery/sanity/delta"""
        body = {
            "workspace_id": self.workspace_id,
            "game_id": self.game_id,
            "actor_id": actor_id,
            "deltas": deltas,
            "context": context or {},
        }
        r = self._client.post("/v1/orrery/sanity/delta", json=body)
        r.raise_for_status()
        return r.json()

    def get_sanity(self) -> dict[str, float]:
        """GET /v1/orrery/sanity?workspace_id=…"""
        r = self._client.get("/v1/orrery/sanity", params={"workspace_id": self.workspace_id})
        r.raise_for_status()
        return r.json()

    # ── Query / registry ──────────────────────────────────────────────────────

    def query(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """GET /v1/orrery/query"""
        params = {"workspace_id": self.workspace_id, **(filters or {})}
        r = self._client.get("/v1/orrery/query", params=params)
        r.raise_for_status()
        return r.json()

    def luminyx(self) -> dict[str, Any]:
        """GET /v1/orrery/luminyx"""
        r = self._client.get("/v1/orrery/luminyx", params={"workspace_id": self.workspace_id})
        r.raise_for_status()
        return r.json()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OrreryClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
