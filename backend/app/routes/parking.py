from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.parking import ParkingRecord
from app.models.history import ParkingHistory
from app.schemas.parking import (
    ParkingCreate, 
    ParkingResponse,
    ParkingStatusUpdate
)

from datetime import datetime
router = APIRouter(prefix="/parking", tags=["Parking"])

@router.get("/", response_model = list[ParkingResponse])
def get_parking_spaces(db: Session = Depends(get_db)):
    parking_spaces = db.query(ParkingRecord).all()
    return parking_spaces

@router.post("/", response_model = ParkingResponse, status_code = 201)
def create_parking_space(parking: ParkingCreate, db: Session = Depends(get_db)):
    new_parking = ParkingRecord(
        slot_number=parking.slot_number,
        location=parking.location,
        current_rate=parking.current_rate
    )

    try:
        db.add(new_parking)
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code = 409,
            detail = "A parking space with this slot number already exists"
        )
    
    return new_parking

@router.put("/{parking_id}", response_model = ParkingResponse)
def update_parking_status(parking_id: int, parking_update: ParkingStatusUpdate, db: Session = Depends(get_db)):
    parking = db.query(ParkingRecord).filter(ParkingRecord.parking_id == parking_id).first()
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
            parking_id = parking.parking_id,
            user_id = parking.user_id,
            time_arrived = current_time,
            rate_at_entry = parking.current_rate,
            fare_charged = 0.00
        )
        db.add(history)

    # Case 3: occupied -> vacant
    elif old_status == "occupied" and new_status == "vacant":
        history = db.query(ParkingHistory).filter(
            ParkingHistory.parking_id == parking.parking_id,
            ParkingHistory.time_left.is_(None)
        ).order_by(ParkingHistory.time_arrived.desc()).first()

        if history is None:
            raise HTTPException(
                status_code = 400,
                detail = "No active parking session found"
            )
        
        history.time_left = current_time
        duration_hours = (current_time - history.time_arrived).total_seconds()/3600
        history.fare_charged = (duration_hours * float(history.rate_at_entry))
        parking.user_id = None

    parking.status = new_status
    parking.last_updated = current_time
    db.commit()
    return parking