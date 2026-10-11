import cv2
import numpy as np

from vehicle.vehicle_detector import VehicleDetector
from vehicle.occupancy import is_space_occupied
from vehicle.occupancy_tracker import OccupancyTracker

class OccupancyPipeline:
    def __init__(self, layout, detector_mode = "simulator", confirmation_frames = 3,
                 model_path = "yolo11n.pt", confidence_threshold = 0.5):
        self.layout = layout
        self.detector_mode = detector_mode
        self.detector = VehicleDetector(
            mode=detector_mode,
            model_path=model_path,
            confidence_threshold=confidence_threshold,
        )
        self.tracker = OccupancyTracker(required_confirmations = confirmation_frames)
        self.last_detections = []
        self.last_slot_detections = {}
        self.space_bounds = {}
        if detector_mode == "parking_spaces":
            self.space_bounds = {
                space["slot_number"]: (
                    np.asarray(space["polygon"], dtype=np.float32),
                    min(point[0] for point in space["polygon"]),
                    min(point[1] for point in space["polygon"]),
                    max(point[0] for point in space["polygon"]),
                    max(point[1] for point in space["polygon"]),
                )
                for space in layout["spaces"]
            }

    def process_frame(self, frame):
        vehicles = self.detector.detect(frame)
        # Expose the current frame's detections for visualization without changing
        # the pipeline's return value or feeding overlay data into tracking.
        self.last_detections = vehicles
        if self.detector_mode == "parking_spaces":
            detected_states = {}
            slot_detections = {}
            for detection in vehicles:
                x1, y1, x2, y2 = detection["bounding_box"]
                center = ((x1 + x2) / 2, (y1 + y2) / 2)
                best_slot = None
                best_distance = -1.0
                for slot_number, (polygon, min_x, min_y, max_x, max_y) in self.space_bounds.items():
                    if min_x <= center[0] <= max_x and min_y <= center[1] <= max_y:
                        distance = cv2.pointPolygonTest(polygon, center, True)
                        if distance >= 0 and distance > best_distance:
                            best_slot = slot_number
                            best_distance = distance

                if best_slot is None:
                    continue

                occupied = detection["class_name"] == "space-occupied"
                previous = detected_states.get(best_slot)
                if previous is None or detection["confidence"] > previous[1]:
                    detected_states[best_slot] = (occupied, detection["confidence"])
                    slot_detections[best_slot] = detection

            self.last_slot_detections = slot_detections
            return self.tracker.update({
                slot_number: state[0]
                for slot_number, state in detected_states.items()
            })

        self.last_slot_detections = {}
        detected_states = {}
        for space in self.layout["spaces"]:
            slot_number = space["slot_number"]
            polygon = space["polygon"]
            occupied = False
            for vehicle in vehicles:
                if is_space_occupied(vehicle["bounding_box"], polygon):
                    occupied = True
                    break

            detected_states[slot_number] = occupied

        confirmed_changes = self.tracker.update(detected_states)
        return confirmed_changes
