from sqlalchemy import Column, Integer, String, Enum, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base

class ParkingRecord(Base):
    __tablename__ = "parking_records"
    __table_args__ = (UniqueConstraint("lot_id", "slot_number", name="uq_parking_lot_slot"),)

    parking_id = Column(Integer, primary_key = True, index = True, autoincrement = True)
    lot_id = Column(Integer, ForeignKey("parking_lots.lot_id"), nullable=False, index=True)
    slot_number = Column(String(20), nullable = False)
    location = Column(String(100), nullable = False)
    status = Column(Enum("vacant", "occupied"), nullable = False, default = "vacant")
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable = True)
    claim_code = Column(String(20), unique = True, nullable = False)
    current_rate = Column(Numeric(10, 2), nullable = False)
    last_updated = Column(DateTime, server_default = func.now(), onupdate = func.now())
