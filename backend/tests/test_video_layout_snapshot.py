import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "mysql+pymysql://user:password@localhost/testdb")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "detection"))

from detection.vehicle.run_irl import resolve_video_layout


class VideoLayoutSnapshotTests(unittest.TestCase):
    def test_worker_uses_and_validates_the_submitted_layout_snapshot(self):
        reviewed = {"spaces": [{"slot_number": "A1", "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]}]}
        with patch("detection.vehicle.run_irl.load_layout", side_effect=AssertionError("must use snapshot")):
            selected = resolve_video_layout("lot", "camera", reviewed)
        self.assertIs(selected, reviewed)

    def test_local_video_path_still_loads_saved_layout(self):
        saved = {"spaces": [{"slot_number": "A1", "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]}]}
        with patch("detection.vehicle.run_irl.load_layout", return_value=saved) as load:
            selected = resolve_video_layout("lot", "camera")
        load.assert_called_once_with("lot", "camera")
        self.assertIs(selected, saved)


if __name__ == "__main__":
    unittest.main()
