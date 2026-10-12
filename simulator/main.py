import argparse
import os
import sys

if "--headless" in sys.argv:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    FPS,
    ENTRANCE,
    EXIT,
    PARKING_SPACES
)

from parking import ParkingLot
from scenario import get_aisle_targets, get_parking_target
from vehicle import Vehicle
from frame_stream import FrameStream


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
    aisle_target, entry_approach_target, exit_approach_target = get_aisle_targets(slot_number)
    car = Vehicle(
        vehicle_id,
        *ENTRANCE,
        target_position=entry_approach_target,
        color=car_color
    )
    car.slot_number = slot_number
    car.aisle_target = aisle_target
    car.entry_approach_target = entry_approach_target
    car.exit_approach_target = exit_approach_target
    car.waypoints = [entry_approach_target, aisle_target, parking_target]
    cars.append(car)
    return vehicle_id_number + 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    pygame.init()

    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT)
    )

    if not args.headless:
        pygame.display.set_caption("Parking Lot Simulator")
    frame_stream = FrameStream(port=args.port)
    stream_url = frame_stream.start()
    print(f"Simulator live feed: {stream_url}")

    clock = pygame.time.Clock()
    button_font = pygame.font.Font(None, 28)
    leave_button_font = pygame.font.Font(None, 22)
    spawn_button = pygame.Rect(WINDOW_WIDTH - 180, 12, 165, 42)

    parking_lot = ParkingLot()

    cars = []
    next_vehicle_id = 1

    running = True

    while running:

        leave_buttons = {
            car.vehicle_id: pygame.Rect(
                PARKING_SPACES[car.slot_number][0] + 5,
                PARKING_SPACES[car.slot_number][1]
                + PARKING_SPACES[car.slot_number][3]
                - 30,
                PARKING_SPACES[car.slot_number][2] - 10,
                28
            )
            for car in cars if car.state == "parked"
        }

        for command, value in frame_stream.drain_commands():
            if command == "spawn":
                next_vehicle_id = spawn_car(parking_lot, cars, next_vehicle_id)
            elif command == "leave":
                car = next((item for item in cars if item.slot_number == value and item.state == "parked"), None)
                if car is not None:
                    car.waypoints = [car.aisle_target, car.exit_approach_target, EXIT]
                    car.current_waypoint = 0
                    car.set_target(car.waypoints[0])
                    car.state = "leaving"

        for event in pygame.event.get() if not args.headless else ():

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
                        car.waypoints = [
                            car.aisle_target,
                            car.exit_approach_target,
                            EXIT,
                        ]
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

        if not args.headless:
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
                    leave_text = leave_button_font.render(
                        button_label,
                        True,
                        (255, 255, 255)
                    )
                    screen.blit(leave_text, leave_text.get_rect(center=leave_button.center))

        pygame.display.flip()

        # Publish only rendered pixels. The detector consumes this camera-like
        # feed and does not receive simulator reservation or vehicle state.
        rgb_frame = pygame.surfarray.array3d(screen).transpose((1, 0, 2))
        frame_stream.publish(
            rgb_frame[:, :, ::-1].copy(),
            {
                "cars": [
                    {"slot_number": car.slot_number, "vehicle_id": car.vehicle_id, "state": car.state}
                    for car in cars
                ],
                "available_spaces": [
                    slot for slot in parking_lot.parking_spaces
                    if slot not in parking_lot.occupied_spaces
                ],
            },
        )

        clock.tick(FPS)

    frame_stream.stop()
    pygame.quit()


if __name__ == "__main__":
    main()
