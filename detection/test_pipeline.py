import cv2
import argparse
from dotenv import dotenv_values
from pathlib import Path
from layout.layout_manager import load_layout
from layout.layout_sync import synchronize_layout
from vehicle.occupancy_pipeline import OccupancyPipeline
from api.occupancy_updater import OccupancyUpdater

IMAGE_PATH = "parking_layout_v1.png"
def main():
    config = dotenv_values(Path(__file__).resolve().parent / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--lot", default=config.get("PARKING_LOT_SLUG", "simulator"))
    parser.add_argument("--camera", default=config.get("CAMERA_ID", "default"))
    args = parser.parse_args()
    image = cv2.imread(IMAGE_PATH)
    if image is None:
        raise ValueError(f"Could not load image: {IMAGE_PATH}")

    layout = load_layout(args.lot, args.camera)
    sync_result = synchronize_layout(layout, lot_slug=args.lot)
    synchronized_spaces = sync_result["spaces"]

    for space in synchronized_spaces:
        print(
            f"  {space['slot_number']} "
            f"→ parking_id={space['parking_id']}"
        )

    pipeline = OccupancyPipeline(
        layout = layout,
        detector_mode = "simulator",
        confirmation_frames = 3
    )

    updater = OccupancyUpdater(synchronized_spaces, lot_id=sync_result["lot_id"])

    print("\n========== Occupancy Pipeline Test ==========")

    # Process the same frame several times
    # so the tracker can confirm the state.
    try:
        for frame_number in range(1, 5):
            changes = pipeline.process_frame(image)
            print(f"Frame {frame_number}: {changes}")
            if changes:
                updater.apply_changes(changes)
    finally:
        updater.close()

if __name__ == "__main__":
    main()
