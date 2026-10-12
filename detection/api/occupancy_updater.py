import logging
import queue
import time
from threading import Thread

import requests

from api.parking_api import ParkingAPI


logger = logging.getLogger(__name__)
_CLEAR_LOT = object()


class OccupancyUpdater:
    def __init__(self, synchronized_spaces, lot_id=None):
        self.api = ParkingAPI()
        self.lot_id = lot_id
        self.parking_ids = {
            space["slot_number"]: space["parking_id"]
            for space in synchronized_spaces
        }
        self._pending_changes = queue.Queue()
        self._worker = Thread(
            target=self._process_pending_changes,
            name="parking-occupancy-sync",
            daemon=True,
        )
        self._worker.start()

    def apply_changes(self, changes):
        if changes:
            self._pending_changes.put(dict(changes))

    def clear_lot_occupancy(self):
        """Queue a lot-wide vacant reset after any previously detected changes."""
        if self.lot_id is not None:
            self._pending_changes.put(_CLEAR_LOT)

    def close(self):
        self._pending_changes.put(None)
        self._worker.join(timeout=30)
        if self._worker.is_alive():
            logger.warning(
                "Occupancy sync is still retrying; pending updates will be lost when this process exits"
            )

    def _process_pending_changes(self):
        while True:
            changes = self._pending_changes.get()
            try:
                if changes is None:
                    return
                if changes is _CLEAR_LOT:
                    self._clear_lot_occupancy()
                else:
                    self._apply_changes(changes)
            finally:
                self._pending_changes.task_done()

    def _apply_changes(self, changes):
        for slot_number, occupied in changes.items():
            parking_id = self.parking_ids.get(slot_number)
            if parking_id is None:
                logger.error("No parking_id found for detected space %s", slot_number)
                continue

            status = "occupied" if occupied else "vacant"
            retry_delay = 1
            while True:
                try:
                    self.api.update_parking_status(
                        parking_id=parking_id,
                        status=status,
                        lot_id=self.lot_id,
                    )
                    logger.info(
                        "Updated parking space %s (parking_id=%s) to %s",
                        slot_number,
                        parking_id,
                        status,
                    )
                    break
                except requests.exceptions.RequestException as error:
                    response = error.response
                    retryable = (
                        response is None
                        or response.status_code in (408, 429)
                        or response.status_code >= 500
                    )
                    if not retryable:
                        logger.error(
                            "Occupancy update rejected for %s (parking_id=%s): %s",
                            slot_number,
                            parking_id,
                            error,
                        )
                        break

                    logger.warning(
                        "Occupancy update for %s failed; retrying in %s seconds: %s",
                        slot_number,
                        retry_delay,
                        error,
                    )
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)

    def _clear_lot_occupancy(self):
        retry_delay = 1
        while True:
            try:
                result = self.api.clear_lot_occupancy(self.lot_id)
                logger.info(
                    "Cleared occupancy for lot_id=%s (%s occupied spaces were vacated)",
                    self.lot_id,
                    result.get("vacated_count", "unknown"),
                )
                return
            except requests.exceptions.RequestException as error:
                response = error.response
                retryable = (
                    response is None
                    or response.status_code in (408, 429)
                    or response.status_code >= 500
                )
                if not retryable:
                    logger.error("Lot occupancy reset was rejected for lot_id=%s: %s", self.lot_id, error)
                    return
                logger.warning(
                    "Lot occupancy reset failed; retrying in %s seconds: %s",
                    retry_delay,
                    error,
                )
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)
