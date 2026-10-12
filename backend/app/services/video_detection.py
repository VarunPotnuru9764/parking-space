import sys
import threading
import uuid
from argparse import Namespace
from pathlib import Path


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
