import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "mysql+pymysql://user:password@localhost/testdb")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.users import User
from app.models.video_detection_job import VideoDetectionJob
from app.services.video_detection import has_active_video_job


class PersistentVideoJobRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            self.engine,
            tables=[User.__table__, VideoDetectionJob.__table__],
        )
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.add(User(user_id=1, name="Admin", email="admin@example.test", password_hash="unused", role="admin"))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(
            self.engine,
            tables=[VideoDetectionJob.__table__, User.__table__],
        )
        self.engine.dispose()

    def _job(self, job_id, status, created_at, *, updated_at=None):
        return VideoDetectionJob(
            job_id=job_id, user_id=1, lot_slug="lot", camera_id="camera",
            content_type="video/mp4", status=status, input_object=f"{job_id}/input.mp4",
            layout_object=f"{job_id}/layout.json", reference_object=f"{job_id}/reference.jpg",
            frame_object=f"{job_id}/preview.jpg", result_object=f"{job_id}/result.mp4",
            created_at=created_at, updated_at=updated_at,
        )

    def test_stale_queued_job_is_failed_and_no_longer_blocks_new_jobs(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stale = self._job("stale-job", "queued", now - timedelta(minutes=20))
        self.db.add(stale)
        self.db.commit()

        self.assertFalse(has_active_video_job(self.db))

        self.db.refresh(stale)
        self.assertEqual(stale.status, "failed")
        self.assertIsNotNone(stale.finished_at)

    def test_recent_running_job_remains_active(self):
        recent = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        self.db.add(self._job("active-job", "running", recent, updated_at=recent))
        self.db.commit()

        self.assertTrue(has_active_video_job(self.db))


if __name__ == "__main__":
    unittest.main()
