from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fare_history import FareHistory
from app.models.history import ParkingHistory
from app.models.lots import ParkingLot
from app.models.parking import ParkingRecord


def validate_lot(db: Session, lot_id: int | None) -> None:
    if lot_id is not None and db.query(ParkingLot.lot_id).filter(ParkingLot.lot_id == lot_id).first() is None:
        raise HTTPException(status_code=404, detail="Parking lot not found")


def get_session_rows(
    db: Session,
    user_id: int | None = None,
    lot_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    search: str | None = None,
):
    query = db.query(ParkingHistory, ParkingRecord, ParkingLot).join(
        ParkingRecord, ParkingRecord.parking_id == ParkingHistory.parking_id
    ).join(ParkingLot, ParkingLot.lot_id == ParkingHistory.lot_id)
    if user_id is not None:
        query = query.filter(ParkingHistory.user_id == user_id)
    if lot_id is not None:
        query = query.filter(ParkingHistory.lot_id == lot_id)
    if start_date is not None:
        query = query.filter(ParkingHistory.time_arrived >= start_date)
    if end_date is not None:
        query = query.filter(ParkingHistory.time_arrived <= end_date)
    if search:
        query = query.filter(ParkingRecord.slot_number.ilike(f"%{search.strip()}%"))
    return query.order_by(ParkingHistory.time_arrived.desc(), ParkingHistory.history_id.desc()).all()


def recorded_fare(db: Session, history: ParkingHistory) -> Decimal:
    if history.time_left is not None:
        return Decimal(str(history.fare_charged or 0))
    amount = db.query(func.coalesce(func.sum(FareHistory.charge), 0)).filter(
        FareHistory.history_id == history.history_id,
        FareHistory.lot_id == history.lot_id,
    ).scalar()
    return Decimal(str(amount or 0))


def serialize_session(db: Session, row) -> dict:
    history, parking, lot = row
    elapsed = None
    if history.duration is not None:
        elapsed = float(history.duration)
    elif history.time_left is not None:
        elapsed = (history.time_left - history.time_arrived).total_seconds() / 3600
    else:
        elapsed = (datetime.now() - history.time_arrived).total_seconds() / 3600
    return {
        "history_id": history.history_id,
        "lot_id": history.lot_id,
        "parking_lot": lot.name,
        "parking_id": history.parking_id,
        "space_id": parking.slot_number,
        "status": "active" if history.time_left is None else "completed",
        "recorded_start": history.time_arrived,
        "recorded_start_note": "Recorded occupancy start; this may be when the detector first observed the space occupied, not the vehicle's actual arrival.",
        "departure_time": history.time_left,
        "duration_hours": max(0.0, elapsed),
        "average_rate": float(history.average_rate) if history.average_rate is not None else None,
        "recorded_fare": float(recorded_fare(db, history)),
    }


def validate_date_range(start_date: datetime | None, end_date: datetime | None) -> None:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be earlier than or equal to end_date")


def build_report(db: Session, rows: list, lots: list[ParkingLot], selected_lot_id: int | None) -> dict:
    sessions = [serialize_session(db, row) for row in rows]
    all_spaces = []
    for lot in lots:
        if selected_lot_id is not None and lot.lot_id != selected_lot_id:
            continue
        spaces = db.query(ParkingRecord).filter(ParkingRecord.lot_id == lot.lot_id).all()
        all_spaces.extend((lot, space) for space in spaces)

    lot_usage = {}
    space_usage = {}
    daily_usage = {}
    for item in sessions:
        lot_name = item["parking_lot"]
        lot_usage[lot_name] = lot_usage.get(lot_name, 0) + 1
        space_key = f'{lot_name} / {item["space_id"]}'
        space_usage[space_key] = space_usage.get(space_key, 0) + 1
        day_key = item["recorded_start"].date().isoformat()
        daily_usage[day_key] = daily_usage.get(day_key, 0) + 1

    vacant = sum(1 for _, space in all_spaces if space.status == "vacant")
    occupied = sum(1 for _, space in all_spaces if space.status == "occupied")
    total_spaces = len(all_spaces)
    return {
        "total_lots": sum(1 for lot in lots if selected_lot_id is None or lot.lot_id == selected_lot_id),
        "total_spaces": total_spaces,
        "vacant_spaces": vacant,
        "occupied_spaces": occupied,
        "occupancy_percentage": round(occupied / total_spaces * 100, 2) if total_spaces else 0.0,
        "total_sessions": len(sessions),
        "total_recorded_duration_hours": round(sum(item["duration_hours"] for item in sessions), 4),
        "total_recorded_charges": round(sum(item["recorded_fare"] for item in sessions), 2),
        "sessions": sessions,
        "lot_usage": [{"parking_lot": name, "session_count": count} for name, count in sorted(lot_usage.items())],
        "space_usage": [{"space": name, "session_count": count} for name, count in sorted(space_usage.items())],
        "activity_over_time": [{"date": day, "session_count": count} for day, count in sorted(daily_usage.items())],
    }
