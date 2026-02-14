"""Event schema helpers for pipeline handlers and orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, cast


class EventSchemaError(ValueError):
    """Raised when an incoming pipeline event is invalid."""


_KNOWN_FIELDS = {
    "job_id",
    "source_url",
    "title",
    "style",
    "voice_id",
    "bucket",
    "article_s3_key",
    "article_char_count",
    "script_s3_key",
    "script_metadata_s3_key",
    "audio_s3_key",
    "audio_estimated_duration_sec",
}


def _read_optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise EventSchemaError(f"event field '{field_name}' must be a string")
    value = value.strip()
    if not value:
        raise EventSchemaError(f"event field '{field_name}' must not be empty")
    return value


def _read_optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int:  # bool is a subtype of int; reject it
        raise EventSchemaError(f"event field '{field_name}' must be an integer")
    if value < 0:
        raise EventSchemaError(f"event field '{field_name}' must be >= 0")
    return value


@dataclass(frozen=True)
class PipelineEvent:
    job_id: str | None = None
    source_url: str | None = None
    title: str | None = None
    style: str = "podcast"
    voice_id: str | None = None
    bucket: str | None = None
    article_s3_key: str | None = None
    article_char_count: int | None = None
    script_s3_key: str | None = None
    script_metadata_s3_key: str | None = None
    audio_s3_key: str | None = None
    audio_estimated_duration_sec: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], stage: str | None = None) -> "PipelineEvent":
        if not isinstance(payload, Mapping):
            raise EventSchemaError("event must be a JSON object")

        event = cls(
            job_id=_read_optional_string(payload.get("job_id"), "job_id"),
            source_url=_read_optional_string(payload.get("source_url"), "source_url"),
            title=_read_optional_string(payload.get("title"), "title"),
            style=_read_optional_string(payload.get("style"), "style") or "podcast",
            voice_id=_read_optional_string(payload.get("voice_id"), "voice_id"),
            bucket=_read_optional_string(payload.get("bucket"), "bucket"),
            article_s3_key=_read_optional_string(payload.get("article_s3_key"), "article_s3_key"),
            article_char_count=_read_optional_int(payload.get("article_char_count"), "article_char_count"),
            script_s3_key=_read_optional_string(payload.get("script_s3_key"), "script_s3_key"),
            script_metadata_s3_key=_read_optional_string(
                payload.get("script_metadata_s3_key"),
                "script_metadata_s3_key",
            ),
            audio_s3_key=_read_optional_string(payload.get("audio_s3_key"), "audio_s3_key"),
            audio_estimated_duration_sec=_read_optional_int(
                payload.get("audio_estimated_duration_sec"),
                "audio_estimated_duration_sec",
            ),
            extras={key: value for key, value in payload.items() if key not in _KNOWN_FIELDS},
        )
        if stage:
            event.validate_for_stage(stage)
        return event

    def validate_for_stage(self, stage: str) -> None:
        if stage == "fetch":
            if not self.job_id or not self.source_url:
                raise EventSchemaError("event must include job_id and source_url")
            return
        if stage == "rewrite":
            if not self.job_id or not self.article_s3_key:
                raise EventSchemaError("event must include job_id and article_s3_key")
            return
        if stage == "generate":
            if not self.job_id or not self.script_s3_key:
                raise EventSchemaError("event must include job_id and script_s3_key")
            return
        raise EventSchemaError(f"unsupported pipeline stage: {stage}")

    def require_fetch_fields(self) -> tuple[str, str]:
        """Return required fields for the fetch stage."""
        self.validate_for_stage("fetch")
        return cast(str, self.job_id), cast(str, self.source_url)

    def require_rewrite_fields(self) -> tuple[str, str]:
        """Return required fields for the rewrite stage."""
        self.validate_for_stage("rewrite")
        return cast(str, self.job_id), cast(str, self.article_s3_key)

    def require_generate_fields(self) -> tuple[str, str]:
        """Return required fields for the generate stage."""
        self.validate_for_stage("generate")
        return cast(str, self.job_id), cast(str, self.script_s3_key)

    def resolved_bucket(self, default_bucket: str) -> str:
        return self.bucket or default_bucket

    def with_updates(self, **updates: Any) -> "PipelineEvent":
        return replace(self, **updates)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = dict(self.extras)
        for key, value in (
            ("job_id", self.job_id),
            ("source_url", self.source_url),
            ("title", self.title),
            ("style", self.style),
            ("voice_id", self.voice_id),
            ("bucket", self.bucket),
            ("article_s3_key", self.article_s3_key),
            ("article_char_count", self.article_char_count),
            ("script_s3_key", self.script_s3_key),
            ("script_metadata_s3_key", self.script_metadata_s3_key),
            ("audio_s3_key", self.audio_s3_key),
            ("audio_estimated_duration_sec", self.audio_estimated_duration_sec),
        ):
            if value is not None:
                data[key] = value
        return data
