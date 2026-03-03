"""Lambda handler: synthesize podcast audio from script text."""

from __future__ import annotations

import logging
import re
from typing import Any

from podcast_anything.config import load_settings
from podcast_anything.event_schema import PipelineEvent
from podcast_anything.s3 import get_text, put_bytes
from podcast_anything.tts import synthesize_speech

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_DUO_LINE_RE = re.compile(r"^\s*(HOST_A|HOST_B)\s*:\s*(.*)$", re.IGNORECASE)


def _estimate_duration_sec(text: str, wpm: int = 150) -> int:
    words = len(text.split())
    minutes = words / max(wpm, 1)
    return int(minutes * 60)


def _default_duo_voice_ids(settings: Any) -> tuple[str, str]:
    if settings.tts_provider == "elevenlabs":
        return settings.elevenlabs_voice_id, settings.elevenlabs_duo_voice_id
    return settings.polly_voice_id, settings.polly_duo_voice_id


def _parse_duo_turns(script_text: str) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    active_speaker: str | None = None
    active_lines: list[str] = []

    def flush_active() -> None:
        nonlocal active_lines
        if not active_speaker or not active_lines:
            active_lines = []
            return
        merged = "\n".join(active_lines).strip()
        if merged:
            turns.append((active_speaker, merged))
        active_lines = []

    for raw_line in script_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if active_speaker and active_lines:
                active_lines.append("")
            continue

        match = _DUO_LINE_RE.match(raw_line)
        if match:
            flush_active()
            active_speaker = match.group(1).upper()
            first_content = match.group(2).strip()
            active_lines = [first_content] if first_content else []
            continue

        if active_speaker:
            active_lines.append(stripped)

    flush_active()
    return turns


def _synthesize_duo_audio(
    script_text: str,
    *,
    speaker_a_voice_id: str,
    speaker_b_voice_id: str,
    provider: str,
    output_format: str,
    text_type: str,
    elevenlabs_api_key: str | None,
    elevenlabs_model_id: str,
) -> bytes:
    turns = _parse_duo_turns(script_text)
    if not turns:
        raise ValueError(
            "script_mode=duo requires script lines prefixed with HOST_A: or HOST_B:."
        )

    logger.info(
        "Starting duo audio synthesis",
        extra={"turn_count": len(turns), "provider": provider},
    )
    audio_parts: list[bytes] = []
    for index, (speaker, turn_text) in enumerate(turns):
        voice_id = speaker_a_voice_id if speaker == "HOST_A" else speaker_b_voice_id
        turn_audio = synthesize_speech(
            turn_text,
            voice_id=voice_id,
            provider=provider,
            output_format=output_format,
            text_type=text_type,
            max_text_chars=1800,
            elevenlabs_api_key=elevenlabs_api_key,
            elevenlabs_model_id=elevenlabs_model_id,
        )
        audio_parts.append(turn_audio)
        logger.info(
            "Synthesized duo turn",
            extra={
                "turn_index": index,
                "speaker": speaker,
                "voice_id": voice_id,
                "text_chars": len(turn_text),
                "audio_bytes": len(turn_audio),
            },
        )

    return b"".join(audio_parts)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    pipeline_event = PipelineEvent.from_dict(event)
    job_id, script_key = pipeline_event.require_generate_fields()

    settings = load_settings()
    bucket = pipeline_event.resolved_bucket(settings.bucket)
    default_voice_id, default_voice_id_b = _default_duo_voice_ids(settings)
    voice_id = pipeline_event.voice_id or default_voice_id
    voice_id_b = pipeline_event.voice_id_b or default_voice_id_b
    output_format = (
        settings.elevenlabs_output_format if settings.tts_provider == "elevenlabs" else "mp3"
    )
    text_type = "text" if settings.tts_provider == "elevenlabs" else "ssml"

    script_text = get_text(bucket, script_key)
    if pipeline_event.script_mode == "duo":
        audio = _synthesize_duo_audio(
            script_text,
            speaker_a_voice_id=voice_id,
            speaker_b_voice_id=voice_id_b,
            provider=settings.tts_provider,
            output_format=output_format,
            text_type=text_type,
            elevenlabs_api_key=settings.elevenlabs_api_key,
            elevenlabs_model_id=settings.elevenlabs_model_id,
        )
    else:
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
