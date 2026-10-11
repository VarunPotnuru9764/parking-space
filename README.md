# Parking Space Detection System
A Python project for managing parking spaces, tracking occupancy, and calculating parking fares. It contains a FastAPI backend, a vehicle detection and occupancy package, and a standalone Pygame parking lot simulator

## Project structure
backend/      FastAPI API, SQLAlchemy models, authentication, and fare scheduler
detection/    Vehicle detection, occupancy tracking, parking layout tools, and API sync
simulator/   Standalone Pygame parking lot simulation
frontend/    React-based lot/camera parking-layout review and polygon editor

## Requirements
- Python 3.10 or later
- A database supported by the configured SQLAlchemy URL (the backend requirements include PyMySQL)
- For the detection package, the packages in `detection/requirements.txt`; YOLO mode may require compatible PyTorch support
- For the simulator, Pygame

Each component has its own requirements file. Install dependencies for the component you plan to run, for example:

In powershell terminal
cd backend
python -m venv venv
./venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt

Run equivalent `pip install -r requirements.txt` commands from each subsection for those components

## Configuration
A) The backend reads `.env` from its current working directory. Create `backend/.env` with:

DATABASE_URL = mysql+pymysql://USER:PASSWORD@HOST:3306/DATABASE \n
SECRET_KEY = replace-with-a-long-random-secret

B) The detection layout synchronization module reads `detection/.env` and expects:

API_URL = http://localhost:8000
PARKING_LOT_SLUG = simulator
CAMERA_ID = default

Keep real credentials and secret keys out of version control. The backend creates its database tables at startup; the configured database must already exist and be reachable

## Run the backend
From the `backend` directory, with its dependencies and `.env` configured:

In powershell terminal
python -m uvicorn main:app --reload

The API listens at `http://localhost:8000`. The root endpoint returns a status message, and FastAPI's interactive documentation is available at `http://localhost:8000/docs`.

The API exposes:
- `GET /lots/` and `POST /lots/` to list and create parking lots (`name`, unique `slug`, optional location)
- `GET /parking/?lot_id=...` and `POST /parking/` to list/create spaces within one lot; omitted lot selection preserves the legacy `simulator` default
- `POST /parking/bulk` to idempotently add up to 1,000 spaces to one lot without modifying existing records
- `PUT /parking/{parking_id}?lot_id=...` to update a space's `vacant` or `occupied` status within the selected lot
- `POST /auth/register` and `POST /auth/login` for user registration and bearer-token login
- `GET /auth/me` for the authenticated user's profile
- `POST /parking/{parking_id}/claim/initiate` and `/confirm` for authenticated parking claims
- `GET` and `PUT /layouts/{lot_slug}/{camera_id}` to load/save validated camera-specific layouts through the detection layout manager

Fare rules, occupancy percentages, current rates and active parking histories are scoped by lot. The scheduler processes each lot independently and records fare intervals at 15-minute boundaries while the API process is running. Claims are associated with the lot of their parking record; the same user may hold one active claim per lot.

### Multi-lot MySQL migration (manual, required)

The application does not alter existing MySQL columns automatically. Before deploying this code, stop the API and take a verified database backup. Then:

1. Inspect `SHOW INDEX FROM parking_records;` and note the name of the existing single-column unique index on `slot_number`.
2. Open `backend/migrations/001_multilot_mysql.sql`. Replace the placeholder instruction with `ALTER TABLE parking_records DROP INDEX <that_index_name>;` before adding the composite `(lot_id, slot_number)` unique key. Do not drop the unique `claim_code` index.
3. Run the migration once against the configured database. It creates the `Simulator` lot and assigns all existing spaces, fare rules, parking history and fare-history rows to it, retaining their record IDs and values. The migration is one-time and contains `ALTER TABLE` statements; do not rerun it.
4. Verify row counts and foreign keys, and confirm every existing `parking_records`, `parking_history`, `fare_history` and `fare_rules` row has `lot_id` set to the Simulator lot. Investigate any orphaned history rows before migration; do not delete them to make the migration pass. Only then restart the API.
5. Create each real-world lot through `POST /lots/` or `/docs`. Use a stable slug such as `campus-west`. Keep the simulator records in the Simulator lot.
6. Create a reviewed layout JSON for each lot and camera. Run the layout workflow with `--lot campus-west --camera gate-a`; it stores to `detection/layout/layouts/campus-west/gate-a.json`. Existing `detection/layout/parking_layout.json` remains the simulator fallback and is never overwritten by those lot/camera saves.
7. Configure `PARKING_LOT_SLUG` and `CAMERA_ID` in `detection/.env`, then run `python test_pipeline.py --lot campus-west --camera gate-a` to sync only that lot and apply occupancy changes. The bulk sync adds missing slots and leaves existing statuses, rates and claim codes unchanged. Layouts should use unique slot names within that lot; the same slot label may be reused in another lot.

For a lot with about 300 spaces, `POST /parking/bulk` creates missing rows in one request. The sync path assigns new claim codes on the server; save the generated codes printed by the sync to a secure provisioning record and assign them to the appropriate physical bays before enabling user claims. Add fare-rule rows for each real lot with that lot's `lot_id`; rules are selected by lot, and a lot without matching rules accrues no fare intervals. Do not bulk import the real lot into the Simulator slug.

## Detection and layout tools
The `detection` package includes YOLO vehicle detection, a color-based simulator detector, occupancy tracking, parking-layout detection/review, and synchronization with the backend API. The default occupancy pipeline mode is `simulator`; the YOLO detector loads `yolo11n.pt` by default

### Pretrained parking-space extraction

`detection/test_layout.py` can run a pretrained Ultralytics detector whose classes represent parking spaces (for example, the published [parking-lot-yolo26m checkpoint](https://huggingface.co/simahanyan/parking-lot-yolo26m), which predicts `space-empty` and `space-occupied`). This detects parking-space regions rather than cars. It returns rectangular boxes, so the resulting four-point polygons approximate bay extents; it does not segment painted boundary lines. Review every candidate before saving.

Download the checkpoint from the model page to a local `.pt` file, then from `detection` run:

```powershell
python test_layout.py --image parking_layout.png --model-weights path\to\parking_lot.pt
```

The interactive review accepts candidate IDs and asks for slot names. It saves through `layout/layout_manager.py` to the selected lot/camera layout under `layout/layouts/`. Add `--sync` to invoke the existing API/database synchronization after review; this requires `detection/.env` and a running configured backend. Without `--model-weights`, the existing contour detector remains available for simple rendered layouts. The detector dependency is already in `detection/requirements.txt` (`ultralytics`); inference also needs the checkpoint and compatible PyTorch runtime. CUDA is optional.

The supplied `parking_layout.png` and simulator MP4s are synthetic rendered views, not camera footage. Parking-space checkpoints are generally trained on real aerial or surround-view imagery, so predictions on this simulator art are out of distribution and should not be treated as validated. The pretrained checkpoint was not run as part of this change because it is not present locally; use the review step on representative camera footage and verify polygons before saving or syncing. The existing saved layout remains usable directly by the occupancy pipeline, which continues to consume the same `spaces`/`polygon` schema.

The existing example/test scripts use local image files and/or contact the backend. For example, from `detection` with the backend running and `.env` configured:

A) In powershell terminal
python test_layout.py --lot campus-west --camera gate-a --export-review

This detects candidates from `parking_layout.png` and writes a timestamped review bundle under `detection/layout/review_sessions/`. Use `--image path\to\frame.png` for another source image. The bundle preserves the original detector candidate IDs and polygons for import into the React editor.

B) From `frontend`, install and start the editor:

```powershell
npm install
npm run dev
```

Open the Vite URL, choose the same original image and import the JSON review bundle. The editor supports drawing missed spaces, removing detections, renaming slots, dragging polygon vertices, and undo/redo. Enter the lot slug and camera ID, then save. The backend validates and writes the existing `{"spaces":[{"slot_number":"...","polygon":[[x,y], ...]}]}` schema via `layout_manager.save_layout`, into a separate `detection/layout/layouts/<lot>/<camera>.json` file. Start the backend first; its development CORS policy allows the local Vite origins.

C) In powershell terminal
python test_pipeline.py

This script loads the selected lot/camera layout, synchronizes only that lot, then applies confirmed occupancy changes. Set `PARKING_LOT_SLUG` and `CAMERA_ID` in `detection/.env`, or pass `--lot` and `--camera` explicitly. These scripts are manual workflow examples, not a configured automated test suite.

## Run the simulator
From `simulator`:

In powershell terminal
python main.py

The Pygame window lets you spawn cars and send parked cars to the exit. It publishes the rendered window as an MJPEG camera feed at `http://127.0.0.1:8765/video`. The stream contains only rendered pixels; the detection process does not read simulator reservation or vehicle state

## Run live detection
Start the backend with its database configuration, then use two terminals:

1) From `simulator`, run `python main.py`.
2) From `detection`, run `python -m vehicle.run_simulator`

The detector reads the simulator's live camera feed, applies confirmed occupancy changes to the backend, and displays/saves an annotated feed. Press `Q` in the detection preview to stop detection. Close the simulator window to stop the frame stream. The simulator requirements include OpenCV for encoding its rendered frames

### Run real-world video detection

The real-world workflow processes the video in `detection`, classifies parking-space crops with the supplied occupancy model, draws statuses against the reviewed camera polygons, and sends confirmed status changes to the selected lot. It uses `detection/layout/layouts/<lot>/<camera>.json` and the same API synchronization/updater path as the simulator. From `detection` (with the backend running and `detection/.env` configured), run:

```powershell
python -m vehicle.run_irl --lot campus-west --camera gate-a
```

The default input is `12125602_30fps.mp4`, the camera layout reference image is `parking_layout_v2.png`, and the default parking-space weights are `models/parking_lot.pt` (`space-empty` / `space-occupied`). The runner fits and feature-aligns each video frame to the reference image dimensions, so detection and reviewed polygons use the same coordinate space. Use a reference image from the same camera view; the alignment check fails if it cannot reliably match the scene. Playback and the annotated output retain the source video's frame rate and duration. Inference runs asynchronously and skips a requested frame when the previous inference is still running; the latest detection overlay is carried across intervening frames. By default, it attempts inference on every source frame (`--frame-stride 1`), synchronizes only the selected lot, previews in a fitted window, and writes an annotated recording at the reference image dimensions to a timestamped file under `detection/output/`. Increase `--frame-stride` to reduce inference load without changing playback/output FPS. After three confirming inference frames, it updates slots that match a model prediction. Unmatched slots are reported and left unchanged rather than being incorrectly marked vacant. Press `Q` to stop early. It refuses to overwrite an existing output file.

Use `--video path\to\another_video.mp4`, `--reference-image path\to\layout_frame.png`, or `--model-weights path\to\weights.pt` to change inputs. For a vehicle detector instead of the parking-space classifier, pass `--detector-mode vehicles --model-weights models\yolo11n.pt`; generic vehicle weights may perform poorly on small cars in aerial footage. Use `--no-sync` for a local preview that does not contact or update the backend, and `--no-preview` to process without opening a GUI window. This video runner processes the file once rather than exposing a network camera URL; an actual IP camera can be added later as another `VideoCapture` source.

## Current scope
The detection scripts that synchronize layouts or occupancy require a running backend and valid API/database configuration. The simulator can be run independently
