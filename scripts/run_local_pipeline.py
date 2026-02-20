"""Run the article -> script -> audio pipeline locally using the Lambda handlers.

This still uses AWS services (S3, Bedrock, Polly), so AWS credentials and
required environment variables must be set.
"""
from __future__ import annotations

import argparse
import json
import os
import uuid

from podcast_anything.handlers.fetch_article import handler as fetch_article
from podcast_anything.handlers.rewrite_script import handler as rewrite_script
from podcast_anything.handlers.generate_audio import handler as generate_audio


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local pipeline using Lambda handlers.")
    parser.add_argument("url", help="Public article URL")
    parser.add_argument("--title", default=None, help="Optional title for the article")
    parser.add_argument("--style", default="podcast", help="Script style label")
    parser.add_argument("--job-id", default=None, help="Optional job id (uuid)")
    parser.add_argument("--bucket", default=os.environ.get("MP_BUCKET"), help="S3 bucket")
    parser.add_argument("--voice-id", default=None, help="Polly voice id override")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    job_id = args.job_id or str(uuid.uuid4())

    event = {
        "job_id": job_id,
        "source_url": args.url,
        "title": args.title,
        "style": args.style,
    }
    if args.bucket:
        event["bucket"] = args.bucket
    if args.voice_id:
        event["voice_id"] = args.voice_id

    event = fetch_article(event, None)
    event = rewrite_script(event, None)
    event = generate_audio(event, None)

    print(json.dumps(event, indent=2))


if __name__ == "__main__":
    main()
