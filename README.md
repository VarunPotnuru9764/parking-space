# Parking Space Detection System
A Python project for managing parking spaces, tracking occupancy, and calculating parking fares. It contains a FastAPI backend, a vehicle detection and occupancy package, and a standalone Pygame parking lot simulator

## Project structure
backend/      FastAPI API, SQLAlchemy models, authentication, and fare scheduler
detection/    Vehicle detection, occupancy tracking, parking layout tools, and API sync
simulator/   Standalone Pygame parking lot simulation
frontend/    Placeholder directory; no frontend files are currently present

## Requirements
- Python 3.10 or later
- A database supported by the configured SQLAlchemy URL (the backend requirements include PyMySQL)
- For the detection package, the packages in `detection/requirements.txt`; YOLO mode may require compatible PyTorch support
- For the simulator, Pygame

Each component has its own requirements file. Install dependencies for the component you plan to run, for example:

In powershell terminal
cd backend/detection/simulator
python -m venv venv
./venv/Scripts/Activate.ps1
python -m pip install -r requirements.tx

Run equivalent `pip install -r requirements.txt` commands from each subsection for those components

## Configuration
A) The backend reads `.env` from its current working directory. Create `backend/.env` with:

DATABASE_URL = mysql+pymysql://USER:PASSWORD@HOST:3306/DATABASE \n
SECRET_KEY = replace-with-a-long-random-secret

B) The detection layout synchronization module reads `detection/.env` and expects:

API_URL = http://localhost:8000

Keep real credentials and secret keys out of version control. The backend creates its database tables at startup; the configured database must already exist and be reachable

## Run the backend
From the `backend` directory, with its dependencies and `.env` configured:

In powershell terminal
python -m uvicorn main:app --reload

The API listens at `http://localhost:8000`. The root endpoint returns a status message, and FastAPI's interactive documentation is available at `http://localhost:8000/docs`.

The API exposes:
- `GET /parking/` and `POST /parking/` to list and create parking spaces
- `PUT /parking/{parking_id}` to update a space's `vacant` or `occupied` status
- `POST /auth/register` and `POST /auth/login` for user registration and bearer-token login
- `GET /auth/me` for the authenticated user's profile
- `POST /parking/{parking_id}/claim/initiate` and `/confirm` for authenticated parking claims

Fare rules and parking history are managed by backend services and the scheduler. The scheduler records fare intervals at 15-minute boundaries while the API process is running

## Detection and layout tools
The `detection` package includes YOLO vehicle detection, a color-based simulator detector, occupancy tracking, parking-layout detection/review, and synchronization with the backend API. The default occupancy pipeline mode is `simulator`; the YOLO detector loads `yolo11n.pt` by default

The existing example/test scripts use local image files and/or contact the backend. For example, from `detection` with the backend running and `.env` configured:

A) In powershell terminal
python test_layout.py

This script runs parking-space candidate detection on `parking_layout.png`, displays the detected candidates, and provides an interactive review process where the user selects and names the valid parking spaces. It then saves the reviewed layout to `layout/parking_layout.json` and synchronizes the detected spaces with the parking-space records through the API. This script is a manual example for validating the layout detection and synchronization workflow, not a configured automated test suite

B) In powershell terminal
python test_pipeline.py

This script loads `parking_layout_v1.png` and the saved `layout/parking_layout.json`, synchronizes slots with the API, then applies confirmed occupancy changes. `test_layout.py` runs parking-space candidate detection and interactive layout review using `parking_layout.png`; it also synchronizes the resulting layout with the API. These scripts are manual examples, not a configured automated test suite

## Run the simulator
From `simulator`:

In powershell terminal
python main.py

The Pygame window lets you spawn cars and send parked cars to the exit. The simulator is currently standalone; its code does not itself stream frames to the detection pipeline or update the backend

## Current scope
The detection scripts that synchronize layouts or occupancy require a running backend and valid API/database configuration. The simulator can be run independently
