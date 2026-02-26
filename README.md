# Podcast Anything

Turn source content into a podcast-ready script and audio file.

Current stage supports:
- public article URLs
- YouTube URLs (captions fetched locally by the CLI, then sent to AWS)

The pipeline rewrites source content into a single-speaker podcast script with Bedrock, then generates audio with Amazon Polly.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [YouTube Flow](#youtube-flow)
- [API Endpoints](#api-endpoints)
- [Development](#development)
- [Testing](#testing)
- [Infrastructure (CDK)](#infrastructure-cdk)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)

## Overview

This repo is an AWS-first pipeline for turning source material into a podcast.

Current output:
- `script.txt` (podcast-style script)
- `audio.mp3` (single-speaker podcast audio)

Future inputs can include:
- meeting transcripts
- images/whiteboard sketches
- other podcasts
- multi-source curation inputs

## Features

- Step Functions orchestration: `fetch -> rewrite -> generate`
- Lambda handlers for source fetch, script rewrite, and audio generation
- API Gateway HTTP API to start executions and query status
- API-first local CLI (`scripts/start_execution.py`)
- YouTube URL support without AWS-side caption scraping
  - CLI fetches captions locally when possible
  - backend receives transcript text
- Polly SSML + `generative` engine with chunked synthesis
- CDK (Python) infrastructure
- Unit tests + GitHub Actions CI + Ruff linting

## Architecture

High-level flow:

1. Start execution via `scripts/start_execution.py` or `POST /executions`.
2. Fetch normalized source text and store it in S3 as `source.txt`.
3. Rewrite source text into a podcast script with Bedrock.
4. Generate audio with Polly and store `audio.mp3`.
5. Query execution status with `GET /executions`.

Core AWS services:
- S3
- Lambda
- Step Functions
- API Gateway (HTTP API)
- Bedrock Runtime
- Polly

```mermaid
flowchart LR
  subgraph CLIENT[Client Side]
    U[User]
    SE[scripts/start_execution.py]
    CC[Local caption fetch\n(YouTube only, in CLI)]
    U --> SE
    SE -->|YouTube URL| CC
  end

  subgraph API[HTTP API]
    APIGW[API Gateway HTTP API]
    POSTX[POST /executions]
    GETX[GET /executions]
    SAE[Lambda: StartExecutionApiFn]
    GES[Lambda: GetExecutionApiFn]
    APIGW --> POSTX --> SAE
    APIGW --> GETX --> GES
  end

  SE -->|Article URL| APIGW
  CC -->|source_url + transcript_text| APIGW
  U -->|status request| APIGW
  APIGW -->|status response| U

  SAE --> SFN[Step Functions\nPipelineStateMachine]
  GES -->|DescribeExecution| SFN
  SFN -->|execution status| GES

  subgraph PIPE[State Machine Execution Order]
    F[FetchArticleStep\nLambda: FetchArticleFn\n(fetch article or persist provided transcript)]
    R[RewriteScriptStep\nLambda: RewriteScriptFn]
    G[GenerateAudioStep\nLambda: GenerateAudioFn]
    F -->|event + article_s3_key| R
    R -->|event + script_s3_key| G
  end

  SFN -->|invokes first step| F
  F -->|write source.txt| S3[(S3 ArtifactsBucket)]
  S3 -->|read source.txt| R
  R -->|write script.txt + script.json| S3
  R -->|InvokeModel| BR[Bedrock Runtime]
  S3 -->|read script.txt| G
  G -->|write audio.mp3| S3
  G -->|SynthesizeSpeech| P[Amazon Polly]
```

More details:
- `SYSTEM.md`
- `infra/INFRA.md`

## Quick Start

### Prerequisites

- Python 3.10+
- `uv`
- AWS credentials configured for CLI/boto3
- Docker running (for CDK Lambda layer bundling)
- CDK CLI (`brew install aws-cdk` or `npm i -g aws-cdk`)

### Setup

```bash
uv venv .venv
source .venv/bin/activate
uv sync --extra infra
```

If not using `uv`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r infra/requirements.txt
```

Load environment variables:

```bash
set -a; source .env; set +a
```

### Required Environment Variables

- `MP_BUCKET`: S3 bucket for artifacts (must be globally unique)
- `BEDROCK_MODEL_ID`: Bedrock model ID (Nova or Anthropic family supported)

Optional:
- `AWS_REGION` (default `us-east-1`)
- `POLLY_VOICE_ID` (default `Joanna`, must support Polly `generative` engine in your region)

### Deploy Infrastructure

```bash
cd infra
cdk bootstrap
cdk synth
cdk deploy PodcastAnythingStack
```

### Run One Pipeline Execution

Article URL:

```bash
python scripts/start_execution.py "https://example.com/article"
```

The CLI uses the deployed HTTP API (`POST /executions`) by default.

## YouTube Flow

AWS-side YouTube caption fetching is intentionally disabled.

For a YouTube URL, `scripts/start_execution.py` will:
- try to fetch captions locally on your machine
- send transcript text to the API/backend
- start the Step Functions execution

URL-only example:

```bash
python scripts/start_execution.py "https://www.youtube.com/watch?v=7eNey0TN2pw"
```

If local caption fetch fails (captions unavailable/restricted or local network blocked), use a transcript file:

```bash
python scripts/start_execution.py "https://www.youtube.com/watch?v=7eNey0TN2pw" \
  --transcript-file ./my_transcript.txt
```

Optional helper to fetch/save captions locally:

```bash
python scripts/fetch_youtube_transcript.py "https://www.youtube.com/watch?v=7eNey0TN2pw"
```

You can also use `yt-dlp` locally and pass the resulting plain-text transcript with `--transcript-file`.

## API Endpoints

The stack deploys an HTTP API with:
- `POST /executions`
- `GET /executions?execution_arn=...`

### `POST /executions`

Starts a Step Functions execution.

Body fields:
- `source_url` (required): article URL or YouTube URL
- `style` (optional, default `podcast`)
- `source_text` or `transcript_text` (required for YouTube URLs; optional for other sources)
- `state_machine_arn` (optional override)

### `GET /executions`

Returns execution status and parsed input/output (when available).

### Resolve API URL

```bash
aws cloudformation describe-stacks \
  --stack-name PodcastAnythingStack \
  --query "Stacks[0].Outputs[?OutputKey=='HttpApiUrl'].OutputValue | [0]" \
  --output text
```

### API Examples

```bash
API_URL="https://<your-api-id>.execute-api.us-east-1.amazonaws.com"

curl -sS -X POST "$API_URL/executions" \
  -H "content-type: application/json" \
  -d '{"source_url":"https://en.wikipedia.org/wiki/Vision_transformer","style":"podcast"}'
```

```bash
curl -sS -X POST "$API_URL/executions" \
  -H "content-type: application/json" \
  -d '{"source_url":"https://www.youtube.com/watch?v=7eNey0TN2pw","transcript_text":"<paste transcript here>","style":"podcast"}'
```

```bash
curl -sS "$API_URL/executions?execution_arn=<execution-arn>"
```

## Development

### Repo Structure

- `src/podcast_anything/` runtime package
- `src/podcast_anything/handlers/` Lambda handlers
- `src/podcast_anything/api/` API service + API Gateway Lambda handlers
- `src/podcast_anything/event_schema.py` typed pipeline event schema
- `src/podcast_anything/youtube.py` YouTube URL parsing + local transcript helpers
- `scripts/start_execution.py` local execution launcher (API-first)
- `scripts/fetch_youtube_transcript.py` optional local transcript helper
- `infra/` CDK app (Python)
- `infra/INFRA.md` infra breakdown + architecture sketch
- `SYSTEM.md` system contracts / architecture notes

### Artifacts (S3)

The pipeline stores artifacts under `jobs/<job_id>/`:
- `jobs/<job_id>/source.txt`
- `jobs/<job_id>/script.txt`
- `jobs/<job_id>/script.json`
- `jobs/<job_id>/audio.mp3`

`source.txt` stores normalized source text for both article and YouTube transcript inputs.

### Audio Generation Notes

- Polly engine: `generative`
- Polly text type: `ssml`
- Long scripts are chunked before synthesis and concatenated into one MP3

## Testing

Run the test suite:

```bash
scripts/test.sh
```

Test inventory:
- `tests/TESTS.md`

CI:
- GitHub Actions runs tests + CDK synth on PRs and pushes to `main`
- Ruff runs in CI for lint checks

## Infrastructure (CDK)

Stack name:
- `PodcastAnythingStack`

Primary resources:
- S3 artifacts bucket
- Lambda dependency layer (`requests`, `beautifulsoup4`)
- Lambda functions: `FetchArticleFn`, `RewriteScriptFn`, `GenerateAudioFn`
- API Lambda functions: `StartExecutionApiFn`, `GetExecutionApiFn`
- Step Functions state machine: `PipelineStateMachine`
- HTTP API Gateway routes: `POST /executions`, `GET /executions`
- IAM policies for S3, Bedrock, Polly, and Step Functions status/start calls

Useful commands:

```bash
cd infra
cdk synth PodcastAnythingStack
cdk deploy PodcastAnythingStack
cdk destroy PodcastAnythingStack
```

See `infra/INFRA.md` for details and the architecture sketch.

## Troubleshooting

- `ModuleNotFoundError: No module named 'podcast_anything'`
  - Run `uv sync` (or `pip install -r requirements.txt`) in the active virtual environment.
- `You must specify a region`
  - Set `AWS_REGION` in `.env` and load it, or pass `--region us-east-1` to AWS CLI commands.
- `docker: Cannot connect to the Docker daemon`
  - Start Docker Desktop before `cdk synth` / `cdk deploy` (Lambda layer bundling uses Docker).
- Bedrock `AccessDeniedException` or model not available
  - Confirm model access is enabled for your account/region and `BEDROCK_MODEL_ID` is valid in that region.
- YouTube execution start fails with transcript-related validation
  - The backend requires transcript text for YouTube URLs.
  - Use `scripts/start_execution.py` (it auto-fetches locally) or pass `transcript_text` / `source_text` directly to the API.
- Local YouTube caption fetch fails in `scripts/start_execution.py`
  - The video may not have captions, captions may be restricted, or YouTube may be rate-limiting/blocking your network.
  - Retry later or use `--transcript-file`.
- S3 bucket creation fails with `BucketAlreadyExists`
  - Update `MP_BUCKET` to a globally unique name (for example include account ID + region).
- CDK warns it cannot assume bootstrap roles but proceeds
  - Usually non-fatal if your current credentials still have deploy permissions.
- Polly fails with `EngineNotSupportedException` or voice errors
  - Pick a `POLLY_VOICE_ID` that supports Polly `generative` engine in the configured region.

## Security Notes

- Keep `.env` out of version control.
- Do not commit long-lived AWS access keys.
