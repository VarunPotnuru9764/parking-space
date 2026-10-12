"""Play real-world parking footage through the existing occupancy pipeline.

Run from the detection directory with:
    python -m vehicle.run_irl --lot campus-west --camera gate-a
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import time

import cv2
import numpy as np
from dotenv import dotenv_values

from api.occupancy_updater import OccupancyUpdater
from layout.layout_manager import load_layout
from layout.layout_sync import synchronize_layout
from vehicle.occupancy_pipeline import OccupancyPipeline
from vehicle.run_simulator import draw_overlay


DETECTION_DIR = Path(__file__).resolve().parents[1]
DEFAULT_VIDEO = DETECTION_DIR / "12125602_30fps.mp4"
DEFAULT_REFERENCE_IMAGE = DETECTION_DIR / "parking_layout_v2.png"
DEFAULT_MODEL = DETECTION_DIR / "models" / "parking_lot.pt"


def resize_video_frame(frame, target_width, target_height):
    """Fit a video frame to the layout image size without distorting vehicles."""
    source_height, source_width = frame.shape[:2]
    scale = max(target_width / source_width, target_height / source_height)
    resized_width = round(source_width * scale)
    resized_height = round(source_height * scale)
    resized = cv2.resize(
        frame, (resized_width, resized_height), interpolation=cv2.INTER_AREA
    )
    left = (resized_width - target_width) // 2
    top = (resized_height - target_height) // 2
    return resized[top:top + target_height, left:left + target_width]


def estimate_frame_to_reference(reference, frame):
    """Register the video view to the reviewed image using static scene features."""
    ref_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=3000)
    ref_points, ref_descriptors = orb.detectAndCompute(ref_gray, None)
    frame_points, frame_descriptors = orb.detectAndCompute(frame_gray, None)
    if ref_descriptors is None or frame_descriptors is None:
        raise ValueError("Could not find enough visual features to align the reference image")

    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(
        ref_descriptors, frame_descriptors, k=2
    )
    matches = [first for first, second in pairs if first.distance < 0.7 * second.distance]
    if len(matches) < 30:
        raise ValueError(
            "The reference image does not appear to match this video view; "
            "choose a frame from the same camera and scene"
        )

    reference_to_frame, inlier_mask = cv2.findHomography(
        np.float32([ref_points[item.queryIdx].pt for item in matches]).reshape(-1, 1, 2),
        np.float32([frame_points[item.trainIdx].pt for item in matches]).reshape(-1, 1, 2),
        cv2.RANSAC,
        4.0,
    )
    inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
    if reference_to_frame is None or inliers < 30:
        raise ValueError(
            "Could not reliably align the video to the reviewed reference image; "
            "check that both show the same camera view"
        )

    return np.linalg.inv(reference_to_frame), inliers


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
                        help="YOLO weights matching the selected detector mode")
    parser.add_argument("--detector-mode", choices=("parking_spaces", "vehicles"),
                        default="parking_spaces",
                        help="Classify parking spaces directly, or detect vehicles")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--confirm-frames", type=int, default=3)
    parser.add_argument("--frame-stride", type=int, default=1,
                        help="Attempt inference every Nth source frame; output always keeps source FPS (default: 1)")
    parser.add_argument("--inference-threads", type=int, default=1,
                        help="CPU threads reserved for each inference (default: 1 to keep playback responsive)")
    parser.add_argument("--no-sync", action="store_true",
                        help="Preview only; do not synchronize or update backend occupancy")
    parser.add_argument("--no-preview", action="store_true",
                        help="Do not open the OpenCV preview window")
    parser.add_argument("--output", type=Path,
                        help="Annotated MP4 path; defaults to a timestamped path under detection/output")
    return parser.parse_args()


def run_video(args, on_frame=None, on_progress=None, stop_event=None):
    if args.frame_stride < 1:
        raise ValueError("--frame-stride must be at least 1")
    if args.inference_threads < 1:
        raise ValueError("--inference-threads must be at least 1")
    import torch
    torch.set_num_threads(args.inference_threads)
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

    ref_height, ref_width = reference.shape[:2]
    # Run detection and polygon overlap in the reviewed reference image's pixel
    # space. The frame transform preserves aspect ratio and center-crops to the
    # reviewed view, avoiding stretched vehicles and mismatched coordinates.
    frame_width, frame_height = ref_width, ref_height
    video_layout = layout
    normalized_first = resize_video_frame(first_frame, frame_width, frame_height)
    frame_to_reference, alignment_inliers = estimate_frame_to_reference(
        reference, normalized_first
    )
    source_height, source_width = first_frame.shape[:2]
    fit_scale = max(frame_width / source_width, frame_height / source_height)
    fitted_width = round(source_width * fit_scale)
    fitted_height = round(source_height * fit_scale)
    crop_left = (fitted_width - frame_width) // 2
    crop_top = (fitted_height - frame_height) // 2
    source_to_fitted = np.array(
        [[fit_scale, 0, -crop_left], [0, fit_scale, -crop_top], [0, 0, 1]],
        dtype=np.float64,
    )
    source_to_reference = frame_to_reference @ source_to_fitted

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
        detector_mode=("yolo" if args.detector_mode == "vehicles" else "parking_spaces"),
        confirmation_frames=args.confirm_frames,
        model_path=str(model_path),
        confidence_threshold=args.confidence,
    )

    source_fps = video.get(cv2.CAP_PROP_FPS)
    if not source_fps or source_fps <= 0:
        source_fps = 30.0
    fps = source_fps
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
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

    print(
        f"Video feed: {video_path} ({source_width}x{source_height} at {source_fps:.2f} fps); "
        f"detection size: {frame_width}x{frame_height}; output: {fps:.2f} fps"
    )
    print(f"Reference-image alignment: {alignment_inliers} feature inliers")
    print(f"Camera layout: {args.lot}/{args.camera} ({len(video_layout['spaces'])} spaces)")
    print(f"YOLO weights: {model_path}")
    if not args.no_sync:
        print(f"Backend updates scoped to lot_id={sync_result['lot_id']}")
    print(f"Annotated output: {output_path}")
    print(
        f"Attempting inference every {args.frame_stride} source frame(s); "
        "busy inference frames are skipped while every source frame is played and saved. "
        "Press Q in the preview window to stop early."
    )

    frame = first_frame
    frame_period = 1.0 / source_fps
    playback_started = time.monotonic()
    source_frame_index = 0
    submitted_inferences = 0
    skipped_inferences = 0
    last_stats_frame = 0
    last_detections = []
    last_slot_detections = {}
    tracker_states = {}
    overlay_frame = None
    overlay_mask = None
    detection_executor = ThreadPoolExecutor(max_workers=1)
    pending_detection = None
    initial_snapshot_reported = False

    def accept_detection_result(future):
        nonlocal last_detections, last_slot_detections, tracker_states
        nonlocal overlay_frame, overlay_mask
        changes = future.result()
        last_detections = list(pipeline.last_detections)
        last_slot_detections = dict(pipeline.last_slot_detections)
        tracker_states = dict(pipeline.tracker.states)
        # Render the expensive labels and polygons only when inference changes.
        # Reuse this transparent-by-mask overlay for the source frames between
        # inference results so playback rendering stays lightweight.
        overlay_frame = draw_overlay(
            np.zeros((frame_height, frame_width, 3), dtype=np.uint8),
            video_layout,
            last_detections,
            tracker_states,
            slot_detections=last_slot_detections,
        )
        overlay_gray = cv2.cvtColor(overlay_frame, cv2.COLOR_BGR2GRAY)
        _, overlay_mask = cv2.threshold(overlay_gray, 0, 255, cv2.THRESH_BINARY)
        if changes:
            print(f"Confirmed changes: {changes}")
            if updater is not None:
                updater.apply_changes(changes)
        return changes

    overlay_frame = draw_overlay(
        np.zeros((frame_height, frame_width, 3), dtype=np.uint8),
        video_layout,
        last_detections,
        tracker_states,
        slot_detections=last_slot_detections,
    )
    overlay_gray = cv2.cvtColor(overlay_frame, cv2.COLOR_BGR2GRAY)
    _, overlay_mask = cv2.threshold(overlay_gray, 0, 255, cv2.THRESH_BINARY)

    try:
        while frame is not None and not (stop_event is not None and stop_event.is_set()):
            detection_frame = cv2.warpPerspective(
                frame,
                source_to_reference,
                (frame_width, frame_height),
                flags=cv2.INTER_LINEAR,
            )
            if pending_detection is not None and pending_detection.done():
                accept_detection_result(pending_detection)
                pending_detection = None
            if source_frame_index % args.frame_stride == 0:
                if pending_detection is None:
                    pending_detection = detection_executor.submit(
                        pipeline.process_frame, detection_frame.copy()
                    )
                    submitted_inferences += 1
                else:
                    skipped_inferences += 1

            if not initial_snapshot_reported and tracker_states:
                confirmed = len(tracker_states)
                unmatched = len(video_layout["spaces"]) - confirmed
                print(
                    f"Initial occupancy snapshot: {confirmed}/{len(video_layout['spaces'])} "
                    f"spaces classified; {unmatched} unmatched spaces remain unchanged."
                )
                initial_snapshot_reported = True

            annotated = detection_frame.copy()
            cv2.copyTo(overlay_frame, overlay_mask, annotated)
            writer.write(annotated)
            if on_frame is not None:
                on_frame(annotated, source_frame_index + 1, total_frames)
            if on_progress is not None:
                on_progress(source_frame_index + 1, total_frames)
            if not args.no_preview:
                preview_scale = min(1.0, 1280 / frame_width, 800 / frame_height)
                preview = cv2.resize(
                    annotated,
                    (round(frame_width * preview_scale), round(frame_height * preview_scale)),
                    interpolation=cv2.INTER_AREA,
                )
                cv2.imshow(f"IRL Parking Detection · {args.lot}/{args.camera}", preview)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            source_frame_index += 1
            if source_frame_index - last_stats_frame >= max(1, round(source_fps * 5)):
                elapsed = max(time.monotonic() - playback_started, 1e-6)
                print(
                    f"Playback {source_frame_index / elapsed:.1f}/{source_fps:.1f} FPS; "
                    f"inference {submitted_inferences / elapsed:.1f} FPS "
                    f"({skipped_inferences} requests skipped while busy)"
                )
                last_stats_frame = source_frame_index
            next_frame_time = playback_started + source_frame_index * frame_period
            delay = next_frame_time - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            success, frame = video.read()
            if not success:
                frame = None

        if pending_detection is not None:
            accept_detection_result(pending_detection)
            pending_detection = None
    finally:
        video.release()
        writer.release()
        detection_executor.shutdown(wait=True)
        if updater is not None:
            updater.clear_lot_occupancy()
            updater.close()
        if not args.no_preview:
            cv2.destroyAllWindows()

    print(
        f"Inference frames submitted: {submitted_inferences}; "
        f"skipped while inference was busy: {skipped_inferences}"
    )
    print(f"Annotated video saved to: {output_path}")
    return output_path


def main():
    return run_video(parse_args())


if __name__ == "__main__":
    main()
