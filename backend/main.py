import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, SessionLocal, engine
from app.config import get_setting
from app.models.users import User
from app.models.parking import ParkingRecord
from app.models.lots import ParkingLot
from app.models.fares import FareRule
from app.models.history import ParkingHistory
from app.models.fare_history import FareHistory
from app.models.audit import AuditEvent, EmailChallenge, PasswordResetToken, UserSecurity
from app.models.detection_job import DetectionJob
from app.models.video_detection_job import VideoDetectionJob, VideoDetectionSlot
from app.routes.parking import router as parking_router
from app.routes.claim import router as claim_router
from app.routes.auth import router as auth_router
from app.routes.lots import router as lots_router
from app.routes.layouts import router as layouts_router
from app.routes.users import router as users_router
from app.routes.admin import router as admin_router
from app.routes.video_detection import router as video_detection_router
from app.routes.simulator_detection import router as simulator_detection_router
from app.services.simulator_detection import simulator_detection_jobs
from app.scheduler import fare_scheduler
from app.services.audit import record_event

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_task = asyncio.create_task(fare_scheduler())

    try:
        yield
    finally:
        simulator_detection_jobs.shutdown()
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass

Base.metadata.create_all(bind=engine)
app = FastAPI(lifespan = lifespan)
configured_origins = get_setting(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
allowed_origins = [
    origin.strip().rstrip("/")
    for origin in (configured_origins or "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Detection-Token"],
)

@app.middleware("http")
async def capture_http_warnings(request: Request, call_next):
    response = await call_next(request)
    is_auth_failure_logged_by_route = request.url.path in {"/auth/login", "/auth/mfa/verify"}
    should_record = response.status_code >= 500 or response.status_code in {403, 409, 422, 429}
    should_record = should_record or (response.status_code == 401 and not is_auth_failure_logged_by_route)
    if should_record:
        event_type = "system.error" if response.status_code >= 500 else "system.warning"
        db = SessionLocal()
        try:
            record_event(
                db,
                request,
                event_type,
                f"{request.method} {request.url.path} returned HTTP {response.status_code}.",
                success=False,
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logging.exception("Unable to persist HTTP warning/error audit event")
        finally:
            db.close()
    return response

app.include_router(parking_router)
app.include_router(claim_router)
app.include_router(auth_router)
app.include_router(lots_router)
app.include_router(layouts_router)
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(video_detection_router)
app.include_router(simulator_detection_router)

@app.get("/")
def root():
    return {"message": "Parking Space Detection System API is running"}


@app.get("/health/ready", tags=["Health"])
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logging.warning("Readiness check failed because the database is unavailable")
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ready", "database": "available"}
