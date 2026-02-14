"""Unit tests for pipeline event schema validation."""
from __future__ import annotations

import unittest

from ml_publication.event_schema import EventSchemaError, PipelineEvent


class PipelineEventTests(unittest.TestCase):
    def test_validates_stage_requirements(self) -> None:
        with self.assertRaisesRegex(EventSchemaError, "job_id and source_url"):
            PipelineEvent.from_dict({}, stage="fetch")

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

    def test_rejects_invalid_field_types(self) -> None:
        with self.assertRaisesRegex(EventSchemaError, "must be a string"):
            PipelineEvent.from_dict({"job_id": 123}, stage="fetch")

        with self.assertRaisesRegex(EventSchemaError, "must be >= 0"):
            PipelineEvent.from_dict({"audio_estimated_duration_sec": -1})

    def test_stage_require_helpers_return_required_fields(self) -> None:
        fetch_event = PipelineEvent.from_dict(
            {"job_id": "job-1", "source_url": "https://example.com/article"}
        )
        self.assertEqual(
            ("job-1", "https://example.com/article"),
            fetch_event.require_fetch_fields(),
        )

        rewrite_event = PipelineEvent.from_dict(
            {"job_id": "job-2", "article_s3_key": "jobs/job-2/article.txt"}
        )
        self.assertEqual(
            ("job-2", "jobs/job-2/article.txt"),
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
