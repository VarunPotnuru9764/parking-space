from pydantic import BaseModel, Field


class ParkingLotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    location: str | None = Field(default=None, max_length=255)


class ParkingLotResponse(BaseModel):
    lot_id: int
    name: str
    slug: str
    location: str | None

    model_config = {"from_attributes": True}
