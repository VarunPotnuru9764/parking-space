import pygame

from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    FPS,
    ENTRANCE,
    EXIT,
    AISLE_Y,
    AISLE_HEIGHT,
    CAR_HEIGHT,
    PARKING_SPACES
)

from parking import ParkingLot
from scenario import get_parking_target
from vehicle import Vehicle


CAR_COLORS = (
    (230, 70, 70),
    (70, 170, 240),
    (80, 210, 130),
    (220, 120, 240),
    (245, 190, 60),
    (60, 210, 210),
)


def spawn_car(parking_lot, cars, vehicle_id_number):
    vehicle_id = f"CAR-{vehicle_id_number}"
    used_colors = {
        reservation[1]
        for reservation in parking_lot.occupied_spaces.values()
    }
    preferred_color_index = (vehicle_id_number - 1) % len(CAR_COLORS)
    car_color = next(
        (
            CAR_COLORS[(preferred_color_index + offset) % len(CAR_COLORS)]
            for offset in range(len(CAR_COLORS))
            if CAR_COLORS[(preferred_color_index + offset) % len(CAR_COLORS)]
            not in used_colors
        ),
        CAR_COLORS[preferred_color_index]
    )
    slot_number = parking_lot.reserve_vacant_space(vehicle_id, car_color)

    if slot_number is None:
        return vehicle_id_number

    parking_target = get_parking_target(slot_number)
    aisle_target = (
        parking_target[0],
        AISLE_Y + (AISLE_HEIGHT - CAR_HEIGHT) / 2
    )
    car = Vehicle(
        vehicle_id,
        *ENTRANCE,
        target_position=aisle_target,
        color=car_color
    )
    car.slot_number = slot_number
    car.aisle_target = aisle_target
    car.waypoints = [aisle_target, parking_target]
    cars.append(car)
    return vehicle_id_number + 1


def main():

    pygame.init()

    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT)
    )

    pygame.display.set_caption(
        "Parking Lot Simulator"
    )

    clock = pygame.time.Clock()
    button_font = pygame.font.Font(None, 28)
    spawn_button = pygame.Rect(WINDOW_WIDTH - 180, 12, 165, 42)

    parking_lot = ParkingLot()

    cars = []
    next_vehicle_id = 1

    running = True

    while running:

        leave_buttons = {
            car.vehicle_id: pygame.Rect(
                PARKING_SPACES[car.slot_number][0] + 5,
                (
                    PARKING_SPACES[car.slot_number][1]
                    + PARKING_SPACES[car.slot_number][3]
                    + 6
                    if car.slot_number in ("P04", "P05", "P06")
                    else PARKING_SPACES[car.slot_number][1] - 34
                ),
                PARKING_SPACES[car.slot_number][2] - 10,
                28
            )
            for car in cars if car.state == "parked"
        }

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and spawn_button.collidepoint(event.pos)
            ):
                next_vehicle_id = spawn_car(
                    parking_lot,
                    cars,
                    next_vehicle_id
                )

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for car in cars:
                    button = leave_buttons.get(car.vehicle_id)
                    if button and button.collidepoint(event.pos):
                        car.waypoints = [car.aisle_target, EXIT]
                        car.current_waypoint = 0
                        car.set_target(car.waypoints[0])
                        car.state = "leaving"
                        break

        current_time = pygame.time.get_ticks() / 1000

        exited_cars = []

        for car in cars:
            if car.state == "entering":
                if car.move():
                    car.current_waypoint += 1

                    if car.current_waypoint < len(car.waypoints):
                        car.set_target(car.waypoints[car.current_waypoint])
                    else:
                        car.state = "parked"
                        car.parked_start_time = current_time

            elif car.state == "leaving":
                if car.move():
                    car.current_waypoint += 1

                    if car.current_waypoint < len(car.waypoints):
                        car.set_target(car.waypoints[car.current_waypoint])
                    else:
                        car.state = "exited"
                        exited_cars.append(car)

        for car in exited_cars:
            parking_lot.release_space(car.slot_number, car.vehicle_id)
            cars.remove(car)

        # --------------------------------
        # DRAW
        # --------------------------------

        parking_lot.draw(screen)

        for car in cars:
            pygame.draw.rect(
                screen,
                car.color,
                car.get_rect()
            )

        button_color = (55, 145, 90) if len(parking_lot.occupied_spaces) < len(parking_lot.parking_spaces) else (110, 110, 110)
        button_label = "Spawn Car" if button_color != (110, 110, 110) else "Lot Full"
        pygame.draw.rect(screen, button_color, spawn_button, border_radius=6)
        button_text = button_font.render(button_label, True, (255, 255, 255))
        screen.blit(button_text, button_text.get_rect(center=spawn_button.center))

        for car in cars:
            leave_button = leave_buttons.get(car.vehicle_id)
            if leave_button and car.state == "parked":
                pygame.draw.rect(screen, car.color, leave_button, border_radius=5)
                if leave_button.collidepoint(pygame.mouse.get_pos()):
                    button_label = f"Leave {car.vehicle_id}"
                else:
                    parked_seconds = int(current_time - car.parked_start_time)
                    minutes, seconds = divmod(parked_seconds, 60)
                    button_label = f"{minutes:02d}:{seconds:02d}"
                leave_text = button_font.render(
                    button_label,
                    True,
                    (255, 255, 255)
                )
                screen.blit(leave_text, leave_text.get_rect(center=leave_button.center))

        pygame.display.flip()

        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
