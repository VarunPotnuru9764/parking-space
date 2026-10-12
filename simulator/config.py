WINDOW_WIDTH = 1250
WINDOW_HEIGHT = 825

FPS = 30
PARKING_SPACES = {
    **{f"P{index + 1:02d}": (150 + index * 164, 60, 130, 150) for index in range(6)},
    **{f"P{index + 7:02d}": (150 + index * 164, 340, 130, 150) for index in range(6)},
    **{f"P{index + 13:02d}": (150 + index * 164, 620, 130, 150) for index in range(6)},
}

# Two horizontal drive aisles serve the three parking rows.
AISLES = {
    "A1": (225, 95),
    "A2": (505, 95),
}
ACCESS_LANE_X = 10
ACCESS_LANE_WIDTH = 120
EXIT_LANE_X = 1120
EXIT_LANE_WIDTH = 120
SLOT_AISLES = {
    **{f"P{index:02d}": "A1" for index in range(1, 7)},
    **{f"P{index:02d}": "A1" for index in range(7, 10)},
    **{f"P{index:02d}": "A2" for index in range(10, 13)},
    **{f"P{index:02d}": "A2" for index in range(13, 19)},
}

CAR_WIDTH = 100
CAR_HEIGHT = 53
CAR_SPEED = 3.75

# Corner gates connect to the main aisles through their side approaches.
ENTRANCE = (20, 45)
EXIT = (WINDOW_WIDTH - CAR_WIDTH - 20, WINDOW_HEIGHT - CAR_HEIGHT - 45)
