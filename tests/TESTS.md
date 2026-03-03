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
- `test_accepts_duo_script_mode`: accepts `script_mode=duo` and normalizes it into the event model.
- `test_stage_require_helpers_return_required_fields`: validates `require_fetch_fields`, `require_rewrite_fields`, and `require_generate_fields`.

## `tests/test_handlers.py`

- `test_requires_job_id_and_source_url`: `fetch_article.handler` rejects missing required input fields.
- `test_fetches_extracts_and_stores_article`: `fetch_article.handler` fetches, extracts, stores text, and returns expected output keys.
- `test_rejects_youtube_url_without_provided_transcript`: `fetch_article.handler` rejects YouTube URLs when no transcript text is provided.
- `test_requires_job_id_and_article_s3_key`: `rewrite_script.handler` rejects missing required input fields.
- `test_reads_article_rewrites_and_stores_outputs`: `rewrite_script.handler` builds prompt, calls Bedrock helper, stores script and metadata.
- `test_requires_job_id_and_script_s3_key`: `generate_audio.handler` rejects missing required input fields.
- `test_reads_script_synthesizes_audio_and_stores_mp3`: `generate_audio.handler` reads script, synthesizes audio with provider-aware defaults, stores MP3, returns expected keys.
- `test_uses_event_voice_override`: `generate_audio.handler` prefers event `voice_id` over default config voice.
- `test_uses_elevenlabs_defaults_when_provider_selected`: `generate_audio.handler` switches to ElevenLabs defaults when `TTS_PROVIDER=elevenlabs`.
- `test_duo_script_mode_synthesizes_with_two_voices`: duo mode alternates between configured speaker A/B voices and concatenates turn audio.
- `test_duo_script_mode_uses_event_voice_overrides`: duo mode prefers event voice overrides for both speakers.
- `test_duo_script_mode_requires_host_labels`: duo mode fails fast when script lines are missing `HOST_A`/`HOST_B` labels.

## `tests/test_llm.py`

- `test_routes_anthropic_ids`: routes Anthropic model IDs to `call_bedrock_anthropic`.
- `test_routes_nova_ids`: routes Nova model IDs to `call_bedrock_nova`.
- `test_raises_for_unsupported_model_ids`: raises `LLMError` for unsupported model families.
- `test_builds_duo_script_prompt_with_host_labels`: duo mode prompt includes explicit `HOST_A`/`HOST_B` dialogue constraints.
- `test_rejects_unknown_script_mode`: prompt builder rejects unsupported script modes.

## `tests/test_tts.py`

- `test_short_text_makes_single_request`: short text performs one Polly request in plain text mode.
- `test_long_text_is_split_into_multiple_requests`: long text is chunked and synthesized across multiple Polly requests.
- `test_raises_when_audio_stream_missing`: raises `TTSError` when Polly response has no `AudioStream`.
- `test_raises_when_text_is_empty`: rejects empty/whitespace text input.
- `test_ssml_mode_wraps_speak_and_sets_text_type`: SSML mode wraps content with SSML tags and sets `TextType=ssml`.
- `test_rejects_invalid_text_type`: rejects unsupported `text_type` values.
- `test_rejects_unknown_provider`: rejects unsupported `provider` values.
- `test_elevenlabs_mode_calls_http_api`: ElevenLabs mode calls the text-to-speech HTTP API and concatenates audio chunks.
- `test_elevenlabs_requires_api_key`: ElevenLabs mode fails fast when API key is missing.
- `test_elevenlabs_rejects_ssml_mode`: ElevenLabs mode rejects SSML in this pipeline.
- `test_elevenlabs_wraps_request_exceptions`: ElevenLabs mode wraps HTTP client errors in `TTSError`.

## `tests/test_config.py`

- `test_defaults_to_polly_provider`: loads `polly` defaults when no `TTS_PROVIDER` is set.
- `test_rejects_unknown_tts_provider`: rejects unsupported provider values at config load.
- `test_requires_elevenlabs_api_key_when_provider_selected`: enforces API key requirement for ElevenLabs provider.
- `test_loads_elevenlabs_settings`: loads ElevenLabs-specific environment configuration.

## `tests/test_api.py`

- `test_start_pipeline_execution_uses_explicit_state_machine_arn`: starts Step Functions execution with a provided ARN.
- `test_start_pipeline_execution_includes_source_text_when_provided`: includes caller-provided source/transcript text in Step Functions input.
- `test_start_pipeline_execution_rejects_youtube_without_transcript`: rejects YouTube URLs unless transcript text is provided by the caller.
- `test_start_pipeline_execution_rejects_invalid_script_mode`: rejects unsupported `script_mode` values.
- `test_start_pipeline_execution_rejects_blank_voice_id_b`: rejects blank secondary voice overrides.
- `test_start_pipeline_execution_resolves_state_machine_arn_from_stack`: resolves ARN from CloudFormation outputs before starting execution.
- `test_resolve_state_machine_arn_raises_when_output_missing`: fails fast when `PipelineStateMachineArn` output is absent.
- `test_start_pipeline_execution_generates_job_id_when_missing`: auto-generates a unique job ID when none is provided.
- `test_start_execution_handler_rejects_invalid_json`: returns `400` for malformed JSON request bodies.
- `test_start_execution_handler_returns_accepted`: returns `202` and delegates execution start to service layer.
- `test_start_execution_handler_accepts_transcript_text_alias`: accepts `transcript_text` and forwards it as `source_text`.
- `test_start_execution_handler_forwards_script_mode`: forwards `script_mode` from API request body to service layer.
- `test_start_execution_handler_forwards_duo_voice_overrides`: forwards `voice_id` and `voice_id_b` overrides to service layer.
- `test_start_execution_handler_rejects_youtube_without_transcript`: returns `400` when a YouTube URL is submitted without transcript text.
- `test_get_execution_handler_requires_execution_arn`: returns `400` when execution identifier is missing.
- `test_get_execution_handler_returns_status`: returns `200` with execution status payload from service layer.

## `tests/test_start_execution_script.py`

- `test_returns_none_for_non_youtube_without_transcript_file`: leaves article URLs unchanged when no transcript file is provided.
- `test_uses_transcript_file_before_youtube_fetch`: prefers `--transcript-file` content over automatic YouTube caption fetch.
- `test_auto_fetches_youtube_transcript_locally`: auto-fetches captions locally for YouTube URLs before calling AWS.
- `test_returns_clear_error_when_local_youtube_fetch_fails`: returns an actionable local caption fetch error with `--transcript-file` fallback guidance.

## `tests/test_youtube.py`

- `test_detects_supported_youtube_hosts`: detects supported YouTube URL hosts.
- `test_extracts_video_id_from_common_formats`: extracts video IDs from watch, short, and embed URL formats.
- `test_raises_when_video_id_cannot_be_extracted`: raises a clear error for malformed YouTube URLs.
- `test_returns_clean_error_when_youtube_blocks_cloud_ip`: maps cloud-IP transcript block errors to a clearer actionable message.
