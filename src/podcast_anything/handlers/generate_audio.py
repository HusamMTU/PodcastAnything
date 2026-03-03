"""Lambda handler: synthesize podcast audio from script text."""

from __future__ import annotations

import logging
from typing import Any

from podcast_anything.config import load_settings
from podcast_anything.event_schema import PipelineEvent
from podcast_anything.s3 import get_text, put_bytes
from podcast_anything.tts import synthesize_speech

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _estimate_duration_sec(text: str, wpm: int = 150) -> int:
    words = len(text.split())
    minutes = words / max(wpm, 1)
    return int(minutes * 60)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    pipeline_event = PipelineEvent.from_dict(event)
    job_id, script_key = pipeline_event.require_generate_fields()

    settings = load_settings()
    bucket = pipeline_event.resolved_bucket(settings.bucket)
    default_voice_id = (
        settings.elevenlabs_voice_id
        if settings.tts_provider == "elevenlabs"
        else settings.polly_voice_id
    )
    voice_id = pipeline_event.voice_id or default_voice_id
    output_format = (
        settings.elevenlabs_output_format if settings.tts_provider == "elevenlabs" else "mp3"
    )
    text_type = "text" if settings.tts_provider == "elevenlabs" else "ssml"

    script_text = get_text(bucket, script_key)
    audio = synthesize_speech(
        script_text,
        voice_id=voice_id,
        provider=settings.tts_provider,
        output_format=output_format,
        text_type=text_type,
        max_text_chars=1800,
        elevenlabs_api_key=settings.elevenlabs_api_key,
        elevenlabs_model_id=settings.elevenlabs_model_id,
    )

    audio_key = f"jobs/{job_id}/audio.mp3"
    put_bytes(bucket, audio_key, audio, content_type="audio/mpeg")

    logger.info("Stored audio", extra={"job_id": job_id, "key": audio_key})

    return pipeline_event.with_updates(
        bucket=bucket,
        audio_s3_key=audio_key,
        audio_estimated_duration_sec=_estimate_duration_sec(script_text),
    ).to_dict()
