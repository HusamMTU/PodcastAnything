#!/usr/bin/env python3
"""Start a Podcast Anything Step Functions execution."""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start a Step Functions execution for Podcast Anything."
    )
    parser.add_argument("source_url", help="Article URL to process")
    parser.add_argument("job_id", nargs="?", default=None, help="Optional job id")
    parser.add_argument("style", nargs="?", default="podcast", help="Podcast style label")
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region (default: AWS_REGION or us-east-1)",
    )
    parser.add_argument(
        "--stack-name",
        default=os.environ.get("STACK_NAME", "PodcastAnythingStack"),
        help="CloudFormation stack name used to resolve the state machine ARN",
    )
    parser.add_argument(
        "--state-machine-arn",
        default=os.environ.get("PIPELINE_STATE_MACHINE_ARN"),
        help="Optional explicit state machine ARN (skips stack output lookup)",
    )
    return parser.parse_args()


def _resolve_state_machine_arn(
    *,
    cloudformation: Any,
    stack_name: str,
) -> str:
    response = cloudformation.describe_stacks(StackName=stack_name)
    stacks = response.get("Stacks", [])
    if not stacks:
        raise RuntimeError(f"Stack '{stack_name}' was not found.")

    outputs = stacks[0].get("Outputs", [])
    for output in outputs:
        if output.get("OutputKey") == "PipelineStateMachineArn":
            arn = output.get("OutputValue")
            if arn:
                return arn
    raise RuntimeError(
        f"Could not resolve PipelineStateMachineArn from stack '{stack_name}'."
    )


def main() -> None:
    args = _parse_args()
    job_id = args.job_id or f"job-{int(time.time())}"

    try:
        session = boto3.session.Session(region_name=args.region)
        state_machine_arn = args.state_machine_arn
        if not state_machine_arn:
            cloudformation = session.client("cloudformation")
            state_machine_arn = _resolve_state_machine_arn(
                cloudformation=cloudformation,
                stack_name=args.stack_name,
            )

        payload = {
            "job_id": job_id,
            "source_url": args.source_url,
            "style": args.style,
        }

        stepfunctions = session.client("stepfunctions")
        response = stepfunctions.start_execution(
            stateMachineArn=state_machine_arn,
            input=json.dumps(payload),
        )
    except (ClientError, BotoCoreError, RuntimeError) as exc:
        raise SystemExit(f"error: {exc}") from exc

    print(json.dumps(response, default=str, indent=2))


if __name__ == "__main__":
    main()
