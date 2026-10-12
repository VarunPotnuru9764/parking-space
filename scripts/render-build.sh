#!/usr/bin/env bash
set -euo pipefail

# Keep the API's ML stack and Pygame's SDL dependencies isolated. The simulator
# launcher automatically uses simulator/venv when this environment exists.
python -m pip install -r backend/requirements.txt
python -m venv simulator/venv
simulator/venv/bin/python -m pip install -r simulator/requirements.txt
