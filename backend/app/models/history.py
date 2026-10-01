from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey
from app.database import Base

class ParkingHistory(Base):
    __tablename__ = "parking_history"

    history_id = Column(Integer, primary_key = True, index = True, autoincrement = True)
    parking_id = Column(Integer, ForeignKey("parking_records.parking_id"), nullable = False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable = True)
    time_arrived = Column(DateTime, nullable = False)
    time_left = Column(DateTime, nullable = True)
    duration = Column(Numeric(10, 4), nullable=True)
    average_rate = Column(Numeric(10, 2), nullable=True)
    fare_charged = Column(Numeric(10, 2), nullable = False, default = 0.00)