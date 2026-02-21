"""Unit tests for API service and API handlers."""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from podcast_anything.api import handlers
from podcast_anything.api.service import resolve_state_machine_arn, start_pipeline_execution


class ApiServiceTests(unittest.TestCase):
    @patch("podcast_anything.api.service.boto3.session.Session")
    def test_start_pipeline_execution_uses_explicit_state_machine_arn(self, mock_session_cls: Mock) -> None:
        mock_session = Mock()
        mock_sf = Mock()
        mock_sf.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123:execution:sm:exec-1",
            "startDate": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        mock_session.client.return_value = mock_sf
        mock_session_cls.return_value = mock_session

        result = start_pipeline_execution(
            source_url="https://example.com/article",
            job_id="job-1",
            style="podcast",
            state_machine_arn="arn:aws:states:us-east-1:123:stateMachine:sm",
            region="us-east-1",
        )

        mock_session.client.assert_called_once_with("stepfunctions")
        mock_sf.start_execution.assert_called_once()
        self.assertEqual("job-1", result["job_id"])
        self.assertEqual("arn:aws:states:us-east-1:123:stateMachine:sm", result["state_machine_arn"])

    @patch("podcast_anything.api.service.boto3.session.Session")
    def test_start_pipeline_execution_resolves_state_machine_arn_from_stack(self, mock_session_cls: Mock) -> None:
        mock_session = Mock()
        mock_cf = Mock()
        mock_cf.describe_stacks.return_value = {
            "Stacks": [
                {
                    "Outputs": [
                        {
                            "OutputKey": "PipelineStateMachineArn",
                            "OutputValue": "arn:aws:states:us-east-1:123:stateMachine:resolved-sm",
                        }
                    ]
                }
            ]
        }
        mock_sf = Mock()
        mock_sf.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123:execution:resolved-sm:exec-1",
            "startDate": datetime(2026, 1, 2, tzinfo=timezone.utc),
        }
        mock_session.client.side_effect = [mock_cf, mock_sf]
        mock_session_cls.return_value = mock_session

        result = start_pipeline_execution(
            source_url="https://example.com/article",
            job_id="job-2",
            stack_name="PodcastAnythingStack",
            region="us-east-1",
        )

        mock_cf.describe_stacks.assert_called_once_with(StackName="PodcastAnythingStack")
        mock_sf.start_execution.assert_called_once()
        self.assertEqual(
            "arn:aws:states:us-east-1:123:stateMachine:resolved-sm",
            result["state_machine_arn"],
        )

    def test_resolve_state_machine_arn_raises_when_output_missing(self) -> None:
        cloudformation = Mock()
        cloudformation.describe_stacks.return_value = {"Stacks": [{"Outputs": []}]}

        with self.assertRaisesRegex(Exception, "PipelineStateMachineArn"):
            resolve_state_machine_arn(cloudformation=cloudformation, stack_name="PodcastAnythingStack")


class ApiHandlerTests(unittest.TestCase):
    def test_start_execution_handler_rejects_invalid_json(self) -> None:
        response = handlers.start_execution_handler({"body": "{bad-json"}, None)
        self.assertEqual(400, response["statusCode"])
        self.assertIn("invalid JSON request body", response["body"])

    @patch("podcast_anything.api.handlers.start_pipeline_execution")
    def test_start_execution_handler_returns_accepted(self, mock_start: Mock) -> None:
        mock_start.return_value = {
            "job_id": "job-1",
            "execution_arn": "arn:execution",
        }
        event = {
            "body": json.dumps({"source_url": "https://example.com/article", "style": "podcast"}),
            "queryStringParameters": {"region": "us-east-1"},
        }

        response = handlers.start_execution_handler(event, None)

        self.assertEqual(202, response["statusCode"])
        mock_start.assert_called_once()

    def test_get_execution_handler_requires_execution_arn(self) -> None:
        response = handlers.get_execution_handler({}, None)
        self.assertEqual(400, response["statusCode"])
        self.assertIn("execution_arn", response["body"])

    @patch("podcast_anything.api.handlers.get_execution_status")
    def test_get_execution_handler_returns_status(self, mock_get_status: Mock) -> None:
        mock_get_status.return_value = {
            "execution_arn": "arn:execution",
            "status": "SUCCEEDED",
        }
        event = {"queryStringParameters": {"execution_arn": "arn:execution"}}

        response = handlers.get_execution_handler(event, None)

        self.assertEqual(200, response["statusCode"])
        mock_get_status.assert_called_once_with(execution_arn="arn:execution", region=None)


if __name__ == "__main__":
    unittest.main()

