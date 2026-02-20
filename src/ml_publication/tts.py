"""Polly TTS helper."""
from __future__ import annotations

import html
import re

import boto3


class TTSError(RuntimeError):
    pass


def _split_text_for_polly(text: str, max_text_chars: int) -> list[str]:
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
    return (
        "<speak>"
        '<prosody rate="95%">'
        f"{escaped}"
        "</prosody>"
        "</speak>"
    )


def synthesize_speech(
    text: str,
    voice_id: str,
    output_format: str = "mp3",
    max_text_chars: int = 2500,
    text_type: str = "text",
) -> bytes:
    if text_type not in {"text", "ssml"}:
        raise TTSError("text_type must be either 'text' or 'ssml'.")

    chunks = _split_text_for_polly(text, max_text_chars=max_text_chars)
    client = boto3.client("polly")
    audio_parts: list[bytes] = []

    for index, chunk in enumerate(chunks):
        request_text = _chunk_to_ssml(chunk) if text_type == "ssml" else chunk
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
        audio_parts.append(stream.read())

    return b"".join(audio_parts)
