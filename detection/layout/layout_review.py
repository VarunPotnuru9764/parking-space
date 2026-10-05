def review_candidates(candidates):
    print("\nDetected candidates:")

    for candidate in candidates:
        print(f"Candidate {candidate['candidate_id']}")

    while True:
        user_input = input("\nEnter the candidate numbers to accept: ")
        try:
            selected_ids = [int(value) for value in user_input.split()]

        except ValueError:
            print("Please enter numbers only")
            continue

        candidate_ids = {candidate["candidate_id"] for candidate in candidates}
        invalid_ids = [candidate_id for candidate_id in selected_ids if candidate_id not in candidate_ids]
        if invalid_ids:
            print(f"Invalid candidate numbers: {invalid_ids}")
            continue

        if len(selected_ids) == 0:
            print("Please select at least one candidate")
            continue

        break

    accepted_candidates = [candidate for candidate in candidates if candidate["candidate_id"] in selected_ids]
    print(f"\nAccepted {len(accepted_candidates)} parking-space candidates")
    return accepted_candidates

def name_candidates(candidates):
    named_candidates = []
    print("\nName the accepted parking spaces")

    used_names = set()
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        while True:
            name = input(f"Name for Candidate {candidate_id}: ").strip()
            if not name:
                print("Name cannot be empty")
                continue

            if name in used_names:
                print("That parking-space name is already used")
                continue

            break

        used_names.add(name)
        named_candidates.append({
            "slot_number": name,
            "polygon": candidate["polygon"].tolist()
        })

    return named_candidates

def create_layout(candidates):
    accepted_candidates = review_candidates(candidates)
    named_candidates = name_candidates(accepted_candidates)
    return {"spaces": named_candidates}