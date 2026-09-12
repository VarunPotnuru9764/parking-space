from pydantic import BaseModel

class ParkingClaim(BaseModel):
    claim_code: str

class ParkingClaimConfirm(BaseModel):
    claim_token: str