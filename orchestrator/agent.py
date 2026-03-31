import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from strands import Agent, tool
from strands._async import run_async
from strands.multiagent.a2a import A2AServer

from a2a.client import ClientConfig, ClientFactory
from a2a.client.client import ClientEvent
from a2a.client.helpers import create_text_message_object
from a2a.types import Message, Role, Task, TextPart

from model_env import model_kwargs
from orchestrator.ui_stream_patch import apply_ui_stream_patch
from transport.agent_progress import emit_agent_progress, emit_stream_chunk

RESEARCHER_URL = "http://localhost:9101"
WRITER_URL = "http://localhost:9102"


def _parts_to_text(parts) -> str:
    chunks = []
    for part in parts:
        root = part.root
        if isinstance(root, TextPart) and root.text:
            chunks.append(root.text)
    return "\n".join(chunks)


def _task_or_message_to_output(result: Message | Task) -> str:
    if isinstance(result, Message):
        return _parts_to_text(result.parts)
    if result.history:
        for message in reversed(result.history):
            if message.role == Role.agent:
                return _parts_to_text(message.parts)
    if result.artifacts:
        texts = []
        for art in result.artifacts:
            texts.append(_parts_to_text(art.parts))
        combined = "\n".join(t for t in texts if t)
        if combined:
            return combined
    if result.status and result.status.message:
        return _parts_to_text(result.status.message.parts)
    return ""


def _a2a_event_to_text(event: ClientEvent | Message) -> str:
    if isinstance(event, Message):
        return _task_or_message_to_output(event)
    task, _update = event
    if isinstance(task, Task):
        return _task_or_message_to_output(task)
    return ""


async def _send_a2a_text(agent_base_url: str, text: str, stream_label: str) -> str:
    base = agent_base_url.rstrip("/")
    config = ClientConfig(streaming=True)
    client = await ClientFactory.connect(base, client_config=config)
    try:
        message = create_text_message_object(content=text)
        # Running text for prefix-style cumulative frames from the task.
        cumulative = ""
        async for event in client.send_message(message):
            chunk = _a2a_event_to_text(event)
            if not chunk:
                continue
            if len(chunk) >= len(cumulative) and chunk.startswith(cumulative):
                delta = chunk[len(cumulative) :]
                if delta:
                    emit_stream_chunk(stream_label, delta, append=True)
                cumulative = chunk
            else:
                # Token-sized shards (or other non-prefix frames): append to UI and to cumulative.
                # Never do `cumulative = chunk` here — that was wiping full text and left only the
                # last token for the final sync + return value.
                emit_stream_chunk(stream_label, chunk, append=True)
                cumulative += chunk
        # Ensure UI matches full aggregated output (idempotent if streaming already matched).
        if cumulative.strip():
            emit_stream_chunk(stream_label, cumulative, append=False)
        return cumulative
    finally:
        await client.close()


def _invoke_remote_agent(agent_url: str, text: str) -> str:
    base = agent_url.rstrip("/")
    if base == RESEARCHER_URL.rstrip("/"):
        stream_label = "Researcher"
        emit_agent_progress("Researcher", "Calling researcher A2A agent…")
    elif base == WRITER_URL.rstrip("/"):
        stream_label = "Writer"
        emit_agent_progress("Writer", "Calling writer A2A agent…")
    else:
        stream_label = "Worker"
    return run_async(lambda: _send_a2a_text(agent_url, text, stream_label))


@tool
def call_researcher(topic: str) -> str:
    """Delegate to the remote Researcher A2A agent."""
    emit_stream_chunk("Orchestrator", f"📋 Calling Researcher for: {topic}\n\n", append=False)
    outline = _invoke_remote_agent(RESEARCHER_URL, topic)
    emit_stream_chunk("Orchestrator", "\n\n✅ Research complete — passing outline to Writer…\n\n", append=True)
    emit_agent_progress("Orchestrator", "Research complete; handing off to writer…")
    return outline


@tool
def call_writer(outline: str) -> str:
    """Delegate to the remote Writer A2A agent."""
    emit_stream_chunk("Orchestrator", "✍️  Calling Writer…\n\n", append=True)
    article = _invoke_remote_agent(WRITER_URL, outline)
    if article.strip():
        emit_stream_chunk("Orchestrator", "\n\n---\n**Final article:**\n\n" + article, append=True)
    return article


ORCHESTRATOR_PROMPT = """
You are an orchestrator that coordinates a researcher and a writer to produce articles.

Follow these rules STRICTLY:
1. Call call_researcher EXACTLY ONCE with the topic. Accept whatever the researcher returns.
2. Call call_writer EXACTLY ONCE, passing the researcher's output as the outline.
3. Return the writer's output as your final answer.

IMPORTANT:
- Do NOT call call_researcher more than once, even if you think the outline is incomplete.
- Do NOT call call_writer more than once.
- Do NOT rewrite or add to the article yourself — just return what call_writer produced.
- Do NOT explain what you are doing. Simply call the tools in order and return the result.
"""

orchestrator = Agent(
    name="orchestrator",
    description="Coordinates research and writing agents to produce complete articles.",
    system_prompt=ORCHESTRATOR_PROMPT,
    tools=[call_researcher, call_writer],
    **model_kwargs(agent_name="orchestrator"),
)

apply_ui_stream_patch()

# Expose the Orchestrator itself via A2A
a2a_server = A2AServer(
    agent=orchestrator,
    host="0.0.0.0",
    port=9200,
)

if __name__ == "__main__":
    print("Orchestrator Agent starting on port 9200...")
    a2a_server.serve()
