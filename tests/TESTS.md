# Test Inventory

This file lists all unit tests in `tests/` and what each one validates.

## How To Run

```bash
scripts/test.sh
```

## `tests/test_article.py`

- `test_rejects_non_http_urls`: rejects unsupported URL schemes (for example `ftp://`) in article fetch.
- `test_wraps_request_errors`: converts `requests` exceptions into `ArticleError` with a clear message.
- `test_prefers_article_tag_content`: extracts text from `<article>` paragraphs when present.
- `test_falls_back_to_page_paragraphs`: falls back to all `<p>` tags when no `<article>` block is available.
- `test_raises_if_no_readable_paragraphs`: raises `ArticleError` when no paragraph content can be extracted.

## `tests/test_event_schema.py`

- `test_validates_stage_requirements`: enforces required fields for `fetch`, `rewrite`, and `generate` stages.
- `test_keeps_unknown_fields_when_round_tripping`: preserves unknown fields in `extras` during `from_dict` -> `to_dict`.
- `test_rejects_invalid_field_types`: rejects invalid types and negative numeric fields.
- `test_stage_require_helpers_return_required_fields`: validates `require_fetch_fields`, `require_rewrite_fields`, and `require_generate_fields`.

## `tests/test_handlers.py`

- `test_requires_job_id_and_source_url`: `fetch_article.handler` rejects missing required input fields.
- `test_fetches_extracts_and_stores_article`: `fetch_article.handler` fetches, extracts, stores text, and returns expected output keys.
- `test_requires_job_id_and_article_s3_key`: `rewrite_script.handler` rejects missing required input fields.
- `test_reads_article_rewrites_and_stores_outputs`: `rewrite_script.handler` builds prompt, calls Bedrock helper, stores script and metadata.
- `test_requires_job_id_and_script_s3_key`: `generate_audio.handler` rejects missing required input fields.
- `test_reads_script_synthesizes_audio_and_stores_mp3`: `generate_audio.handler` reads script, synthesizes SSML audio, stores MP3, returns expected keys.
- `test_uses_event_voice_override`: `generate_audio.handler` prefers event `voice_id` over default config voice.

## `tests/test_llm.py`

- `test_routes_anthropic_ids`: routes Anthropic model IDs to `call_bedrock_anthropic`.
- `test_routes_nova_ids`: routes Nova model IDs to `call_bedrock_nova`.
- `test_raises_for_unsupported_model_ids`: raises `LLMError` for unsupported model families.

## `tests/test_tts.py`

- `test_short_text_makes_single_request`: short text performs one Polly request in plain text mode.
- `test_long_text_is_split_into_multiple_requests`: long text is chunked and synthesized across multiple Polly requests.
- `test_raises_when_audio_stream_missing`: raises `TTSError` when Polly response has no `AudioStream`.
- `test_raises_when_text_is_empty`: rejects empty/whitespace text input.
- `test_ssml_mode_wraps_speak_and_sets_text_type`: SSML mode wraps content with SSML tags and sets `TextType=ssml`.
- `test_rejects_invalid_text_type`: rejects unsupported `text_type` values.
