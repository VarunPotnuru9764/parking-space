"""Backend configuration shared by local development and hosted deployments."""

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]

# Hosted environment variables take precedence; the file keeps local development simple.
load_dotenv(BACKEND_DIR / ".env", override=False)


def get_setting(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def get_required_setting(name: str) -> str:
    value = get_setting(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required backend setting: {name}")
    return value
