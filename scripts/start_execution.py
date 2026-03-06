#!/usr/bin/env python3
"""Start a Podcast Anything execution.

Default mode calls the deployed HTTP API (`POST /executions`).
Optional direct mode calls Step Functions directly.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from podcast_anything.api.service import PipelineApiError, start_pipeline_execution
from podcast_anything.youtube import YouTubeTranscriptError, fetch_transcript_text, is_youtube_url


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a Podcast Anything pipeline execution.")
    parser.add_argument(
        "source",
        nargs="?",
        help="Source URL to process (article or YouTube)",
    )
    parser.add_argument(
        "--source-file",
        default=None,
        help="Optional local source document to upload (.pdf, .docx, .txt)",
    )
    parser.add_argument(
        "--style",
        default="podcast",
        help="Podcast style label (default: podcast)",
    )
    parser.add_argument(
        "--script-mode",
        choices=["single", "duo"],
        default="single",
        help="Script format mode: single host or two-host dialogue (default: single)",
    )
    parser.add_argument(
        "--voice-id",
        default=None,
        help="Optional voice override for single mode or HOST_A in duo mode",
    )
    parser.add_argument(
        "--voice-id-b",
        default=None,
        help="Optional second voice override for HOST_B in duo mode",
    )
    parser.add_argument(
        "--transcript-file",
        default=None,
        help="Optional path to transcript text file (overrides automatic local caption fetch)",
    )
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


def _read_transcript_file(path: str | None) -> str | None:
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as file_obj:
        text = file_obj.read().strip()
    if not text:
        raise RuntimeError(f"Transcript file is empty: {path}")
    return text


def _read_source_file_payload(path: str | None) -> tuple[str, str] | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        raise RuntimeError(f"Source file was not found: {path}")
    file_bytes = file_path.read_bytes()
    if not file_bytes:
        raise RuntimeError(f"Source file is empty: {path}")
    encoded = base64.b64encode(file_bytes).decode("ascii")
    return file_path.name, encoded


def _resolve_source_input(
    *,
    source: str | None,
    source_file: str | None,
) -> tuple[str | None, tuple[str, str] | None]:
    if bool(source) == bool(source_file):
        raise RuntimeError("Provide exactly one of a source URL or --source-file <path>.")
    if source_file:
        return None, _read_source_file_payload(source_file)
    return source, None


def _resolve_source_text(*, source_url: str | None, transcript_file: str | None) -> str | None:
    if not source_url:
        return None

    file_text = _read_transcript_file(transcript_file)
    if file_text is not None:
        return file_text

    if not is_youtube_url(source_url):
        return None

    print("Fetching YouTube captions locally...", file=sys.stderr)
    try:
        transcript_text = fetch_transcript_text(source_url)
    except YouTubeTranscriptError as exc:
        raise RuntimeError(
            "Could not fetch YouTube captions locally. The video may not have captions, "
            "captions may be disabled/restricted, or YouTube may be rate-limiting/blocking "
            "your network. Retry later or provide a local transcript with "
            "`--transcript-file <path>`.\n"
            f"Details: {exc}"
        ) from exc

    print(f"Fetched YouTube captions locally ({len(transcript_text)} chars).", file=sys.stderr)
    return transcript_text


def _post_execution(
    *,
    api_url: str,
    source_url: str | None,
    source_file_name: str | None,
    source_file_base64: str | None,
    job_id: str | None,
    style: str,
    script_mode: str,
    voice_id: str | None,
    voice_id_b: str | None,
    source_text: str | None,
) -> dict:
    payload = {"style": style, "script_mode": script_mode}
    if source_url:
        payload["source_url"] = source_url
    if source_file_name:
        payload["source_file_name"] = source_file_name
    if source_file_base64:
        payload["source_file_base64"] = source_file_base64
    if job_id:
        payload["job_id"] = job_id
    if voice_id:
        payload["voice_id"] = voice_id
    if voice_id_b:
        payload["voice_id_b"] = voice_id_b
    if source_text:
        payload["source_text"] = source_text

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
        source_url, source_file_payload = _resolve_source_input(
            source=args.source,
            source_file=args.source_file,
        )
        if source_file_payload and args.transcript_file:
            raise RuntimeError("--transcript-file can only be used with a source URL.")
        source_text = _resolve_source_text(
            source_url=source_url,
            transcript_file=args.transcript_file,
        )
        source_file_name = source_file_payload[0] if source_file_payload else None
        source_file_base64 = source_file_payload[1] if source_file_payload else None
        if args.mode == "api":
            api_url = args.api_url or _resolve_stack_output(
                region=args.region,
                stack_name=args.stack_name,
                output_key="HttpApiUrl",
            )
            response = _post_execution(
                api_url=api_url,
                source_url=source_url,
                source_file_name=source_file_name,
                source_file_base64=source_file_base64,
                job_id=None,
                style=args.style,
                script_mode=args.script_mode,
                voice_id=args.voice_id,
                voice_id_b=args.voice_id_b,
                source_text=source_text,
            )
        else:
            response = start_pipeline_execution(
                source_url=source_url,
                source_text=source_text,
                source_file_name=source_file_name,
                source_file_base64=source_file_base64,
                job_id=None,
                style=args.style,
                script_mode=args.script_mode,
                voice_id=args.voice_id,
                voice_id_b=args.voice_id_b,
                region=args.region,
                stack_name=args.stack_name,
                state_machine_arn=args.state_machine_arn,
            )
    except (PipelineApiError, RuntimeError) as exc:
        raise SystemExit(f"error: {exc}") from exc

    print(json.dumps(response, default=str, indent=2))


if __name__ == "__main__":
    main()
