import cv2
from vehicle.vehicle_detector import VehicleDetector

IMAGE_PATH = "parking_frame.png"
def main():
    image = cv2.imread(IMAGE_PATH)
    if image is None:
        raise ValueError(f"Could not load image: {IMAGE_PATH}")

    detector = VehicleDetector()
    vehicles = detector.detect(image)
    print("\nDetected vehicles:")
    for vehicle in vehicles:
        print(
            f"{vehicle['class_name']} "
            f"confidence={vehicle['confidence']:.2f} "
            f"box={vehicle['bounding_box']}"
        )

if __name__ == "__main__":
    main()