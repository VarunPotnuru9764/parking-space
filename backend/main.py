from fastapi import FastAPI
from app.database import Base, engine
from app.models.users import User
from app.models.parking import ParkingRecord
from app.models.fares import FareRule
from app.models.history import ParkingHistory

Base.metadata.create_all(bind=engine)
app = FastAPI()

@app.get("/")
def root():
    return {"message": "Parking Space Detection System API is running"}