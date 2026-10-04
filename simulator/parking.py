import pygame

from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    PARKING_SPACES,
    AISLE_Y,
    AISLE_HEIGHT,
    ENTRANCE,
    EXIT,
    CAR_WIDTH,
    CAR_HEIGHT
)


class ParkingLot:

    def __init__(self):
        self.parking_spaces = PARKING_SPACES
        self.occupied_spaces = {}

    def reserve_vacant_space(self, vehicle_id, color):
        for slot_number in self.parking_spaces:
            if slot_number not in self.occupied_spaces:
                self.occupied_spaces[slot_number] = (vehicle_id, color)
                return slot_number
        return None

    def release_space(self, slot_number, vehicle_id):
        reservation = self.occupied_spaces.get(slot_number)
        if reservation is not None and reservation[0] == vehicle_id:
            del self.occupied_spaces[slot_number]

    def draw(self, screen):

        # Background
        screen.fill((40, 40, 40))

        # Main aisle
        pygame.draw.rect(
            screen,
            (75, 75, 75),
            (
                0,
                AISLE_Y,
                WINDOW_WIDTH,
                AISLE_HEIGHT
            )
        )

        # Parking spaces
        font = pygame.font.Font(None, 28)

        for slot_number, (x, y, width, height) in self.parking_spaces.items():

            reservation = self.occupied_spaces.get(slot_number)
            slot_color = reservation[1] if reservation else (220, 220, 220)

            pygame.draw.rect(
                screen,
                slot_color,
                (x, y, width, height),
                3
            )

            text = font.render(
                slot_number,
                True,
                slot_color
            )

            text_rect = text.get_rect(
                center=(
                    x + width / 2,
                    y + height / 2
                )
            )

            screen.blit(text, text_rect)

        # Entrance and exit gates are centered on their car positions.
        gate_width = 140
        gate_height = 80
        for label, car_position in (("ENTRANCE", ENTRANCE), ("EXIT", EXIT)):
            gate_center = (
                car_position[0] + CAR_WIDTH / 2,
                car_position[1] + CAR_HEIGHT / 2
            )

            pygame.draw.rect(
                screen,
                (220, 220, 220),
                (
                    gate_center[0] - gate_width / 2,
                    gate_center[1] - gate_height / 2,
                    gate_width,
                    gate_height
                ),
                2
            )

            gate_text = font.render(label, True, (220, 220, 220))
            gate_text_rect = gate_text.get_rect(center=gate_center)
            screen.blit(gate_text, gate_text_rect)
