# ML Publication Pipeline

Minimal ML engineering pipeline that turns a public article URL into:
- a podcast-style script (`script.txt`)
- an audio file (`audio.mp3`)

The implementation is AWS-backed and intentionally simple for learning.

## What Is Implemented

1. Fetch article HTML and extract readable text.
2. Rewrite article text into podcast-style script via Bedrock.
3. Synthesize script into MP3 via Polly.
4. Store artifacts in S3 under `jobs/<job_id>/`.

Current orchestration:
- Local script: `scripts/run_local_pipeline.py`
- AWS components: Lambda functions are deployed, but no Step Functions state machine yet.

## Repo Structure

- `src/ml_publication/` Runtime package
- `src/ml_publication/handlers/` Lambda handlers
- `scripts/run_local_pipeline.py` Local runner that chains all handlers
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
- `POLLY_VOICE_ID`: defaults to `Joanna`

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

## Run Tests

```bash
scripts/test.sh
```

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
- IAM policies for S3, Bedrock invoke, and Polly synthesize

## Troubleshooting

- `ModuleNotFoundError: No module named 'ml_publication'`
  - Run `uv sync` (or `pip install -r requirements.txt`) in the active virtual environment.
- `docker: Cannot connect to the Docker daemon`
  - Start Docker Desktop before running `cdk synth` or `cdk deploy` (the Lambda layer bundling uses Docker).
- Bedrock `AccessDeniedException` or model not available
  - Confirm model access is enabled for your account/region and that `BEDROCK_MODEL_ID` is valid in that region.
- S3 bucket creation fails with `BucketAlreadyExists`
  - Update `MP_BUCKET` to a globally unique name (for example include account ID + region).
- CDK warns it cannot assume bootstrap roles but proceeds
  - This is usually non-fatal if your current credentials still have deploy permissions.

## Security Note

- Keep `.env` out of version control.
- Do not commit long-lived AWS access keys.
