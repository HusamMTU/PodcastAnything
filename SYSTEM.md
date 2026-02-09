Goal
Build a minimal, AWS-first pipeline that takes an Article URL, rewrites it into a podcast-style script with an LLM, and generates podcast audio with TTS.

Scope (Phase 1)
- Input: Public Article URL
- Output: Podcast script (text) + MP3 audio
- No meeting capture, no transcription

High-Level Flow
1. Submit an Article URL to the pipeline.
2. Fetch and clean the article text.
3. Generate a podcast-style script with an LLM.
4. Generate audio from the script via TTS.
5. Store artifacts in S3 and metadata in DynamoDB.

AWS Services (Phase 1)
- S3: raw article text, script, audio output
- Lambda: fetch + clean article, LLM call, TTS call
- Step Functions: orchestration and retries
- Bedrock: LLM for podcast rewrite
- Polly: TTS audio generation
- DynamoDB: job status + metadata
- CloudWatch: logs and metrics

Data Contract (S3 Paths)
- s3://<bucket>/jobs/<job_id>/input.json
- s3://<bucket>/jobs/<job_id>/article.txt
- s3://<bucket>/jobs/<job_id>/script.json
- s3://<bucket>/jobs/<job_id>/script.txt
- s3://<bucket>/jobs/<job_id>/audio.mp3
- s3://<bucket>/jobs/<job_id>/status.json

Input Schema (input.json)
{
  "job_id": "uuid",
  "source_url": "https://example.com/article",
  "title": "optional",
  "language": "en",
  "voice_id": "Joanna",
  "style": "podcast"
}

Script Schema (script.json)
{
  "job_id": "uuid",
  "title": "string",
  "summary": "string",
  "segments": [
    {
      "speaker": "HOST",
      "text": "string"
    }
  ],
  "estimated_duration_sec": 420
}

Pipeline Steps (Step Functions)
- FetchArticle: Lambda fetches and cleans article text
- RewriteScript: Lambda calls Bedrock to create podcast script
- GenerateAudio: Lambda calls Polly, saves MP3
- PersistStatus: Lambda writes status.json + DynamoDB

Assumptions
- Article is publicly accessible and mostly text-based
- English content is first target
- Single voice TTS for Phase 1

Success Criteria (Phase 1)
- Given a URL, produce a clean script and MP3 in S3
- Job status tracked in DynamoDB
- End-to-end run completes within 3-5 minutes for typical articles

Future Phases
- Add YouTube URL ingest with audio extraction and transcription
- Add multi-speaker voices and sound design
- Add evaluation and quality scoring for scripts
