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
from transport.agent_progress import emit_agent_progress

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


async def _send_a2a_text(agent_base_url: str, text: str) -> str:
    base = agent_base_url.rstrip("/")
    config = ClientConfig(streaming=False)
    client = await ClientFactory.connect(base, client_config=config)
    try:
        message = create_text_message_object(content=text)
        best = ""
        async for event in client.send_message(message):
            chunk = _a2a_event_to_text(event)
            if chunk:
                best = chunk
        return best
    finally:
        await client.close()


def _invoke_remote_agent(agent_url: str, text: str) -> str:
    base = agent_url.rstrip("/")
    if base == RESEARCHER_URL.rstrip("/"):
        emit_agent_progress("Researcher", "Calling researcher A2A agent…")
    elif base == WRITER_URL.rstrip("/"):
        emit_agent_progress("Writer", "Calling writer A2A agent…")
    return run_async(lambda: _send_a2a_text(agent_url, text))


@tool
def call_researcher(topic: str) -> str:
    """Delegate to the remote Researcher A2A agent."""
    outline = _invoke_remote_agent(RESEARCHER_URL, topic)
    emit_agent_progress("Orchestrator", "Research complete; handing off to writer…")
    return outline


@tool
def call_writer(outline: str) -> str:
    """Delegate to the remote Writer A2A agent."""
    return _invoke_remote_agent(WRITER_URL, outline)


ORCHESTRATOR_PROMPT = """
You are an orchestrator that coordinates research and writing.
1. Use call_researcher to create an outline.
2. Use call_writer to turn that outline into an article.
Return the final article.
"""

orchestrator = Agent(
    name="orchestrator",
    description="Coordinates research and writing agents to produce complete articles.",
    system_prompt=ORCHESTRATOR_PROMPT,
    tools=[call_researcher, call_writer],
    **model_kwargs(),
)

# Expose the Orchestrator itself via A2A
a2a_server = A2AServer(
    agent=orchestrator,
    host="0.0.0.0",
    port=9200,
)

if __name__ == "__main__":
    print("Orchestrator Agent starting on port 9200...")
    a2a_server.serve()
