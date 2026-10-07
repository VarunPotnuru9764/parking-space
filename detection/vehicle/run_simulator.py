import cv2
import numpy as np
import time
import threading

from layout.layout_manager import load_layout
from layout.layout_sync import synchronize_layout

from vehicle.occupancy_pipeline import OccupancyPipeline
from vehicle.occupancy import calculate_overlap_ratio
from api.occupancy_updater import OccupancyUpdater

LIVE_FEED_URL = "http://127.0.0.1:8765/video"
OUTPUT_VIDEO_PATH = "../simulator/parking_simulation_annotated.mp4"


def scale_layout_to_frame(layout, frame_width, frame_height, reference_width, reference_height):
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

def draw_overlay(frame, layout, vehicles, tracker_states):
    output = frame.copy()
    for vehicle in vehicles:
        x1, y1, x2, y2 = vehicle["bounding_box"]
        confidence = vehicle.get("confidence", 0.0)
        cv2.rectangle(output, (x1, y1), (x2, y2), (255, 200, 0), 2)
        cv2.putText(
            output,
            f"Vehicle {confidence:.0%}",
            (x1, max(18, y1 - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 200, 0),
            2,
            cv2.LINE_AA,
        )

    for space in layout["spaces"]:
        slot_number = space["slot_number"]
        polygon = space["polygon"]
        polygon_points = np.array(polygon, dtype=np.int32)
        occupied = tracker_states.get(slot_number, False)
        color = (0, 0, 255) if occupied else (0, 200, 0)

        cv2.polylines(output, [polygon_points], True, color, 3, cv2.LINE_AA)

        best_overlap = 0.0
        best_confidence = 0.0
        for vehicle in vehicles:
            overlap = calculate_overlap_ratio(vehicle["bounding_box"], polygon)
            if overlap > best_overlap:
                best_overlap = overlap
                best_confidence = vehicle.get("confidence", 0.0)

        status = "OCCUPIED" if occupied else "VACANT"
        lines = (
            f"{slot_number}: {status}",
            f"Ovl {best_overlap:.0%} | Conf {best_confidence:.0%}",
        )
        x, y, width, height = cv2.boundingRect(polygon_points)
        font = 0.42
        line_height = 17
        label_x = x + 7
        label_y = y + 7

        text_sizes = [
            cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font, 1)[0]
            for text in lines
        ]
        panel_width = min(width - 8, max(size[0] for size in text_sizes) + 10)
        panel_height = line_height * len(lines) + 7
        x2 = min(frame.shape[1], label_x + panel_width)
        y2 = min(frame.shape[0], label_y + panel_height)
        roi = output[label_y:y2, label_x:x2]
        if roi.size:
            shade = roi.copy()
            cv2.rectangle(shade, (0, 0), (shade.shape[1] - 1, shade.shape[0] - 1), (20, 20, 20), -1)
            cv2.addWeighted(shade, 0.68, roi, 0.32, 0, roi)

        for line_index, text in enumerate(lines):
            text_y = label_y + 13 + line_index * line_height
            cv2.putText(
                output,
                text,
                (label_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                font,
                color,
                1,
                cv2.LINE_AA,
            )
    return output

def update_api(updater, changes):
    try:
        updater.apply_changes(changes)
    except Exception as e:
        print(f"API update failed: {e}")

def main():
    layout = load_layout()
    video = cv2.VideoCapture(LIVE_FEED_URL)
    if not video.isOpened():
        raise ValueError(
            f"Could not open live simulator feed: {LIVE_FEED_URL}. "
            "Start simulator/main.py first."
        )

    video.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    print(f"Waiting for live frames from {LIVE_FEED_URL}...")
    success, first_frame = video.read()
    while not success:
        time.sleep(0.1)
        success, first_frame = video.read()

    frame_height, frame_width = first_frame.shape[:2]
    reference_image = cv2.imread("parking_layout.png")
    if reference_image is None:
        video.release()
        raise ValueError("Could not load layout reference image: parking_layout.png")
    reference_height, reference_width = reference_image.shape[:2]
    video_layout = scale_layout_to_frame(
        layout,
        frame_width,
        frame_height,
        reference_width,
        reference_height,
    )

    # Use video-pixel coordinates for both occupancy detection and the overlay.
    # Passing the unscaled reference-image polygons to the pipeline makes their
    # lower edges extend into the aisle and can mark passing cars as parked.
    sync_result = synchronize_layout(video_layout)
    synchronized_spaces = sync_result["spaces"]

    print("\nSynchronized parking spaces:")
    for space in synchronized_spaces:
        print(
            f"  {space['slot_number']} "
            f"→ parking_id={space['parking_id']}"
        )

    pipeline = OccupancyPipeline(layout = sync_result, detector_mode = "simulator", confirmation_frames = 3)
    updater = OccupancyUpdater(synchronized_spaces)
    
    print("\nStarting live simulator detection...")
    print("Press Q to stop\n")

    fps = video.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
    writer = cv2.VideoWriter(
        OUTPUT_VIDEO_PATH,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (frame_width, frame_height),
    )
    if not writer.isOpened():
        video.release()
        raise ValueError(f"Could not create output video: {OUTPUT_VIDEO_PATH}")

    frame = first_frame

    while True:
        if frame is None:
            success, frame = video.read()
            if not success:
                time.sleep(0.02)
                continue

        changes = pipeline.process_frame(frame)
        if changes:
            print(f"Confirmed changes: {changes}")
            threading.Thread(target = update_api, args = (updater, changes), daemon = True).start()

        annotated_frame = draw_overlay(
            frame,
            video_layout,
            pipeline.last_detections,
            pipeline.tracker.states,
        )
        writer.write(annotated_frame)
        cv2.imshow("Parking Occupancy Detection", annotated_frame)
        frame = None
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video.release()
    writer.release()
    cv2.destroyAllWindows()
    print(f"Annotated video saved to: {OUTPUT_VIDEO_PATH}")

if __name__ == "__main__":
    main()
