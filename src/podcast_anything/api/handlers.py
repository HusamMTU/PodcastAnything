"""Lambda handlers for API-style operations."""
from __future__ import annotations

from typing import Any

from podcast_anything.api.http import HttpRequestError, json_response, parse_json_body, read_query_param
from podcast_anything.api.service import PipelineApiError, get_execution_status, start_pipeline_execution


def _error_response(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, HttpRequestError):
        return json_response(exc.status_code, {"error": str(exc)})
    if isinstance(exc, PipelineApiError):
        return json_response(400, {"error": str(exc)})
    return json_response(500, {"error": "internal server error"})


def start_execution_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    try:
        payload = parse_json_body(event)
        result = start_pipeline_execution(
            source_url=payload.get("source_url"),
            job_id=payload.get("job_id"),
            style=payload.get("style", "podcast"),
            region=read_query_param(event, "region"),
            stack_name=read_query_param(event, "stack_name"),
            state_machine_arn=payload.get("state_machine_arn")
            or read_query_param(event, "state_machine_arn"),
        )
    except Exception as exc:
        return _error_response(exc)

    return json_response(202, result)


def get_execution_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    try:
        execution_arn = read_query_param(event, "execution_arn")
        if not execution_arn:
            path_params = event.get("pathParameters") or {}
            raw_from_path = path_params.get("execution_arn")
            if isinstance(raw_from_path, str):
                execution_arn = raw_from_path.strip() or None

        if not execution_arn:
            raise HttpRequestError("missing required parameter: execution_arn")

        result = get_execution_status(
            execution_arn=execution_arn,
            region=read_query_param(event, "region"),
        )
    except Exception as exc:
        return _error_response(exc)

    return json_response(200, result)

