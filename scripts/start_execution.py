#!/usr/bin/env python3
"""Start a Podcast Anything execution.

Default mode calls the deployed HTTP API (`POST /executions`).
Optional direct mode calls Step Functions directly.
"""
from __future__ import annotations

import argparse
import json
import os
from urllib import error as urlerror
from urllib import request as urlrequest

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from podcast_anything.api.service import PipelineApiError, start_pipeline_execution


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start a Podcast Anything pipeline execution."
    )
    parser.add_argument("source_url", help="Article URL to process")
    parser.add_argument("job_id", nargs="?", default=None, help="Optional job id")
    parser.add_argument("style", nargs="?", default="podcast", help="Podcast style label")
    parser.add_argument(
        "--mode",
        choices=["api", "direct"],
        default="api",
        help="Execution mode: api (default) or direct Step Functions call",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region (default: AWS_REGION or us-east-1)",
    )
    parser.add_argument(
        "--stack-name",
        default=os.environ.get("STACK_NAME", "PodcastAnythingStack"),
        help="CloudFormation stack name used to resolve HttpApiUrl/StateMachineArn",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("PIPELINE_API_URL"),
        help="Optional API base URL (skips CloudFormation output lookup)",
    )
    parser.add_argument(
        "--state-machine-arn",
        default=os.environ.get("PIPELINE_STATE_MACHINE_ARN"),
        help="Optional explicit state machine ARN for --mode direct",
    )
    return parser.parse_args()


def _resolve_stack_output(*, region: str, stack_name: str, output_key: str) -> str:
    try:
        session = boto3.session.Session(region_name=region)
        cloudformation = session.client("cloudformation")
        response = cloudformation.describe_stacks(StackName=stack_name)
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(str(exc)) from exc

    stacks = response.get("Stacks", [])
    if not stacks:
        raise RuntimeError(f"Stack '{stack_name}' was not found.")

    outputs = stacks[0].get("Outputs", [])
    for output in outputs:
        if output.get("OutputKey") == output_key:
            value = output.get("OutputValue")
            if value:
                return value
    raise RuntimeError(
        f"Could not resolve '{output_key}' from stack '{stack_name}' in region '{region}'."
    )


def _post_execution(*, api_url: str, source_url: str, job_id: str | None, style: str) -> dict:
    payload = {"source_url": source_url, "style": style}
    if job_id:
        payload["job_id"] = job_id

    body = json.dumps(payload).encode("utf-8")
    url = f"{api_url.rstrip('/')}/executions"
    req = urlrequest.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urlrequest.urlopen(req, timeout=30) as response:
            response_text = response.read().decode("utf-8")
            if not response_text:
                return {"status_code": response.status}
            result = json.loads(response_text)
            result.setdefault("status_code", response.status)
            return result
    except urlerror.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API error ({exc.code}): {error_body}") from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f"API connection error: {exc.reason}") from exc


def main() -> None:
    args = _parse_args()

    try:
        if args.mode == "api":
            api_url = args.api_url or _resolve_stack_output(
                region=args.region,
                stack_name=args.stack_name,
                output_key="HttpApiUrl",
            )
            response = _post_execution(
                api_url=api_url,
                source_url=args.source_url,
                job_id=args.job_id,
                style=args.style,
            )
        else:
            response = start_pipeline_execution(
                source_url=args.source_url,
                job_id=args.job_id,
                style=args.style,
                region=args.region,
                stack_name=args.stack_name,
                state_machine_arn=args.state_machine_arn,
            )
    except (PipelineApiError, RuntimeError) as exc:
        raise SystemExit(f"error: {exc}") from exc

    print(json.dumps(response, default=str, indent=2))


if __name__ == "__main__":
    main()
