import sys
import threading
import uuid
from argparse import Namespace
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.video_detection_job import VideoDetectionJob, VideoDetectionSlot


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DETECTION_DIR = PROJECT_ROOT / "detection"
MODEL_PATH = DETECTION_DIR / "models" / "parking_lot.pt"
OUTPUT_DIR = DETECTION_DIR / "output" / "web_jobs"

if str(DETECTION_DIR) not in sys.path:
    sys.path.insert(0, str(DETECTION_DIR))


class VideoDetectionJobs:
    """In-process background video jobs with a latest-frame preview."""

    def __init__(self):
        self._lock = threading.RLock()
        self._jobs = {}

    def start(self, video_path: Path, lot_slug: str, camera_id: str, reference_path: Path):
        job_id = uuid.uuid4().hex
        output_path = OUTPUT_DIR / f"{job_id}.mp4"
        job = {
            "job_id": job_id,
            "lot_slug": lot_slug,
            "camera_id": camera_id,
            "status": "queued",
            "message": "Waiting for a detection worker",
            "error": None,
            "frame_number": 0,
            "total_frames": 0,
            "latest_frame": None,
            "output_path": output_path,
            "stop_event": threading.Event(),
            "thread": None,
        }
        with self._lock:
            if any(job["status"] in {"queued", "running"} for job in self._jobs.values()):
                video_path.unlink(missing_ok=True)
                raise RuntimeError("Another video detection is already running")
            self._jobs[job_id] = job
        worker = threading.Thread(
            target=self._run,
            args=(job_id, video_path, output_path, reference_path),
            name=f"parking-video-detection-{job_id[:8]}",
            daemon=True,
        )
        job["thread"] = worker
        worker.start()
        return self.get(job_id)

    def _run(self, job_id, video_path, output_path, reference_path):
        with self._lock:
            job = self._jobs[job_id]
            job["status"] = "running"
            job["message"] = "Video detection is running"

        def publish_frame(frame, frame_number, total_frames):
            encoded_ok, encoded = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78]
            )
            if not encoded_ok:
                return
            with self._lock:
                active_job = self._jobs.get(job_id)
                if active_job is not None:
                    active_job["latest_frame"] = encoded.tobytes()
                    active_job["frame_number"] = frame_number
                    active_job["total_frames"] = total_frames

        def report_progress(frame_number, total_frames):
            with self._lock:
                active_job = self._jobs.get(job_id)
                if active_job is not None:
                    active_job["frame_number"] = frame_number
                    active_job["total_frames"] = total_frames

        try:
            import cv2

            from vehicle.run_irl import run_video

            job_config = self.get(job_id)
            args = Namespace(
                video=video_path,
                lot=job_config["lot_slug"],
                camera=job_config["camera_id"],
                reference_image=reference_path,
                model_weights=MODEL_PATH,
                detector_mode="parking_spaces",
                confidence=0.5,
                confirm_frames=3,
                frame_stride=1,
                inference_threads=1,
                no_sync=False,
                no_preview=True,
                output=output_path,
            )
            run_video(
                args,
                on_frame=publish_frame,
                on_progress=report_progress,
                stop_event=job["stop_event"],
            )
            with self._lock:
                stopped = job["stop_event"].is_set()
                job["status"] = "stopped" if stopped else "completed"
                job["message"] = (
                    "Detection stopped; parking occupancy was cleared"
                    if stopped else "Video detection completed; parking occupancy was cleared on shutdown"
                )
        except Exception as exc:
            with self._lock:
                job["status"] = "failed"
                job["error"] = str(exc)
                job["message"] = "Video detection stopped because of an error"
        finally:
            video_path.unlink(missing_ok=True)

    def get(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "job_id": job["job_id"],
                "lot_slug": job["lot_slug"],
                "camera_id": job["camera_id"],
                "status": job["status"],
                "message": job["message"],
                "error": job["error"],
                "frame_number": job["frame_number"],
                "total_frames": job["total_frames"],
                "has_frame": job["latest_frame"] is not None,
                "has_result": job["status"] in {"completed", "stopped"} and job["output_path"].is_file(),
            }

    def frame(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            return job["latest_frame"] if job else None

    def stop(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job["status"] in {"queued", "running"}:
                job["message"] = "Stopping detection and clearing parking occupancy"
                job["stop_event"].set()
            return self.get(job_id)

    def result_path(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job["status"] not in {"completed", "stopped"} or not job["output_path"].is_file():
                return None
            return job["output_path"]

    def has_active_job(self):
        with self._lock:
            return any(job["status"] in {"queued", "running"} for job in self._jobs.values())


video_detection_jobs = VideoDetectionJobs()


def cloud_video_detection_enabled() -> bool:
    """Use Cloud Run on Render; retain the local worker for development."""
    import os
    return bool(os.environ.get("RENDER_EXTERNAL_URL"))


def _job_payload(job: VideoDetectionJob) -> dict:
    return {
        "job_id": job.job_id,
        "lot_slug": job.lot_slug,
        "camera_id": job.camera_id,
        "status": job.status,
        "message": job.message,
        "error": job.error,
        "frame_number": job.frame_number,
        "total_frames": job.total_frames,
        "has_frame": bool(job.frame_available),
        "has_result": job.status in {"completed", "stopped"} and bool(job.result_object),
    }


def _expire_stale_video_jobs(db, now=None) -> int:
    now = now or datetime.now(timezone.utc)
    jobs = db.query(VideoDetectionJob).filter(
        VideoDetectionJob.status.in_(("queued", "running"))
    ).all()
    expired = 0
    for job in jobs:
        baseline = job.updated_at or job.started_at or job.created_at
        stale_after = 15 * 60 if job.status == "queued" else 3 * 60 * 60
        if baseline:
            baseline = baseline.replace(tzinfo=timezone.utc) if baseline.tzinfo is None else baseline
        if baseline and (now - baseline).total_seconds() > stale_after:
            job.status = "failed"
            job.message = "Video detection timed out"
            job.error = "No worker update was received before the job timeout"
            job.finished_at = now.replace(tzinfo=None)
            job.updated_at = job.finished_at
            expired += 1
    if expired:
        db.commit()
    return expired


def get_persistent_video_job(db, job_id: str, user_id: int):
    _expire_stale_video_jobs(db)
    job = db.query(VideoDetectionJob).filter(
        VideoDetectionJob.job_id == job_id,
        VideoDetectionJob.user_id == user_id,
    ).first()
    return _job_payload(job) if job else None


def has_active_video_job(db=None) -> bool:
    own_session = db is None
    db = db or SessionLocal()
    try:
        _expire_stale_video_jobs(db)
        return video_detection_jobs.has_active_job() or db.query(VideoDetectionJob.job_id).filter(
            VideoDetectionJob.status.in_(("queued", "running"))
        ).first() is not None
    finally:
        if own_session:
            db.close()


def _lock_video_slot(db) -> None:
    slot = db.query(VideoDetectionSlot).filter(VideoDetectionSlot.slot_id == 1).with_for_update().first()
    if slot is None:
        try:
            db.add(VideoDetectionSlot(slot_id=1))
            db.flush()
        except IntegrityError:
            db.rollback()
            db.query(VideoDetectionSlot).filter(VideoDetectionSlot.slot_id == 1).with_for_update().first()


def start_cloud_video_detection(db, *, user_id: int, video_path: Path, byte_count: int,
                                lot_slug: str, camera_id: str, content_type: str,
                                layout: dict, reference_path: Path) -> dict:
    from app.services import cloud_storage, cloud_run_jobs
    import json

    job_id = str(uuid.uuid4())
    prefix = f"video-jobs/{job_id}"
    suffix = video_path.suffix.lower().lstrip(".")
    objects = {
        "input": f"{prefix}/input.{suffix}",
        "layout": f"{prefix}/layout.json",
        "reference": f"{prefix}/reference{reference_path.suffix.lower()}",
        "frame": f"{prefix}/preview.jpg",
        "result": f"{prefix}/result.mp4",
    }
    cloud_storage.upload_file(objects["input"], content_type, video_path, byte_count)
    cloud_storage.upload_bytes(objects["layout"], "application/json", json.dumps(layout, separators=(",", ":")).encode())
    cloud_storage.upload_file(objects["reference"], "image/" + reference_path.suffix.lower().lstrip("."),
                              reference_path, reference_path.stat().st_size)
    _lock_video_slot(db)
    if db.query(VideoDetectionJob.job_id).filter(
        VideoDetectionJob.status.in_(("queued", "running"))
    ).first() is not None:
        db.rollback()
        raise RuntimeError("Another video detection is already running")
    job = VideoDetectionJob(
        job_id=job_id, user_id=user_id, lot_slug=lot_slug, camera_id=camera_id,
        content_type=content_type, status="queued", message="Waiting for a Cloud Run worker",
        input_object=objects["input"], layout_object=objects["layout"],
        reference_object=objects["reference"], frame_object=objects["frame"],
        result_object=objects["result"],
    )
    db.add(job)
    db.commit()
    try:
        cloud_run_jobs.execute_video_detection(job_id)
    except Exception as exc:
        job.status = "failed"
        job.message = "Video detection could not be started"
        job.error = "Cloud Run could not start the video worker; inspect trigger service logs"
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        job.updated_at = job.finished_at
        db.commit()
        raise RuntimeError("Could not start the Cloud Run video worker") from exc
    return _job_payload(job)


def stop_persistent_video_job(db, job_id: str, user_id: int):
    job = db.query(VideoDetectionJob).filter(
        VideoDetectionJob.job_id == job_id,
        VideoDetectionJob.user_id == user_id,
    ).first()
    if job is None:
        return None
    if job.status in {"queued", "running"}:
        job.cancel_requested = True
        job.message = "Stopping detection and clearing parking occupancy"
        db.commit()
    return _job_payload(job)
