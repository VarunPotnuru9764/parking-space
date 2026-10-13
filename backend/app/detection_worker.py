"""Cloud Run Jobs entry point for parking-layout inference."""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.detection_job import DetectionJob

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from detection.layout.pretrained_layout_detector import PretrainedParkingSpaceDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("layout-detection-worker")
MODEL_PATH = PROJECT_ROOT / "detection" / "models" / "parking_lot.pt"


def process_job(job_id: str) -> None:
    db: Session = SessionLocal()
    try:
        job = db.query(DetectionJob).filter(DetectionJob.job_id == job_id).with_for_update().first()
        if job is None:
            raise RuntimeError(f"Detection job {job_id} was not found")
        if job.status != "queued":
            LOGGER.info("Job %s is already %s; skipping duplicate execution", job_id, job.status)
            return
        image_bytes = bytes(job.image_data or b"")
        if not image_bytes:
            raise RuntimeError("Detection job has no uploaded image")
        job.status = "running"
        job.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        lot_slug, camera_id = job.lot_slug, job.camera_id
    finally:
        db.close()

    try:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not decode the uploaded image")
        detector = PretrainedParkingSpaceDetector(MODEL_PATH, confidence=0.25)
        candidates = detector.detect(image)
        result = {
            "format": "parking-layout-review-v1",
            "lot_slug": lot_slug,
            "camera_id": camera_id,
            "image_width": int(image.shape[1]),
            "image_height": int(image.shape[0]),
            "detector_candidates": [
                {
                    "candidate_id": int(candidate["candidate_id"]),
                    "stable_id": f"detector-{candidate['candidate_id']}",
                    "polygon": candidate["polygon"],
                    "confidence": candidate.get("confidence"),
                    "class_name": candidate.get("class_name"),
                }
                for candidate in candidates
            ],
        }
        db = SessionLocal()
        try:
            job = db.query(DetectionJob).filter(DetectionJob.job_id == job_id).with_for_update().first()
            if job is None:
                raise RuntimeError(f"Detection job {job_id} disappeared before completion")
            job.result_json = json.dumps(result, separators=(",", ":"))
            job.status = "succeeded"
            job.error = None
            job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
        finally:
            db.close()
        LOGGER.info("Job %s completed with %s candidates", job_id, len(candidates))
    except Exception as exc:
        LOGGER.exception("Layout inference failed for job %s", job_id)
        db = SessionLocal()
        try:
            job = db.query(DetectionJob).filter(DetectionJob.job_id == job_id).with_for_update().first()
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:2000]
                job.image_data = None
                job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db.commit()
        finally:
            db.close()
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    process_job(args.job_id)


if __name__ == "__main__":
    main()
