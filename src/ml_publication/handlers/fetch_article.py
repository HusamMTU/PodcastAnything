"""Lambda handler: fetch and extract article text."""
from __future__ import annotations

import logging
from typing import Any

from ml_publication import article
from ml_publication.config import load_settings
from ml_publication.event_schema import PipelineEvent
from ml_publication.s3 import put_text

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    pipeline_event = PipelineEvent.from_dict(event, stage="fetch")
    job_id = pipeline_event.job_id
    source_url = pipeline_event.source_url
    assert job_id is not None
    assert source_url is not None

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
