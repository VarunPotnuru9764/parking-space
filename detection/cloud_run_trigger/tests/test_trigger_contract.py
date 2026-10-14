import os
import sys
from types import ModuleType
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("PROJECT_ID", "test-project")
os.environ.setdefault("TRIGGER_SECRET", "test-secret")

from detection.cloud_run_trigger.main import (
    TriggerRequest, _job_launch, _signed_read_url, _validate_object_name,
)
from fastapi import HTTPException


class TriggerContractTests(unittest.TestCase):
    job_id = "12345678-1234-4abc-8def-123456789abc"

    def test_legacy_layout_request_selects_original_job_and_timeout(self):
        request = TriggerRequest(job_id=self.job_id)
        job_name, argument, payload = _job_launch(request)

        self.assertEqual(job_name, "parking-detection-worker")
        self.assertEqual(argument, "--job-id")
        self.assertEqual(
            payload["overrides"],
            {
                "containerOverrides": [{"args": ["--job-id", self.job_id]}],
                "taskCount": 1,
                "timeout": "900s",
            },
        )

    def test_video_request_selects_separate_job_without_changing_layout(self):
        request = TriggerRequest(job_id=self.job_id, job_type="video")
        job_name, argument, payload = _job_launch(request)

        self.assertEqual(job_name, "parking-video-detection-worker")
        self.assertEqual(argument, "--video-job-id")
        self.assertEqual(
            payload["overrides"]["containerOverrides"][0]["args"],
            ["--video-job-id", self.job_id],
        )
        self.assertNotIn("timeout", payload["overrides"])

    def test_storage_paths_are_scoped_to_video_jobs(self):
        _validate_object_name(f"video-jobs/{self.job_id}/reference.png")
        with self.assertRaises(HTTPException):
            _validate_object_name(f"other/{self.job_id}/input.mp4")
        with self.assertRaises(HTTPException):
            _validate_object_name(f"video-jobs/{self.job_id}/../secret.txt")

    def test_signed_read_uses_attached_identity_iam_signer(self):
        blob = Mock()
        blob.generate_signed_url.return_value = "https://storage.example/signed"
        credentials = SimpleNamespace(token="runtime-access-token")
        auth_request = object()
        signer_factory = Mock()
        fake_google = ModuleType("google")
        fake_auth = ModuleType("google.auth")
        fake_auth.iam = SimpleNamespace(Signer=signer_factory)
        fake_google.auth = fake_auth

        with patch.dict(sys.modules, {"google": fake_google, "google.auth": fake_auth}):
            result = _signed_read_url(blob, auth_request, credentials, "trigger@example.iam.gserviceaccount.com")

        self.assertEqual(result, "https://storage.example/signed")
        signer_factory.assert_called_once_with(
            auth_request, credentials, "trigger@example.iam.gserviceaccount.com"
        )
        kwargs = blob.generate_signed_url.call_args.kwargs
        self.assertEqual(kwargs["method"], "GET")
        self.assertEqual(kwargs["expiration"], timedelta(minutes=15))
        self.assertEqual(kwargs["access_token"], credentials.token)
        self.assertIs(kwargs["credentials"], signer_factory.return_value)


if __name__ == "__main__":
    unittest.main()
