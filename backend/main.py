from fastapi import FastAPI

from app.database import Base, engine
from app.models.users import User
from app.models.parking import ParkingRecord
from app.models.fares import FareRule
from app.models.history import ParkingHistory
from app.routes.parking import router as parking_router
from app.routes.claim import router as claim_router

Base.metadata.create_all(bind=engine)
app = FastAPI()
app.include_router(parking_router)
app.include_router(claim_router)

@app.get("/")
def root():
    return {"message": "Parking Space Detection System API is running"}