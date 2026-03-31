import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from strands.types.agent import ConcurrentInvocationMode

from model_env import model_kwargs

researcher = Agent(
    name="researcher",
    description="Specialized agent that creates structured research outlines for any topic.",
    system_prompt=(
        "You are a research agent. When given a topic, produce a thorough, "
        "well-structured bullet-point outline covering key aspects, benefits, "
        "challenges, and future outlook. Write the outline directly — do not use any tools."
    ),
    concurrent_invocation_mode=ConcurrentInvocationMode.UNSAFE_REENTRANT,
    **model_kwargs(agent_name="researcher"),
)

# Expose as A2A Server
a2a_server = A2AServer(
    agent=researcher,
    host="0.0.0.0",
    port=9101,
)

if __name__ == "__main__":
    print("Researcher Agent starting on port 9101...")
    a2a_server.serve()
