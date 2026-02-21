"""Utilities for API Gateway Lambda proxy handlers."""
from __future__ import annotations

import base64
import json
from typing import Any


class HttpRequestError(ValueError):
    """Raised when API request parsing fails."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def json_response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def parse_json_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if body in (None, ""):
        return {}
    if not isinstance(body, str):
        raise HttpRequestError("request body must be a JSON string")

    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body).decode("utf-8")
        except Exception as exc:  # defensive conversion for proxy events
            raise HttpRequestError("invalid base64 request body") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HttpRequestError("invalid JSON request body") from exc

    if not isinstance(payload, dict):
        raise HttpRequestError("request body must be a JSON object")

    return payload


def read_query_param(event: dict[str, Any], name: str) -> str | None:
    query = event.get("queryStringParameters") or {}
    value = query.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise HttpRequestError(f"query parameter '{name}' must be a string")
    cleaned = value.strip()
    return cleaned or None

