from api.parking_api import ParkingAPI
class OccupancyUpdater:
    def __init__(self, synchronized_spaces):
        self.api = ParkingAPI()
        self.parking_ids = {
            space["slot_number"]: space["parking_id"]
            for space in synchronized_spaces
        }

    def apply_changes(self, changes):
        for slot_number, occupied in changes.items():
            parking_id = self.parking_ids.get(slot_number)
            if parking_id is None:
                print(f"WARNING: No parking_id found for {slot_number}")
                continue

            status = ("occupied" if occupied else "vacant")
            print(
                f"Updating {slot_number} "
                f"(parking_id={parking_id}) "
                f"→ {status}"
            )

            self.api.update_parking_status(
                parking_id = parking_id,
                status = status
            )