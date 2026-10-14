import os
import re

import requests


def _trigger(job_id: str, job_type: str) -> dict:
    trigger_url = os.environ.get("CLOUD_RUN_TRIGGER_URL", "").strip()
    trigger_secret = os.environ.get("CLOUD_RUN_TRIGGER_SECRET", "")

    missing = [
        name
        for name, value in (
            ("CLOUD_RUN_TRIGGER_URL", trigger_url),
            ("CLOUD_RUN_TRIGGER_SECRET", trigger_secret),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing Cloud Run trigger configuration: {', '.join(missing)}"
        )

    if not re.fullmatch(r"[0-9a-fA-F-]{36}", job_id):
        raise ValueError("Invalid detection job ID")

    payload = {"job_id": job_id}
    if job_type != "layout":
        payload["job_type"] = job_type
    response = requests.post(
        f"{trigger_url.rstrip('/')}/trigger",
        json=payload,
        headers={"Authorization": f"Bearer {trigger_secret}"},
        timeout=30,
    )

    if not response.ok:
        raise RuntimeError(
            f"Cloud Run trigger returned HTTP {response.status_code}"
        )

    return response.json()


def execute_layout_detection(job_id: str) -> dict:
    """Launch a layout job using the original trigger payload contract."""
    return _trigger(job_id, "layout")


def execute_video_detection(job_id: str) -> dict:
    """Launch the separate Cloud Run video-detection job."""
    return _trigger(job_id, "video")
