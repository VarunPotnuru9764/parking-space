from pathlib import Path

import requests
from dotenv import dotenv_values

env_path = Path(__file__).resolve().parent.parent / ".env"
config = dotenv_values(env_path)
API_URL = (config.get("API_URL") or "http://localhost:8000").rstrip("/")
DETECTION_API_TOKEN = config.get("DETECTION_API_TOKEN")
DEFAULT_LOT_SLUG = config.get("PARKING_LOT_SLUG", "simulator")
REQUEST_TIMEOUT_SECONDS = 10


def get_lots():
    response = requests.get(f"{API_URL}/lots/", timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def resolve_lot_id(lot_id=None, lot_slug=None):
    if lot_id is not None:
        return int(lot_id)
    slug = lot_slug or DEFAULT_LOT_SLUG
    lot = next((item for item in get_lots() if item["slug"] == slug), None)
    if lot is None:
        raise ValueError(f"No parking lot with slug {slug!r}; create it through POST /lots/ first")
    return int(lot["lot_id"])


def get_parking_spaces(lot_id=None, lot_slug=None):
    scoped_lot_id = resolve_lot_id(lot_id, lot_slug)
    response = requests.get(
        f"{API_URL}/parking/",
        params={"lot_id": scoped_lot_id},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def compare_layout_with_database(layout, db_spaces):
    layout_by_slot = {space["slot_number"]: space for space in layout["spaces"]}
    db_by_slot = {space["slot_number"]: space for space in db_spaces}
    reused = [
        {"slot_number": name, "parking_id": db_by_slot[name]["parking_id"], "polygon": item["polygon"]}
        for name, item in layout_by_slot.items() if name in db_by_slot
    ]
    new_spaces = [item for name, item in layout_by_slot.items() if name not in db_by_slot]
    missing = [
        {"slot_number": name, "parking_id": item["parking_id"]}
        for name, item in db_by_slot.items() if name not in layout_by_slot
    ]
    return {"reused": reused, "new_spaces": new_spaces, "missing_from_layout": missing}


def synchronize_layout(layout, lot_id=None, lot_slug=None):
    scoped_lot_id = resolve_lot_id(lot_id, lot_slug)
    db_spaces = get_parking_spaces(lot_id=scoped_lot_id)
    comparison = compare_layout_with_database(layout, db_spaces)
    new_claim_codes = {}
    if comparison["new_spaces"]:
        payload = {
            "lot_id": scoped_lot_id,
            "spaces": [
                {
                    "slot_number": item["slot_number"],
                    "location": item.get("location", f"{lot_slug or DEFAULT_LOT_SLUG}:{item['slot_number']}"),
                    "current_rate": item.get("current_rate", 50.0),
                }
                for item in comparison["new_spaces"]
            ],
        }
        response = requests.post(
            f"{API_URL}/parking/bulk",
            json=payload,
            headers={"X-Detection-Token": DETECTION_API_TOKEN} if DETECTION_API_TOKEN else {},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        new_claim_codes = response.json().get("new_claim_codes", {})
        print(f"Synchronized {len(comparison['new_spaces'])} new spaces into lot {scoped_lot_id}")
        if new_claim_codes:
            print("Generated claim codes (save these to your lot's secure provisioning record):")
            for slot_number, code in new_claim_codes.items():
                print(f"  {slot_number}: {code}")

    final_spaces = get_parking_spaces(lot_id=scoped_lot_id)
    final_by_slot = {item["slot_number"]: item for item in final_spaces}
    synchronized = [
        {
            "lot_id": scoped_lot_id,
            "slot_number": item["slot_number"],
            "parking_id": final_by_slot[item["slot_number"]]["parking_id"],
            "polygon": item["polygon"],
        }
        for item in layout["spaces"] if item["slot_number"] in final_by_slot
    ]
    return {
        "lot_id": scoped_lot_id,
        "spaces": synchronized,
        "created": [item for item in synchronized if item["slot_number"] in {s["slot_number"] for s in comparison["new_spaces"]}],
        "new_claim_codes": new_claim_codes,
        "missing_from_layout": compare_layout_with_database(layout, final_spaces)["missing_from_layout"],
    }
