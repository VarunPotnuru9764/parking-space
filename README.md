# ParkingSpace

ParkingSpace is a multi-lot parking management system. It combines a React portal, a FastAPI service, camera-layout tools, vehicle/space occupancy detection, and a Pygame parking simulator.

## Repository layout

| Directory | Purpose |
| --- | --- |
| `frontend/` | React 18 portal, user/admin pages, and the camera-layout editor |
| `backend/` | FastAPI routes, SQLAlchemy models, authentication, reports, fare scheduling, and managed detection jobs |
| `detection/` | Layout detection and validation, occupancy pipelines, video processing, and API synchronization |
| `simulator/` | Pygame parking-lot simulation and local MJPEG/status/control service |

## Requirements

- Python 3.10 or newer
- Node.js and npm
- A reachable database supported by SQLAlchemy; MySQL with PyMySQL is included in the backend dependencies
- The Python dependencies for the backend and, for detection features, the detection package
- The supplied model files under `detection/models/` for model-based detection

The Python components have separate requirement files. You can use one Python environment for the backend and detection features, or separate environments as long as the backend process can import the detection dependencies when using layout generation or managed detection jobs.

## Configuration

Create `backend/.env`:

```dotenv
DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:3306/DATABASE
SECRET_KEY=replace-with-a-long-random-secret
DETECTION_API_TOKEN=replace-with-a-long-random-service-token
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Copy `backend/.env.example` for a complete local template. The backend reads operating-system environment variables first, then values from `backend/.env`; hosted services should receive settings through their environment-variable controls.

The database named in `DATABASE_URL` must already exist and be reachable. The backend loads `backend/.env` by path, regardless of the launch directory, and hosted environment variables override local file values. It creates missing tables at startup; it does not migrate existing tables or data.

Create `detection/.env` for layout synchronization and occupancy updates:

```dotenv
API_URL=http://localhost:8000
PARKING_LOT_SLUG=simulator
CAMERA_ID=default
DETECTION_API_TOKEN=the-same-secret-token-as-backend
```

The token must match `backend/.env`. Keep both environment files private and do not commit credentials.

For email-based password reset and MFA, add SMTP settings to `backend/.env`:

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_FROM=parking@example.com
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_SSL=false
FRONTEND_URL=http://localhost:5173/#/reset-password
```

Use the TLS mode and credentials required by your mail provider. For implicit SSL, use the provider's SSL port (commonly 465) and set `SMTP_USE_SSL=true`.

To point the frontend at a backend on a different URL, create `frontend/.env` with:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

The default API URL is `http://localhost:8000`. The backend's development CORS configuration allows the Vite origins `http://localhost:5173` and `http://127.0.0.1:5173`.

Copy `frontend/.env.example` and `detection/.env.example` for local templates. In production, `CORS_ORIGINS` is a comma-separated list of exact browser origins, without paths or trailing slashes. Add the Vercel production domain there. `VITE_API_BASE_URL` is compiled into the browser bundle and must point to the public HTTPS API URL; it must not contain secrets.

## Install and run

### Backend

From the repository root, create and populate a Python environment. Install detection dependencies in the same environment if you plan to use model-based layout generation or video detection:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m pip install -r detection\requirements.txt -r simulator\requirements.txt
```

Then start the API from `backend/`:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

The API is at `http://localhost:8000`; interactive documentation is at `http://localhost:8000/docs`.

### Frontend

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://127.0.0.1:5173`). To make a production bundle, run `npm run build` from `frontend/`.

### Simulator and standalone detection

For the standalone Pygame window and its MJPEG stream, run from `simulator/` using an environment with simulator dependencies:

```powershell
python main.py
```

The simulator exposes its rendered feed at `http://127.0.0.1:8765/video`.

To run the standalone simulator detector, start the simulator and then, in another terminal, run from `detection/`:

```powershell
python -m vehicle.run_simulator
```

## Portal features

Public visitors can view the public site and parking availability when the API is reachable. Registered accounts are regular users; administrator privileges must be provisioned by a trusted operator.

User accounts can view active parking, history, and reports; initiate and confirm parking claims; review login activity; change passwords; and manage MFA. Password reset and MFA email delivery require working SMTP configuration.

Administrators can manage lots and parking spaces, configure camera layouts, run video or simulator detection, manage fare rules, and view reports, users, and activity logs. Management endpoints enforce the administrator role in the backend.

Parking availability and space summaries are served by the API. Layouts, parking records, history, fare rules, and reports are scoped to a parking lot. Occupancy updates from detection use the shared detection token or an administrator bearer token.

## Lots, spaces, and camera layouts

Create a lot through the admin portal or `POST /lots/`. A lot has a unique slug, such as `campus-west`. Create or synchronize its parking spaces through the admin portal or the detection layout workflow. Space labels only need to be unique within their lot.

Layouts are stored per lot and camera under:

```text
detection/layout/layouts/<lot-slug>/<camera-id>.json
```

The legacy `detection/layout/parking_layout.json` remains the fallback layout for the Simulator lot's `default` camera. Do not use it for other lots.

In the admin portal, open **Layout Configuration**, select a lot and camera, upload an image from that camera, generate candidates, review the polygons and slot names, and save the layout. Candidate generation uses `detection/models/parking_lot.pt`. Always review candidates before saving. Saving the reference image alongside the layout enables the web video-detection workflow.

The standalone layout tool can also export a review bundle. From `detection/`, with the backend configured and running:

```powershell
python test_layout.py --lot campus-west --camera gate-a --export-review
```

Pass `--image path\to\frame.png` to use a different image. The contour-based candidate detector is available without model weights; `--model-weights path\to\weights.pt` selects a pretrained parking-space detector.

## Occupancy detection

### Real-world video

The admin portal's **Video Detection** page accepts MP4, MOV, AVI, MKV, or WebM uploads up to 500 MB. Select the lot and camera whose reviewed layout and reference photo match the recording. The backend shows an annotated frame preview, synchronizes confirmed occupancy states to that lot, and produces a downloadable annotated video. Occupancy is cleared for that lot when processing ends or is stopped.

For standalone processing, run from `detection/` with the backend and `detection/.env` configured:

```powershell
python -m vehicle.run_irl --lot campus-west --camera gate-a
```

The defaults use `12125602_30fps.mp4`, `parking_layout_v2.png`, and `models/parking_lot.pt`. Supply `--video`, `--reference-image`, or `--model-weights` to choose other files. The reference image must show the same camera view as the video. Use `--no-sync` for preview-only processing or `--no-preview` to disable the local preview window. The standalone runner writes a timestamped annotated recording under `detection/output/` unless `--output` is supplied. `--frame-stride` changes inference frequency while output playback retains the source frame rate.

The default `parking_spaces` mode classifies parking-space crops as `space-empty` or `space-occupied`. `--detector-mode vehicles --model-weights models\yolo11n.pt` selects vehicle detection instead; generic vehicle weights may be unsuitable for small or distant cars.

### Simulator detection

The admin portal's **Simulator Detection** page starts and controls the Pygame simulator and detector as a managed job. It streams annotated frames and provides controls to spawn cars and send parked cars out. Stopping the job clears occupancy in the Simulator lot. The backend runtime must have the simulator and detection dependencies installed.

### Detection behavior

The occupancy tracker requires repeated confirming frames before applying changes. API updates are queued and retried with capped backoff for connection failures, HTTP 408/429, and server errors. Permanent client errors are logged and not retried. Video processing requires a saved layout and a camera reference image; unmatched spaces are left unchanged. Detection reaching the end of a video or being stopped clears occupancy in the selected lot.

## API overview

The FastAPI docs at `/docs` show the full schemas. Main route groups include:

- `/auth` — registration, login, profile, MFA, and password reset
- `/lots` and `/parking` — lots, spaces, bulk sync, occupancy, and claim-related records
- `/layouts` — camera layouts, candidate generation, and reference photos
- `/users/me` — personal parking, history, reports, login activity, and password changes
- `/admin` — administrator reports, fare rules, user views, and activity logs
- `/video-detection` and `/simulator-detection` — administrator-managed detection jobs

Lot creation, manual space management, layout saves, fare-rule changes, and detection-job controls require an administrator account. Detection synchronization endpoints also accept the configured `X-Detection-Token` where supported.

## Database and deployment notes

The backend calls `Base.metadata.create_all()` at startup. This creates tables that are missing but does not alter existing columns, add new columns to existing tables, or perform a multi-lot data migration. The repository currently has no checked-in SQL migration for converting a legacy single-lot database. Before deploying against an existing database, back it up and plan and verify the required schema/data migration separately. Do not assume an existing database is ready for the current multi-lot models just because the API starts.

Fare rules are evaluated independently per lot. The scheduler records fare intervals at 15-minute boundaries while the API process runs; a lot without a matching fare rule does not accrue intervals. Reported amounts reflect recorded fares, not confirmed payments. Stopping video or simulator detection clears occupancy and closes active parking sessions through the occupancy endpoint.

## Deploying to Vercel, Render, and Aiven

1. **Prepare Aiven MySQL.** Create the service, database, and a dedicated application user. Use the service host and port from Aiven, enable TLS, and use the provided CA certificate when configuring certificate verification. The backend SQLAlchemy URL uses the `mysql+pymysql` driver; URL-encode reserved characters in the username or password. Restrict Aiven's IP filter to the Render service's outbound IP ranges (or dedicated outbound IPs if configured). Take a backup before importing production data.
2. **Prepare the schema and accounts.** For a new database, the backend creates missing tables when it starts. For an existing database, `create_all()` is not a migration: first develop and verify a schema/data migration against a copy. Provision the first administrator through a trusted operator process; public registration never grants admin access. Create the Simulator lot and its spaces if using simulator detection.
3. **Create the Render API Web Service** from the repository with the repository root as its root directory. The root `.python-version` pins the service to Python 3.13.5 so the simulator's pinned Pygame release has a compatible Linux wheel. If the Render service has a `PYTHON_VERSION` environment variable, set it to `3.13.5` too because it takes precedence over `.python-version`. Build command: `bash scripts/render-build.sh`. This installs the backend ML stack in the API environment and the simulator dependencies in an isolated `simulator/venv`; the simulator launcher uses that environment when available. Start command: `cd backend && PYTHONPATH=.. uvicorn main:app --host 0.0.0.0 --port $PORT`. Set the health check path to `/health/ready`. Configure `DATABASE_URL`, `SECRET_KEY`, `DETECTION_API_TOKEN`, `API_URL`, `CORS_ORIGINS`, and any SMTP settings in Render's environment controls. `API_URL` should be `https://<your-render-service>.onrender.com`, and `DETECTION_API_TOKEN` must match the backend token; both are read by detection code from hosted environment variables. `CORS_ORIGINS` should contain the exact Vercel production origin, for example `https://your-app.vercel.app`, plus any custom domain. The health endpoint returns 503 until MySQL responds.
4. **Create the Vercel project** with `frontend/` as the project root, `npm run build` as the build command, and `dist` as the output directory. Set `VITE_API_BASE_URL` to the Render API's public HTTPS origin for Production and Preview as appropriate. Redeploy after changing environment variables. The app uses hash-based navigation, so application routes remain on the root browser path.
5. **Verify staging end to end.** Check `/health/ready`, register a normal user, verify the browser can call the API without CORS errors, and exercise account and parking flows before using production data. Configure SMTP separately if password reset or MFA is needed.

### Detection deployment boundary

The current video and simulator jobs run in threads inside the API process. The simulator itself runs as a subprocess using its isolated `simulator/venv`. Job state is held in process memory, and uploads, output videos, camera reference photos, and saved layouts use local filesystem paths. A restart loses active job state; Render's default filesystem is ephemeral. Do not deploy a separate worker and expect it to work with the current API: it would not share the job state or local files.

For a reliable separate detection worker, first move job state to durable storage, add a queue between the API and worker, and put uploads/results/reference images in shared object storage. Then run inference in a private Render Background Worker with its own pinned Python and ML dependencies. Until then, keep detection as a single-service feature only if you accept its restart and storage limits, or defer using the detection pages for the initial release. Avoid scaling a service that owns active detection jobs to multiple instances.

## Development checks

The repository includes manually invoked scripts such as `detection/test_layout.py`, `detection/test_pipeline.py`, and scripts under `detection/` for vehicle and occupancy checks. They are workflow utilities and may require local images, model weights, a configured database, or a running backend; the repository does not define a unified automated test command.
