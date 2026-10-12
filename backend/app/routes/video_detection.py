import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models.lots import ParkingLot
from app.models.users import User
from app.services.audit import record_event
from app.services.video_detection import DETECTION_DIR, video_detection_jobs
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
        load_layout(lot_slug, camera_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=f"No valid saved layout exists for this lot and camera: {exc}") from exc
    reference_path = _reference_image(lot_slug, camera_id)
    if simulator_detection_jobs.has_active_job():
        raise HTTPException(status_code=409, detail="Stop simulator detection before starting video detection")

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

    record_event(
        db,
        request,
        "video_detection.started",
        f"Started video detection for lot {lot_slug}, camera {camera_id}.",
        current_user.user_id,
    )
    db.commit()
    try:
        job = video_detection_jobs.start(upload_path, lot_slug, camera_id, reference_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return job


@router.get("/jobs/{job_id}")
def get_video_detection_job(job_id: str, current_user: User = Depends(require_admin)):
    job = video_detection_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Video detection job not found")
    return job


@router.get("/jobs/{job_id}/frame")
def get_video_detection_frame(job_id: str, current_user: User = Depends(require_admin)):
    frame = video_detection_jobs.frame(job_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="No annotated frame is available yet")
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Frame-Available": "true"},
    )


@router.post("/jobs/{job_id}/stop")
def stop_video_detection_job(job_id: str, current_user: User = Depends(require_admin)):
    job = video_detection_jobs.stop(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Video detection job not found")
    return job


@router.get("/jobs/{job_id}/result")
def get_video_detection_result(job_id: str, current_user: User = Depends(require_admin)):
    result_path = video_detection_jobs.result_path(job_id)
    if result_path is None:
        raise HTTPException(status_code=409, detail="The annotated video is not ready yet")
    return FileResponse(result_path, media_type="video/mp4", filename=f"parking-detection-{job_id[:8]}.mp4")
