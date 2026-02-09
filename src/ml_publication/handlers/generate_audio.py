"""Lambda handler: synthesize podcast audio from script text."""
from __future__ import annotations

import logging
from typing import Any

from ml_publication.config import load_settings
from ml_publication.s3 import get_text, put_bytes
from ml_publication.tts import synthesize_speech

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _estimate_duration_sec(text: str, wpm: int = 150) -> int:
    words = len(text.split())
    minutes = words / max(wpm, 1)
    return int(minutes * 60)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    job_id = event.get("job_id")
    script_key = event.get("script_s3_key")
    if not job_id or not script_key:
        raise ValueError("event must include job_id and script_s3_key")

    settings = load_settings()
    bucket = event.get("bucket", settings.bucket)
    voice_id = event.get("voice_id", settings.polly_voice_id)

    script_text = get_text(bucket, script_key)
    audio = synthesize_speech(script_text, voice_id=voice_id)

    audio_key = f"jobs/{job_id}/audio.mp3"
    put_bytes(bucket, audio_key, audio, content_type="audio/mpeg")

    logger.info("Stored audio", extra={"job_id": job_id, "key": audio_key})

    return {
        **event,
        "bucket": bucket,
        "audio_s3_key": audio_key,
        "audio_estimated_duration_sec": _estimate_duration_sec(script_text),
    }
