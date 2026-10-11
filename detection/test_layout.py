import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import cv2
from layout.layout_review import create_layout
from layout.layout_manager import save_layout
from layout.layout_detector import (ParkingSpaceDetector, draw_candidates as draw_contour_candidates)
from layout.layout_sync import (
    get_parking_spaces, 
    compare_layout_with_database,
    synchronize_layout
)

def main():
    parser = argparse.ArgumentParser(description="Detect, review, save and optionally sync parking-space polygons")
    parser.add_argument("--image", default="parking_layout.png", help="Image to inspect (video users can extract a representative frame)")
    parser.add_argument("--model-weights", help="Pretrained Ultralytics parking-space detector checkpoint (.pt)")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--sync", action="store_true", help="Synchronize reviewed spaces with the configured backend")
    parser.add_argument("--lot", default="simulator", help="Lot slug; its layout is stored separately")
    parser.add_argument("--camera", default="default", help="Camera identifier for the layout file")
    parser.add_argument(
        "--export-review", nargs="?", const="auto",
        help="Export all untouched detector candidates for the React editor (optional JSON path)",
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.is_absolute():
        image_path = Path(__file__).resolve().parent / image_path
    image = cv2.imread(str(image_path))
    if image is None:
        print("Could not load image")
        return

    if args.model_weights:
        from layout.pretrained_layout_detector import (
            PretrainedParkingSpaceDetector,
            draw_candidates as draw_pretrained_candidates,
        )
        detector = PretrainedParkingSpaceDetector(args.model_weights, confidence=args.confidence)
        draw = draw_pretrained_candidates
    else:
        detector = ParkingSpaceDetector()
        draw = draw_contour_candidates
    candidates = detector.detect(image)
    print(f"Detected {len(candidates)} candidate parking spaces")
    for candidate in candidates:
        print(
            f"Candidate {candidate['candidate_id']}: "
            f"{candidate['polygon'].tolist() if hasattr(candidate['polygon'], 'tolist') else candidate['polygon']}"
        )

    if args.export_review:
        if args.export_review == "auto":
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            safe_lot = re.sub(r"[^A-Za-z0-9_-]", "_", args.lot)[:80] or "lot"
            safe_camera = re.sub(r"[^A-Za-z0-9_-]", "_", args.camera)[:80] or "camera"
            export_path = Path(__file__).resolve().parent / "layout" / "review_sessions" / f"{safe_lot}-{safe_camera}-{timestamp}.json"
        else:
            export_path = Path(args.export_review)
            if not export_path.is_absolute():
                export_path = Path(__file__).resolve().parent / export_path
        export_path.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            "format": "parking-layout-review-v1",
            "lot_slug": args.lot,
            "camera_id": args.camera,
            "image_filename": image_path.name,
            "image_width": int(image.shape[1]),
            "image_height": int(image.shape[0]),
            "detector_candidates": [
                {
                    "candidate_id": int(candidate["candidate_id"]),
                    "stable_id": f"detector-{candidate['candidate_id']}",
                    "polygon": candidate["polygon"].tolist() if hasattr(candidate["polygon"], "tolist") else candidate["polygon"],
                    "confidence": candidate.get("confidence"),
                    "class_name": candidate.get("class_name"),
                }
                for candidate in candidates
            ],
        }
        export_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        print(f"Review bundle exported to: {export_path}")
        print("Import this JSON and the original image in the React Parking Layout Configuration Tool.")
        return

    output = draw(image, candidates)
    cv2.imshow("Parking Space Detection", output)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    layout = create_layout(candidates)
    save_layout(layout, args.lot, args.camera)

    if not args.sync:
        print("Layout saved. Pass --sync to synchronize reviewed spaces with the backend.")
        return

    sync_result = synchronize_layout(layout, lot_slug=args.lot)
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
