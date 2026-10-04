WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700

FPS = 30
PARKING_SPACES = {
    "P01": (220, 60, 160, 160),
    "P02": (420, 60, 160, 160),
    "P03": (620, 60, 160, 160),
    "P04": (220, 480, 160, 160),
    "P05": (420, 480, 160, 160),
    "P06": (620, 480, 160, 160),
}

AISLE_Y = 260
AISLE_HEIGHT = 180

CAR_WIDTH = 80
CAR_HEIGHT = 45
CAR_SPEED = 3

# ENTRANCE is the car's top-left spawn position. Its center aligns with
# the aisle centerline.
ENTRANCE = (
    60,
    AISLE_Y + (AISLE_HEIGHT - CAR_HEIGHT) / 2
)

# EXIT is the car's top-left position; it mirrors the entrance across the lot.
EXIT = (
    WINDOW_WIDTH - ENTRANCE[0] - CAR_WIDTH,
    ENTRANCE[1]
)
