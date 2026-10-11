from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class ParkingLot(Base):
    __tablename__ = "parking_lots"

    lot_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(120), nullable=False, unique=True)
    slug = Column(String(80), nullable=False, unique=True)
    location = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
