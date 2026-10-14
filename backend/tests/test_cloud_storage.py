import unittest
from unittest.mock import Mock, patch

from app.services import cloud_storage


class CloudStorageTriggerTests(unittest.TestCase):
    @patch.dict("os.environ", {
        "CLOUD_RUN_TRIGGER_URL": "https://trigger.example",
        "CLOUD_RUN_TRIGGER_SECRET": "test-secret",
    })
    @patch("app.services.cloud_storage.requests.post")
    def test_upload_session_uses_protected_trigger(self, post):
        post.return_value = Mock(ok=True, json=lambda: {"upload_url": "https://storage.example/session"})

        url = cloud_storage.create_upload_session("video-jobs/job/input.mp4", "video/mp4")

        self.assertEqual(url, "https://storage.example/session")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-secret")
        self.assertEqual(post.call_args.kwargs["json"]["content_type"], "video/mp4")

    @patch.dict("os.environ", {
        "CLOUD_RUN_TRIGGER_URL": "https://trigger.example",
        "CLOUD_RUN_TRIGGER_SECRET": "test-secret",
    })
    @patch("app.services.cloud_storage.requests.post")
    def test_signed_read_uses_protected_trigger(self, post):
        post.return_value = Mock(ok=True, json=lambda: {"download_url": "https://storage.example/read"})

        url = cloud_storage.create_download_url("video-jobs/job/preview.jpg")

        self.assertEqual(url, "https://storage.example/read")
        self.assertTrue(post.call_args.args[0].endswith("/storage/signed-read"))

    def test_rejects_non_https_upload_url(self):
        with patch.dict("os.environ", {
            "CLOUD_RUN_TRIGGER_URL": "https://trigger.example",
            "CLOUD_RUN_TRIGGER_SECRET": "test-secret",
        }), patch("app.services.cloud_storage.requests.post") as post:
            post.return_value = Mock(ok=True, json=lambda: {"upload_url": "http://invalid"})
            with self.assertRaisesRegex(RuntimeError, "invalid upload URL"):
                cloud_storage.create_upload_session("video-jobs/job/input.mp4", "video/mp4")


if __name__ == "__main__":
    unittest.main()
