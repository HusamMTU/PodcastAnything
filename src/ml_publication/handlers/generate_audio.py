"""Lambda handler: synthesize podcast audio from script text."""
from __future__ import annotations

import logging
from typing import Any

from ml_publication.config import load_settings
from ml_publication.event_schema import PipelineEvent
from ml_publication.s3 import get_text, put_bytes
from ml_publication.tts import synthesize_speech

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _estimate_duration_sec(text: str, wpm: int = 150) -> int:
    words = len(text.split())
    minutes = words / max(wpm, 1)
    return int(minutes * 60)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    pipeline_event = PipelineEvent.from_dict(event, stage="generate")
    job_id = pipeline_event.job_id
    script_key = pipeline_event.script_s3_key
    assert job_id is not None
    assert script_key is not None

    settings = load_settings()
    bucket = pipeline_event.resolved_bucket(settings.bucket)
    voice_id = pipeline_event.voice_id or settings.polly_voice_id

    script_text = get_text(bucket, script_key)
    audio = synthesize_speech(script_text, voice_id=voice_id)

    audio_key = f"jobs/{job_id}/audio.mp3"
    put_bytes(bucket, audio_key, audio, content_type="audio/mpeg")

    logger.info("Stored audio", extra={"job_id": job_id, "key": audio_key})

    return pipeline_event.with_updates(
        bucket=bucket,
        audio_s3_key=audio_key,
        audio_estimated_duration_sec=_estimate_duration_sec(script_text),
    ).to_dict()
