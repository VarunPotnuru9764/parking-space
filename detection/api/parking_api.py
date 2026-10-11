import requests
class ParkingAPI:
    def __init__(self, base_url = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def get_parking_spaces(self, lot_id=None):
        params = {"lot_id": lot_id} if lot_id is not None else None
        response = requests.get(f"{self.base_url}/parking/", params=params)
        response.raise_for_status()
        return response.json()

    def update_parking_status(self, parking_id, status, lot_id=None):
        params = {"lot_id": lot_id} if lot_id is not None else None
        response = requests.put(f"{self.base_url}/parking/{parking_id}", params=params, json={"status": status})
        response.raise_for_status()
        return response.json()
