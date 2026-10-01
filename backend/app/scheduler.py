import asyncio
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.history import ParkingHistory
from app.services.fare_engine import (
    calculate_occupancy,
    select_fare_rule,
    generate_fare_interval
)

def get_next_boundary():
    now = datetime.now()
    next_minute = ((now.minute // 15) + 1) * 15
    if next_minute >= 60:
        next_boundary = (now.replace(minute = 0, second = 0, microsecond = 0) + timedelta(hours = 1))
    else:
        next_boundary = now.replace(minute = next_minute, second = 0, microsecond = 0)

    return next_boundary

def process_fare_intervals(boundary_time: datetime):
    db = SessionLocal()
    try:
        occupancy = calculate_occupancy(db)
        result = select_fare_rule(
            occupancy_percentage = occupancy,
            current_time = boundary_time,
            db = db
        )
        if result is None:
            print("No matching fare rule found")
            return

        rule = result["rule"]
        rate = result["rate"]
        print(
            f"[Scheduler] {boundary_time} | "
            f"Occupancy: {occupancy:.2f}% | "
            f"Rule: {rule.rule_name} | "
            f"Rate: ₹{rate:.2f}/hour"
        )
        active_histories = db.query(ParkingHistory).filter(ParkingHistory.time_left.is_(None)).all()
        for history in active_histories:
            fare_record = generate_fare_interval(
                history_id = history.history_id,
                interval_end = boundary_time,
                rule_id = rule.rule_id,
                rate = rate,
                db = db
            )
            if fare_record is not None:
                print(
                    f"[Scheduler] History {history.history_id}: "
                    f"{fare_record.interval_start} → "
                    f"{fare_record.interval_end} | "
                    f"₹{fare_record.charge:.2f}"
                )

    except Exception as e:
        db.rollback()
        print(f"[Scheduler] Error: {e}")

    finally:
        db.close()

async def fare_scheduler():
    print("[Scheduler] Fare scheduler started.")
    while True:
        next_boundary = get_next_boundary()
        now = datetime.now()
        wait_seconds = (next_boundary - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        process_fare_intervals(next_boundary)