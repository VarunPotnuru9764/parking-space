import cv2
import numpy as np

class ParkingSpaceDetector:
    def __init__(self):
        pass

    def detect(self, image):
        if image is None:
            raise ValueError("Could not load input image")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        candidates = []
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        image_height, image_width = gray.shape
        image_area = image_width * image_height
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < image_area * 0.01:
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue

            approximation = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            if len(approximation) != 4:
                continue

            if not cv2.isContourConvex(approximation):
                continue

            x, y, width, height = cv2.boundingRect(approximation)
            if width == 0 or height == 0:
                continue

            aspect_ratio = width / height
            if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                continue

            candidates.append({
                "polygon": approximation.reshape(4, 2),
                "area": area,
                "bounding_box": (x, y, width, height)
            })

        candidates.sort(key = lambda candidate: (candidate["bounding_box"][1], candidate["bounding_box"][0]))
        for index, candidate in enumerate(candidates):
            candidate["candidate_id"] = index + 1

        return candidates

def draw_candidates(image, candidates):
    output = image.copy()
    for candidate in candidates:
        polygon = candidate["polygon"]
        candidate_id = candidate["candidate_id"]
        cv2.polylines(output, [polygon], True, (0, 255, 0), 3)
        x, y, width, height = candidate["bounding_box"]
        cv2.putText(output, f"Candidate {candidate_id}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return output