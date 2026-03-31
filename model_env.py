"""Optional Agent model selection via environment or agents.yaml.

Strands defaults to Amazon Bedrock (`BedrockModel`), which requires AWS credentials.
Set one of the following for local development:

  STRANDS_MODEL_PROVIDER=ollama   # needs Ollama running; optional OLLAMA_HOST, OLLAMA_MODEL
  STRANDS_MODEL_PROVIDER=openai   # needs OPENAI_API_KEY; optional OPENAI_MODEL

Bedrock profile resolution (when STRANDS_MODEL_PROVIDER is unset):

  STRANDS_AWS_PROFILE, then AWS_PROFILE, then AWS_DEFAULT_PROFILE, then "aws" so IDE-only
  launches still use the common SSO profile name without relying on shell env.
  Use STRANDS_BOTO_DEFAULT_SESSION=1 to restore Strands' default credential chain only.

  STRANDS_AWS_REGION / AWS_REGION / AWS_DEFAULT_REGION should match your Bedrock region.

Per-agent model configuration (read from agents.yaml at the workspace root):

  Edit agents.yaml to set model_id and max_tokens per agent.
  NOTE: changes take effect only after restarting the affected agent process.

  Environment variables always override agents.yaml:
    STRANDS_MODEL_ID_ORCHESTRATOR   — Bedrock model ID for the orchestrator
    STRANDS_MODEL_ID_RESEARCHER     — Bedrock model ID for the researcher
    STRANDS_MODEL_ID_WRITER         — Bedrock model ID for the writer
    STRANDS_BEDROCK_MAX_TOKENS_ORCHESTRATOR
    STRANDS_BEDROCK_MAX_TOKENS_WORKER
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

AgentRole = Literal["orchestrator", "worker"]
AgentName = Literal["orchestrator", "researcher", "writer"]

_AGENTS_YAML = Path(__file__).resolve().parent / "agents.yaml"

# Hard-coded fallbacks used when agents.yaml is absent and no env override is set.
_DEFAULT_MODEL_ID = "us.anthropic.claude-opus-4-5"
_DEFAULT_MAX_TOKENS: dict[AgentRole, int] = {
    "orchestrator": 4000,
    "worker": 8000,
}


def _load_yaml_config() -> dict:
    """Return the parsed agents.yaml, or an empty dict if unavailable."""
    try:
        import yaml  # PyYAML — already a transitive dep of many AWS packages
        with open(_AGENTS_YAML) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _yaml_agent_cfg(agent_name: AgentName) -> dict:
    cfg = _load_yaml_config()
    return (cfg.get("bedrock") or {}).get(agent_name) or {}


def _bedrock_model_id(agent_name: AgentName) -> str:
    env_key = f"STRANDS_MODEL_ID_{agent_name.upper()}"
    if env_val := os.environ.get(env_key, "").strip():
        return env_val
    return _yaml_agent_cfg(agent_name).get("model_id") or _DEFAULT_MODEL_ID


def _bedrock_max_tokens(agent_name: AgentName) -> int:
    role: AgentRole = "orchestrator" if agent_name == "orchestrator" else "worker"
    env_key = (
        "STRANDS_BEDROCK_MAX_TOKENS_ORCHESTRATOR"
        if role == "orchestrator"
        else "STRANDS_BEDROCK_MAX_TOKENS_WORKER"
    )
    if env_val := os.environ.get(env_key, "").strip():
        try:
            return max(1, int(env_val))
        except ValueError:
            pass
    yaml_val = _yaml_agent_cfg(agent_name).get("max_tokens")
    if yaml_val is not None:
        try:
            return max(1, int(yaml_val))
        except (ValueError, TypeError):
            pass
    return _DEFAULT_MAX_TOKENS[role]


def _bedrock_model_kwargs(agent_name: AgentName) -> dict[str, Any]:
    import boto3
    from strands.models.bedrock import BedrockModel

    if os.environ.get("STRANDS_BOTO_DEFAULT_SESSION", "").lower() in ("1", "true", "yes"):
        return {}

    profile = (
        os.environ.get("STRANDS_AWS_PROFILE")
        or os.environ.get("AWS_PROFILE")
        or os.environ.get("AWS_DEFAULT_PROFILE")
        or "aws"
    )
    region = (
        os.environ.get("STRANDS_AWS_REGION")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
    )
    if not region:
        probe = boto3.Session(profile_name=profile)
        region = probe.region_name
    if not region:
        region = "us-east-1"
    session = boto3.Session(profile_name=profile, region_name=region)

    model_id = _bedrock_model_id(agent_name)
    max_tokens = _bedrock_max_tokens(agent_name)
    print(f"[model_env] {agent_name}: model_id={model_id}  max_tokens={max_tokens}")
    return {
        "model": BedrockModel(
            model_id=model_id,
            boto_session=session,
            max_tokens=max_tokens,
        ),
    }


def model_kwargs(*, role: AgentRole = "worker", agent_name: AgentName = "writer") -> dict[str, Any]:
    """Return Strands Agent `model=` kwargs for the given agent.

    Args:
        role:       "orchestrator" or "worker" (legacy; kept for back-compat).
        agent_name: "orchestrator", "researcher", or "writer".
                    Preferred over `role` — gives per-agent model control.
    """
    provider = (os.environ.get("STRANDS_MODEL_PROVIDER") or "").strip().lower()
    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        host = os.environ.get("OLLAMA_HOST") or None
        if host == "":
            host = None
        model_id = os.environ.get("OLLAMA_MODEL", "llama3.2")
        return {"model": OllamaModel(host, model_id=model_id)}
    if provider == "openai":
        from strands.models.openai import OpenAIModel

        model_id = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        return {"model": OpenAIModel(model_id=model_id)}
    return _bedrock_model_kwargs(agent_name)
