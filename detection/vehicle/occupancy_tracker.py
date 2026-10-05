class OccupancyTracker:
    def __init__(self, required_confirmations = 3):
        self.required_confirmations = required_confirmations
        self.states = {}
        self.pending_states = {}
        self.pending_counts = {}

    def update(self, detected_states):
        changes = {}
        for slot_number, detected_state in detected_states.items():
            current_state = self.states.get(slot_number,False)
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