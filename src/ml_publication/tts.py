"""Polly TTS helper."""
from __future__ import annotations

import boto3


class TTSError(RuntimeError):
    pass


def synthesize_speech(text: str, voice_id: str, output_format: str = "mp3") -> bytes:
    client = boto3.client("polly")
    response = client.synthesize_speech(
        Text=text,
        VoiceId=voice_id,
        OutputFormat=output_format,
        Engine="neural",
    )

    stream = response.get("AudioStream")
    if not stream:
        raise TTSError("Polly response missing AudioStream.")
    return stream.read()
