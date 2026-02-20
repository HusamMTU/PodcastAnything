Project
Podcast Anything

Goal
Build an AWS-first system for turning inputs into podcast episodes.
Current stage takes an article URL, rewrites it into a podcast-style script with an LLM, and generates podcast audio with TTS.

Current Scope (Implemented)
- Input: Public article URL
- Output: Podcast script text + MP3 audio
- Orchestration: Local runner (`scripts/run_local_pipeline.py`) and Step Functions state machine
- Execution helper script: `scripts/start_execution.sh` for starting Step Functions runs
- Not implemented yet: DynamoDB job tracking

High-Level Flow
1. Submit an event with `job_id` and `source_url`.
2. Fetch and clean article text.
3. Rewrite article text into podcast script text with Bedrock.
4. Generate audio from script with Polly (SSML + generative engine, with chunked synthesis).
5. Store artifacts in S3 under the job prefix.

AWS Services (Implemented)
- S3: Store article text, script, metadata, and audio output
- Lambda: `fetch_article`, `rewrite_script`, `generate_audio`
- Step Functions: Orchestrates `fetch -> rewrite -> generate`
- Bedrock Runtime: LLM inference (Anthropic and Nova request formats supported)
- Polly: TTS audio generation (`generative` engine, `ssml` text type)
- CloudWatch: Lambda logs

Data Contract (S3 Paths)
- `s3://<bucket>/jobs/<job_id>/article.txt`
- `s3://<bucket>/jobs/<job_id>/script.txt`
- `s3://<bucket>/jobs/<job_id>/script.json`
- `s3://<bucket>/jobs/<job_id>/audio.mp3`

Input Event Contract
{
  "job_id": "uuid-or-string",
  "source_url": "https://example.com/article",
  "title": "optional title",
  "style": "podcast",
  "voice_id": "Joanna",
  "bucket": "optional-bucket-override"
}

Script Metadata Contract (`script.json`)
{
  "job_id": "uuid-or-string",
  "source_url": "https://example.com/article",
  "title": "optional title",
  "style": "podcast",
  "model_id": "bedrock-model-id",
  "script_s3_key": "jobs/<job_id>/script.txt"
}

Handler Contracts
- `fetch_article`: reads `job_id`, `source_url`; writes `article.txt`; returns `article_s3_key`
- `rewrite_script`: reads `job_id`, `article_s3_key`; writes `script.txt` and `script.json`; returns `script_s3_key`
- `generate_audio`: reads `job_id`, `script_s3_key`; writes `audio.mp3`; returns `audio_s3_key`
  - synthesis mode: SSML with chunking (`max_text_chars=1800`) to avoid Polly request length limits
- Event validation: shared typed schema in `src/ml_publication/event_schema.py`

Infrastructure (CDK)
- Creates one S3 artifacts bucket named from `MP_BUCKET`
- Creates three Lambda functions and one Python dependency layer
- Creates one Step Functions state machine: `PipelineStateMachine`
- Grants least-required service permissions for S3 + Bedrock + Polly

Assumptions
- Article is publicly accessible and text-heavy
- English content first
- Single voice TTS in current phase

Planned Next
- DynamoDB status tracking
- Additional source types beyond article links
- Multi-speaker output and richer audio formatting
