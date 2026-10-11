class OccupancyTracker:
    def __init__(self, required_confirmations = 3):
        self.required_confirmations = required_confirmations
        self.states = {}
        self.pending_states = {}
        self.pending_counts = {}

    def update(self, detected_states):
        changes = {}
        for slot_number in set(self.pending_states) - detected_states.keys():
            self.pending_states.pop(slot_number, None)
            self.pending_counts.pop(slot_number, None)

        for slot_number, detected_state in detected_states.items():
            # Establish a complete initial snapshot, including vacant spaces.
            # Without this branch, vacant slots never appear in `changes` and
            # remain at stale backend values after startup.
            if slot_number not in self.states:
                pending_state = self.pending_states.get(slot_number)
                if pending_state != detected_state:
                    self.pending_states[slot_number] = detected_state
                    self.pending_counts[slot_number] = 1
                else:
                    self.pending_counts[slot_number] += 1

                if self.pending_counts[slot_number] >= self.required_confirmations:
                    self.states[slot_number] = detected_state
                    changes[slot_number] = detected_state
                    self.pending_states.pop(slot_number, None)
                    self.pending_counts.pop(slot_number, None)
                continue

            current_state = self.states[slot_number]
            if detected_state == current_state:
                self.pending_states.pop(slot_number, None)
                self.pending_counts.pop(slot_number, None)
                continue

            pending_state = self.pending_states.get(slot_number)
            if pending_state != detected_state:
                self.pending_states[slot_number] = (detected_state)
                self.pending_counts[slot_number] = 1

            else:
                self.pending_counts[slot_number] += 1

            if (self.pending_counts[slot_number] >= self.required_confirmations):
                self.states[slot_number] = detected_state
                changes[slot_number] = detected_state
                self.pending_states.pop(slot_number, None)
                self.pending_counts.pop(slot_number, None)

        return changes
