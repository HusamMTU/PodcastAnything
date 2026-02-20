"""Lambda handler: rewrite article into podcast-style script."""
from __future__ import annotations

import logging
from typing import Any

from podcast_anything.config import load_settings
from podcast_anything.event_schema import PipelineEvent
from podcast_anything.llm import build_podcast_prompt, call_bedrock
from podcast_anything.s3 import get_text, put_json, put_text

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    pipeline_event = PipelineEvent.from_dict(event)
    job_id, article_key = pipeline_event.require_rewrite_fields()

    settings = load_settings()
    bucket = pipeline_event.resolved_bucket(settings.bucket)

    article_text = get_text(bucket, article_key)
    prompt = build_podcast_prompt(
        article_text=article_text,
        title=pipeline_event.title,
        style=pipeline_event.style,
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
            "source_url": pipeline_event.source_url,
            "title": pipeline_event.title,
            "style": pipeline_event.style,
            "model_id": settings.bedrock_model_id,
            "script_s3_key": script_key,
        },
    )

    logger.info("Stored podcast script", extra={"job_id": job_id, "key": script_key})

    return pipeline_event.with_updates(
        bucket=bucket,
        script_s3_key=script_key,
        script_metadata_s3_key=metadata_key,
    ).to_dict()
