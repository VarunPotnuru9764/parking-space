"""Detection-service settings for local runs and hosted environments."""

import os
from pathlib import Path

from dotenv import dotenv_values


DETECTION_DIR = Path(__file__).resolve().parents[1]
_DOTENV = dotenv_values(DETECTION_DIR / ".env")


def get_setting(name: str, default: str | None = None) -> str | None:
    """Prefer the host environment, then the local detection/.env file."""
    return os.environ.get(name) or _DOTENV.get(name) or default
