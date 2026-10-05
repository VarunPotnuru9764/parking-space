import cv2
from ultralytics import YOLO

class VehicleDetector:
    def __init__(self, mode = "yolo", model_path = "yolo11n.pt", confidence_threshold = 0.5):
        self.mode = mode
        self.confidence_threshold = confidence_threshold
        if self.mode == "yolo":
            self.model = YOLO(model_path)

        elif self.mode == "simulator":
            self.model = None

        else:
            raise ValueError("Invalid vehicle detection mode")
        
        self.vehicle_classes = {
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck"
        }

    def detect(self, frame):
            if self.mode == "yolo":
                return self.detect_yolo(frame)

            if self.mode == "simulator":
                return self.detect_simulator(frame)

    def detect_yolo(self, frame):
        results = self.model(frame, verbose = False)
        vehicles = []
        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                class_id = int(box.cls[0])
                if class_id not in self.vehicle_classes:
                    continue

                confidence = float(box.conf[0])
                if confidence < self.confidence_threshold:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                vehicles.append({
                    "class_id": class_id,
                    "class_name": self.vehicle_classes[class_id],
                    "confidence": confidence,
                    "bounding_box": (x1, y1, x2, y2)
                })

        return vehicles

    def detect_simulator(self, frame):
        hsv = cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 60, 40), (180, 255, 255))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        vehicles = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 500:
                continue

            x, y, width, height = cv2.boundingRect(contour)
            if width <= 0 or height <= 0:
                continue

            aspect_ratio = width / height
            if aspect_ratio < 0.5 or aspect_ratio > 2.5:
                continue

            bounding_box = (x, y, x + width, y + height)
            vehicles.append({
                "class_id": -1,
                "class_name": "simulator_vehicle",
                "confidence": 1.0,
                "bounding_box": bounding_box
            })

        return vehicles