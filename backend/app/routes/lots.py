from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_admin
from app.models.users import User
from app.models.lots import ParkingLot
from app.schemas.lots import ParkingLotCreate, ParkingLotResponse
from app.services.audit import record_event

router = APIRouter(prefix="/lots", tags=["Parking lots"])


@router.get("/", response_model=list[ParkingLotResponse])
def list_lots(db: Session = Depends(get_db)):
    return db.query(ParkingLot).order_by(ParkingLot.lot_id).all()


@router.post("/", response_model=ParkingLotResponse, status_code=201)
def create_lot(payload: ParkingLotCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    lot = ParkingLot(name=payload.name.strip(), slug=payload.slug, location=payload.location)
    db.add(lot)
    try:
        db.flush()
        record_event(db, request, "parking_lot.created", f"Created parking lot '{lot.name}' ({lot.slug}).", current_user.user_id)
        db.commit()
        db.refresh(lot)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Lot name or slug already exists")
    return lot
