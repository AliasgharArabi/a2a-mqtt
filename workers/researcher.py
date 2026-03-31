import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer

from model_env import model_kwargs

@tool
def research_topic(topic: str) -> str:
    """Produce a short bullet-point outline about the given topic."""
    # In a real scenario, this would call an LLM or search tool.
    # For this example, we return a mock outline.
    return f"Outline for {topic}:\n1. Introduction to {topic}\n2. Key benefits\n3. Future outlook"

researcher = Agent(
    name="researcher",
    description="Specialized agent that creates structured research outlines for any topic.",
    system_prompt="You are a research agent who creates structured outlines.",
    tools=[research_topic],
    **model_kwargs(),
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
