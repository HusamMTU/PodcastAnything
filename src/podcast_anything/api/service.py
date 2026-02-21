"""Service layer for starting and inspecting pipeline executions."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class PipelineApiError(RuntimeError):
    """Raised when API-level pipeline actions fail."""


def _default_region() -> str:
    return (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )


def _default_stack_name() -> str:
    return os.environ.get("STACK_NAME", "PodcastAnythingStack")


def _default_state_machine_arn() -> str | None:
    value = os.environ.get("PIPELINE_STATE_MACHINE_ARN")
    if not value:
        return None
    cleaned = value.strip()
    return cleaned or None


def _require_non_empty(value: str | None, field_name: str) -> str:
    if value is None:
        raise PipelineApiError(f"missing required field: {field_name}")
    if not isinstance(value, str):
        raise PipelineApiError(f"field must be a string: {field_name}")
    cleaned = value.strip()
    if not cleaned:
        raise PipelineApiError(f"field must not be empty: {field_name}")
    return cleaned


def _format_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _try_parse_json(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _generate_job_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    short_suffix = uuid.uuid4().hex[:8]
    return f"job-{timestamp}-{short_suffix}"


def resolve_state_machine_arn(*, cloudformation: Any, stack_name: str) -> str:
    try:
        response = cloudformation.describe_stacks(StackName=stack_name)
    except (ClientError, BotoCoreError) as exc:
        raise PipelineApiError(str(exc)) from exc

    stacks = response.get("Stacks", [])
    if not stacks:
        raise PipelineApiError(f"stack not found: {stack_name}")

    outputs = stacks[0].get("Outputs", [])
    for output in outputs:
        if output.get("OutputKey") == "PipelineStateMachineArn":
            arn = output.get("OutputValue")
            if arn:
                return arn

    raise PipelineApiError(
        f"could not resolve PipelineStateMachineArn from stack '{stack_name}'"
    )


def start_pipeline_execution(
    *,
    source_url: str,
    job_id: str | None = None,
    style: str = "podcast",
    region: str | None = None,
    stack_name: str | None = None,
    state_machine_arn: str | None = None,
) -> dict[str, Any]:
    cleaned_source_url = _require_non_empty(source_url, "source_url")
    cleaned_job_id = job_id.strip() if isinstance(job_id, str) and job_id.strip() else None
    cleaned_style = style.strip() if isinstance(style, str) and style.strip() else "podcast"
    cleaned_region = region.strip() if isinstance(region, str) and region.strip() else _default_region()
    cleaned_stack_name = (
        stack_name.strip()
        if isinstance(stack_name, str) and stack_name.strip()
        else _default_stack_name()
    )
    cleaned_state_machine_arn = (
        state_machine_arn.strip()
        if isinstance(state_machine_arn, str) and state_machine_arn.strip()
        else _default_state_machine_arn()
    )

    resolved_job_id = cleaned_job_id or _generate_job_id()
    payload = {
        "job_id": resolved_job_id,
        "source_url": cleaned_source_url,
        "style": cleaned_style,
    }

    try:
        session = boto3.session.Session(region_name=cleaned_region)
        if not cleaned_state_machine_arn:
            cloudformation = session.client("cloudformation")
            cleaned_state_machine_arn = resolve_state_machine_arn(
                cloudformation=cloudformation,
                stack_name=cleaned_stack_name,
            )

        stepfunctions = session.client("stepfunctions")
        response = stepfunctions.start_execution(
            stateMachineArn=cleaned_state_machine_arn,
            input=json.dumps(payload),
        )
    except (ClientError, BotoCoreError) as exc:
        raise PipelineApiError(str(exc)) from exc

    return {
        "job_id": resolved_job_id,
        "source_url": cleaned_source_url,
        "style": cleaned_style,
        "region": cleaned_region,
        "state_machine_arn": cleaned_state_machine_arn,
        "execution_arn": response.get("executionArn"),
        "start_date": _format_datetime(response.get("startDate")),
    }


def get_execution_status(
    *,
    execution_arn: str,
    region: str | None = None,
) -> dict[str, Any]:
    cleaned_execution_arn = _require_non_empty(execution_arn, "execution_arn")
    cleaned_region = region.strip() if isinstance(region, str) and region.strip() else _default_region()

    try:
        session = boto3.session.Session(region_name=cleaned_region)
        stepfunctions = session.client("stepfunctions")
        response = stepfunctions.describe_execution(executionArn=cleaned_execution_arn)
    except (ClientError, BotoCoreError) as exc:
        raise PipelineApiError(str(exc)) from exc

    return {
        "execution_arn": response.get("executionArn"),
        "state_machine_arn": response.get("stateMachineArn"),
        "status": response.get("status"),
        "start_date": _format_datetime(response.get("startDate")),
        "stop_date": _format_datetime(response.get("stopDate")),
        "input": _try_parse_json(response.get("input")),
        "output": _try_parse_json(response.get("output")),
    }
