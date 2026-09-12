from fastapi import APIRouter, Depends, HTTPException
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

import secrets
from datetime import datetime, timedelta    
router = APIRouter(prefix="/parking", tags=["Parking Claims"])
claim_tokens = {}

@router.post("/{parking_id}/claim/initiate")
def initiate_parking_claim(parking_id: int, claim: ParkingClaim, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    parking = db.query(ParkingRecord).filter(ParkingRecord.parking_id == parking_id).first()
    if parking is None:
        raise HTTPException(
            status_code = 404,
            detail = "Parking space not found"
        )

    if parking.status != "occupied":
            raise HTTPException(
                status_code = 400,
                detail = "Only an occupied parking space can be claimed"
            )

    if parking.claim_code != claim.claim_code:
            raise HTTPException(
                status_code = 403,
                detail = "Invalid claim code"
            )

    if parking.user_id is not None:
            raise HTTPException(
                status_code = 409,
                detail = "This parking space has already been claimed"
            )

    history = db.query(ParkingHistory).filter(
            ParkingHistory.parking_id == parking.parking_id,
            ParkingHistory.time_left.is_(None)
        ).order_by(ParkingHistory.time_arrived.desc()).first()
    
    if history is None:
        raise HTTPException(
            status_code = 400,
            detail = "No active parking session found"
        )

    '''user = db.query(User).filter(User.user_id == claim.user_id).first()
    if user is None:
        raise HTTPException(
            status_code = 404,
            detail = "User not found"
    )'''

    current_time = datetime.now()
    claim_window = timedelta(minutes = 5)
    if current_time > history.time_arrived + claim_window:
        raise HTTPException(
            status_code = 400,
            detail = "The claim window for this parking space has expired"
        )

    existing_claim = db.query(ParkingHistory).filter(
            ParkingHistory.user_id == current_user.user_id,
            ParkingHistory.time_left.is_(None)
        ).first()
    
    if existing_claim is not None:
        raise HTTPException(
            status_code = 409,
            detail = "You already have an active parking claim"
        )

    token = secrets.token_urlsafe(32)
    expires_at = current_time + timedelta(seconds = 60)

    claim_tokens[token] = {
        "parking_id": parking_id,
        "user_id": current_user.user_id,
        "expires_at": expires_at
    }

    return {
        "message": "Claim initiated. Please confirm within 60 seconds",
        "claim_token": token,
        "expires_in": 60
    }

@router.post("/{parking_id}/claim/confirm")
def confirm_parking_claim(parking_id: int, claim: ParkingClaimConfirm, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    token_data = claim_tokens.get(claim.claim_token)
    if token_data is None:
        raise HTTPException(
            status_code = 400,
            detail = "Invalid claim token"
        )

    if token_data["parking_id"] != parking_id:
        raise HTTPException(
            status_code = 403,
            detail = "Claim token does not belong to this parking space"
        )

    if token_data["user_id"] != current_user.user_id:
        raise HTTPException(
            status_code = 403,
            detail = "Claim token does not belong to this user"
        )

    current_time = datetime.now()
    if current_time > token_data["expires_at"]:
        del claim_tokens[claim.claim_token]
        raise HTTPException(
            status_code = 400,
            detail = "Claim token has expired"
        )

    parking = db.query(ParkingRecord).filter(ParkingRecord.parking_id == parking_id).first()
    if parking is None:
        raise HTTPException(
            status_code = 404,
            detail = "Parking space not found"
        )
    
    if parking.status != "occupied":
        raise HTTPException(
            status_code = 400,
            detail = "Only an occupied parking space can be claimed"
        )

    ''' if parking.claim_code != claim.claim_code:
        raise HTTPException(
            status_code = 403,
            detail = "Invalid claim code"
        ) '''
    
    if parking.user_id is not None:
        raise HTTPException(
            status_code = 409,
            detail = "This parking space has already been claimed"
        )

    history = db.query(ParkingHistory).filter(
        ParkingHistory.parking_id == parking.parking_id,
        ParkingHistory.time_left.is_(None)
    ).order_by(ParkingHistory.time_arrived.desc()).first()

    if history is None:
        raise HTTPException(
            status_code = 400,
            detail = "No active parking session found"
        )

    '''user = db.query(User).filter(User.user_id == claim.user_id).first()
    if user is None:
        raise HTTPException(
            status_code = 404,
            detail = "User not found"
    )'''

    current_time = datetime.now()
    claim_window = timedelta(minutes = 5)
    if current_time > history.time_arrived + claim_window:
        raise HTTPException(
            status_code = 400,
            detail = "The claim window for this parking space has expired"
        )

    existing_claim = db.query(ParkingHistory).filter(
        ParkingHistory.user_id == current_user.user_id,
        ParkingHistory.time_left.is_(None)
    ).first()

    if existing_claim is not None:
        raise HTTPException(
            status_code = 409,
            detail = "You already have an active parking claim"
        )
    
    parking.user_id = current_user.user_id
    history.user_id = current_user.user_id
    del claim_tokens[claim.claim_token]
    db.commit()

    return {
        "message": "Parking space claimed successfully",
        "parking_id": parking.parking_id,
        "slot_number": parking.slot_number,
        "user_id": parking.user_id
    }