from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models.parking import ParkingRecord
from app.models.history import ParkingHistory
from app.models.users import User
from app.schemas.claim import (
    ParkingClaimConfirm,
    ParkingClaim
)
from app.services.audit import record_event

import secrets
from datetime import datetime, timedelta    
router = APIRouter(prefix="/parking", tags=["Parking Claims"])
claim_tokens = {}

def _record_failed_claim(db: Session, request: Request, current_user: User, parking_id: int, detail: str) -> None:
    record_event(db, request, "parking.claim_failed", f"Claim attempt for space ID {parking_id} failed: {detail}", current_user.user_id, current_user.email, False)
    db.commit()


@router.post("/{parking_id}/claim/initiate")
def initiate_parking_claim(parking_id: int, claim: ParkingClaim, request: Request, lot_id: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    parking = db.query(ParkingRecord).filter(ParkingRecord.parking_id == parking_id).first()
    if parking is not None and lot_id is not None and parking.lot_id != lot_id:
        parking = None
    if parking is None:
        _record_failed_claim(db, request, current_user, parking_id, "space not found")
        raise HTTPException(
            status_code = 404,
            detail = "Parking space not found"
        )

    if parking.status != "occupied":
            _record_failed_claim(db, request, current_user, parking_id, "space is not occupied")
            raise HTTPException(
                status_code = 400,
                detail = "Only an occupied parking space can be claimed"
            )

    if parking.claim_code != claim.claim_code:
            _record_failed_claim(db, request, current_user, parking_id, "invalid claim code")
            raise HTTPException(
                status_code = 403,
                detail = "Invalid claim code"
            )

    if parking.user_id is not None:
            _record_failed_claim(db, request, current_user, parking_id, "space has already been claimed")
            raise HTTPException(
                status_code = 409,
                detail = "This parking space has already been claimed"
            )

    history = db.query(ParkingHistory).filter(
            ParkingHistory.parking_id == parking.parking_id,
            ParkingHistory.time_left.is_(None)
        ).order_by(ParkingHistory.time_arrived.desc()).first()
    
    if history is None:
        _record_failed_claim(db, request, current_user, parking_id, "no active parking session")
        raise HTTPException(
            status_code = 400,
            detail = "No active parking session found"
        )

    current_time = datetime.now()
    claim_window = timedelta(minutes = 5)
    if current_time > history.time_arrived + claim_window:
        _record_failed_claim(db, request, current_user, parking_id, "claim window expired")
        raise HTTPException(
            status_code = 400,
            detail = "The claim window for this parking space has expired"
        )

    existing_claim = db.query(ParkingHistory).filter(
            ParkingHistory.user_id == current_user.user_id,
            ParkingHistory.lot_id == parking.lot_id,
            ParkingHistory.time_left.is_(None)
        ).first()
    
    if existing_claim is not None:
        _record_failed_claim(db, request, current_user, parking_id, "user already has an active parking claim")
        raise HTTPException(
            status_code = 409,
            detail = "You already have an active parking claim"
        )

    token = secrets.token_urlsafe(32)
    expires_at = current_time + timedelta(seconds = 60)

    claim_tokens[token] = {
        "parking_id": parking_id,
        "lot_id": parking.lot_id,
        "user_id": current_user.user_id,
        "expires_at": expires_at
    }
    record_event(db, request, "parking.claim_initiated", f"Claim initiated for space '{parking.slot_number}'.", current_user.user_id, current_user.email)
    db.commit()

    return {
        "message": "Claim initiated. Please confirm within 60 seconds",
        "claim_token": token,
        "expires_in": 60
    }

@router.post("/{parking_id}/claim/confirm")
def confirm_parking_claim(parking_id: int, claim: ParkingClaimConfirm, request: Request, lot_id: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    token_data = claim_tokens.get(claim.claim_token)
    if token_data is None:
        _record_failed_claim(db, request, current_user, parking_id, "invalid claim token")
        raise HTTPException(
            status_code = 400,
            detail = "Invalid claim token"
        )

    if token_data["parking_id"] != parking_id:
        _record_failed_claim(db, request, current_user, parking_id, "claim token belongs to another space")
        raise HTTPException(
            status_code = 403,
            detail = "Claim token does not belong to this parking space"
        )

    if lot_id is not None and token_data["lot_id"] != lot_id:
        _record_failed_claim(db, request, current_user, parking_id, "claim token belongs to another lot")
        raise HTTPException(status_code=403, detail="Claim token does not belong to this parking lot")

    if token_data["user_id"] != current_user.user_id:
        _record_failed_claim(db, request, current_user, parking_id, "claim token belongs to another user")
        raise HTTPException(
            status_code = 403,
            detail = "Claim token does not belong to this user"
        )

    current_time = datetime.now()
    if current_time > token_data["expires_at"]:
        claim_tokens.pop(claim.claim_token, None)
        _record_failed_claim(db, request, current_user, parking_id, "claim token expired")
        raise HTTPException(
            status_code = 400,
            detail = "Claim token has expired"
        )

    parking = db.query(ParkingRecord).filter(
        ParkingRecord.parking_id == parking_id,
        ParkingRecord.lot_id == token_data["lot_id"]
    ).first()
    if parking is None:
        _record_failed_claim(db, request, current_user, parking_id, "space not found")
        raise HTTPException(
            status_code = 404,
            detail = "Parking space not found"
        )
    
    if parking.status != "occupied":
        _record_failed_claim(db, request, current_user, parking_id, "space is not occupied")
        raise HTTPException(
            status_code = 400,
            detail = "Only an occupied parking space can be claimed"
        )

    if parking.user_id is not None:
        _record_failed_claim(db, request, current_user, parking_id, "space has already been claimed")
        raise HTTPException(
            status_code = 409,
            detail = "This parking space has already been claimed"
        )

    history = db.query(ParkingHistory).filter(
        ParkingHistory.parking_id == parking.parking_id,
        ParkingHistory.time_left.is_(None)
    ).order_by(ParkingHistory.time_arrived.desc()).first()

    if history is None:
        _record_failed_claim(db, request, current_user, parking_id, "no active parking session")
        raise HTTPException(
            status_code = 400,
            detail = "No active parking session found"
        )

    current_time = datetime.now()
    claim_window = timedelta(minutes = 5)
    if current_time > history.time_arrived + claim_window:
        _record_failed_claim(db, request, current_user, parking_id, "claim window expired")
        raise HTTPException(
            status_code = 400,
            detail = "The claim window for this parking space has expired"
        )

    existing_claim = db.query(ParkingHistory).filter(
        ParkingHistory.user_id == current_user.user_id,
            ParkingHistory.lot_id == parking.lot_id,
        ParkingHistory.time_left.is_(None)
    ).first()

    if existing_claim is not None:
        _record_failed_claim(db, request, current_user, parking_id, "user already has an active parking claim")
        raise HTTPException(
            status_code = 409,
            detail = "You already have an active parking claim"
        )
    
    parking.user_id = current_user.user_id
    history.user_id = current_user.user_id
    del claim_tokens[claim.claim_token]
    record_event(db, request, "parking.claim_confirmed", f"Parking space '{parking.slot_number}' claimed successfully.", current_user.user_id, current_user.email)
    db.commit()

    return {
        "message": "Parking space claimed successfully",
        "parking_id": parking.parking_id,
        "lot_id": parking.lot_id,
        "slot_number": parking.slot_number,
        "user_id": parking.user_id
    }
