"""Protected Cloud Run Job and private Cloud Storage trigger API."""

from datetime import timedelta
import hmac
import os
import re
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


app = FastAPI()

PROJECT_ID = os.environ["PROJECT_ID"]
REGION = os.environ.get("REGION", "asia-southeast1")
JOB_NAME = os.environ.get("JOB_NAME", "parking-detection-worker")
VIDEO_JOB_NAME = os.environ.get("VIDEO_JOB_NAME", "parking-video-detection-worker")
GCS_BUCKET = os.environ.get("GCS_BUCKET", "")
TRIGGER_SECRET = os.environ["TRIGGER_SECRET"]
JOB_ID_PATTERN = re.compile(r"[0-9a-fA-F-]{36}")
OBJECT_PATTERN = re.compile(
    r"video-jobs/[0-9a-fA-F-]{36}/(?:input\.[a-zA-Z0-9]{2,5}|layout\.json|"
    r"reference\.(?:jpg|jpeg|png|webp|bmp)|preview\.jpg|result\.mp4)"
)


class TriggerRequest(BaseModel):
    job_id: str
    job_type: str = "layout"


class UploadSessionRequest(BaseModel):
    object_name: str
    content_type: str = Field(min_length=1, max_length=128)


class SignedReadRequest(BaseModel):
    object_name: str


def _authorize(authorization: str | None) -> None:
    expected = f"Bearer {TRIGGER_SECRET}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _validate_object_name(object_name: str) -> None:
    if not OBJECT_PATTERN.fullmatch(object_name):
        raise HTTPException(status_code=400, detail="Invalid video artifact path")


def _require_bucket() -> str:
    if not GCS_BUCKET:
        raise HTTPException(status_code=503, detail="Video artifact storage is not configured")
    return GCS_BUCKET


def _signed_read_url(blob, auth_request, credentials, service_account_email: str) -> str:
    """Sign a short-lived GET URL with the attached identity's IAM signer."""
    from google.auth import iam

    signer = iam.Signer(auth_request, credentials, service_account_email)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=15),
        method="GET",
        service_account_email=service_account_email,
        access_token=credentials.token,
        credentials=signer,
    )


def _credentials():
    import google.auth

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return credentials


def _job_launch(request: TriggerRequest) -> tuple[str, str, dict]:
    if not JOB_ID_PATTERN.fullmatch(request.job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    if request.job_type not in {"layout", "video"}:
        raise HTTPException(status_code=400, detail="Invalid job type")

    if request.job_type == "layout":
        job_name, argument = JOB_NAME, "--job-id"
    else:
        job_name, argument = VIDEO_JOB_NAME, "--video-job-id"
    overrides = {
        "containerOverrides": [{"args": [argument, request.job_id]}],
        "taskCount": 1,
    }
    if request.job_type == "layout":
        overrides["timeout"] = "900s"
    return job_name, argument, {"overrides": overrides}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/trigger")
def trigger_job(
    request: TriggerRequest,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    job_name, _, payload = _job_launch(request)
    from google.auth.transport.requests import AuthorizedSession

    credentials = _credentials()
    session = AuthorizedSession(credentials)
    url = (
        f"https://run.googleapis.com/v2/projects/{quote(PROJECT_ID, safe='')}"
        f"/locations/{quote(REGION, safe='')}/jobs/{quote(job_name, safe='')}:run"
    )
    try:
        response = session.post(url, json=payload, timeout=25)
    finally:
        session.close()
    if not response.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Cloud Run Jobs API returned HTTP {response.status_code}",
        )
    return {"status": "triggered", "job_id": request.job_id, "job_type": request.job_type}


@app.post("/storage/upload-session")
def create_upload_session(
    request: UploadSessionRequest,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    _validate_object_name(request.object_name)
    bucket_name = _require_bucket()
    from google.auth.transport.requests import AuthorizedSession

    credentials = _credentials()
    session = AuthorizedSession(credentials)
    url = f"https://storage.googleapis.com/upload/storage/v1/b/{quote(bucket_name, safe='')}/o"
    try:
        response = session.post(
            url,
            params={"uploadType": "resumable", "name": request.object_name},
            headers={
                "Content-Type": "application/json",
                "X-Upload-Content-Type": request.content_type,
            },
            json={"name": request.object_name, "contentType": request.content_type},
            timeout=30,
        )
    finally:
        session.close()
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Cloud Storage returned HTTP {response.status_code} while creating an upload session",
        )
    upload_url = response.headers.get("Location")
    if not upload_url or not upload_url.startswith("https://"):
        raise HTTPException(status_code=502, detail="Cloud Storage did not return an upload URL")
    return {"upload_url": upload_url, "object_name": request.object_name}


@app.post("/storage/signed-read")
def create_signed_read_url(
    request: SignedReadRequest,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    _validate_object_name(request.object_name)
    bucket_name = _require_bucket()
    import google.auth
    from google.auth.transport.requests import Request
    from google.cloud import storage

    credentials = _credentials()
    auth_request = Request()
    credentials.refresh(auth_request)
    service_account_email = os.environ.get("SERVICE_ACCOUNT_EMAIL") or getattr(
        credentials, "service_account_email", None
    )
    if not service_account_email:
        raise HTTPException(status_code=500, detail="Trigger service identity is unavailable")

    client = storage.Client(project=PROJECT_ID, credentials=credentials)
    blob = client.bucket(bucket_name).blob(request.object_name)
    try:
        signed_url = _signed_read_url(blob, auth_request, credentials, service_account_email)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not sign Cloud Storage read URL") from exc
    return {"download_url": signed_url}
