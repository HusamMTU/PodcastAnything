#!/usr/bin/env python3
"""Fetch a YouTube transcript locally and save it as plain text."""

from __future__ import annotations

import argparse
from pathlib import Path

from podcast_anything.youtube import YouTubeTranscriptError, extract_video_id, fetch_transcript_text


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a YouTube transcript locally and write it to a .txt file."
    )
    parser.add_argument("youtube_url", help="YouTube video URL")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output .txt path (default: ./youtube-<video_id>-transcript.txt)",
    )
    parser.add_argument(
        "--print",
        dest="print_text",
        action="store_true",
        help="Print transcript to stdout in addition to writing the file",
    )
    return parser.parse_args()


def _default_output_path(youtube_url: str) -> Path:
    video_id = extract_video_id(youtube_url)
    return Path(f"youtube-{video_id}-transcript.txt")


def main() -> None:
    args = _parse_args()

    try:
        transcript_text = fetch_transcript_text(args.youtube_url)
        output_path = Path(args.output) if args.output else _default_output_path(args.youtube_url)
    except YouTubeTranscriptError as exc:
        raise SystemExit(f"error: {exc}") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(transcript_text + "\n", encoding="utf-8")

    print(f"Wrote transcript to {output_path}")
    if args.print_text:
        print()
        print(transcript_text)


if __name__ == "__main__":
    main()
