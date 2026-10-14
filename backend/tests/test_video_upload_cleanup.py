import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("DATABASE_URL", "mysql+pymysql://user:password@localhost/testdb")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "detection"))

from app.routes import video_detection


class VideoUploadCleanupTests(unittest.TestCase):
    def test_cloud_upload_temp_file_is_removed_when_cloud_staging_fails(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            upload_path = Path(directory) / "clip.mp4"
            upload_path.write_bytes(b"video-bytes")
            with patch.object(video_detection, "cloud_video_detection_enabled", return_value=True), \
                    patch.object(video_detection, "start_cloud_video_detection", side_effect=RuntimeError("upload failed")):
                with self.assertRaisesRegex(RuntimeError, "upload failed"):
                    video_detection._start_video_job(
                        upload_path, db=Mock(), user_id=7, byte_count=11,
                        lot_slug="lot", camera_id="camera", content_type="video/mp4",
                        layout_snapshot={}, reference_path=Path(directory) / "reference.jpg",
                    )

            self.assertFalse(upload_path.exists())


if __name__ == "__main__":
    unittest.main()
