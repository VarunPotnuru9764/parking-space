import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("DATABASE_URL", "mysql+pymysql://user:password@localhost/testdb")

import cv2
from app import detection_worker


class VideoWorkerSafetyTests(unittest.TestCase):
    def test_preview_object_is_not_the_layout_snapshot(self):
        job = SimpleNamespace(
            input_object="video-jobs/id/input.mp4",
            layout_object="video-jobs/id/layout.json",
            reference_object="video-jobs/id/reference.jpg",
            frame_object="video-jobs/id/preview.jpg",
            result_object="video-jobs/id/result.mp4",
        )

        objects = detection_worker._video_artifact_objects(job)

        self.assertEqual(objects["frame"], job.frame_object)
        self.assertEqual(objects["layout"], job.layout_object)
        self.assertNotEqual(objects["frame"], objects["layout"])

    def test_detection_worker_imports_opencv_for_preview_encoding(self):
        self.assertIs(detection_worker.cv2, cv2)
        self.assertTrue(callable(detection_worker.cv2.imencode))

    def test_cancel_flag_is_read_from_persistent_job_state_and_session_closes(self):
        session = Mock()
        session.query.return_value.filter.return_value.scalar.return_value = True
        with patch("app.detection_worker.SessionLocal", return_value=session):
            requested = detection_worker._is_video_cancel_requested("job-id")

        self.assertTrue(requested)
        session.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
