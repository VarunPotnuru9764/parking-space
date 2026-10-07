import cv2
import numpy as np

def calculate_overlap_ratio(bounding_box, parking_polygon):
    """Return the fraction of a detected vehicle box inside a parking polygon."""
    x1, y1, x2, y2 = bounding_box
    polygon = np.array(parking_polygon, dtype = np.int32)

    min_x = min(x1, int(polygon[:, 0].min()))
    min_y = min(y1, int(polygon[:, 1].min()))

    max_x = max(x2, int(polygon[:, 0].max()))
    max_y = max(y2, int(polygon[:, 1].max()))

    width = max_x - min_x + 1
    height = max_y - min_y + 1

    if width <= 0 or height <= 0:
        return 0.0

    polygon_mask = np.zeros((height, width), dtype = np.uint8)
    vehicle_mask = np.zeros((height, width), dtype = np.uint8)

    shifted_polygon = polygon.copy()
    shifted_polygon[:, 0] -= min_x
    shifted_polygon[:, 1] -= min_y

    cv2.fillPoly(polygon_mask, [shifted_polygon], 255)
    shifted_box = (x1 - min_x, y1 - min_y, x2 - min_x, y2 - min_y)
    cv2.rectangle(
        vehicle_mask,
        (shifted_box[0], shifted_box[1]),
        (shifted_box[2], shifted_box[3]),
        255,
        -1
    )

    vehicle_area = cv2.countNonZero(vehicle_mask)
    if vehicle_area == 0:
        return 0.0

    intersection = cv2.bitwise_and(polygon_mask, vehicle_mask)
    overlap_area = cv2.countNonZero(intersection)
    return overlap_area / vehicle_area

def is_space_occupied(bounding_box, parking_polygon, overlap_threshold = 0.30):
    overlap_ratio = calculate_overlap_ratio(bounding_box,parking_polygon)
    return overlap_ratio >= overlap_threshold
