from sqlalchemy import Column, Integer, String, Numeric, Time, Boolean
from app.database import Base

class FareRule(Base):
    __tablename__ = "fare_rules"

    rule_id = Column(Integer, primary_key = True, index = True, autoincrement = True)
    rule_name = Column(String(100), nullable = False)
    base_rate = Column(Numeric(10, 2), nullable = False)
    min_occupancy = Column(Numeric(5, 2), nullable = False)
    max_occupancy = Column(Numeric(5, 2), nullable = False)
    occupancy_multiplier = Column(Numeric(5, 2), nullable = False)
    peak_multiplier = Column(Numeric(5, 2), nullable = False, default = 1.00)
    start_time = Column(Time, nullable = True)
    end_time = Column(Time, nullable = True)
    active = Column(Boolean, nullable = False, default = False)