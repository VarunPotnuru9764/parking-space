import os
import unittest

os.environ.setdefault("DATABASE_URL", "mysql+pymysql://user:password@localhost/testdb")

from app.database import Base
from app.models.video_detection_job import VideoDetectionJob, VideoDetectionSlot


class VideoDetectionModelTests(unittest.TestCase):
    def test_persistent_video_job_table_has_state_and_artifact_references(self):
        table = VideoDetectionJob.__table__
        self.assertEqual(table.name, "video_detection_jobs")
        for column in (
            "status", "frame_number", "total_frames", "cancel_requested",
            "input_object", "layout_object", "reference_object", "frame_object", "result_object",
        ):
            self.assertIn(column, table.columns)

    def test_concurrency_slot_is_a_separate_singleton_table(self):
        self.assertEqual(VideoDetectionSlot.__tablename__, "video_detection_slots")
        self.assertIn("video_detection_jobs", Base.metadata.tables)
        self.assertIn("video_detection_slots", Base.metadata.tables)


if __name__ == "__main__":
    unittest.main()
