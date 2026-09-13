"""Load and push Virtual Devices dynamic JSON profiles to PG3/IoX.

(C) 2026 Stephen Jenkins
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

BASE_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "base_profile.json"
PROFILE_NODEDEFS = (
    Path(__file__).resolve().parents[1] / "profile" / "nodedef" / "nodedefs.xml"
)


def load_base_profile(path: Path | None = None) -> dict[str, Any]:
    """Return the base dynamic profile (editors + nodedefs)."""
    profile_path = path or BASE_PROFILE_PATH
    return json.loads(profile_path.read_text(encoding="utf-8"))


def _wait_mqtt_ready(poly, *, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if getattr(poly, "connected", False) and getattr(poly, "subscribed", False):
            return True
        time.sleep(0.05)
    return False


def push_json_profile(poly, profile: dict[str, Any] | None = None, *, wait: bool = True):
    """Send a JSON profile update via polyglot.updateJsonProfile()."""
    if wait and not _wait_mqtt_ready(poly):
        raise TimeoutError("MQTT not ready for JSON profile push")

    payload = profile if profile is not None else load_base_profile()
    options = {"waitResponse": True} if wait else {}
    response = poly.updateJsonProfile(payload, options)
    return response


def sync_profile_to_isy(poly, *, wait_json: bool = True) -> None:
    """Push JSON profile, then static installprofile when XML profile is present."""
    push_json_profile(poly, wait=wait_json)
    if PROFILE_NODEDEFS.is_file():
        poly.updateProfile()
