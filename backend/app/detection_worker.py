"""Cloud Run Jobs entry point for parking-layout inference."""

import argparse
import json
import logging
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.detection_job import DetectionJob
from app.models.video_detection_job import VideoDetectionJob

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from detection.layout.pretrained_layout_detector import PretrainedParkingSpaceDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("layout-detection-worker")
MODEL_PATH = PROJECT_ROOT / "detection" / "models" / "parking_lot.pt"


def _video_artifact_objects(job) -> dict[str, str]:
    """Keep each artifact mapped to its own persisted object name."""
    return {
        "input": job.input_object,
        "layout": job.layout_object,
        "reference": job.reference_object,
        "frame": job.frame_object,
        "result": job.result_object,
    }


def _is_video_cancel_requested(job_id: str) -> bool:
    session = SessionLocal()
    try:
        return bool(session.query(VideoDetectionJob.cancel_requested).filter(
            VideoDetectionJob.job_id == job_id
        ).scalar())
    finally:
        session.close()


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


def process_video_job(job_id: str) -> None:
    """Run the existing video pipeline from immutable GCS input snapshots."""
    import json
    from argparse import Namespace

    from detection.vehicle.run_irl import run_video
    from google.cloud import storage

    bucket_name = os.environ.get("VIDEO_STORAGE_BUCKET") or os.environ.get("GCS_BUCKET")
    if not bucket_name:
        raise RuntimeError("VIDEO_STORAGE_BUCKET is required for video jobs")
    db = SessionLocal()
    try:
        job = db.query(VideoDetectionJob).filter(VideoDetectionJob.job_id == job_id).with_for_update().first()
        if job is None:
            raise RuntimeError(f"Video detection job {job_id} was not found")
        if job.status != "queued":
            LOGGER.info("Video job %s is already %s; skipping duplicate execution", job_id, job.status)
            return
        job.status = "running"
        job.message = "Video detection is running"
        job.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        job.updated_at = job.started_at
        db.commit()
        artifacts = _video_artifact_objects(job)
        lot_slug, camera_id = job.lot_slug, job.camera_id
    finally:
        db.close()

    stop_event = threading.Event()
    with tempfile.TemporaryDirectory(prefix="parking-video-") as temp_dir:
        temp_path = Path(temp_dir)
        video_path = temp_path / Path(artifacts["input"]).name
        reference_path = temp_path / Path(artifacts["reference"]).name
        output_path = temp_path / "annotated.mp4"
        try:
            bucket = storage.Client().bucket(bucket_name)
            bucket.blob(artifacts["input"]).download_to_filename(str(video_path))
            layout = json.loads(bucket.blob(artifacts["layout"]).download_as_bytes())
            bucket.blob(artifacts["reference"]).download_to_filename(str(reference_path))
        except Exception as exc:
            failed = SessionLocal()
            try:
                current = failed.query(VideoDetectionJob).filter(VideoDetectionJob.job_id == job_id).first()
                if current is not None:
                    current.status = "failed"
                    current.message = "Video detection stopped because of an error"
                    current.error = "Could not download the video job inputs; inspect Cloud Run logs"
                    current.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    failed.commit()
            finally:
                failed.close()
            raise
        last_db_update = [0.0]

        def update_state(frame_number=None, total_frames=None, preview=None, *, final=None, error=None):
            now = time.monotonic()
            if final is None and now - last_db_update[0] < 1.0 and preview is None:
                return
            if preview is not None:
                bucket.blob(artifacts["frame"]).upload_from_string(preview, content_type="image/jpeg")
            session = SessionLocal()
            try:
                current = session.query(VideoDetectionJob).filter(VideoDetectionJob.job_id == job_id).first()
                if current is None:
                    return
                if frame_number is not None:
                    current.frame_number = int(frame_number)
                if total_frames is not None:
                    current.total_frames = int(total_frames)
                current.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                if preview is not None:
                    current.frame_available = True
                if final is not None:
                    current.status = final
                    current.message = (
                        "Detection stopped; parking occupancy was cleared"
                        if final == "stopped" else
                        "Video detection completed; parking occupancy was cleared on shutdown"
                        if final == "completed" else "Video detection stopped because of an error"
                    )
                    current.error = error
                    current.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    current.updated_at = current.finished_at
                session.commit()
            finally:
                session.close()
            last_db_update[0] = now

        def watch_cancel():
            while not stop_event.wait(2):
                try:
                    if _is_video_cancel_requested(job_id):
                        stop_event.set()
                except Exception:
                    LOGGER.warning("Could not check cancellation for video job %s", job_id, exc_info=True)

        watcher = threading.Thread(target=watch_cancel, name=f"video-cancel-{job_id[:8]}", daemon=True)
        watcher.start()
        def publish_frame(frame, frame_number, total_frames):
            if frame_number % 15:
                return
            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
            update_state(frame_number, total_frames, encoded.tobytes() if ok else None)

        def report_progress(frame_number, total_frames):
            update_state(frame_number, total_frames)

        try:
            args = Namespace(
                video=video_path, lot=lot_slug, camera=camera_id,
                reference_image=reference_path, model_weights=MODEL_PATH,
                detector_mode="parking_spaces", confidence=0.5, confirm_frames=3,
                frame_stride=1, inference_threads=1, no_sync=False,
                no_preview=True, output=output_path,
            )
            run_video(args, on_frame=publish_frame, on_progress=report_progress,
                      stop_event=stop_event, layout_override=layout)
            bucket.blob(artifacts["result"]).upload_from_filename(str(output_path), content_type="video/mp4")
            update_state(final="stopped" if stop_event.is_set() else "completed")
        except Exception as exc:
            LOGGER.exception("Video inference failed for job %s", job_id)
            update_state(final="failed", error="Video processing failed; inspect Cloud Run logs")
            raise
        finally:
            stop_event.set()
            watcher.join(timeout=3)


def main() -> None:
    parser = argparse.ArgumentParser()
    jobs = parser.add_mutually_exclusive_group(required=True)
    jobs.add_argument("--job-id")
    jobs.add_argument("--video-job-id")
    args = parser.parse_args()
    if args.video_job_id:
        process_video_job(args.video_job_id)
    else:
        process_job(args.job_id)


if __name__ == "__main__":
    main()
