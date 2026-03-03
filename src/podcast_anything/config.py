"""Runtime configuration for Lambda handlers and local runs."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    bucket: str
    region: str
    bedrock_model_id: str
    tts_provider: str = "polly"
    polly_voice_id: str = "Joanna"
    polly_duo_voice_id: str = "Joanna"
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_duo_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_output_format: str = "mp3_44100_128"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    bucket = os.environ.get("MP_BUCKET")
    if not bucket:
        raise ConfigError("Missing required environment variable: MP_BUCKET")

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"

    bedrock_model_id = _require_env("BEDROCK_MODEL_ID")
    tts_provider = (os.environ.get("TTS_PROVIDER", "polly") or "polly").strip().lower()
    if tts_provider not in {"polly", "elevenlabs"}:
        raise ConfigError("TTS_PROVIDER must be either 'polly' or 'elevenlabs'")

    polly_voice_id = (os.environ.get("POLLY_VOICE_ID", "Joanna")).strip()
    polly_duo_voice_id = (
        os.environ.get("POLLY_DUO_VOICE_ID", polly_voice_id or "Joanna")
    ).strip()
    elevenlabs_api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip() or None
    elevenlabs_voice_id = (os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")).strip()
    elevenlabs_duo_voice_id = (
        os.environ.get("ELEVENLABS_DUO_VOICE_ID", elevenlabs_voice_id or "JBFqnCBsd6RMkjVDRZzb")
    ).strip()
    elevenlabs_model_id = (os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")).strip()
    elevenlabs_output_format = (os.environ.get("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128")).strip()

    if not polly_voice_id:
        raise ConfigError("POLLY_VOICE_ID must not be empty")
    if not polly_duo_voice_id:
        raise ConfigError("POLLY_DUO_VOICE_ID must not be empty")
    if tts_provider == "elevenlabs" and not elevenlabs_api_key:
        raise ConfigError("Missing required environment variable: ELEVENLABS_API_KEY")
    if not elevenlabs_voice_id:
        raise ConfigError("ELEVENLABS_VOICE_ID must not be empty")
    if not elevenlabs_duo_voice_id:
        raise ConfigError("ELEVENLABS_DUO_VOICE_ID must not be empty")
    if not elevenlabs_model_id:
        raise ConfigError("ELEVENLABS_MODEL_ID must not be empty")
    if not elevenlabs_output_format:
        raise ConfigError("ELEVENLABS_OUTPUT_FORMAT must not be empty")

    return Settings(
        bucket=bucket,
        region=region,
        bedrock_model_id=bedrock_model_id,
        tts_provider=tts_provider,
        polly_voice_id=polly_voice_id,
        polly_duo_voice_id=polly_duo_voice_id,
        elevenlabs_api_key=elevenlabs_api_key,
        elevenlabs_voice_id=elevenlabs_voice_id,
        elevenlabs_duo_voice_id=elevenlabs_duo_voice_id,
        elevenlabs_model_id=elevenlabs_model_id,
        elevenlabs_output_format=elevenlabs_output_format,
    )
