import json
from pathlib import Path

LAYOUT_FILE = Path(__file__).parent / "parking_layout.json"
def validate_layout(layout):
    if not isinstance(layout, dict):
        raise ValueError("Layout must be a dictionary")

    if "spaces" not in layout:
        raise ValueError("Layout must contain 'spaces'")

    spaces = layout["spaces"]
    if not isinstance(spaces, list):
        raise ValueError("'spaces' must be a list")

    if len(spaces) == 0:
        raise ValueError("At least one parking space is required")

    slot_names = set()
    for space in spaces:
        if "slot_number" not in space:
            raise ValueError("Every parking space must have a slot number")

        if "polygon" not in space:
            raise ValueError("Every parking space must have a polygon")

        slot_number = space["slot_number"]
        polygon = space["polygon"]
        if not isinstance(slot_number, str) or not slot_number.strip():
            raise ValueError("Parking-space names must be non-empty strings")

        if slot_number in slot_names:
            raise ValueError(f"Duplicate parking-space name: {slot_number}")

        slot_names.add(slot_number)
        if not isinstance(polygon, list):
            raise ValueError(f"Polygon for {slot_number} must be a list")

        if len(polygon) < 3:
            raise ValueError(f"Polygon for {slot_number} must have at least 3 points")

        for point in polygon:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError(f"Invalid polygon point in {slot_number}")

    return True

def save_layout(layout):
    validate_layout(layout)
    with open(LAYOUT_FILE, "w") as file:
        json.dump(layout, file, indent=4)

    print(f"Parking layout saved to: {LAYOUT_FILE}")

def load_layout():
    if not LAYOUT_FILE.exists():
        raise FileNotFoundError("No parking layout has been saved yet")

    with open(LAYOUT_FILE, "r") as file:
        layout = json.load(file)

    validate_layout(layout)
    return layout