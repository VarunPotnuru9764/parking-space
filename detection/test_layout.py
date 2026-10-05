import cv2
from layout.layout_review import create_layout
from layout.layout_manager import save_layout
from layout.layout_detector import (ParkingSpaceDetector, draw_candidates)
from layout.layout_sync import (
    get_parking_spaces, 
    compare_layout_with_database,
    synchronize_layout
)

IMAGE_PATH = "parking_layout.png"
def main():
    image = cv2.imread(IMAGE_PATH)
    if image is None:
        print("Could not load image")
        return

    detector = ParkingSpaceDetector()
    candidates = detector.detect(image)
    print(f"Detected {len(candidates)} candidate parking spaces")
    for candidate in candidates:
        print(
            f"Candidate {candidate['candidate_id']}: "
            f"{candidate['polygon'].tolist()}"
        )

    output = draw_candidates(image, candidates)
    cv2.imshow("Parking Space Detection", output)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    layout = create_layout(candidates)
    save_layout(layout)

    sync_result = synchronize_layout(layout)
    print("\nFinal parking layout:")
    print(layout)

    print("\n========== Synchronization Result ==========")

    print("\nSynchronized spaces:")

    for space in sync_result["spaces"]:
        print(
            f"  {space['slot_number']} "
            f"→ parking_id={space['parking_id']}"
        )

    print("\nCreated:")

    for space in sync_result["created"]:
        print(
            f"  {space['slot_number']} "
            f"→ parking_id={space['parking_id']}"
        )

    print("\nMissing from layout:")

    for space in sync_result["missing_from_layout"]:
        print(
            f"  {space['slot_number']} "
            f"→ parking_id={space['parking_id']}"
        )

if __name__ == "__main__":
    main()