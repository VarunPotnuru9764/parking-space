import json
import math
from pathlib import Path

LAYOUT_FILE = Path(__file__).parent / "parking_layout.json"

def layout_file(lot_slug=None, camera_id=None):
    if lot_slug is None and camera_id is None:
        return LAYOUT_FILE
    if not lot_slug or not camera_id:
        raise ValueError("Both lot_slug and camera_id are required for a camera layout")
    safe_lot = "".join(ch for ch in lot_slug.lower() if ch.isalnum() or ch in "-_")
    safe_camera = "".join(ch for ch in camera_id.lower() if ch.isalnum() or ch in "-_")
    if not safe_lot or not safe_camera:
        raise ValueError("lot_slug and camera_id must contain letters, numbers, '-' or '_'")
    return Path(__file__).parent / "layouts" / safe_lot / f"{safe_camera}.json"
def _orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

def _segments_intersect(a, b, c, d):
    ab_c, ab_d = _orientation(a, b, c), _orientation(a, b, d)
    cd_a, cd_b = _orientation(c, d, a), _orientation(c, d, b)
    epsilon = 1e-9
    if ab_c * ab_d < -epsilon and cd_a * cd_b < -epsilon:
        return True

    def on_segment(p, q, r):
        return (min(p[0], r[0]) - epsilon <= q[0] <= max(p[0], r[0]) + epsilon
                and min(p[1], r[1]) - epsilon <= q[1] <= max(p[1], r[1]) + epsilon)

    return (
        (abs(ab_c) <= epsilon and on_segment(a, c, b))
        or (abs(ab_d) <= epsilon and on_segment(a, d, b))
        or (abs(cd_a) <= epsilon and on_segment(c, a, d))
        or (abs(cd_b) <= epsilon and on_segment(c, b, d))
    )

def validate_layout(layout, image_size=None):
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

        normalized_name = slot_number.strip().casefold()
        if normalized_name in slot_names:
            raise ValueError(f"Duplicate parking-space name: {slot_number}")

        slot_names.add(normalized_name)
        if not isinstance(polygon, list):
            raise ValueError(f"Polygon for {slot_number} must be a list")

        if len(polygon) < 3:
            raise ValueError(f"Polygon for {slot_number} must have at least 3 points")

        numeric_points = []
        for point in polygon:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError(f"Invalid polygon point in {slot_number}")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in point):
                raise ValueError(f"Polygon points for {slot_number} must contain finite numbers")
            numeric_points.append((float(point[0]), float(point[1])))
            if image_size is not None:
                width, height = image_size
                if not 0 <= point[0] <= width or not 0 <= point[1] <= height:
                    raise ValueError(f"Polygon for {slot_number} extends outside the source image")

        area_twice = sum(
            numeric_points[i][0] * numeric_points[(i + 1) % len(numeric_points)][1]
            - numeric_points[(i + 1) % len(numeric_points)][0] * numeric_points[i][1]
            for i in range(len(numeric_points))
        )
        if abs(area_twice) < 1e-6:
            raise ValueError(f"Polygon for {slot_number} has zero area")
        point_count = len(numeric_points)
        for first in range(point_count):
            a, b = numeric_points[first], numeric_points[(first + 1) % point_count]
            if a == b:
                raise ValueError(f"Polygon for {slot_number} has a repeated neighboring vertex")
            for second in range(first + 1, point_count):
                if second == first or second == first + 1 or (first == 0 and second == point_count - 1):
                    continue
                c, d = numeric_points[second], numeric_points[(second + 1) % point_count]
                if _segments_intersect(a, b, c, d):
                    raise ValueError(f"Polygon for {slot_number} crosses itself")

    return True

def save_layout(layout, lot_slug=None, camera_id=None):
    validate_layout(layout)
    target = layout_file(lot_slug, camera_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as file:
        json.dump(layout, file, indent=4)

    print(f"Parking layout saved to: {target}")

def load_layout(lot_slug=None, camera_id=None):
    target = layout_file(lot_slug, camera_id)
    if not target.exists() and lot_slug == "simulator" and camera_id == "default" and LAYOUT_FILE.exists():
        target = LAYOUT_FILE
    if not target.exists():
        raise FileNotFoundError("No parking layout has been saved yet")

    with open(target, "r") as file:
        layout = json.load(file)

    validate_layout(layout)
    return layout
