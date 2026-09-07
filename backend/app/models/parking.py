from sqlalchemy import Column, Integer, String, Enum, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class ParkingRecord(Base):
    __tablename__ = "parking_records"

    parking_id = Column(Integer, primary_key = True, index = True, autoincrement = True)
    slot_number = Column(String(20), unique = True, nullable = False)
    location = Column(String(100), nullable = False)
    status = Column(Enum("vacant", "occupied"), nullable = False, default = "vacant")
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable = True)
    current_rate = Column(Numeric(10, 2), nullable = False)
    last_updated = Column(DateTime, server_default = func.now(), onupdate = func.now())