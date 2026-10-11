from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class ParkingCreate(BaseModel):
    lot_id: int | None = None
    slot_number: str
    location: str
    claim_code: str
    current_rate: float = Field(gt = 0)

class ParkingBulkSpace(BaseModel):
    slot_number: str
    location: str
    current_rate: float = Field(default=50.0, gt=0)

class ParkingBulkCreate(BaseModel):
    lot_id: int
    spaces: list[ParkingBulkSpace] = Field(min_length=1, max_length=1000)

class ParkingStatusUpdate(BaseModel):
    status: Literal["vacant", "occupied"]

class ParkingResponse(BaseModel):
    parking_id: int
    lot_id: int
    slot_number: str
    location: str
    status: str
    user_id: int | None
    current_rate: float
    last_updated: datetime

    model_config = {"from_attributes": True}

class ParkingBulkResult(BaseModel):
    spaces: list[ParkingResponse]
    new_claim_codes: dict[str, str]
