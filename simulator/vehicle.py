import math
from config import (CAR_WIDTH, CAR_HEIGHT, CAR_SPEED)

class Vehicle:
    def __init__(self, vehicle_id, x, y, target_position=None, color=(200, 50, 50)):
        self.vehicle_id = vehicle_id
        self.x = float(x)
        self.y = float(y)
        self.color = color

        self.target_position = target_position
        self.state = "entering"

        self.waypoints = []
        self.current_waypoint = 0

    def set_target(self, target_position):
        self.target_position = target_position

    def move(self):
        if self.target_position is None:
            return

        target_x, target_y = self.target_position
        dx = target_x - self.x
        dy = target_y - self.y

        distance = math.sqrt(dx * dx + dy * dy)

        if distance <= CAR_SPEED:
            self.x = target_x
            self.y = target_y
            return True

        self.x += (dx / distance) * CAR_SPEED
        self.y += (dy / distance) * CAR_SPEED
        return False

    def get_center(self):
        return (
            self.x + CAR_WIDTH / 2,
            self.y + CAR_HEIGHT / 2
        )

    def get_rect(self):
        return (
            int(self.x),
            int(self.y),
            CAR_WIDTH,
            CAR_HEIGHT
        )
