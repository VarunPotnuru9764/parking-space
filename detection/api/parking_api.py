from pathlib import Path

import requests
from dotenv import dotenv_values


REQUEST_TIMEOUT_SECONDS = 10
DETECTION_DIR = Path(__file__).resolve().parents[1]
config = dotenv_values(DETECTION_DIR / ".env")
DEFAULT_API_URL = config.get("API_URL") or "http://localhost:8000"

class ParkingAPI:
    def __init__(self, base_url=DEFAULT_API_URL):
        self.base_url = base_url.rstrip("/")

    def get_parking_spaces(self, lot_id=None):
        params = {"lot_id": lot_id} if lot_id is not None else None
        response = requests.get(
            f"{self.base_url}/parking/",
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    def update_parking_status(self, parking_id, status, lot_id=None):
        params = {"lot_id": lot_id} if lot_id is not None else None
        response = requests.put(
            f"{self.base_url}/parking/{parking_id}",
            params=params,
            json={"status": status},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
