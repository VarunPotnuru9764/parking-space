from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password, verify_password
from app.database import get_db
from app.models.audit import AuditEvent
from app.models.lots import ParkingLot
from app.models.users import User
from app.schemas.admin import PasswordChange
from app.services.audit import record_event
from app.services.reporting import (
    build_report,
    get_session_rows,
    serialize_session,
    validate_date_range,
    validate_lot,
)

router = APIRouter(prefix="/users/me", tags=["User account"])


@router.get("/parking")
def get_active_parking(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = get_session_rows(db, user_id=current_user.user_id)
    active_rows = [row for row in rows if row[0].time_left is None]
    return {"active_sessions": [serialize_session(db, row) for row in active_rows]}


@router.get("/history")
def get_my_parking_history(
    lot_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    search: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_date_range(start_date, end_date)
    validate_lot(db, lot_id)
    rows = get_session_rows(db, current_user.user_id, lot_id, start_date, end_date, search)
    return {
        "items": [serialize_session(db, row) for row in rows[offset:offset + limit]],
        "total": len(rows),
        "offset": offset,
        "limit": limit,
    }


@router.get("/reports")
def get_my_reports(
    lot_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_date_range(start_date, end_date)
    validate_lot(db, lot_id)
    rows = get_session_rows(db, current_user.user_id, lot_id, start_date, end_date)
    lots_query = db.query(ParkingLot)
    if lot_id is not None:
        lots_query = lots_query.filter(ParkingLot.lot_id == lot_id)
    report = build_report(db, rows, lots_query.all(), lot_id)
    return {
        "total_sessions": report["total_sessions"],
        "total_recorded_duration_hours": report["total_recorded_duration_hours"],
        "total_recorded_charges": report["total_recorded_charges"],
        "activity_over_time": report["activity_over_time"],
    }


@router.get("/login-activity")
def get_my_login_activity(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AuditEvent).filter(
        AuditEvent.event_type.in_(("login.success", "login.failed")),
        (AuditEvent.actor_user_id == current_user.user_id) | (AuditEvent.email == current_user.email),
    ).order_by(AuditEvent.created_at.desc(), AuditEvent.event_id.desc())
    total = query.count()
    return {
        "items": [{
            "event_id": event.event_id,
            "timestamp": event.created_at,
            "successful": event.success,
            "account_email": event.email,
            "client_ip": event.client_ip,
            "user_agent": event.user_agent,
        } for event in query.offset(offset).limit(limit).all()],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.put("/password")
def change_my_password(
    payload: PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = hash_password(payload.new_password)
    record_event(db, request, "account.password_changed", "Account password changed.", current_user.user_id, current_user.email)
    db.commit()
    return {"message": "Password changed successfully"}
