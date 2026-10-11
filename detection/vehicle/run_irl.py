"""Play real-world parking footage through the existing occupancy pipeline.

Run from the detection directory with:
    python -m vehicle.run_irl --lot campus-west --camera gate-a
"""

import argparse
from datetime import datetime
from pathlib import Path
import threading
import time

import cv2
from dotenv import dotenv_values

from api.occupancy_updater import OccupancyUpdater
from layout.layout_manager import load_layout
from layout.layout_sync import synchronize_layout
from vehicle.occupancy_pipeline import OccupancyPipeline
from vehicle.run_simulator import draw_overlay


DETECTION_DIR = Path(__file__).resolve().parents[1]
DEFAULT_VIDEO = DETECTION_DIR / "12125602_30fps.mp4"
DEFAULT_REFERENCE_IMAGE = DETECTION_DIR / "parking_layout_v2.png"
DEFAULT_MODEL = DETECTION_DIR / "models" / "yolo11n.pt"


def scale_layout_to_frame(layout, frame_width, frame_height, reference_width, reference_height):
    """Scale reviewed camera polygons from their reference image to video size."""
    scale_x = frame_width / reference_width
    scale_y = frame_height / reference_height
    return {
        **layout,
        "spaces": [
            {
                **space,
                "polygon": [
                    [round(point[0] * scale_x), round(point[1] * scale_y)]
                    for point in space["polygon"]
                ],
            }
            for space in layout["spaces"]
        ],
    }


def update_api(updater, changes):
    try:
        updater.apply_changes(changes)
    except Exception as error:
        print(f"API update failed: {error}")


def parse_args():
    env = dotenv_values(DETECTION_DIR / ".env")
    parser = argparse.ArgumentParser(
        description="Run live occupancy detection against a real-world video file"
    )
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO, help="Input video file")
    parser.add_argument("--lot", default=env.get("PARKING_LOT_SLUG", "campus-west"))
    parser.add_argument("--camera", default=env.get("CAMERA_ID", "gate-a"))
    parser.add_argument("--reference-image", type=Path, default=DEFAULT_REFERENCE_IMAGE,
                        help="Image whose dimensions were used to draw the camera layout")
    parser.add_argument("--model-weights", type=Path, default=DEFAULT_MODEL,
                        help="Pretrained YOLO vehicle detector weights")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--confirm-frames", type=int, default=3)
    parser.add_argument("--no-sync", action="store_true",
                        help="Preview only; do not synchronize or update backend occupancy")
    parser.add_argument("--no-preview", action="store_true",
                        help="Do not open the OpenCV preview window")
    parser.add_argument("--output", type=Path,
                        help="Annotated MP4 path; defaults to a timestamped path under detection/output")
    return parser.parse_args()


def main():
    args = parse_args()
    video_path = args.video if args.video.is_absolute() else (Path.cwd() / args.video)
    reference_path = args.reference_image if args.reference_image.is_absolute() else (Path.cwd() / args.reference_image)
    model_path = args.model_weights if args.model_weights.is_absolute() else (Path.cwd() / args.model_weights)

    for path, description in (
        (video_path, "video"),
        (reference_path, "layout reference image"),
        (model_path, "YOLO model weights"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"Could not find {description}: {path}")

    layout = load_layout(args.lot, args.camera)
    reference = cv2.imread(str(reference_path))
    if reference is None:
        raise ValueError(f"Could not read layout reference image: {reference_path}")

    video = cv2.VideoCapture(str(video_path))
    if not video.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    success, first_frame = video.read()
    if not success or first_frame is None:
        video.release()
        raise ValueError(f"Video contains no readable frames: {video_path}")

    frame_height, frame_width = first_frame.shape[:2]
    ref_height, ref_width = reference.shape[:2]
    video_layout = scale_layout_to_frame(
        layout, frame_width, frame_height, ref_width, ref_height
    )

    updater = None
    if args.no_sync:
        sync_result = {"lot_id": None, "spaces": video_layout["spaces"]}
        print("Preview-only mode: backend synchronization and updates are disabled.")
    else:
        sync_result = synchronize_layout(layout, lot_slug=args.lot)
        if len(sync_result["spaces"]) != len(video_layout["spaces"]):
            video.release()
            raise RuntimeError(
                "The backend sync did not return every layout space; refusing to run with a partial lot mapping."
            )
        updater = OccupancyUpdater(sync_result["spaces"], lot_id=sync_result["lot_id"])

    pipeline = OccupancyPipeline(
        layout=video_layout,
        detector_mode="yolo",
        confirmation_frames=args.confirm_frames,
        model_path=str(model_path),
        confidence_threshold=args.confidence,
    )

    fps = video.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 30.0
    output_path = args.output
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = DETECTION_DIR / "output" / f"irl-{args.lot}-{args.camera}-{timestamp}.mp4"
    elif not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    if output_path.exists():
        video.release()
        raise FileExistsError(f"Output already exists; choose another path to avoid overwriting: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (frame_width, frame_height)
    )
    if not writer.isOpened():
        video.release()
        raise ValueError(f"Could not create annotated video: {output_path}")

    print(f"Video feed: {video_path} ({frame_width}x{frame_height} at {fps:.2f} fps)")
    print(f"Camera layout: {args.lot}/{args.camera} ({len(video_layout['spaces'])} spaces)")
    print(f"YOLO weights: {model_path}")
    if not args.no_sync:
        print(f"Backend updates scoped to lot_id={sync_result['lot_id']}")
    print(f"Annotated output: {output_path}")
    print("Press Q in the preview window to stop early. The input video is processed once.")

    frame = first_frame
    frame_period = 1.0 / fps
    next_frame_time = time.monotonic()
    try:
        while frame is not None:
            changes = pipeline.process_frame(frame)
            if changes:
                print(f"Confirmed changes: {changes}")
                if updater is not None:
                    threading.Thread(
                        target=update_api, args=(updater, changes), daemon=True
                    ).start()

            annotated = draw_overlay(
                frame, video_layout, pipeline.last_detections, pipeline.tracker.states
            )
            writer.write(annotated)
            if not args.no_preview:
                cv2.imshow(f"IRL Parking Detection · {args.lot}/{args.camera}", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            next_frame_time += frame_period
            delay = next_frame_time - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            success, frame = video.read()
            if not success:
                frame = None
    finally:
        video.release()
        writer.release()
        if not args.no_preview:
            cv2.destroyAllWindows()

    print(f"Annotated video saved to: {output_path}")


if __name__ == "__main__":
    main()
