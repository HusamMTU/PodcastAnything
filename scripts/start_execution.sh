#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "usage: scripts/start_execution.sh <source_url> [job_id] [style]"
  exit 1
fi

SOURCE_URL="$1"
JOB_ID="${2:-job-$(date +%s)}"
STYLE="${3:-podcast}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-MlPublicationPipeline}"
STATE_MACHINE_ARN="${PIPELINE_STATE_MACHINE_ARN:-}"

if [[ -z "$STATE_MACHINE_ARN" ]]; then
  STATE_MACHINE_ARN="$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='PipelineStateMachineArn'].OutputValue | [0]" \
    --output text)"
fi

if [[ -z "$STATE_MACHINE_ARN" || "$STATE_MACHINE_ARN" == "None" ]]; then
  echo "error: could not resolve PipelineStateMachineArn from stack '$STACK_NAME' in region '$REGION'"
  exit 1
fi

INPUT_JSON="$(printf '{"job_id":"%s","source_url":"%s","style":"%s"}' "$JOB_ID" "$SOURCE_URL" "$STYLE")"

aws stepfunctions start-execution \
  --region "$REGION" \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --input "$INPUT_JSON"
