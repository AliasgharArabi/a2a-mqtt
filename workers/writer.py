import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer

from model_env import model_kwargs

@tool
def expand_outline(outline: str) -> str:
    """Turn a bullet outline into a short article."""
    return f"Full Article based on:\n{outline}\n\nThis is a detailed expansion of the research provided."

writer = Agent(
    name="writer",
    description="Specialized agent that expands bullet outlines into readable articles.",
    system_prompt="You are a writing agent that expands outlines into articles.",
    tools=[expand_outline],
    **model_kwargs(),
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
