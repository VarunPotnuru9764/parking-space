from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class ParkingCreate(BaseModel):
    slot_number: str
    location: str
    current_rate: float = Field(gt = 0)

class ParkingStatusUpdate(BaseModel):
    status: Literal["vacant", "occupied"]

class ParkingResponse(BaseModel):
    parking_id: int
    slot_number: str
    location: str
    status: str
    user_id: int | None
    current_rate: float
    last_updated: datetime