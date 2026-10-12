import pygame

from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    PARKING_SPACES,
    AISLES,
    ACCESS_LANE_X,
    ACCESS_LANE_WIDTH,
    EXIT_LANE_X,
    EXIT_LANE_WIDTH,
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

        # Square-ended aisles stop short of the window edges.
        for aisle_name, (aisle_y, aisle_height) in AISLES.items():
            pygame.draw.rect(
                screen,
                (40, 40, 40),
                (
                    20,
                    aisle_y,
                    WINDOW_WIDTH - 40,
                    aisle_height,
                ),
            )
        access_start = ENTRANCE[1]
        access_end = AISLES["A2"][0] + AISLES["A2"][1]
        pygame.draw.rect(
            screen,
            (40, 40, 40),
            (ACCESS_LANE_X, access_start, ACCESS_LANE_WIDTH, access_end - access_start),
        )
        pygame.draw.rect(
            screen,
            (40, 40, 40),
            (
                EXIT_LANE_X,
                AISLES["A1"][0],
                EXIT_LANE_WIDTH,
                WINDOW_HEIGHT - 10 - AISLES["A1"][0],
            ),
        )

        # Subtle center marks make the connecting aisles legible while keeping
        # their pavement the same color as the rest of the lot.
        marking_color = (88, 88, 88)
        for aisle_y, aisle_height in AISLES.values():
            center_y = round(aisle_y + aisle_height / 2)
            for x in range(130, WINDOW_WIDTH - 130, 54):
                pygame.draw.rect(screen, marking_color, (x, center_y - 1, 28, 2))

        entry_center_x = round(ENTRANCE[0] + CAR_WIDTH / 2)
        exit_center_x = round(EXIT[0] + CAR_WIDTH / 2)
        entry_approach_start = round(ENTRANCE[1] + CAR_HEIGHT / 2 + 36)
        exit_approach_end = round(EXIT[1] + CAR_HEIGHT / 2 - 36)
        for y in range(entry_approach_start, AISLES["A2"][0] + AISLES["A2"][1], 42):
            pygame.draw.rect(screen, marking_color, (entry_center_x - 1, y, 2, 20))
        for y in range(AISLES["A1"][0], exit_approach_end, 42):
            pygame.draw.rect(screen, marking_color, (exit_center_x - 1, y, 2, 20))

        # Parking spaces
        font = pygame.font.Font(None, 28)
        aisle_font = pygame.font.Font(None, 24)
        for aisle_name, (aisle_y, aisle_height) in AISLES.items():
            aisle_label = aisle_font.render(aisle_name, True, (190, 190, 190))
            label_rect = pygame.Rect(16, round(aisle_y + aisle_height / 2 - 15), 44, 30)
            pygame.draw.rect(screen, (48, 48, 48), label_rect)
            pygame.draw.rect(screen, marking_color, label_rect, 1)
            screen.blit(aisle_label, aisle_label.get_rect(center=label_rect.center))

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

            label_rect = pygame.Rect(0, 0, 58, 34)
            label_rect.center = (x + width / 2, y + height / 2)
            pygame.draw.rect(screen, (48, 48, 48), label_rect)
            pygame.draw.rect(screen, slot_color, label_rect, 1)
            text_rect = text.get_rect(center=label_rect.center)

            screen.blit(text, text_rect)

        # Entrance and exit gates are centered on their car positions.
        gate_width = 120
        gate_height = 70
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

            gate_accent = (95, 180, 125) if label == "ENTRANCE" else (205, 125, 95)
            pygame.draw.rect(
                screen,
                gate_accent,
                (
                    gate_center[0] - gate_width / 2 + 7,
                    gate_center[1] - gate_height / 2 + 8,
                    4,
                    gate_height - 16,
                ),
            )

            gate_font = pygame.font.Font(None, 22)
            gate_text = gate_font.render(label, True, (220, 220, 220))
            gate_text_rect = gate_text.get_rect(center=gate_center)
            screen.blit(gate_text, gate_text_rect)
