from vehicle import Vehicle
from config import AISLES, PARKING_SPACES, SLOT_AISLES, ENTRANCE, EXIT, CAR_WIDTH, CAR_HEIGHT

def get_parking_target(slot_number):

    x, y, width, height = PARKING_SPACES[slot_number]

    # Center the horizontal car inside the parking space
    target_x = x + (width - CAR_WIDTH) / 2
    target_y = y + (height - CAR_HEIGHT) / 2

    return target_x, target_y


def get_aisle_targets(slot_number):
    """Return the bay aisle point and the connected side-aisle targets."""
    aisle_y, aisle_height = AISLES[SLOT_AISLES[slot_number]]
    parking_target = get_parking_target(slot_number)
    aisle_position_y = aisle_y + (aisle_height - CAR_HEIGHT) / 2
    slot_aisle_target = (parking_target[0], aisle_position_y)
    entry_approach_target = (ENTRANCE[0], aisle_position_y)
    exit_approach_target = (EXIT[0], aisle_position_y)
    return slot_aisle_target, entry_approach_target, exit_approach_target
