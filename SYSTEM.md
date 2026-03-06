Project
Podcast Anything

Goal
Build an AWS-first system for turning inputs into podcast episodes.
Current stage takes an article URL, a YouTube video URL plus transcript text, or an uploaded document (`.pdf`, `.docx`, `.txt`), rewrites it into a podcast script with an LLM (`single` or `duo` mode), and generates podcast audio with TTS.

Current Scope (Implemented)
- Input: Public article URL, YouTube video URL with caller-provided transcript/source text (`source_text`), or uploaded document bytes (`source_file_name` + `source_file_base64`) for `.pdf`, `.docx`, `.txt`
- Output: Podcast script text + MP3 audio
- Orchestration: Step Functions state machine
- Execution helper script: `scripts/start_execution.py` (API-first, direct Step Functions fallback; auto-fetches YouTube captions locally when possible; supports `--source-file`)
- API endpoints: `POST /executions` and `GET /executions`
- Not implemented yet: DynamoDB job tracking

High-Level Flow
1. Submit an event with `source_url` or uploaded document payload; the service generates `job_id` automatically.
2. Fetch and clean source text (article body), extract uploaded document text, or accept caller-provided source/transcript text.
3. Rewrite source text into podcast script text with Bedrock.
4. Generate audio from script with the configured TTS provider (Polly or ElevenLabs, with chunked synthesis).
5. Store artifacts in S3 under the job prefix.

AWS Services (Implemented)
- S3: Store normalized source text, script, metadata, and audio output
- Lambda: `fetch_article`, `rewrite_script`, `generate_audio`
- Step Functions: Orchestrates `fetch -> rewrite -> generate`
- API Gateway (HTTP API): exposes execution start and status routes
- Bedrock Runtime: LLM inference (Anthropic and Nova request formats supported)
- Polly: TTS audio generation (`generative` engine, `ssml` text type) when `TTS_PROVIDER=polly`
- ElevenLabs API: TTS audio generation (`text` input via HTTP API) when `TTS_PROVIDER=elevenlabs`
- CloudWatch: Lambda logs

API Layer
- `src/podcast_anything/api/service.py`: shared start/status operations over Step Functions
- `src/podcast_anything/api/handlers.py`: API Gateway-compatible Lambda proxy handlers

Data Contract (S3 Paths)
- `s3://<bucket>/jobs/<job_id>/source.txt`
- `s3://<bucket>/jobs/<job_id>/script.txt`
- `s3://<bucket>/jobs/<job_id>/script.json`
- `s3://<bucket>/jobs/<job_id>/audio.mp3`

Input Event Contract
{
  "job_id": "uuid-or-string",
  "source_url": "optional URL source; mutually exclusive with source_file_base64",
  "source_text": "optional raw source/transcript text for URL-based inputs only",
  "source_file_name": "required when source_file_base64 is present",
  "source_file_base64": "optional base64-encoded uploaded .pdf/.docx/.txt; mutually exclusive with source_url and source_text",
  "title": "optional title",
  "style": "podcast",
  "script_mode": "single | duo (default: single)",
  "voice_id": "HOST_A voice override",
  "voice_id_b": "HOST_B voice override (duo mode)",
  "bucket": "optional-bucket-override"
}

Script Metadata Contract (`script.json`)
{
  "job_id": "uuid-or-string",
  "source_url": "https://example.com/article",
  "title": "optional title",
  "style": "podcast",
  "script_mode": "single | duo",
  "model_id": "bedrock-model-id",
  "script_s3_key": "jobs/<job_id>/script.txt"
}

Handler Contracts
- `fetch_article`: reads `job_id` and exactly one of `source_url` or `source_file_base64`; fetches article text, extracts uploaded document text, or uses provided `source_text`; writes `source.txt`; returns `article_s3_key` and inferred `source_type`
- `rewrite_script`: reads `job_id`, `article_s3_key`; writes `script.txt` and `script.json`; returns `script_s3_key`
  - script mode:
    - `single`: single-host narrative script
    - `duo`: two-host dialogue with `HOST_A:` / `HOST_B:` line labels
- `generate_audio`: reads `job_id`, `script_s3_key`; writes `audio.mp3`; returns `audio_s3_key`
  - voice routing:
    - `single`: uses `voice_id` override or provider default voice
    - `duo`: alternates between `voice_id` (`HOST_A`) and `voice_id_b` (`HOST_B`), with provider duo defaults when overrides are absent
  - synthesis mode by provider:
    - Polly: SSML with chunking (`max_text_chars=1800`) to avoid Polly request length limits
    - ElevenLabs: plain text chunking (`max_text_chars=1800`) with provider HTTP API calls
- Event validation: shared typed schema in `src/podcast_anything/event_schema.py`

Infrastructure (CDK)
- Creates one S3 artifacts bucket named from `MP_BUCKET`
- Creates three Lambda functions and one Python dependency layer
- Creates two API Lambda functions (`StartExecutionApiFn`, `GetExecutionApiFn`)
- Creates one Step Functions state machine: `PipelineStateMachine`
- Creates one HTTP API with routes:
  - `POST /executions`
  - `GET /executions`
- Grants least-required service permissions for S3 + Bedrock + Step Functions APIs
- Adds Polly permissions only when `TTS_PROVIDER=polly`

Assumptions
- Article is publicly accessible and text-heavy, caller can provide transcript text for video inputs, or uploaded documents are text-bearing `.pdf`, `.docx`, or `.txt`
- English content first
- Script output can be `single` or `duo`; TTS supports per-turn duo voices when script lines are `HOST_A:` / `HOST_B:` labeled
- Uploaded documents are small enough to fit current API/Lambda/Step Functions request size limits; larger document uploads should move to a presigned S3 flow

Planned Next
- DynamoDB status tracking
- Presigned S3 upload flow for larger documents
- Multi-speaker output and richer audio formatting
