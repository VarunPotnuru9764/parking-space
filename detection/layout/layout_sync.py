from dotenv import dotenv_values
from pathlib import Path
import requests

env_path = Path(__file__).resolve().parent.parent / ".env"
config = dotenv_values(env_path)
API_URL = config["API_URL"]

def get_parking_spaces():
    response = requests.get(f"{API_URL}/parking/")
    response.raise_for_status()
    return response.json()

def create_parking_space(space):
    slot_number = space["slot_number"]
    while True:
        claim_code = input(f"Enter claim code for {slot_number}: ").strip()
        if not claim_code:
            print("Claim code cannot be empty")
            continue

        location = input(f"Enter location for {slot_number}: ").strip()
        if not location:
            print("Location cannot be empty")
            continue

        payload = {
            "slot_number": slot_number,
            "claim_code": claim_code,
            "location": location,
            "current_rate": 50.00
        }

        response = requests.post(f"{API_URL}/parking/", json=payload)
        if response.status_code == 409:
            print("A parking space with this claim code already exists")
            continue

        response.raise_for_status()
        return response.json()

def compare_layout_with_database(layout, db_spaces):
    layout_spaces = layout["spaces"]
    layout_by_slot = {
        space["slot_number"]: space
        for space in layout_spaces
    }

    db_by_slot = {
        space["slot_number"]: space
        for space in db_spaces
    }

    reused = []
    new_spaces = []
    missing_from_layout = []

    for slot_number, layout_space in layout_by_slot.items():
        if slot_number in db_by_slot:
            db_space = db_by_slot[slot_number]
            reused.append({
                "slot_number": slot_number,
                "parking_id": db_space["parking_id"],
                "polygon": layout_space["polygon"]
            })

        else:
            new_spaces.append(layout_space)

    for slot_number, db_space in db_by_slot.items():
        if slot_number not in layout_by_slot:
            missing_from_layout.append({
                "slot_number": slot_number,
                "parking_id": db_space["parking_id"]
            })

    return {
        "reused": reused,
        "new_spaces": new_spaces,
        "missing_from_layout": missing_from_layout
    }

def synchronize_layout(layout):
    db_spaces = get_parking_spaces()
    comparison = compare_layout_with_database(layout, db_spaces)

    created = []
    for space in comparison["new_spaces"]:
        print(f"Creating new parking space: {space['slot_number']}")
        created_space = create_parking_space(space)
        created.append({
            "slot_number": created_space["slot_number"],
            "parking_id": created_space["parking_id"]
        })

    final_db_spaces = get_parking_spaces()
    final_db_by_slot = {space["slot_number"]: space for space in final_db_spaces}

    synchronized_spaces = []
    for layout_space in layout["spaces"]:
        slot_number = layout_space["slot_number"]
        db_space = final_db_by_slot.get(slot_number)
        if db_space is None:
            print(f"WARNING: {slot_number} could not be found in the database after synchronization")
            continue

        synchronized_spaces.append({
            "slot_number": slot_number,
            "parking_id": db_space["parking_id"],
            "polygon": layout_space["polygon"]
        })

    layout_slots = {space["slot_number"] for space in layout["spaces"]}
    missing_from_layout = []
    for db_space in final_db_spaces:
        if db_space["slot_number"] not in layout_slots:
            missing_from_layout.append({
                "slot_number": db_space["slot_number"],
                "parking_id": db_space["parking_id"]
            })

    return {
        "spaces": synchronized_spaces,
        "created": created,
        "missing_from_layout": missing_from_layout
    }