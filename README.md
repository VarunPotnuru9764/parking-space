# Parking Space Detection System
A Python project for managing parking spaces, tracking occupancy, and calculating parking fares. It contains a FastAPI backend, a vehicle detection and occupancy package, and a standalone Pygame parking lot simulator

## Project structure
backend/      FastAPI API, SQLAlchemy models, authentication, and fare scheduler
detection/    Vehicle detection, occupancy tracking, parking layout tools, and API sync
simulator/   Standalone Pygame parking lot simulation
frontend/    React web application and the lot/camera parking-layout polygon editor

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

For local detection and simulator development on Windows, use a dedicated environment rather than the backend environment. From the project root, run:

```powershell
cd detection
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r ..\simulator\requirements.txt
```

Use `.\.venv\Scripts\python.exe` to run detection scripts. To start the simulator, open a second PowerShell terminal, change to the `simulator` directory, and run `..\detection\.venv\Scripts\python.exe main.py`. The detector-to-API updater retries transient network errors, HTTP 408/429 responses, and server errors with capped exponential backoff; permanent client errors are logged and not retried.

## Configuration
A) The backend reads `.env` from its current working directory. Create `backend/.env` with:

DATABASE_URL = mysql+pymysql://USER:PASSWORD@HOST:3306/DATABASE \n
SECRET_KEY = replace-with-a-long-random-secret
DETECTION_API_TOKEN = replace-with-a-long-random-service-token

B) The detection layout synchronization module reads `detection/.env` and expects:

API_URL = http://localhost:8000
PARKING_LOT_SLUG = simulator
CAMERA_ID = default
DETECTION_API_TOKEN = same-long-random-service-token-as-backend

Keep real credentials and secret keys out of version control. The backend creates its database tables at startup; the configured database must already exist and be reachable

Email-based password recovery and two-step verification also need SMTP settings in `backend/.env`:

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_FROM=parking@example.com
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_SSL=false
FRONTEND_URL=http://localhost:5173/#/reset-password
```

Use your mail provider's required TLS mode and credentials; use port 465 with `SMTP_USE_SSL=true` when required. Missing SMTP configuration is reported explicitly. Reset-request delivery failures are recorded for administrators while the public endpoint keeps its response generic to avoid disclosing whether an account exists.

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
- `GET /users/me/parking`, `/users/me/history`, `/users/me/reports`, and `/users/me/login-activity` for the authenticated user's own records
- `PUT /users/me/password` to change the authenticated user's password
- `GET /admin/reports`, `/admin/activity`, `/admin/login-activity`, `/admin/users`, and `/admin/users/{user_id}` for administrator-only reports and read-only user/audit views
- `GET /admin/fare-rules`, `POST /admin/fare-rules`, and `PATCH /admin/fare-rules/{rule_id}` for administrator-only fare-rule management; the fare engine continues to manage the active flag
- `POST /auth/password-reset/request` and `/auth/password-reset/complete` for email-based password reset
- `/auth/mfa/setup`, `/auth/mfa/enable`, `/auth/mfa/disable/request`, `/auth/mfa/verify`, `/auth/mfa/resend`, and `DELETE /auth/mfa` for email-code two-step verification
- `POST /parking/{parking_id}/claim/initiate` and `/confirm` for authenticated parking claims
- `GET` and `PUT /layouts/{lot_slug}/{camera_id}` to load/save validated camera-specific layouts through the detection layout manager

Lot creation (`POST /lots/`), manual space creation (`POST /parking/`), and layout saves (`PUT /layouts/...`) require an authenticated administrator bearer token. The detection synchronization endpoint `POST /parking/bulk` and occupancy status endpoint `PUT /parking/{parking_id}` require either an administrator bearer token or the shared `DETECTION_API_TOKEN` sent in `X-Detection-Token`. Configure the same strong, private token in `backend/.env` and `detection/.env`; never commit it. Detector request and response payloads remain unchanged.

Fare rules, occupancy percentages, current rates and active parking histories are scoped by lot. The scheduler processes each lot independently and records fare intervals at 15-minute boundaries while the API process is running. Claims are associated with the lot of their parking record; the same user may hold one active claim per lot.

The backend creates the new `audit_events`, `email_challenges`, `password_reset_tokens`, and `user_security` tables additively at startup; no existing table columns are changed. The admin activity endpoint includes available login, claim, lot/space, layout, fare-rule, password, and MFA events. Session reports expose recorded occupancy-start timestamps; these are not guaranteed to be the vehicle's actual arrival time. Reported amounts are recorded fares, not confirmed payments. Registration creates normal user accounts; administrator roles must be provisioned by a trusted operator and cannot be self-selected.

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

### Generate layout candidates from the admin portal

An administrator can open **Layout Configuration**, choose a parking lot and camera, upload a parking-lot image, and select **Generate candidates**. The backend runs the configured parking-space model (`detection/models/parking_lot.pt`) and returns the same `parking-layout-review-v1` JSON bundle used by the review editor. Review and adjust the suggested polygons before saving the layout, or download the generated JSON bundle for later review. Candidate inference runs on the backend, so install the backend requirements as well as the frontend and start the backend with the supplied model file present.

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

B) From `frontend`, install and start the web application:

```powershell
npm ci
npm run dev
```

Open the Vite URL for the public ParkingSpace website. Set `VITE_API_BASE_URL` in the frontend environment if the backend is not at `http://localhost:8000`. Login and registration use the existing bearer-token APIs, including email-code MFA challenges when enabled. The user portal connects active parking, history, personal reports, login activity, password changes, password reset and two-step verification to the authenticated API routes. The camera-specific polygon map loads `/layouts/{lot_slug}/{camera_id}`, joins configured identifiers to live parking records and refreshes occupancy; the admin portal connects reports, fare rules, read-only user management, event logs and login activity to admin-only routes. It preserves the existing layout editor, including candidate import, manual drawing, removal, renaming, vertex editing, undo/redo, validation, and save. Layout saves, fare-rule operations, lot creation and management APIs require an account whose backend role is `admin`; registration creates normal user accounts only. Configure SMTP for password reset and MFA email delivery. Start the backend first; its development CORS policy allows the local Vite origins.

Personal parking sessions/history/reports, administrator reports, read-only user management, audit/login activity, fare-rule management, password recovery, and email-code two-step verification are now exposed by the backend. Password recovery and two-step verification require working SMTP settings. The public availability preview and user/admin space summaries use real `GET /lots/` and `GET /parking/` data when the backend is reachable; the remaining portal screens still need to be wired to these newly added endpoints.

C) In powershell terminal
python test_pipeline.py

This script loads the selected lot/camera layout, synchronizes only that lot, then applies confirmed occupancy changes. Set `PARKING_LOT_SLUG` and `CAMERA_ID` in `detection/.env`, or pass `--lot` and `--camera` explicitly. These scripts are manual workflow examples, not a configured automated test suite.

## Run the simulator
From `simulator`:

In powershell terminal
python main.py

The Pygame window lets you spawn cars and send parked cars to the exit. It publishes the rendered window as an MJPEG camera feed at `http://127.0.0.1:8765/video`. The stream contains only rendered pixels; the detection process does not read simulator reservation or vehicle state

## Simulator detection
Administrators can use **Simulator Detection** in the web portal. It starts the simulator and occupancy detector in the backend, shows the annotated live feed, and provides web controls to spawn cars and send parked cars out. Stopping detection resets the Simulator lot occupancy. The web workflow requires the backend environment to include the simulator dependency (`pygame`); no simulator or detector terminal is needed by portal users.

For standalone development only, start the backend and use two terminals:

1) From `simulator`, run `python main.py`.
2) From `detection`, run `python -m vehicle.run_simulator`

The detector reads the simulator's live camera feed, applies confirmed occupancy changes to the backend, and displays/saves an annotated feed. Press `Q` in the detection preview to stop detection. Close the simulator window to stop the frame stream. The simulator requirements include OpenCV for encoding its rendered frames

### Run real-world video detection

The real-world workflow processes the video in `detection`, classifies parking-space crops with the supplied occupancy model, draws statuses against the reviewed camera polygons, and sends confirmed status changes to the selected lot. It uses `detection/layout/layouts/<lot>/<camera>.json` and the same API synchronization/updater path as the simulator. From `detection` (with the backend running and `detection/.env` configured), run:

```powershell
python -m vehicle.run_irl --lot campus-west --camera gate-a
```

When this video runner reaches the end of the recording or is stopped with `Q`/Ctrl+C, it clears occupancy for every space in the selected lot and closes any open parking sessions before exiting. Preview-only runs started with `--no-sync` do not change backend occupancy.

Administrators can also use **Video Detection** in the web portal: select the lot and camera, upload an MP4/MOV/AVI/MKV/WebM recording up to 500 MB, and watch the annotated preview while detection runs. This uses the saved layout reference photo and updates the selected lot; the result video is saved under `detection/output/web_jobs/`. The backend accepts one active web video job at a time. Use **Save reviewed layout** to store the reference image beside its camera layout JSON (for example, `detection/layout/layouts/<lot>/<camera>.reference.jpg`). The web workflow runs detection in the backend; the standalone Pygame simulator is only needed for simulator-based testing.

The default input is `12125602_30fps.mp4`, the camera layout reference image is `parking_layout_v2.png`, and the default parking-space weights are `models/parking_lot.pt` (`space-empty` / `space-occupied`). The runner fits and feature-aligns each video frame to the reference image dimensions, so detection and reviewed polygons use the same coordinate space. Use a reference image from the same camera view; the alignment check fails if it cannot reliably match the scene. Playback and the annotated output retain the source video's frame rate and duration. Inference runs asynchronously and skips a requested frame when the previous inference is still running; the latest detection overlay is carried across intervening frames. By default, it attempts inference on every source frame (`--frame-stride 1`), synchronizes only the selected lot, previews in a fitted window, and writes an annotated recording at the reference image dimensions to a timestamped file under `detection/output/`. Increase `--frame-stride` to reduce inference load without changing playback/output FPS. After three confirming inference frames, it updates slots that match a model prediction. Unmatched slots are reported and left unchanged rather than being incorrectly marked vacant. Press `Q` to stop early. It refuses to overwrite an existing output file.

Use `--video path\to\another_video.mp4`, `--reference-image path\to\layout_frame.png`, or `--model-weights path\to\weights.pt` to change inputs. For a vehicle detector instead of the parking-space classifier, pass `--detector-mode vehicles --model-weights models\yolo11n.pt`; generic vehicle weights may perform poorly on small cars in aerial footage. Use `--no-sync` for a local preview that does not contact or update the backend, and `--no-preview` to process without opening a GUI window. This video runner processes the file once rather than exposing a network camera URL; an actual IP camera can be added later as another `VideoCapture` source.

## Current scope
The detection scripts that synchronize layouts or occupancy require a running backend and valid API/database configuration. The simulator can be run independently
