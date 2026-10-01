from decimal import Decimal
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models.fares import FareRule
from app.models.parking import ParkingRecord
from app.models.history import ParkingHistory
from app.models.fare_history import FareHistory

def is_boundary_time(current_time: datetime) -> bool:
    return current_time.minute % 15 == 0 

def calculate_occupancy(db: Session) -> float:
    total_spaces = db.query(ParkingRecord).count()
    if total_spaces == 0:
        return 0.0

    occupied_spaces = db.query(ParkingRecord).filter(ParkingRecord.status == "occupied").count()
    occupancy_percentage = (occupied_spaces / total_spaces) * 100
    return occupancy_percentage

def select_fare_rule(occupancy_percentage: float, current_time: datetime, db: Session):
    rule = db.query(FareRule).filter(
        FareRule.min_occupancy <= occupancy_percentage,
        FareRule.max_occupancy >= occupancy_percentage
    ).first()

    if rule is None:
        return None

    is_peak = False
    if rule.start_time is not None and rule.end_time is not None:
        current_clock = current_time.time()
        if rule.start_time <= current_clock <= rule.end_time:
            is_peak = True

    rate = float(rule.base_rate) * float(rule.occupancy_multiplier)
    if is_peak:
        rate *= float(rule.peak_multiplier)

    if is_boundary_time(current_time):
        db.query(FareRule).update({FareRule.active: False}, synchronize_session = False)
        db.query(ParkingRecord).update({ParkingRecord.current_rate: rate}, synchronize_session = False)
        rule.active = True
        db.commit()

    return {
        "rule": rule,
        "rate": rate,
        "is_peak": is_peak
    }

def record_fare_interval(history_id: int, rule_id: int, interval_start: datetime, interval_end: datetime, rate: float, db: Session):
    history = db.query(ParkingHistory).filter(ParkingHistory.history_id == history_id).first()
    if history is None:
        return None

    if interval_end <= interval_start:
        return None

    duration_hours = Decimal(str((interval_end - interval_start).total_seconds() / 3600))
    rate_decimal = Decimal(str(rate))
    charge = duration_hours * rate_decimal

    fare_record = FareHistory(
        history_id = history_id,
        rule_id = rule_id,
        interval_start = interval_start,
        interval_end = interval_end,
        rate = rate_decimal,
        charge = charge
    )

    db.add(fare_record)
    db.commit()
    return fare_record

def generate_fare_interval(history_id: int, interval_end: datetime, rule_id: int, rate: float, db: Session):
    history = db.query(ParkingHistory).filter(ParkingHistory.history_id == history_id).first()
    if history is None:
        return None

    if history.time_left is not None:
        interval_end = min(interval_end, history.time_left)

    interval_start = history.time_arrived
    last_fare = db.query(FareHistory).filter(FareHistory.history_id == history_id).order_by(FareHistory.interval_end.desc()).first()
    if last_fare is not None:
        interval_start = last_fare.interval_end

    if interval_end <= interval_start:
        return None
    
    fare_record = record_fare_interval(
        history_id = history_id,
        rule_id = rule_id,
        interval_start = interval_start,
        interval_end = interval_end,
        rate = rate,
        db = db
    )
    return fare_record