import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models.lots import ParkingLot
from app.models.users import User
from app.services.audit import record_event
from app.services.video_detection import (
    DETECTION_DIR, cloud_video_detection_enabled, get_persistent_video_job,
    has_active_video_job, start_cloud_video_detection, stop_persistent_video_job,
    video_detection_jobs,
)
from app.services import cloud_storage
from app.models.video_detection_job import VideoDetectionJob
from app.services.simulator_detection import simulator_detection_jobs
from detection.layout.layout_manager import load_layout


router = APIRouter(prefix="/video-detection", tags=["Video detection"])
LAYOUT_ROOT = DETECTION_DIR / "layout" / "layouts"
LEGACY_REFERENCE_ROOT = DETECTION_DIR / "layout" / "references"
UPLOAD_DIR = DETECTION_DIR / "output" / "web_uploads"
MAX_VIDEO_BYTES = 500 * 1024 * 1024
_SCOPE_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_SUPPORTED_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
_MIME_SUFFIXES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/avi": ".avi",
    "video/x-matroska": ".mkv",
    "video/webm": ".webm",
    "application/octet-stream": ".mp4",
}


def _reference_image(lot_slug: str, camera_id: str) -> Path:
    colocated = LAYOUT_ROOT / lot_slug.lower()
    legacy = LEGACY_REFERENCE_ROOT / lot_slug / camera_id
    references = [
        path for directory, pattern in (
            (colocated, f"{camera_id.lower()}.reference.*"),
            (legacy, "reference.*"),
        )
        for path in directory.glob(pattern)
        if path.suffix.lower() in {".jpg", ".png", ".webp", ".bmp"} and path.is_file()
    ]
    if not references:
        raise HTTPException(
            status_code=409,
            detail="No reference photo is saved for this lot and camera. Generate layout candidates from the camera photo again, then save the reviewed layout.",
        )
    return max(references, key=lambda path: path.stat().st_mtime)


def _start_video_job(upload_path: Path, *, db, user_id: int, byte_count: int,
                    lot_slug: str, camera_id: str, content_type: str,
                    layout_snapshot: dict, reference_path: Path) -> dict:
    cloud_mode = cloud_video_detection_enabled()
    try:
        if cloud_mode:
            return start_cloud_video_detection(
                db, user_id=user_id, video_path=upload_path,
                byte_count=byte_count, lot_slug=lot_slug, camera_id=camera_id,
                content_type=content_type, layout=layout_snapshot,
                reference_path=reference_path,
            )
        return video_detection_jobs.start(upload_path, lot_slug, camera_id, reference_path)
    finally:
        if cloud_mode:
            upload_path.unlink(missing_ok=True)


@router.post("/jobs", status_code=202)
async def start_video_detection(
    request: Request,
    lot_slug: str,
    camera_id: str = "default",
    filename: str = Query(min_length=1, max_length=255),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not _SCOPE_PART.fullmatch(lot_slug) or not _SCOPE_PART.fullmatch(camera_id):
        raise HTTPException(status_code=422, detail="Lot slug and camera ID may contain letters, digits, '_' and '-' only")
    lot = db.query(ParkingLot).filter(ParkingLot.slug == lot_slug).first()
    if lot is None:
        raise HTTPException(status_code=404, detail="Parking lot not found")
    try:
        layout_snapshot = load_layout(lot_slug, camera_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=f"No valid saved layout exists for this lot and camera: {exc}") from exc
    reference_path = _reference_image(lot_slug, camera_id)
    if simulator_detection_jobs.has_active_job():
        raise HTTPException(status_code=409, detail="Stop simulator detection before starting video detection")
    if cloud_video_detection_enabled() and has_active_video_job(db):
        raise HTTPException(status_code=409, detail="Another video detection is already running")

    content_type = request.headers.get("content-type", "application/octet-stream").split(";", 1)[0].lower()
    suffix = Path(filename).suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        suffix = _MIME_SUFFIXES.get(content_type, "")
    if suffix not in _SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Upload an MP4, MOV, AVI, MKV, or WebM video")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    byte_count = 0
    try:
        with upload_path.open("wb") as destination:
            async for chunk in request.stream():
                byte_count += len(chunk)
                if byte_count > MAX_VIDEO_BYTES:
                    raise HTTPException(status_code=413, detail="Video must be 500 MB or smaller")
                destination.write(chunk)
    except Exception:
        upload_path.unlink(missing_ok=True)
        raise
    if byte_count == 0:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="The uploaded video is empty")

    try:
        job = _start_video_job(
            upload_path, db=db, user_id=current_user.user_id, byte_count=byte_count,
            lot_slug=lot_slug, camera_id=camera_id, content_type=content_type,
            layout_snapshot=layout_snapshot, reference_path=reference_path,
        )
        record_event(
            db, request, "video_detection.started",
            f"Started video detection for lot {lot_slug}, camera {camera_id}.",
            current_user.user_id,
        )
        db.commit()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return job


@router.get("/jobs/{job_id}")
def get_video_detection_job(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if cloud_video_detection_enabled():
        job = get_persistent_video_job(db, job_id, current_user.user_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Video detection job not found")
        return job
    job = video_detection_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Video detection job not found")
    return job


@router.get("/jobs/{job_id}/frame")
def get_video_detection_frame(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if cloud_video_detection_enabled():
        job = db.query(VideoDetectionJob).filter(
            VideoDetectionJob.job_id == job_id, VideoDetectionJob.user_id == current_user.user_id
        ).first()
        if job is None or not job.frame_object or not job.frame_available:
            raise HTTPException(status_code=404, detail="No annotated frame is available yet")
        try:
            frame = cloud_storage.download_bytes(job.frame_object)
        except Exception as exc:
            raise HTTPException(status_code=404, detail="No annotated frame is available yet") from exc
        return Response(content=frame, media_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Frame-Available": "true"})
    frame = video_detection_jobs.frame(job_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="No annotated frame is available yet")
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Frame-Available": "true"},
    )


@router.post("/jobs/{job_id}/stop")
def stop_video_detection_job(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if cloud_video_detection_enabled():
        job = stop_persistent_video_job(db, job_id, current_user.user_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Video detection job not found")
        return job
    job = video_detection_jobs.stop(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Video detection job not found")
    return job


@router.get("/jobs/{job_id}/result")
def get_video_detection_result(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if cloud_video_detection_enabled():
        job = db.query(VideoDetectionJob).filter(
            VideoDetectionJob.job_id == job_id, VideoDetectionJob.user_id == current_user.user_id
        ).first()
        if job is None:
            raise HTTPException(status_code=404, detail="Video detection job not found")
        if job.status not in {"completed", "stopped"} or not job.result_object:
            raise HTTPException(status_code=409, detail="The annotated video is not ready yet")
        try:
            response = cloud_storage.stream_download(job.result_object)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Could not retrieve the annotated video") from exc
        return StreamingResponse(
            response.iter_content(chunk_size=1024 * 1024), media_type="video/mp4",
            headers={"Content-Disposition": f'attachment; filename="parking-detection-{job_id[:8]}.mp4"'},
            background=BackgroundTask(response.close),
        )
    result_path = video_detection_jobs.result_path(job_id)
    if result_path is None:
        raise HTTPException(status_code=409, detail="The annotated video is not ready yet")
    return FileResponse(result_path, media_type="video/mp4", filename=f"parking-detection-{job_id[:8]}.mp4")
