from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models.lots import ParkingLot
from app.models.users import User
from app.services.audit import record_event
from app.services.simulator_detection import simulator_detection_jobs
from app.services.video_detection import has_active_video_job
from detection.layout.layout_manager import load_layout


router = APIRouter(prefix="/simulator-detection", tags=["Simulator detection"])


@router.post("/jobs", status_code=202)
def start_simulator_detection(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    lot = db.query(ParkingLot).filter(ParkingLot.slug == "simulator").first()
    if lot is None:
        raise HTTPException(status_code=409, detail="Create the Simulator parking lot before starting simulator detection")
    try:
        load_layout("simulator", "default")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=f"The Simulator lot needs a valid default layout: {exc}") from exc
    if has_active_video_job(db):
        raise HTTPException(status_code=409, detail="Stop the current video detection before starting simulator detection")
    try:
        job = simulator_detection_jobs.start()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Could not start the simulator: {exc}") from exc
    record_event(db, request, "simulator_detection.started", "Started simulator live detection.", current_user.user_id)
    db.commit()
    return job


@router.get("/jobs/active")
def get_active_simulator_detection_job(current_user: User = Depends(require_admin)):
    return {"job": simulator_detection_jobs.active()}


@router.get("/jobs/{job_id}")
def get_simulator_detection_job(job_id: str, current_user: User = Depends(require_admin)):
    job = simulator_detection_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Simulator detection job not found")
    return job


@router.get("/jobs/{job_id}/frame")
def get_simulator_detection_frame(job_id: str, current_user: User = Depends(require_admin)):
    frame = simulator_detection_jobs.frame(job_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="No annotated simulator frame is available yet")
    return Response(content=frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/jobs/{job_id}/spawn")
def spawn_simulator_car(job_id: str, current_user: User = Depends(require_admin)):
    try:
        accepted = simulator_detection_jobs.spawn_car(job_id)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="The simulator control service is unavailable") from exc
    if accepted is None:
        raise HTTPException(status_code=404, detail="Simulator detection job is not running")
    return {"accepted": accepted}


@router.post("/jobs/{job_id}/leave")
def send_simulator_car_out(
    job_id: str,
    slot_number: str = Query(min_length=1, max_length=20),
    current_user: User = Depends(require_admin),
):
    try:
        accepted = simulator_detection_jobs.send_car_out(job_id, slot_number)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="The simulator control service is unavailable") from exc
    if accepted is None:
        raise HTTPException(status_code=404, detail="Simulator detection job is not running")
    return {"accepted": accepted}


@router.post("/jobs/{job_id}/stop")
def stop_simulator_detection_job(job_id: str, current_user: User = Depends(require_admin)):
    job = simulator_detection_jobs.stop(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Simulator detection job not found")
    return job
