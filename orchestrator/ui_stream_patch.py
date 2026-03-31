"""Forward Strands orchestrator LLM chunks to the UI agent stream (HTTP)."""

from __future__ import annotations

import asyncio
from typing import Any

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue

from strands.multiagent.a2a.executor import StrandsA2AExecutor

from transport.agent_progress import emit_stream_chunk

_orig_execute = StrandsA2AExecutor.execute
_orig_handle = StrandsA2AExecutor._handle_streaming_event


async def _patched_execute(
    self: StrandsA2AExecutor, context: RequestContext, event_queue: EventQueue
) -> None:
    await _orig_execute(self, context, event_queue)


async def _patched_handle_streaming_event(
    self: StrandsA2AExecutor, event: dict[str, Any], updater: Any
) -> None:
    # The orchestrator panel content is already managed by the tool functions
    # (call_researcher / call_writer in agent.py via emit_stream_chunk). We intentionally
    # do NOT push LLM data events here because:
    #   1. During tool calls the LLM produces no text — only function-call JSON.
    #   2. The final assistant turn (after all tools) is typically just the writer's article
    #      echoed back, which we already have in the panel.
    # Keeping this patch in place only to call _orig_handle so the A2A streaming pipeline
    # continues to work normally.
    await _orig_handle(self, event, updater)


def apply_ui_stream_patch() -> None:
    if getattr(StrandsA2AExecutor, "_strands_ui_stream_applied", False):
        return
    StrandsA2AExecutor.execute = _patched_execute
    StrandsA2AExecutor._handle_streaming_event = _patched_handle_streaming_event
    StrandsA2AExecutor._strands_ui_stream_applied = True  # type: ignore[attr-defined]
