"""Unit tests for pipeline event schema validation."""

from __future__ import annotations

import unittest

from podcast_anything.event_schema import EventSchemaError, PipelineEvent


class PipelineEventTests(unittest.TestCase):
    def test_validates_stage_requirements(self) -> None:
        with self.assertRaisesRegex(EventSchemaError, "job_id"):
            PipelineEvent.from_dict({}, stage="fetch")

        with self.assertRaisesRegex(
            EventSchemaError,
            "exactly one of source_url or source_file_base64",
        ):
            PipelineEvent.from_dict({"job_id": "job-1"}, stage="fetch")

        with self.assertRaisesRegex(
            EventSchemaError,
            "exactly one of source_url or source_file_base64",
        ):
            PipelineEvent.from_dict(
                {
                    "job_id": "job-1",
                    "source_url": "https://example.com/article",
                    "source_file_name": "notes.txt",
                    "source_file_base64": "aGVsbG8=",
                },
                stage="fetch",
            )

        with self.assertRaisesRegex(EventSchemaError, "job_id and article_s3_key"):
            PipelineEvent.from_dict({"job_id": "job-1"}, stage="rewrite")

        with self.assertRaisesRegex(EventSchemaError, "job_id and script_s3_key"):
            PipelineEvent.from_dict({"job_id": "job-1"}, stage="generate")

    def test_keeps_unknown_fields_when_round_tripping(self) -> None:
        event = PipelineEvent.from_dict(
            {
                "job_id": "job-1",
                "source_url": "https://example.com/article",
                "trace_id": "abc-123",
            },
            stage="fetch",
        )

        output = event.to_dict()
        self.assertEqual("abc-123", output["trace_id"])
        self.assertEqual("job-1", output["job_id"])
        self.assertEqual("podcast", output["style"])
        self.assertEqual("single", output["script_mode"])

    def test_rejects_invalid_field_types(self) -> None:
        with self.assertRaisesRegex(EventSchemaError, "must be a string"):
            PipelineEvent.from_dict({"job_id": 123}, stage="fetch")

        with self.assertRaisesRegex(EventSchemaError, "must be >= 0"):
            PipelineEvent.from_dict({"audio_estimated_duration_sec": -1})

        with self.assertRaisesRegex(EventSchemaError, "script_mode"):
            PipelineEvent.from_dict({"script_mode": "three-way"})

    def test_accepts_duo_script_mode(self) -> None:
        event = PipelineEvent.from_dict(
            {
                "job_id": "job-1",
                "source_url": "https://example.com/article",
                "script_mode": "duo",
                "voice_id_b": "Matthew",
            },
            stage="fetch",
        )

        self.assertEqual("duo", event.script_mode)
        self.assertEqual("Matthew", event.voice_id_b)

    def test_accepts_uploaded_document_fetch_events(self) -> None:
        event = PipelineEvent.from_dict(
            {
                "job_id": "job-1",
                "source_file_name": "brief.pdf",
                "source_file_base64": "aGVsbG8=",
            },
            stage="fetch",
        )

        self.assertEqual("brief.pdf", event.source_file_name)
        self.assertEqual("aGVsbG8=", event.source_file_base64)

    def test_rejects_source_text_with_uploaded_document(self) -> None:
        with self.assertRaisesRegex(EventSchemaError, "cannot also include source_text"):
            PipelineEvent.from_dict(
                {
                    "job_id": "job-1",
                    "source_file_name": "brief.pdf",
                    "source_file_base64": "aGVsbG8=",
                    "source_text": "ignored text",
                },
                stage="fetch",
            )

    def test_stage_require_helpers_return_required_fields(self) -> None:
        fetch_event = PipelineEvent.from_dict(
            {"job_id": "job-1", "source_url": "https://example.com/article"}
        )
        self.assertEqual(
            ("job-1", "https://example.com/article"),
            fetch_event.require_fetch_fields(),
        )

        file_fetch_event = PipelineEvent.from_dict(
            {
                "job_id": "job-file",
                "source_file_name": "brief.pdf",
                "source_file_base64": "aGVsbG8=",
            }
        )
        self.assertEqual(("job-file", None), file_fetch_event.require_fetch_fields())

        rewrite_event = PipelineEvent.from_dict(
            {"job_id": "job-2", "article_s3_key": "jobs/job-2/source.txt"}
        )
        self.assertEqual(
            ("job-2", "jobs/job-2/source.txt"),
            rewrite_event.require_rewrite_fields(),
        )

        generate_event = PipelineEvent.from_dict(
            {"job_id": "job-3", "script_s3_key": "jobs/job-3/script.txt"}
        )
        self.assertEqual(
            ("job-3", "jobs/job-3/script.txt"),
            generate_event.require_generate_fields(),
        )


if __name__ == "__main__":
    unittest.main()
