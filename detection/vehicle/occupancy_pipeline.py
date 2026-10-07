from vehicle.vehicle_detector import VehicleDetector
from vehicle.occupancy import is_space_occupied
from vehicle.occupancy_tracker import OccupancyTracker

class OccupancyPipeline:
    def __init__(self, layout, detector_mode = "simulator", confirmation_frames = 3):
        self.layout = layout
        self.detector = VehicleDetector(mode = detector_mode)
        self.tracker = OccupancyTracker(required_confirmations = confirmation_frames)
        self.last_detections = []

    def process_frame(self, frame):
        vehicles = self.detector.detect(frame)
        # Expose the current frame's detections for visualization without changing
        # the pipeline's return value or feeding overlay data into tracking.
        self.last_detections = vehicles
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
