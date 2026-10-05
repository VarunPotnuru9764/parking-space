import requests
class ParkingAPI:
    def __init__(self, base_url = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def get_parking_spaces(self):
        response = requests.get(f"{self.base_url}/parking/")
        response.raise_for_status()
        return response.json()

    def update_parking_status(self, parking_id, status):
        response = requests.put(f"{self.base_url}/parking/{parking_id}", json = {"status": status})
        response.raise_for_status()
        return response.json()