from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey
from app.database import Base

class FareHistory(Base):
    __tablename__ = "fare_history"

    fare_id = Column(Integer, primary_key = True, index = True, autoincrement = True)
    history_id = Column(Integer, ForeignKey("parking_history.history_id"), nullable = False)
    rule_id = Column(Integer, ForeignKey("fare_rules.rule_id"), nullable = False)
    interval_start = Column(DateTime, nullable = False)
    interval_end = Column(DateTime, nullable = False)
    rate = Column(Numeric(10, 2), nullable = False)
    charge = Column(Numeric(10, 2), nullable = False)