from pydantic import BaseModel

class ParkingClaim(BaseModel):
    user_id: int
    claim_code: str

class ParkingClaimConfirm(BaseModel):
    user_id: int
    claim_token: str