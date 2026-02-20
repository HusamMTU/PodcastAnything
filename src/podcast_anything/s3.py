"""Small S3 helper utilities."""
from __future__ import annotations

import json
from typing import Any

import boto3


def _client():
    return boto3.client("s3")


def put_text(bucket: str, key: str, text: str, content_type: str = "text/plain") -> None:
    _client().put_object(
        Bucket=bucket,
        Key=key,
        Body=text.encode("utf-8"),
        ContentType=f"{content_type}; charset=utf-8",
    )


def get_text(bucket: str, key: str) -> str:
    resp = _client().get_object(Bucket=bucket, Key=key)
    return resp["Body"].read().decode("utf-8")


def put_json(bucket: str, key: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=True, indent=2)
    put_text(bucket, key, body, content_type="application/json")


def get_json(bucket: str, key: str) -> dict[str, Any]:
    return json.loads(get_text(bucket, key))


def put_bytes(bucket: str, key: str, data: bytes, content_type: str) -> None:
    _client().put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
