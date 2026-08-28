"""Verify bootstrap VERSION matches profile/version.txt."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "udi-Virtual-pg3.py"
VERSION_FILE = ROOT / "profile" / "version.txt"


def _entry_version() -> str:
    text = ENTRY.read_text()
    match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    assert match, f"VERSION not found in {ENTRY.name}"
    return match.group(1)


def test_profile_version_matches_entry_script():
    assert VERSION_FILE.exists(), "profile/version.txt is required for ISY profile sync"
    assert VERSION_FILE.read_text().strip() == _entry_version()
