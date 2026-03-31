import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from strands import Agent
from strands.multiagent.a2a import A2AServer
from strands.types.agent import ConcurrentInvocationMode

from model_env import model_kwargs

writer = Agent(
    name="writer",
    description="Specialized agent that expands bullet outlines into readable articles.",
    system_prompt=(
        "You are a writing agent. When given a research outline, write a clear, "
        "well-structured article that expands on every section. "
        "Write the article directly — do not use any tools."
    ),
    # Allow re-entrant A2A requests so a second call while the first is in-flight
    # does not raise ConcurrencyException.
    concurrent_invocation_mode=ConcurrentInvocationMode.UNSAFE_REENTRANT,
    **model_kwargs(agent_name="writer"),
)

# Expose as A2A Server
a2a_server = A2AServer(
    agent=writer,
    host="0.0.0.0",
    port=9102,
)

if __name__ == "__main__":
    print("Writer Agent starting on port 9102...")
    a2a_server.serve()
