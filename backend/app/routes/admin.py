from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models.audit import AuditEvent, UserSecurity
from app.models.fares import FareRule
from app.models.lots import ParkingLot
from app.models.users import User
from app.schemas.admin import FareRuleCreate, FareRuleUpdate
from app.services.audit import record_event
from app.services.reporting import build_report, get_session_rows, validate_date_range, validate_lot

router = APIRouter(prefix="/admin", tags=["Administrator"])


def _fare_rule_view(rule: FareRule) -> dict:
    return {
        "rule_id": rule.rule_id,
        "lot_id": rule.lot_id,
        "rule_name": rule.rule_name,
        "base_rate": float(rule.base_rate),
        "min_occupancy": float(rule.min_occupancy),
        "max_occupancy": float(rule.max_occupancy),
        "occupancy_multiplier": float(rule.occupancy_multiplier),
        "peak_multiplier": float(rule.peak_multiplier),
        "start_time": rule.start_time,
        "end_time": rule.end_time,
        "active": rule.active,
    }


def _ensure_no_occupancy_overlap(db: Session, lot_id: int, minimum: float, maximum: float, exclude_rule_id: int | None = None) -> None:
    query = db.query(FareRule).filter(FareRule.lot_id == lot_id)
    if exclude_rule_id is not None:
        query = query.filter(FareRule.rule_id != exclude_rule_id)
    for rule in query.all():
        if minimum <= float(rule.max_occupancy) and float(rule.min_occupancy) <= maximum:
            raise HTTPException(
                status_code=409,
                detail=f"Occupancy range overlaps fare rule '{rule.rule_name}'. The fare engine requires unambiguous occupancy ranges.",
            )


@router.get("/fare-rules")
def list_fare_rules(
    lot_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    validate_lot(db, lot_id)
    query = db.query(FareRule)
    if lot_id is not None:
        query = query.filter(FareRule.lot_id == lot_id)
    return [_fare_rule_view(rule) for rule in query.order_by(FareRule.lot_id, FareRule.min_occupancy).all()]


@router.post("/fare-rules", status_code=201)
def create_fare_rule(
    payload: FareRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    validate_lot(db, payload.lot_id)
    _ensure_no_occupancy_overlap(db, payload.lot_id, payload.min_occupancy, payload.max_occupancy)
    rule = FareRule(**payload.model_dump())
    db.add(rule)
    record_event(db, request, "fare_rule.created", f"Created fare rule '{payload.rule_name}' for lot {payload.lot_id}.", current_user.user_id)
    db.commit()
    db.refresh(rule)
    return _fare_rule_view(rule)


@router.patch("/fare-rules/{rule_id}")
def update_fare_rule(
    rule_id: int,
    payload: FareRuleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    rule = db.query(FareRule).filter(FareRule.rule_id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Fare rule not found")
    updates = payload.model_dump(exclude_unset=True)
    if "active" in updates:
        raise HTTPException(status_code=422, detail="'active' is maintained by the fare engine and cannot be changed directly")
    candidate_minimum = updates.get("min_occupancy", float(rule.min_occupancy))
    candidate_maximum = updates.get("max_occupancy", float(rule.max_occupancy))
    if candidate_minimum > candidate_maximum:
        raise HTTPException(status_code=422, detail="min_occupancy must not exceed max_occupancy")
    candidate_start = updates.get("start_time", rule.start_time)
    candidate_end = updates.get("end_time", rule.end_time)
    if (candidate_start is None) != (candidate_end is None):
        raise HTTPException(status_code=422, detail="start_time and end_time must be provided together")
    _ensure_no_occupancy_overlap(db, rule.lot_id, candidate_minimum, candidate_maximum, rule.rule_id)
    for name, value in updates.items():
        setattr(rule, name, value)
    record_event(db, request, "fare_rule.updated", f"Updated fare rule '{rule.rule_name}' (ID {rule.rule_id}).", current_user.user_id)
    db.commit()
    db.refresh(rule)
    return _fare_rule_view(rule)


@router.get("/users")
def list_users(
    search: str | None = Query(default=None, max_length=150),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = db.query(User)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter((User.name.ilike(term)) | (User.email.ilike(term)))
    total = query.count()
    users = query.order_by(User.created_at.desc(), User.user_id.desc()).offset(offset).limit(limit).all()
    security = {
        entry.user_id: entry.mfa_enabled
        for entry in db.query(UserSecurity).filter(UserSecurity.user_id.in_([user.user_id for user in users])).all()
    } if users else {}
    return {
        "items": [{
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at,
            "mfa_enabled": security.get(user.user_id, False),
        } for user in users],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/users/{user_id}")
def get_user_details(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    security = db.query(UserSecurity).filter(UserSecurity.user_id == user_id).first()
    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
        "mfa_enabled": bool(security and security.mfa_enabled),
    }


@router.get("/reports")
def get_admin_reports(
    lot_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    validate_date_range(start_date, end_date)
    validate_lot(db, lot_id)
    rows = get_session_rows(db, lot_id=lot_id, start_date=start_date, end_date=end_date)
    lots_query = db.query(ParkingLot)
    if lot_id is not None:
        lots_query = lots_query.filter(ParkingLot.lot_id == lot_id)
    lots = lots_query.order_by(ParkingLot.lot_id).all()
    return build_report(db, rows, lots, lot_id)


def _events_response(query, offset: int, limit: int) -> dict:
    total = query.count()
    events = query.order_by(AuditEvent.created_at.desc(), AuditEvent.event_id.desc()).offset(offset).limit(limit).all()
    return {
        "items": [{
            "event_id": event.event_id,
            "timestamp": event.created_at,
            "event_type": event.event_type,
            "description": event.description,
            "successful": event.success,
            "actor_user_id": event.actor_user_id,
            "account_email": event.email,
            "client_ip": event.client_ip,
            "user_agent": event.user_agent,
        } for event in events],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/activity")
def get_activity_logs(
    event_type: str | None = Query(default=None, max_length=60),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    validate_date_range(start_date, end_date)
    validate_date_range(start_date, end_date)
    query = db.query(AuditEvent)
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)
    if start_date is not None:
        query = query.filter(AuditEvent.created_at >= start_date)
    if end_date is not None:
        query = query.filter(AuditEvent.created_at <= end_date)
    return _events_response(query, offset, limit)


@router.get("/login-activity")
def get_login_activity(
    email: str | None = Query(default=None, max_length=150),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    validate_date_range(start_date, end_date)
    query = db.query(AuditEvent).filter(AuditEvent.event_type.in_(("login.success", "login.failed")))
    if email:
        query = query.filter(AuditEvent.email.ilike(f"%{email.strip()}%"))
    if start_date is not None:
        query = query.filter(AuditEvent.created_at >= start_date)
    if end_date is not None:
        query = query.filter(AuditEvent.created_at <= end_date)
    return _events_response(query, offset, limit)
