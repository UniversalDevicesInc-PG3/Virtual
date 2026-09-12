"""Load and push Virtual Devices dynamic JSON profiles to PG3/IoX.

(C) 2026 Stephen Jenkins
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

BASE_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "base_profile.json"


def load_base_profile(path: Path | None = None) -> dict[str, Any]:
    """Return the base dynamic profile (editors + nodedefs)."""
    profile_path = path or BASE_PROFILE_PATH
    return json.loads(profile_path.read_text(encoding="utf-8"))


def push_json_profile(poly, profile: dict[str, Any] | None = None, *, wait: bool = True):
    """Send a JSON profile update via polyglot.updateJsonProfile()."""
    payload = profile if profile is not None else load_base_profile()
    options = {"waitResponse": True} if wait else {}
    LOGGER.info(
        "Pushing dynamic JSON profile (%d editors, %d nodedefs, wait=%s)",
        len(payload.get("editors", [])),
        len(payload.get("nodedefs", [])),
        wait,
    )
    return poly.updateJsonProfile(payload, options)
