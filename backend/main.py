import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import Base, engine
from app.models.users import User
from app.models.parking import ParkingRecord
from app.models.fares import FareRule
from app.models.history import ParkingHistory
from app.models.fare_history import FareHistory
from app.routes.parking import router as parking_router
from app.routes.claim import router as claim_router
from app.routes.auth import router as auth_router
from app.scheduler import fare_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_task = asyncio.create_task(fare_scheduler())

    yield
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass

Base.metadata.create_all(bind=engine)
app = FastAPI(lifespan = lifespan)

app.include_router(parking_router)
app.include_router(claim_router)
app.include_router(auth_router)

@app.get("/")
def root():
    return {"message": "Parking Space Detection System API is running"}