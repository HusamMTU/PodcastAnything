"""Text-to-speech helper with Polly and ElevenLabs providers."""

from __future__ import annotations

import html
import logging
import re
import time

import boto3
import requests


class TTSError(RuntimeError):
    pass


logger = logging.getLogger(__name__)


def _split_text_for_tts(text: str, max_text_chars: int) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        raise TTSError("Input text is empty.")
    if max_text_chars < 100:
        raise TTSError("max_text_chars must be at least 100.")

    chunks: list[str] = []
    remaining = cleaned

    while remaining:
        if len(remaining) <= max_text_chars:
            chunks.append(remaining)
            break

        window = remaining[:max_text_chars]
        split_at = max(
            window.rfind("\n"),
            window.rfind(". "),
            window.rfind("! "),
            window.rfind("? "),
            window.rfind("; "),
            window.rfind(", "),
            window.rfind(" "),
        )
        if split_at < int(max_text_chars * 0.6):
            split_at = max_text_chars

        chunk = remaining[:split_at].strip()
        if not chunk:
            split_at = max_text_chars
            chunk = remaining[:split_at].strip()

        chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()

    return chunks


def _chunk_to_ssml(text_chunk: str) -> str:
    escaped = html.escape(text_chunk.strip(), quote=False)
    if not escaped:
        raise TTSError("Cannot build SSML from an empty text chunk.")

    escaped = re.sub(r"\n{2,}", '<break time="700ms"/>', escaped)
    escaped = escaped.replace("\n", '<break time="350ms"/>')
    return f'<speak><prosody rate="95%">{escaped}</prosody></speak>'


def _synthesize_with_polly(
    text: str,
    voice_id: str,
    output_format: str = "mp3",
    max_text_chars: int = 2500,
    text_type: str = "text",
) -> bytes:
    if text_type not in {"text", "ssml"}:
        raise TTSError("text_type must be either 'text' or 'ssml'.")

    chunks = _split_text_for_tts(text, max_text_chars=max_text_chars)
    client = boto3.client("polly")
    audio_parts: list[bytes] = []
    total_start = time.perf_counter()

    logger.info(
        "Starting Polly synthesis",
        extra={
            "chunk_count": len(chunks),
            "voice_id": voice_id,
            "text_type": text_type,
            "output_format": output_format,
        },
    )

    for index, chunk in enumerate(chunks):
        request_text = _chunk_to_ssml(chunk) if text_type == "ssml" else chunk
        chunk_start = time.perf_counter()
        response = client.synthesize_speech(
            Text=request_text,
            TextType=text_type,
            VoiceId=voice_id,
            OutputFormat=output_format,
            Engine="generative",
        )
        stream = response.get("AudioStream")
        if not stream:
            raise TTSError(f"Polly response missing AudioStream for chunk {index}.")
        chunk_audio = stream.read()
        audio_parts.append(chunk_audio)
        chunk_elapsed_ms = int((time.perf_counter() - chunk_start) * 1000)
        logger.info(
            "Polly chunk synthesized",
            extra={
                "chunk_index": index,
                "chunk_count": len(chunks),
                "input_chars": len(chunk),
                "audio_bytes": len(chunk_audio),
                "elapsed_ms": chunk_elapsed_ms,
            },
        )

    combined_audio = b"".join(audio_parts)
    total_elapsed_ms = int((time.perf_counter() - total_start) * 1000)
    logger.info(
        "Completed Polly synthesis",
        extra={
            "chunk_count": len(chunks),
            "total_audio_bytes": len(combined_audio),
            "elapsed_ms": total_elapsed_ms,
        },
    )
    return combined_audio


def _synthesize_with_elevenlabs(
    text: str,
    *,
    voice_id: str,
    elevenlabs_api_key: str | None,
    elevenlabs_model_id: str,
    output_format: str = "mp3_44100_128",
    max_text_chars: int = 2500,
    text_type: str = "text",
) -> bytes:
    if text_type != "text":
        raise TTSError("ElevenLabs synthesis supports only text input in this pipeline.")
    if not elevenlabs_api_key:
        raise TTSError("ElevenLabs API key is required for elevenlabs provider.")

    chunks = _split_text_for_tts(text, max_text_chars=max_text_chars)
    audio_parts: list[bytes] = []
    total_start = time.perf_counter()

    logger.info(
        "Starting ElevenLabs synthesis",
        extra={
            "chunk_count": len(chunks),
            "voice_id": voice_id,
            "model_id": elevenlabs_model_id,
            "output_format": output_format,
        },
    )

    endpoint = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    for index, chunk in enumerate(chunks):
        chunk_start = time.perf_counter()
        try:
            response = requests.post(
                endpoint,
                params={"output_format": output_format},
                headers=headers,
                json={
                    "text": chunk,
                    "model_id": elevenlabs_model_id,
                },
                timeout=60,
            )
        except requests.RequestException as exc:
            raise TTSError(f"ElevenLabs request failed for chunk {index}: {exc}") from exc
        if response.status_code >= 400:
            error_body = response.text.strip()[:500]
            raise TTSError(
                "ElevenLabs request failed "
                f"(status={response.status_code}, chunk={index}): {error_body}"
            )
        if not response.content:
            raise TTSError(f"ElevenLabs response missing audio content for chunk {index}.")

        audio_parts.append(response.content)
        chunk_elapsed_ms = int((time.perf_counter() - chunk_start) * 1000)
        logger.info(
            "ElevenLabs chunk synthesized",
            extra={
                "chunk_index": index,
                "chunk_count": len(chunks),
                "input_chars": len(chunk),
                "audio_bytes": len(response.content),
                "elapsed_ms": chunk_elapsed_ms,
            },
        )

    combined_audio = b"".join(audio_parts)
    total_elapsed_ms = int((time.perf_counter() - total_start) * 1000)
    logger.info(
        "Completed ElevenLabs synthesis",
        extra={
            "chunk_count": len(chunks),
            "total_audio_bytes": len(combined_audio),
            "elapsed_ms": total_elapsed_ms,
        },
    )
    return combined_audio


def synthesize_speech(
    text: str,
    voice_id: str,
    *,
    provider: str = "polly",
    output_format: str = "mp3",
    max_text_chars: int = 2500,
    text_type: str = "text",
    elevenlabs_api_key: str | None = None,
    elevenlabs_model_id: str = "eleven_multilingual_v2",
) -> bytes:
    normalized_provider = provider.strip().lower()
    if normalized_provider == "polly":
        return _synthesize_with_polly(
            text=text,
            voice_id=voice_id,
            output_format=output_format,
            max_text_chars=max_text_chars,
            text_type=text_type,
        )
    if normalized_provider == "elevenlabs":
        resolved_output_format = output_format if output_format != "mp3" else "mp3_44100_128"
        return _synthesize_with_elevenlabs(
            text=text,
            voice_id=voice_id,
            elevenlabs_api_key=elevenlabs_api_key,
            elevenlabs_model_id=elevenlabs_model_id,
            output_format=resolved_output_format,
            max_text_chars=max_text_chars,
            text_type=text_type,
        )
    raise TTSError("Unsupported TTS provider. Use 'polly' or 'elevenlabs'.")
