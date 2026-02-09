# ML Publication Pipeline

This project is a learning-focused ML engineering pipeline that takes a public Article URL, rewrites it into a podcast-style script with an LLM, and generates audio via TTS. The current scope is a simple, end-to-end batch flow using AWS services.

**Current Scope**
- Input: Public Article URL
- Output: Podcast script (`script.txt`) + MP3 audio (`audio.mp3`)
- Focus: Clean, minimal pipeline that is easy to understand and extend

**High-Level Flow**
1. Fetch and extract article text.
2. Rewrite into podcast-style script (LLM).
3. Generate audio (TTS).
4. Store artifacts in S3.

**AWS Services (Phase 1)**
- S3: Store article text, script, and audio
- Lambda: 3 handlers for fetch, rewrite, and TTS
- Bedrock: LLM for podcast rewrite
- Polly: TTS for audio

## Project Structure

- `src/ml_publication/` Core Python package
- `src/ml_publication/handlers/` Lambda handlers
- `scripts/` Local runner scripts
- `infra/` AWS CDK (Python) app for infrastructure
- `SYSTEM.md` System spec and data contracts

## Key Files

- `SYSTEM.md` System spec and Phase 1 data contract
- `scripts/run_local_pipeline.py` Local runner (calls handlers in order)
- `src/ml_publication/article.py` Fetch + extract article text
- `src/ml_publication/llm.py` Bedrock prompt + call (Anthropic format)
- `src/ml_publication/tts.py` Polly TTS helper
- `infra/ml_publication_infra/stack.py` CDK stack (S3 + Lambdas + IAM)

## Setup (Local Runner or Infra Deploy)

Prereqs:
- Python 3.10+
- AWS credentials available to the AWS CLI and boto3
- Docker running (required for CDK layer bundling)
- CDK CLI installed (`brew install aws-cdk` or `npm i -g aws-cdk`)

Create and activate a virtual environment, then install deps:
```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Load environment variables from `.env` into your shell:
```bash
set -a; source .env; set +a
```

## Run Locally

The local runner uses the same handlers as Lambda but runs locally. It still calls AWS services (S3, Bedrock, Polly), so your AWS credentials and env vars must be set.

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

## Environment Variables

Required:
- `MP_BUCKET` S3 bucket name for artifacts (must be globally unique; CDK will create this bucket)
- `BEDROCK_MODEL_ID` Bedrock model ID (Anthropic or Nova supported)

Common:
- `AWS_REGION` Defaults to `us-east-1` if not set
- `POLLY_VOICE_ID` Defaults to `Joanna`

Security note:
- Keep `.env` out of git. Do not commit AWS credentials.

## Infrastructure (CDK)

The CDK app lives in `infra/` and creates:
- An S3 bucket for artifacts
- Three Lambda functions
- IAM permissions for S3, Bedrock, and Polly

Install CDK dependencies:
```bash
uv pip install -r infra/requirements.txt
```

From `infra/`:
```bash
cdk bootstrap
cdk synth
cdk deploy
```

Note:
- CDK expects `BEDROCK_MODEL_ID` to be set in the environment at synth time.
- Lambda dependencies are provided via a layer built during synth; Docker is required for bundling.
