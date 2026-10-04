from vehicle import Vehicle
from config import (
    ENTRANCE,
    PARKING_SPACES,
    AISLE_Y,
    CAR_WIDTH,
    CAR_HEIGHT
)

def get_parking_target(slot_number):

    x, y, width, height = PARKING_SPACES[slot_number]

    # Center the horizontal car inside the parking space
    target_x = x + (width - CAR_WIDTH) / 2
    target_y = y + (height - CAR_HEIGHT) / 2

    return target_x, target_y