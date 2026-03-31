"""Optional Agent model selection via environment.

Strands defaults to Amazon Bedrock (`BedrockModel`), which requires AWS credentials.
Set one of the following for local development:

  STRANDS_MODEL_PROVIDER=ollama   # needs Ollama running; optional OLLAMA_HOST, OLLAMA_MODEL
  STRANDS_MODEL_PROVIDER=openai   # needs OPENAI_API_KEY; optional OPENAI_MODEL

Bedrock profile resolution (when STRANDS_MODEL_PROVIDER is unset):

  STRANDS_AWS_PROFILE, then AWS_PROFILE, then AWS_DEFAULT_PROFILE, then "aws" so IDE-only
  launches still use the common SSO profile name without relying on shell env.
  Use STRANDS_BOTO_DEFAULT_SESSION=1 to restore Strands' default credential chain only.

  STRANDS_AWS_REGION / AWS_REGION / AWS_DEFAULT_REGION should match your Bedrock region; SSO refresh
  fails with NoRegionError if none of these are set and the profile has no region.
"""

from __future__ import annotations

import os
from typing import Any


def _bedrock_model_kwargs() -> dict[str, Any]:
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
    return {"model": BedrockModel(boto_session=session)}


def model_kwargs() -> dict[str, Any]:
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
    return _bedrock_model_kwargs()
