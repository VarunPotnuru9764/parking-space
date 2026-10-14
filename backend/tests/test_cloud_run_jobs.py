import os
import unittest
from unittest.mock import Mock, patch

from app.services.cloud_run_jobs import execute_layout_detection, execute_video_detection


class CloudRunJobTriggerTests(unittest.TestCase):
    job_id = "12345678-1234-4abc-8def-123456789abc"

    @patch("app.services.cloud_run_jobs.requests.post")
    def test_layout_trigger_keeps_legacy_payload(self, post):
        post.return_value = Mock(ok=True, json=lambda: {"status": "triggered"})
        with patch.dict(os.environ, {
            "CLOUD_RUN_TRIGGER_URL": "https://trigger.example",
            "CLOUD_RUN_TRIGGER_SECRET": "test-secret",
        }):
            result = execute_layout_detection(self.job_id)

        self.assertEqual(result, {"status": "triggered"})
        self.assertEqual(post.call_args.kwargs["json"], {"job_id": self.job_id})
        self.assertEqual(post.call_args.args[0], "https://trigger.example/trigger")

    @patch("app.services.cloud_run_jobs.requests.post")
    def test_video_trigger_uses_explicit_type(self, post):
        post.return_value = Mock(ok=True, json=lambda: {"status": "triggered"})
        with patch.dict(os.environ, {
            "CLOUD_RUN_TRIGGER_URL": "https://trigger.example/",
            "CLOUD_RUN_TRIGGER_SECRET": "test-secret",
        }):
            execute_video_detection(self.job_id)

        self.assertEqual(
            post.call_args.kwargs["json"],
            {"job_id": self.job_id, "job_type": "video"},
        )

    def test_missing_trigger_configuration_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "CLOUD_RUN_TRIGGER_URL"):
                execute_video_detection(self.job_id)


if __name__ == "__main__":
    unittest.main()
