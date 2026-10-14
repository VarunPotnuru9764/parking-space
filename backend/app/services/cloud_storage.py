"""Private Cloud Storage access brokered by the protected trigger service."""

import os
import threading
import time
import requests

_SIGNED_URL_CACHE = {}
_SIGNED_URL_LOCK = threading.Lock()


def _trigger_settings() -> tuple[str, dict[str, str]]:
    trigger_url = os.environ.get("CLOUD_RUN_TRIGGER_URL", "").strip().rstrip("/")
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
        raise RuntimeError(f"Missing Cloud Storage trigger configuration: {', '.join(missing)}")
    return trigger_url, {"Authorization": f"Bearer {trigger_secret}"}


def create_upload_session(object_name: str, content_type: str) -> str:
    """Ask the trigger service for a resumable upload URL for one artifact."""
    trigger_url, headers = _trigger_settings()
    response = requests.post(
        f"{trigger_url}/storage/upload-session",
        json={"object_name": object_name, "content_type": content_type},
        headers=headers,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Cloud Storage upload-session request returned HTTP {response.status_code}")
    upload_url = response.json().get("upload_url")
    if not isinstance(upload_url, str) or not upload_url.startswith("https://"):
        raise RuntimeError("Cloud Storage trigger returned an invalid upload URL")
    return upload_url


def upload_file(object_name: str, content_type: str, file_path, size: int) -> None:
    """Stream a local temporary file to a trigger-issued resumable URL."""
    upload_url = create_upload_session(object_name, content_type)
    with open(file_path, "rb") as source:
        response = requests.put(
            upload_url,
            data=source,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(size),
                "Content-Range": f"bytes 0-{size - 1}/{size}",
            },
            timeout=(30, 900),
        )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Cloud Storage upload returned HTTP {response.status_code}")


def upload_bytes(object_name: str, content_type: str, content: bytes) -> None:
    upload_url = create_upload_session(object_name, content_type)
    response = requests.put(
        upload_url,
        data=content,
        headers={
            "Content-Type": content_type,
            "Content-Length": str(len(content)),
            "Content-Range": f"bytes 0-{len(content) - 1}/{len(content)}",
        },
        timeout=120,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Cloud Storage upload returned HTTP {response.status_code}")


def create_download_url(object_name: str) -> str:
    now = time.monotonic()
    with _SIGNED_URL_LOCK:
        cached = _SIGNED_URL_CACHE.get(object_name)
        if cached and cached[0] > now:
            return cached[1]
    trigger_url, headers = _trigger_settings()
    response = requests.post(
        f"{trigger_url}/storage/signed-read",
        json={"object_name": object_name},
        headers=headers,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Cloud Storage signed-read request returned HTTP {response.status_code}")
    download_url = response.json().get("download_url")
    if not isinstance(download_url, str) or not download_url.startswith("https://"):
        raise RuntimeError("Cloud Storage trigger returned an invalid download URL")
    with _SIGNED_URL_LOCK:
        _SIGNED_URL_CACHE[object_name] = (now + 12 * 60, download_url)
    return download_url


def stream_download(object_name: str):
    """Return a streaming response from a short-lived signed object URL."""
    download_url = create_download_url(object_name)
    response = requests.get(download_url, stream=True, timeout=(30, 900))
    if not response.ok:
        response.close()
        raise RuntimeError(f"Cloud Storage download returned HTTP {response.status_code}")
    return response


def download_bytes(object_name: str) -> bytes:
    response = stream_download(object_name)
    try:
        return response.content
    finally:
        response.close()
