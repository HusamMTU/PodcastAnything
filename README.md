# Podcast Anything

This repository is for turning anything into a podcast.
Current stage supports an article link as input and generates a single-person style podcast:
- a podcast-style script (`script.txt`)
- an audio file (`audio.mp3`)

Later stages will support additional source types for curation and multi-speaker podcast formats.

## What Is Implemented

1. Fetch article HTML and extract readable text.
2. Rewrite article text into podcast-style script via Bedrock.
3. Synthesize script into MP3 via Polly using SSML + generative engine.
4. Store artifacts in S3 under `jobs/<job_id>/`.

Current orchestration:
- Local script: `scripts/run_local_pipeline.py`
- AWS Step Functions state machine: `fetch -> rewrite -> generate`

## Repo Structure

- `src/podcast_anything/` Runtime package
- `src/podcast_anything/handlers/` Lambda handlers
- `src/podcast_anything/event_schema.py` Typed event schema and stage validation
- `scripts/run_local_pipeline.py` Local runner that chains all handlers
- `scripts/start_execution.sh` Helper to start Step Functions executions
- `infra/` CDK app (Python) for AWS resources
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
uv sync
uv pip install -r infra/requirements.txt
```

If you are not using `uv`, use:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r infra/requirements.txt
```

Load `.env` into your shell:

```bash
set -a; source .env; set +a
```

## Required Environment Variables

- `MP_BUCKET`: S3 bucket name for artifacts (globally unique; CDK creates this exact bucket name)
- `BEDROCK_MODEL_ID`: Bedrock model ID (Anthropic and Nova model families supported)

Optional:
- `AWS_REGION`: defaults to `us-east-1`
- `POLLY_VOICE_ID`: defaults to `Joanna` (must support Polly generative engine in your region)

## Run The Pipeline Locally

```bash
python scripts/run_local_pipeline.py "https://example.com/article"
```

Optional flags:

```bash
python scripts/run_local_pipeline.py "https://example.com/article" \
  --title "My Article" \
  --style podcast \
  --bucket my-bucket \
  --voice-id Joanna
```

Artifacts are written to S3:
- `jobs/<job_id>/article.txt`
- `jobs/<job_id>/script.txt`
- `jobs/<job_id>/script.json`
- `jobs/<job_id>/audio.mp3`

Audio synthesis details:
- Handler uses SSML mode (`TextType=ssml`) with `<prosody>` and pause tags for better pacing.
- Polly engine is set to `generative`.
- Long scripts are chunked automatically before synthesis and concatenated into one MP3 output.

## Run The Pipeline With Step Functions

Recommended helper:

```bash
scripts/start_execution.sh "https://example.com/article" "job-001" "podcast"
```

The script at `scripts/start_execution.sh` resolves `PipelineStateMachineArn` from the `PodcastAnythingStack` stack by default.

You can still call the AWS CLI directly:

```bash
aws stepfunctions start-execution \
  --region "${AWS_REGION:-us-east-1}" \
  --state-machine-arn "$PIPELINE_STATE_MACHINE_ARN" \
  --input '{"job_id":"job-001","source_url":"https://example.com/article","style":"podcast"}'
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
cdk deploy
```

Stack resources:
- S3 artifacts bucket
- Lambda dependency layer (`requests`, `beautifulsoup4`)
- Lambda functions: `FetchArticleFn`, `RewriteScriptFn`, `GenerateAudioFn`
- Step Functions state machine: `PipelineStateMachine`
- IAM policies for S3, Bedrock invoke, and Polly synthesize

## Troubleshooting

- `ModuleNotFoundError: No module named 'podcast_anything'`
  - Run `uv sync` (or `pip install -r requirements.txt`) in the active virtual environment.
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
