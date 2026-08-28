#!/usr/bin/env python3
"""Sync VERSION from bootstrap script to profile/version.txt and server.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION_RE = re.compile(r'^VERSION\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def read_version(entry: Path) -> str:
    match = VERSION_RE.search(entry.read_text())
    if not match:
        raise SystemExit(f"VERSION not found in {entry}")
    return match.group(1)


def write_version_txt(profile_dir: Path, version: str) -> None:
    path = profile_dir / "version.txt"
    path.write_text(f"{version}\n")
    print(f"updated {path}")


def write_server_json(root: Path, version: str) -> None:
    path = root / "server.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    credits = data.get("credits")
    if credits:
        credits[0]["version"] = version
    path.write_text(json.dumps(data, indent=4) + "\n")
    print(f"updated {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entry",
        default="udi-plugin-template-pg3x.py",
        help="Bootstrap script containing VERSION (default: udi-plugin-template-pg3x.py)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Plugin repo root (default: parent of scripts/)",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    entry = root / args.entry
    if not entry.exists():
        raise SystemExit(f"Entry script not found: {entry}")

    version = read_version(entry)
    write_version_txt(root / "profile", version)
    write_server_json(root, version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
