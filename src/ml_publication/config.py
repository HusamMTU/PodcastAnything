"""Runtime configuration for Lambda handlers and local runs."""
from __future__ import annotations

from dataclasses import dataclass
import os


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    bucket: str
    region: str
    bedrock_model_id: str
    polly_voice_id: str


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    bucket = os.environ.get("MP_BUCKET")
    if not bucket:
        raise ConfigError("Missing required environment variable: MP_BUCKET")

    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )

    bedrock_model_id = _require_env("BEDROCK_MODEL_ID")
    polly_voice_id = os.environ.get("POLLY_VOICE_ID", "Joanna")

    return Settings(
        bucket=bucket,
        region=region,
        bedrock_model_id=bedrock_model_id,
        polly_voice_id=polly_voice_id,
    )
