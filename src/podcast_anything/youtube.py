"""YouTube transcript helpers."""
from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import parse_qs, urlparse


class YouTubeTranscriptError(RuntimeError):
    """Raised when a YouTube transcript cannot be fetched or parsed."""


_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


def is_youtube_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return (parsed.hostname or "").lower() in _YOUTUBE_HOSTS


def extract_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if host not in _YOUTUBE_HOSTS:
        raise YouTubeTranscriptError("source_url is not a supported YouTube URL")

    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.lstrip("/").split("/")[0]
        if video_id:
            return video_id

    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
            if video_id:
                return video_id

        for prefix in ("/shorts/", "/embed/", "/live/"):
            if parsed.path.startswith(prefix):
                tail = parsed.path[len(prefix):]
                video_id = tail.split("/")[0]
                if video_id:
                    return video_id

    raise YouTubeTranscriptError("Could not extract video id from YouTube URL")


def _normalize_transcript_lines(lines: Iterable[str]) -> str:
    cleaned = [re.sub(r"\s+", " ", line).strip() for line in lines if line and line.strip()]
    if not cleaned:
        raise YouTubeTranscriptError("YouTube transcript is empty")

    paragraphs: list[str] = []
    chunk: list[str] = []
    for index, line in enumerate(cleaned, start=1):
        chunk.append(line)
        if len(chunk) >= 6:
            paragraphs.append(" ".join(chunk))
            chunk = []

    if chunk:
        paragraphs.append(" ".join(chunk))

    return "\n\n".join(paragraphs).strip()


def _extract_text_lines_from_segments(segments: object) -> list[str]:
    if hasattr(segments, "to_raw_data"):
        segments = segments.to_raw_data()

    lines: list[str] = []
    for item in segments:  # type: ignore[assignment]
        if isinstance(item, dict):
            text = item.get("text")
        else:
            text = getattr(item, "text", None)
        if isinstance(text, str):
            lines.append(text)
    return lines


def _fetch_segments_with_library(video_id: str) -> object:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised in runtime setup, not unit tests
        raise YouTubeTranscriptError(
            "youtube-transcript-api is not installed. Install project dependencies and redeploy the fetch layer."
        ) from exc

    # Support both common library APIs across versions.
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        return YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US"])

    api = YouTubeTranscriptApi()
    if hasattr(api, "fetch"):
        try:
            return api.fetch(video_id, languages=["en", "en-US"])
        except TypeError:
            return api.fetch(video_id)

    raise YouTubeTranscriptError("Unsupported youtube-transcript-api version")


def fetch_transcript_text(url: str) -> str:
    video_id = extract_video_id(url)
    try:
        segments = _fetch_segments_with_library(video_id)
    except YouTubeTranscriptError:
        raise
    except Exception as exc:
        raise YouTubeTranscriptError(f"Failed to fetch YouTube transcript: {exc}") from exc

    lines = _extract_text_lines_from_segments(segments)
    return _normalize_transcript_lines(lines)

