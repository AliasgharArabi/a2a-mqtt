"""Report orchestrator worker progress and streamed output to the UI (HTTP POST to Node)."""

from __future__ import annotations

import os

import requests


def _ui_base() -> str:
    return os.environ.get("STRANDS_UI_BASE", "http://127.0.0.1:3000").rstrip("/")


def _progress_post_url() -> str:
    raw = os.environ.get("STRANDS_UI_PROGRESS_URL")
    if raw:
        u = raw.rstrip("/")
        return u if u.endswith("/api/agent-progress") else f"{u}/api/agent-progress"
    return f"{_ui_base()}/api/agent-progress"


def _agent_stream_post_url() -> str:
    raw = os.environ.get("STRANDS_UI_AGENT_STREAM_URL")
    if raw:
        u = raw.rstrip("/")
        return u if u.endswith("/api/agent-stream") else f"{u}/api/agent-stream"
    return f"{_ui_base()}/api/agent-stream"


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


def emit_stream_chunk(agent: str, chunk: str, append: bool = True) -> None:
    """Append or replace text in the per-agent output panel (POST /api/agent-stream)."""
    if os.environ.get("STRANDS_STREAM_UI", "1").lower() in ("0", "false", "no"):
        return
    if not chunk:
        return
    # Large final payloads (full article); avoid spurious timeouts.
    timeout = max(15.0, min(120.0, 10.0 + len(chunk) / 8000.0))
    try:
        requests.post(
            _agent_stream_post_url(),
            json={"agent": agent, "chunk": chunk, "append": append},
            timeout=timeout,
        )
    except requests.RequestException:
        pass
