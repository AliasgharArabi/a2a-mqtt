"""Report orchestrator worker progress to the UI log stream (HTTP POST to Node)."""

from __future__ import annotations

import os

import requests


def _progress_post_url() -> str:
    raw = os.environ.get(
        "STRANDS_UI_PROGRESS_URL",
        "http://127.0.0.1:3000/api/agent-progress",
    ).rstrip("/")
    if raw.endswith("/api/agent-progress"):
        return raw
    return f"{raw}/api/agent-progress"


def emit_agent_progress(agent: str, message: str) -> None:
    """Append a line to the UI event stream via POST /api/agent-progress (best-effort)."""
    if os.environ.get("STRANDS_PROGRESS", "1").lower() in ("0", "false", "no"):
        return
    try:
        requests.post(
            _progress_post_url(),
            json={"agent": agent, "message": message},
            timeout=3.0,
        )
    except requests.RequestException:
        pass
