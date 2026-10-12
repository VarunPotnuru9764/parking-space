import asyncio
import re
import sys
from functools import lru_cache
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from app.auth import require_admin
from app.models.users import User
from app.database import get_db
from app.services.audit import record_event
from sqlalchemy.orm import Session
from app.models.lots import ParkingLot

# Reuse the detection package's canonical validator and lot/camera path manager.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from detection.layout.layout_manager import LAYOUT_FILE, load_layout, save_layout, validate_layout
from detection.layout.pretrained_layout_detector import PretrainedParkingSpaceDetector

router = APIRouter(prefix="/layouts", tags=["Parking layouts"])
_SCOPE_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
MAX_LAYOUT_IMAGE_BYTES = 20 * 1024 * 1024
MODEL_PATH = PROJECT_ROOT / "detection" / "models" / "parking_lot.pt"
LAYOUT_ROOT = PROJECT_ROOT / "detection" / "layout" / "layouts"
_detector_lock = Lock()


@lru_cache(maxsize=1)
def _candidate_detector():
    return PretrainedParkingSpaceDetector(MODEL_PATH, confidence=0.25)


def _validate_scope(lot_slug: str, camera_id: str):
    if not _SCOPE_PART.fullmatch(lot_slug) or not _SCOPE_PART.fullmatch(camera_id):
        raise HTTPException(status_code=422, detail="Lot slug and camera ID may contain letters, digits, '_' and '-' only")


def _save_reference_photo(lot_slug: str, camera_id: str, content_type: str, request_body: bytes):
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/bmp": ".bmp"}[content_type]
    reference_dir = LAYOUT_ROOT / lot_slug.lower()
    reference_dir.mkdir(parents=True, exist_ok=True)
    reference_path = reference_dir / f"{camera_id.lower()}.reference{suffix}"
    for previous_reference in reference_dir.glob(f"{camera_id.lower()}.reference.*"):
        if previous_reference != reference_path and previous_reference.suffix.lower() in {".jpg", ".png", ".webp", ".bmp"}:
            previous_reference.unlink(missing_ok=True)
    temporary_path = reference_dir / f"reference{suffix}.tmp"
    temporary_path.write_bytes(request_body)
    temporary_path.replace(reference_path)


class LayoutSpace(BaseModel):
    slot_number: str
    polygon: list[list[float]] = Field(min_length=3)

    model_config = {"extra": "forbid"}


class LayoutPayload(BaseModel):
    spaces: list[LayoutSpace] = Field(min_length=1)


@router.post("/{lot_slug}/{camera_id}/candidates")
async def generate_layout_candidates(
    lot_slug: str,
    camera_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Run the configured parking-space model and return an editor review bundle."""
    _validate_scope(lot_slug, camera_id)
    lot = db.query(ParkingLot).filter(ParkingLot.slug == lot_slug).first()
    if lot is None:
        raise HTTPException(status_code=404, detail="Parking lot not found")

    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type not in {"image/jpeg", "image/png", "image/webp", "image/bmp"}:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, WebP, or BMP image")
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_LAYOUT_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 20 MB or smaller")
    # Read once and enforce the limit even when the caller omits Content-Length.
    request_body = await request.body()
    if len(request_body) > MAX_LAYOUT_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 20 MB or smaller")
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Layout inference is not installed on the backend. Install the updated backend requirements and restart it.",
        ) from exc
    image = cv2.imdecode(np.frombuffer(request_body, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=422, detail="Could not decode the uploaded image")

    try:
        candidates = await asyncio.to_thread(_run_candidate_detection, image)
    except (RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not generate layout candidates: {exc}") from exc

    _save_reference_photo(lot_slug, camera_id, content_type, request_body)

    record_event(
        db,
        request,
        "layout.candidates_generated",
        f"Generated {len(candidates)} layout candidates for {lot_slug}/{camera_id}.",
        current_user.user_id,
    )
    db.commit()
    return {
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


@router.post("/{lot_slug}/{camera_id}/reference")
async def save_camera_reference(
    lot_slug: str,
    camera_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Save the original camera photo used to define the reviewed layout."""
    _validate_scope(lot_slug, camera_id)
    lot = db.query(ParkingLot).filter(ParkingLot.slug == lot_slug).first()
    if lot is None:
        raise HTTPException(status_code=404, detail="Parking lot not found")

    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type not in {"image/jpeg", "image/png", "image/webp", "image/bmp"}:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, WebP, or BMP image")
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_LAYOUT_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 20 MB or smaller")
    request_body = await request.body()
    if not request_body:
        raise HTTPException(status_code=422, detail="The reference photo is empty")
    if len(request_body) > MAX_LAYOUT_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 20 MB or smaller")
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Image support is unavailable on the backend") from exc
    image = cv2.imdecode(np.frombuffer(request_body, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=422, detail="Could not decode the uploaded image")

    _save_reference_photo(lot_slug, camera_id, content_type, request_body)
    record_event(
        db,
        request,
        "layout.reference_saved",
        f"Saved reference photo for {lot_slug}/{camera_id}.",
        current_user.user_id,
    )
    db.commit()
    return {"saved": True, "lot_slug": lot_slug, "camera_id": camera_id}


def _run_candidate_detection(image):
    with _detector_lock:
        return _candidate_detector().detect(image)


@router.get("/{lot_slug}")
def list_camera_layouts(lot_slug: str):
    """List the saved camera layouts available to the customer map."""
    if not _SCOPE_PART.fullmatch(lot_slug):
        raise HTTPException(status_code=422, detail="Lot slug may contain letters, digits, '_' and '-' only")
    lot_dir = LAYOUT_ROOT / lot_slug.lower()
    cameras = set(path.stem for path in lot_dir.glob("*.json")) if lot_dir.is_dir() else set()
    # The original simulator layout predates lot-scoped files. Keep exposing it
    # as the simulator's default camera so layout discovery can find it too.
    if lot_slug.lower() == "simulator" and LAYOUT_FILE.is_file():
        cameras.add("default")
    return {"lot_slug": lot_slug, "cameras": sorted(cameras)}


@router.get("/{lot_slug}/{camera_id}")
def get_camera_layout(lot_slug: str, camera_id: str):
    _validate_scope(lot_slug, camera_id)
    try:
        return load_layout(lot_slug, camera_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No saved layout exists for this lot and camera")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.put("/{lot_slug}/{camera_id}")
def put_camera_layout(
    lot_slug: str,
    camera_id: str,
    layout: LayoutPayload,
    request: Request,
    image_width: int = Query(gt=0),
    image_height: int = Query(gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _validate_scope(lot_slug, camera_id)
    try:
        data = layout.model_dump()
        validate_layout(data, image_size=(image_width, image_height))
        save_layout(data, lot_slug, camera_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    record_event(db, request, "layout.updated", f"Saved parking layout for {lot_slug}/{camera_id} with {len(layout.spaces)} spaces.", current_user.user_id)
    db.commit()
    return {"saved": True, "lot_slug": lot_slug, "camera_id": camera_id, "space_count": len(layout.spaces)}
