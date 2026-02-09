"""Lambda handler: rewrite article into podcast-style script."""
from __future__ import annotations

import logging
from typing import Any

from ml_publication.config import load_settings
from ml_publication.llm import build_podcast_prompt, call_bedrock
from ml_publication.s3 import get_text, put_json, put_text

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    job_id = event.get("job_id")
    article_key = event.get("article_s3_key")
    if not job_id or not article_key:
        raise ValueError("event must include job_id and article_s3_key")

    settings = load_settings()
    bucket = event.get("bucket", settings.bucket)

    article_text = get_text(bucket, article_key)
    prompt = build_podcast_prompt(
        article_text=article_text,
        title=event.get("title"),
        style=event.get("style", "podcast"),
    )

    script_text = call_bedrock(settings.bedrock_model_id, prompt)

    script_key = f"jobs/{job_id}/script.txt"
    metadata_key = f"jobs/{job_id}/script.json"

    put_text(bucket, script_key, script_text)
    put_json(
        bucket,
        metadata_key,
        {
            "job_id": job_id,
            "source_url": event.get("source_url"),
            "title": event.get("title"),
            "style": event.get("style", "podcast"),
            "model_id": settings.bedrock_model_id,
            "script_s3_key": script_key,
        },
    )

    logger.info("Stored podcast script", extra={"job_id": job_id, "key": script_key})

    return {
        **event,
        "bucket": bucket,
        "script_s3_key": script_key,
        "script_metadata_s3_key": metadata_key,
    }
