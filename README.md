# Podcast Anything

This repository turns source content into a podcast.
I like learning by listening, and sometimes I want a podcast on a specific topic but cannot find one quickly.
Think of this as podcast-as-a-service for learning.

Why "anything"? Future inputs can include:
- a meeting transcript (or multiple meetings)
- an image of a system design drawn on a whiteboard
- a YouTube video
- another podcast (or two, or three)
- and more

In the current stage, the system takes an article URL and generates a single-speaker podcast:
- a podcast-style script (`script.txt`)
- an audio file (`audio.mp3`)

Later stages will support additional source types for curation and multi-speaker podcast formats.

## What Is Implemented

1. Fetch article HTML and extract readable text.
2. Rewrite the article text into a podcast-style script via Bedrock.
3. Synthesize the script into MP3 via Polly (SSML + generative engine).
4. Store artifacts in S3 under `jobs/<job_id>/`.

Current orchestration:
- AWS Step Functions state machine: `fetch -> rewrite -> generate`
- Trigger helper: `scripts/start_execution.py`

## Repo Structure

- `src/podcast_anything/` Runtime package
- `src/podcast_anything/handlers/` Lambda handlers
- `src/podcast_anything/api/` API service + API Gateway Lambda handlers
- `src/podcast_anything/event_schema.py` Typed event schema and stage validation
- `scripts/start_execution.py` Helper script to start Step Functions executions
- `infra/` CDK app (Python) for AWS resources
- `infra/INFRA.md` Infra resource breakdown and architecture sketch
- `SYSTEM.md` System contracts and architecture notes

## Prerequisites

- Python 3.10+
- `uv` installed
- AWS credentials configured for CLI/boto3
- Docker running (required for CDK layer bundling)
- CDK CLI installed (`brew install aws-cdk` or `npm i -g aws-cdk`)

## Setup

Create the environment and install package + dependencies:

```bash
uv venv .venv
source .venv/bin/activate
uv sync --extra infra
```

If you are not using `uv`, use:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r infra/requirements.txt
```

Load `.env` variables into your shell:

```bash
set -a; source .env; set +a
```

## Required Environment Variables

- `MP_BUCKET`: S3 bucket name for artifacts (globally unique; CDK creates this exact bucket name)
- `BEDROCK_MODEL_ID`: Bedrock model ID (Anthropic and Nova model families supported)

Optional:
- `AWS_REGION`: defaults to `us-east-1`
- `POLLY_VOICE_ID`: defaults to `Joanna` (must support Polly generative engine in your region)

## Run The Pipeline

Before starting executions, make sure the AWS infrastructure is already deployed (`PodcastAnythingStack`), including the Step Functions state machine and S3 bucket.
If it is not deployed yet, run the steps in `Deploy Infrastructure With CDK` first.

Use the helper script (API mode by default):

```bash
python scripts/start_execution.py "https://example.com/article" "job-001" "podcast"
```

Optional flags:

```bash
python scripts/start_execution.py "https://example.com/article" "job-001" "podcast" \
  --region us-east-1 \
  --stack-name PodcastAnythingStack
```

In default mode, the script resolves `HttpApiUrl` from `PodcastAnythingStack` outputs and calls `POST /executions`.

Direct Step Functions mode is still available:

```bash
python scripts/start_execution.py "https://example.com/article" "job-001" "podcast" \
  --mode direct \
  --state-machine-arn "$PIPELINE_STATE_MACHINE_ARN"
```

You can still call the AWS CLI directly:

```bash
aws stepfunctions start-execution \
  --region "${AWS_REGION:-us-east-1}" \
  --state-machine-arn "$PIPELINE_STATE_MACHINE_ARN" \
  --input '{"job_id":"job-001","source_url":"https://example.com/article","style":"podcast"}'
```

The pipeline writes these artifacts to S3:
- `jobs/<job_id>/article.txt`
- `jobs/<job_id>/script.txt`
- `jobs/<job_id>/script.json`
- `jobs/<job_id>/audio.mp3`

Audio synthesis details:
- Handler uses SSML mode (`TextType=ssml`) with `<prosody>` and pause tags for better pacing.
- Polly engine is set to `generative`.
- Long scripts are chunked automatically before synthesis and concatenated into one MP3 output.

## API Endpoints

The CDK stack now deploys an HTTP API with these routes:

- `POST /executions`
  - Starts a new Step Functions execution.
  - Request JSON: `{"source_url":"...","job_id":"optional","style":"podcast"}`
  - Optional: `state_machine_arn` in body or query string.
- `GET /executions?execution_arn=...`
  - Returns Step Functions execution status and parsed input/output when available.

Get API URL from stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name PodcastAnythingStack \
  --query "Stacks[0].Outputs[?OutputKey=='HttpApiUrl'].OutputValue | [0]" \
  --output text
```

Example calls:

```bash
API_URL="https://<your-api-id>.execute-api.us-east-1.amazonaws.com"

curl -sS -X POST "$API_URL/executions" \
  -H "content-type: application/json" \
  -d '{"source_url":"https://en.wikipedia.org/wiki/Vision_transformer","style":"podcast"}'
```

```bash
curl -sS "$API_URL/executions?execution_arn=<execution-arn>"
```

## Run Tests

```bash
scripts/test.sh
```

Test catalog:
- `tests/TESTS.md`

## Deploy Infrastructure With CDK

```bash
cd infra
cdk bootstrap
cdk synth
cdk deploy PodcastAnythingStack
```

Stack resources:
- S3 artifacts bucket
- Lambda dependency layer (`requests`, `beautifulsoup4`)
- Lambda functions: `FetchArticleFn`, `RewriteScriptFn`, `GenerateAudioFn`
- API Lambda functions: `StartExecutionApiFn`, `GetExecutionApiFn`
- Step Functions state machine: `PipelineStateMachine`
- HTTP API Gateway routes:
  - `POST /executions`
  - `GET /executions`
- IAM policies for S3, Bedrock invoke, and Polly synthesize

## Troubleshooting

- `ModuleNotFoundError: No module named 'podcast_anything'`
  - Run `uv sync` (or `pip install -r requirements.txt`) in the active virtual environment.
- `You must specify a region`
  - Set `AWS_REGION` in `.env` and load it, or pass `--region us-east-1` to AWS CLI commands.
- `docker: Cannot connect to the Docker daemon`
  - Start Docker Desktop before running `cdk synth` or `cdk deploy` (the Lambda layer bundling uses Docker).
- Bedrock `AccessDeniedException` or model not available
  - Confirm model access is enabled for your account/region and that `BEDROCK_MODEL_ID` is valid in that region.
- S3 bucket creation fails with `BucketAlreadyExists`
  - Update `MP_BUCKET` to a globally unique name (for example include account ID + region).
- CDK warns it cannot assume bootstrap roles but proceeds
  - This is usually non-fatal if your current credentials still have deploy permissions.
- Step Functions execution fails because of input validation
  - Provide `job_id` and `source_url` for the first step. The handlers now validate stage-specific event fields.
- Polly fails with `EngineNotSupportedException` or voice errors
  - Pick a `POLLY_VOICE_ID` that supports the `generative` engine in your configured region.

## Security Note

- Keep `.env` out of version control.
- Do not commit long-lived AWS access keys.
