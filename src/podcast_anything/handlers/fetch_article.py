"""Lambda handler: fetch and extract article text."""
from __future__ import annotations

import logging
from typing import Any

from podcast_anything import article
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

    html = article.fetch_html(source_url)
    text = article.extract_text(html)

    article_key = f"jobs/{job_id}/article.txt"
    put_text(bucket, article_key, text)

    logger.info("Stored article text", extra={"job_id": job_id, "key": article_key})

    return pipeline_event.with_updates(
        bucket=bucket,
        article_s3_key=article_key,
        article_char_count=len(text),
    ).to_dict()
