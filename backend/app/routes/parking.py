from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_admin, require_admin_or_detection_token
from app.models.parking import ParkingRecord
from app.models.history import ParkingHistory
from app.models.fare_history import FareHistory
from app.models.lots import ParkingLot

from app.schemas.parking import (ParkingCreate, ParkingResponse, ParkingStatusUpdate)
from app.services.fare_engine import (calculate_occupancy, select_fare_rule, generate_fare_interval)

from app.schemas.parking import ParkingBulkCreate, ParkingBulkResult
from app.services.audit import record_event
from decimal import Decimal
from datetime import datetime
import secrets
router = APIRouter(prefix="/parking", tags=["Parking"])

def resolve_lot(db: Session, lot_id: int | None) -> ParkingLot:
    lot = db.query(ParkingLot).filter(
        ParkingLot.lot_id == lot_id if lot_id is not None else ParkingLot.slug == "simulator"
    ).first()
    if lot is None:
        raise HTTPException(status_code=404, detail="Parking lot not found; specify a valid lot_id")
    return lot

@router.get("/", response_model = list[ParkingResponse])
def get_parking_spaces(lot_id: int | None = None, db: Session = Depends(get_db)):
    lot = resolve_lot(db, lot_id)
    parking_spaces = db.query(ParkingRecord).filter(ParkingRecord.lot_id == lot.lot_id).all()
    return parking_spaces

@router.post("/", response_model = ParkingResponse, status_code = 201)
def create_parking_space(parking: ParkingCreate, request: Request, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    lot = resolve_lot(db, parking.lot_id)
    existing_parking = db.query(ParkingRecord).filter(
        ParkingRecord.lot_id == lot.lot_id,
        ParkingRecord.slot_number == parking.slot_number
    ).first()
    if existing_parking is not None:
        raise HTTPException(
            status_code = 409,
            detail = "A parking space with this slot number already exists"
        )
    
    new_parking = ParkingRecord(
        lot_id = lot.lot_id,
        slot_number = parking.slot_number,
        location = parking.location,
        claim_code = parking.claim_code,
        current_rate = parking.current_rate
    )
    try:
        db.add(new_parking)
        db.flush()
        record_event(db, request, "parking_space.created", f"Created parking space '{new_parking.slot_number}' in lot {lot.lot_id}.", current_user.user_id)
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Parking slot or claim code already exists")
    
    return new_parking

@router.post("/bulk", response_model=ParkingBulkResult, status_code=201)
def create_parking_spaces_bulk(payload: ParkingBulkCreate, request: Request, db: Session = Depends(get_db), actor = Depends(require_admin_or_detection_token)):
    lot = resolve_lot(db, payload.lot_id)
    requested_slots = [space.slot_number for space in payload.spaces]
    if len(set(requested_slots)) != len(requested_slots):
        raise HTTPException(status_code=400, detail="Bulk request contains duplicate slot numbers")
    existing = {
        slot for (slot,) in db.query(ParkingRecord.slot_number).filter(
            ParkingRecord.lot_id == lot.lot_id,
            ParkingRecord.slot_number.in_(requested_slots),
        ).all()
    }
    new_records = [
        ParkingRecord(
            lot_id=lot.lot_id,
            slot_number=space.slot_number,
            location=space.location,
            claim_code=secrets.token_urlsafe(15)[:20],
            current_rate=space.current_rate,
        )
        for space in payload.spaces if space.slot_number not in existing
    ]
    db.add_all(new_records)
    try:
        db.commit()
        for record in new_records:
            db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A concurrent slot or claim-code conflict occurred; retry sync")
    if new_records:
        actor_user_id = actor.user_id if actor is not None else None
        record_event(db, request, "parking.spaces_bulk_created", f"Detection sync created {len(new_records)} parking spaces in lot {lot.lot_id}.", actor_user_id)
        db.commit()
    records = db.query(ParkingRecord).filter(
        ParkingRecord.lot_id == lot.lot_id,
        ParkingRecord.slot_number.in_(requested_slots),
    ).all()
    by_slot = {record.slot_number: record for record in records}
    return {
        "spaces": [by_slot[slot] for slot in requested_slots],
        "new_claim_codes": {record.slot_number: record.claim_code for record in new_records},
    }


@router.post("/occupancy/clear")
def clear_lot_occupancy(
    request: Request,
    lot_id: int,
    db: Session = Depends(get_db),
    actor = Depends(require_admin_or_detection_token),
):
    """Mark every space in one lot vacant and close any open parking sessions."""
    lot = resolve_lot(db, lot_id)
    current_time = datetime.now()
    occupancy = calculate_occupancy(db, lot.lot_id)
    fare_result = select_fare_rule(occupancy, current_time, lot.lot_id, db)
    spaces = db.query(ParkingRecord).filter(ParkingRecord.lot_id == lot.lot_id).all()
    vacated_count = 0

    for space in spaces:
        if space.status == "occupied":
            vacated_count += 1
            history = db.query(ParkingHistory).filter(
                ParkingHistory.lot_id == lot.lot_id,
                ParkingHistory.parking_id == space.parking_id,
                ParkingHistory.time_left.is_(None),
            ).order_by(ParkingHistory.time_arrived.desc()).first()
            if history is not None:
                if fare_result is not None:
                    last_fare = db.query(FareHistory).filter(
                        FareHistory.history_id == history.history_id,
                        FareHistory.lot_id == lot.lot_id,
                    ).order_by(FareHistory.interval_end.desc()).first()
                    interval_start = last_fare.interval_end if last_fare is not None else history.time_arrived
                    if current_time > interval_start:
                        interval_hours = Decimal(str((current_time - interval_start).total_seconds() / 3600))
                        interval_rate = Decimal(str(fare_result["rate"]))
                        db.add(FareHistory(
                            lot_id=lot.lot_id,
                            history_id=history.history_id,
                            rule_id=fare_result["rule"].rule_id,
                            interval_start=interval_start,
                            interval_end=current_time,
                            rate=interval_rate,
                            charge=interval_hours * interval_rate,
                        ))
                history.time_left = current_time
                duration_hours = (current_time - history.time_arrived).total_seconds() / 3600
                history.duration = duration_hours
                fare_records = db.query(FareHistory).filter(
                    FareHistory.history_id == history.history_id,
                    FareHistory.lot_id == lot.lot_id,
                ).all()
                total_fare = sum((record.charge for record in fare_records), Decimal("0"))
                history.fare_charged = total_fare
                history.average_rate = (
                    total_fare / Decimal(str(duration_hours)) if duration_hours > 0 else Decimal("0")
                )
            space.user_id = None
            space.status = "vacant"
            space.last_updated = current_time

    actor_user_id = actor.user_id if actor is not None else None
    record_event(
        db,
        request,
        "parking.lot_occupancy_cleared",
        f"Marked all spaces vacant in lot {lot.slug}; {vacated_count} occupied spaces were cleared.",
        actor_user_id,
    )
    db.commit()
    return {"lot_id": lot.lot_id, "space_count": len(spaces), "vacated_count": vacated_count}

@router.put("/{parking_id}", response_model = ParkingResponse)
def update_parking_status(parking_id: int, parking_update: ParkingStatusUpdate, request: Request, lot_id: int | None = None, db: Session = Depends(get_db), actor = Depends(require_admin_or_detection_token)):
    query = db.query(ParkingRecord).filter(ParkingRecord.parking_id == parking_id)
    if lot_id is not None:
        query = query.filter(ParkingRecord.lot_id == lot_id)
    parking = query.first()
    if parking is None:
        raise HTTPException(
            status_code = 404,
            detail = "Parking space not found"
        )
    
    old_status = parking.status
    new_status = parking_update.status
    current_time = datetime.now()

    # Case 1: No actual status transition
    if old_status == new_status:
        return parking

    # Case 2: vacant -> occupied
    if old_status == "vacant" and new_status == "occupied":
        history = ParkingHistory(
            lot_id = parking.lot_id,
            parking_id = parking.parking_id,
            user_id = parking.user_id,
            time_arrived = current_time,
            duration = 0.00,
            average_rate = 0.00,
            fare_charged = 0.00
        )
        db.add(history)
        parking.status = new_status

    # Case 3: occupied -> vacant
    elif old_status == "occupied" and new_status == "vacant":
        history = db.query(ParkingHistory).filter(
            ParkingHistory.lot_id == parking.lot_id,
            ParkingHistory.parking_id == parking.parking_id,
            ParkingHistory.time_left.is_(None)
        ).order_by(ParkingHistory.time_arrived.desc()).first()

        if history is None:
            raise HTTPException(
                status_code = 400,
                detail = "No active parking session found"
            )

        departure_time = current_time
        occupancy = calculate_occupancy(db, parking.lot_id)
        result = select_fare_rule(
            occupancy_percentage = occupancy,
            current_time = departure_time,
            lot_id = parking.lot_id,
            db = db
        )

        if result is not None:
            rule = result["rule"]
            rate = result["rate"]
            generate_fare_interval(
                history_id = history.history_id,
                interval_end = departure_time,
                rule_id = rule.rule_id,
                rate = rate,
                lot_id = parking.lot_id,
                db = db
            )

        history.time_left = departure_time
        duration_hours = (current_time - history.time_arrived).total_seconds()/3600
        history.duration = duration_hours

        fare_records = db.query(FareHistory).filter(
            FareHistory.history_id == history.history_id,
            FareHistory.lot_id == parking.lot_id,
        ).all()
        total_fare = sum(record.charge for record in fare_records)
        history.fare_charged = total_fare

        if duration_hours > 0:
            history.average_rate = (total_fare / Decimal(str(duration_hours)))
        else:
            history.average_rate = 0.00
        
        parking.user_id = None
        parking.status = new_status
    
    parking.last_updated = current_time
    actor_user_id = actor.user_id if actor is not None else None
    record_event(
        db,
        request,
        "parking.status_changed",
        f"Parking space '{parking.slot_number}' changed from {old_status} to {new_status}.",
        actor_user_id,
    )
    db.commit()
    return parking
