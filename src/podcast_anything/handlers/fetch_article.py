"""Lambda handler: fetch and extract source text (article or YouTube transcript)."""
from __future__ import annotations

import logging
from typing import Any

from podcast_anything import article, youtube
from podcast_anything.config import load_settings
from podcast_anything.event_schema import PipelineEvent
from podcast_anything.s3 import put_text

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    pipeline_event = PipelineEvent.from_dict(event)
    job_id, source_url = pipeline_event.require_fetch_fields()

    settings = load_settings()
    bucket = pipeline_event.resolved_bucket(settings.bucket)

    if youtube.is_youtube_url(source_url):
        text = youtube.fetch_transcript_text(source_url)
        source_type = "youtube"
        logger.info("Fetched YouTube transcript", extra={"job_id": job_id})
    else:
        html = article.fetch_html(source_url)
        text = article.extract_text(html)
        source_type = "article"

    article_key = f"jobs/{job_id}/article.txt"
    put_text(bucket, article_key, text)

    logger.info(
        "Stored source text",
        extra={"job_id": job_id, "key": article_key, "source_type": source_type},
    )

    return pipeline_event.with_updates(
        bucket=bucket,
        source_type=source_type,
        article_s3_key=article_key,
        article_char_count=len(text),
    ).to_dict()
