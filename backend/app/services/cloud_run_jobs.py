"""Launch layout inference executions on Google Cloud Run Jobs."""

import json
import os
from urllib.parse import quote

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account


def execute_layout_detection(job_id: str) -> dict:
    project = os.environ.get("CLOUD_RUN_PROJECT_ID", "").strip()
    region = os.environ.get("CLOUD_RUN_REGION", "").strip()
    job_name = os.environ.get("CLOUD_RUN_DETECTION_JOB", "").strip()
    credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    missing = [
        name for name, value in (
            ("CLOUD_RUN_PROJECT_ID", project),
            ("CLOUD_RUN_REGION", region),
            ("CLOUD_RUN_DETECTION_JOB", job_name),
            ("GOOGLE_SERVICE_ACCOUNT_JSON", credentials_json),
        ) if not value
    ]
    if missing:
        raise RuntimeError(f"Missing Cloud Run configuration: {', '.join(missing)}")

    try:
        key_info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            key_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not a valid service account key") from exc

    url = (
        "https://run.googleapis.com/v2/projects/"
        f"{quote(project, safe='')}/locations/{quote(region, safe='')}/jobs/"
        f"{quote(job_name, safe='')}:run"
    )
    payload = {
        "overrides": {
            "containerOverrides": [{"args": ["--job-id", job_id]}],
            "taskCount": 1,
            "timeout": "900s",
        }
    }
    with AuthorizedSession(credentials) as session:
        response = session.post(url, json=payload, timeout=25)
    if not response.ok:
        raise RuntimeError(f"Cloud Run Jobs returned HTTP {response.status_code}: {response.text[:1000]}")
    return response.json()
