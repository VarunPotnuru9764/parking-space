import re
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Reuse the detection package's canonical validator and lot/camera path manager.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from detection.layout.layout_manager import load_layout, save_layout, validate_layout

router = APIRouter(prefix="/layouts", tags=["Parking layouts"])
_SCOPE_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


def _validate_scope(lot_slug: str, camera_id: str):
    if not _SCOPE_PART.fullmatch(lot_slug) or not _SCOPE_PART.fullmatch(camera_id):
        raise HTTPException(status_code=422, detail="Lot slug and camera ID may contain letters, digits, '_' and '-' only")


class LayoutSpace(BaseModel):
    slot_number: str
    polygon: list[list[float]] = Field(min_length=3)

    model_config = {"extra": "forbid"}


class LayoutPayload(BaseModel):
    spaces: list[LayoutSpace] = Field(min_length=1)


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
    image_width: int = Query(gt=0),
    image_height: int = Query(gt=0),
):
    _validate_scope(lot_slug, camera_id)
    try:
        data = layout.model_dump()
        validate_layout(data, image_size=(image_width, image_height))
        save_layout(data, lot_slug, camera_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"saved": True, "lot_slug": lot_slug, "camera_id": camera_id, "space_count": len(layout.spaces)}
