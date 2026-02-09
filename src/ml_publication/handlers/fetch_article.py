"""Lambda handler: fetch and extract article text."""
from __future__ import annotations

import logging
from typing import Any

from ml_publication import article
from ml_publication.config import load_settings
from ml_publication.s3 import put_text

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    job_id = event.get("job_id")
    source_url = event.get("source_url")
    if not job_id or not source_url:
        raise ValueError("event must include job_id and source_url")

    settings = load_settings()
    bucket = event.get("bucket", settings.bucket)

    html = article.fetch_html(source_url)
    text = article.extract_text(html)

    article_key = f"jobs/{job_id}/article.txt"
    put_text(bucket, article_key, text)

    logger.info("Stored article text", extra={"job_id": job_id, "key": article_key})

    return {
        **event,
        "bucket": bucket,
        "article_s3_key": article_key,
        "article_char_count": len(text),
    }
