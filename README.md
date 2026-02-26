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

In the current stage, the system takes a public article URL or a YouTube video URL plus transcript text and generates a single-speaker podcast:
- a podcast-style script (`script.txt`)
- an audio file (`audio.mp3`)

Later stages will support additional source types for curation and multi-speaker podcast formats.

## What Is Implemented

1. Fetch source text from an article page, or accept caller-provided transcript/source text.
2. Rewrite the source text into a podcast-style script via Bedrock.
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
- `src/podcast_anything/youtube.py` YouTube URL parsing + local transcript fetch helpers
- `scripts/start_execution.py` Helper script to start Step Functions executions
- `scripts/fetch_youtube_transcript.py` Local helper to fetch YouTube transcripts into `.txt`
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

The helper script uses the HTTP API by default (`POST /executions`).

Article example:

```bash
python scripts/start_execution.py "https://example.com/article"
```

### YouTube Input (URL Only From User)

AWS-side YouTube transcript fetching is intentionally disabled.
When you pass a YouTube URL to `scripts/start_execution.py`, the script tries to fetch captions locally on your machine first, then sends the transcript text to AWS.

YouTube example (automatic local caption fetch):

```bash
python scripts/start_execution.py "https://www.youtube.com/watch?v=7eNey0TN2pw"
```

If local caption fetch fails (for example captions are unavailable or restricted), use a local transcript file:

1. Fetch captions locally on your machine.
2. Save/export as plain text (`.txt`).
3. Pass that file with `--transcript-file`.

Optional helper (uses `youtube_transcript_api` on your machine):

```bash
python scripts/fetch_youtube_transcript.py "https://www.youtube.com/watch?v=7eNey0TN2pw"
```

This writes a file like `youtube-7eNey0TN2pw-transcript.txt`.

Run the pipeline using the local transcript:

```bash
python scripts/start_execution.py "https://www.youtube.com/watch?v=7eNey0TN2pw" \
  --transcript-file ./my_transcript.txt
```

You can also use `yt-dlp` locally if it works better in your environment, then pass the resulting text file.

The pipeline writes these artifacts to S3:
- `jobs/<job_id>/source.txt`
- `jobs/<job_id>/script.txt`
- `jobs/<job_id>/script.json`
- `jobs/<job_id>/audio.mp3`

`source.txt` stores normalized source text for both article and YouTube transcript inputs.

Audio synthesis details:
- Handler uses SSML mode (`TextType=ssml`) with `<prosody>` and pause tags for better pacing.
- Polly engine is set to `generative`.
- Long scripts are chunked automatically before synthesis and concatenated into one MP3 output.

## API Endpoints

The CDK stack now deploys an HTTP API with these routes:

- `POST /executions`
  - Starts a Step Functions execution
  - Body fields:
    - `source_url` (required): public article URL or YouTube video URL
    - `style` (optional, default `podcast`)
    - `source_text` or `transcript_text` (required for YouTube URLs; optional for other sources)
    - `state_machine_arn` (optional override)
- `GET /executions?execution_arn=...`
  - Returns execution status and parsed input/output (when available)

Get API URL from stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name PodcastAnythingStack \
  --query "Stacks[0].Outputs[?OutputKey=='HttpApiUrl'].OutputValue | [0]" \
  --output text
```

Examples:

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
- YouTube execution start fails with transcript-related validation
  - AWS-side YouTube transcript fetch is disabled.
  - Provide transcript text via API (`transcript_text` / `source_text`) or use `scripts/start_execution.py --transcript-file ...`.
- S3 bucket creation fails with `BucketAlreadyExists`
  - Update `MP_BUCKET` to a globally unique name (for example include account ID + region).
- CDK warns it cannot assume bootstrap roles but proceeds
  - This is usually non-fatal if your current credentials still have deploy permissions.
- Step Functions execution fails because of input validation
  - Provide `source_url` for API start requests.
- Polly fails with `EngineNotSupportedException` or voice errors
  - Pick a `POLLY_VOICE_ID` that supports the `generative` engine in your configured region.

## Security Note

- Keep `.env` out of version control.
- Do not commit long-lived AWS access keys.
