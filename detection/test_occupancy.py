import cv2

from vehicle.vehicle_detector import VehicleDetector
from vehicle.occupancy import calculate_overlap_ratio
from layout.layout_manager import load_layout

IMAGE_PATH = "parking_layout_v1.png"
def main():
    image = cv2.imread(IMAGE_PATH)
    if image is None:
        raise ValueError(f"Could not load image: {IMAGE_PATH}")

    layout = load_layout()
    detector = VehicleDetector(mode = "simulator")
    vehicles = detector.detect(image)

    print("\n========== Occupancy Test ==========")
    for space in layout["spaces"]:
        slot_number = space["slot_number"]
        polygon = space["polygon"]

        best_overlap = 0.0
        for vehicle in vehicles:
            overlap = calculate_overlap_ratio(
                vehicle["bounding_box"],
                polygon
            )

            best_overlap = max(
                best_overlap,
                overlap
            )

        occupied = best_overlap >= 0.30

        print(
            f"{slot_number}: "
            f"{'OCCUPIED' if occupied else 'VACANT'} "
            f"(overlap={best_overlap:.2f})"
        )

if __name__ == "__main__":
    main()