"""Adapter for pretrained Ultralytics parking-space detectors.

The model must predict parking-space regions (for example, space-empty and
space-occupied), rather than vehicle boxes. Ultralytics boxes are converted
to four-corner polygons for review; they are approximate regions, not painted
line segmentation.
"""

from pathlib import Path


class PretrainedParkingSpaceDetector:
    def __init__(self, weights, confidence=0.25, classes=None):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Install detection requirements to use pretrained inference"
            ) from exc

        if not Path(weights).exists():
            raise FileNotFoundError(f"Model weights not found: {weights}")
        self.model = YOLO(str(weights))
        self.confidence = confidence
        self.classes = classes

    def detect(self, image):
        if image is None:
            raise ValueError("Could not load input image")

        result = self.model.predict(
            source=image, conf=self.confidence, classes=self.classes, verbose=False
        )[0]
        candidates = []
        if result.boxes is None:
            return candidates

        for index, box in enumerate(result.boxes):
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().round().astype(int).tolist()
            if x2 <= x1 or y2 <= y1:
                continue
            polygon = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
            candidates.append({
                "candidate_id": index + 1,
                "polygon": polygon,
                "bounding_box": (x1, y1, x2 - x1, y2 - y1),
                "confidence": float(box.conf[0].cpu()),
                "class_name": result.names[int(box.cls[0].cpu())],
            })
        candidates.sort(key=lambda item: (item["bounding_box"][1], item["bounding_box"][0]))
        for index, candidate in enumerate(candidates):
            candidate["candidate_id"] = index + 1
        return candidates


def draw_candidates(image, candidates):
    import cv2
    import numpy as np

    output = image.copy()
    for item in candidates:
        polygon = np.asarray(item["polygon"], dtype=np.int32)
        cv2.polylines(output, [polygon], True, (0, 220, 255), 2)
        x, y, _, _ = item["bounding_box"]
        label = f"{item['candidate_id']} {item.get('class_name', '')} {item.get('confidence', 0):.2f}"
        cv2.putText(output, label, (x, max(y - 6, 18)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 220, 255), 2)
    return output
