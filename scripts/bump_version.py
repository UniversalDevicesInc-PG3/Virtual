#!/usr/bin/env python3
"""Set VERSION in the bootstrap script and run sync_version.py."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

VERSION_RE = re.compile(
    r'^(VERSION\s*=\s*["\'])([^"\']+)(["\'])',
    re.MULTILINE,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help='New version string, e.g. "0.0.2"')
    parser.add_argument(
        "--entry",
        default="udi-plugin-template-pg3x.py",
        help="Bootstrap script to update",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Plugin repo root",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    entry = root / args.entry
    text = entry.read_text()
    if not VERSION_RE.search(text):
        raise SystemExit(f"VERSION assignment not found in {entry}")
    text = VERSION_RE.sub(rf'\g<1>{args.version}\g<3>', text, count=1)
    entry.write_text(text)
    print(f"set VERSION to {args.version} in {entry}")

    sync = root / "scripts" / "sync_version.py"
    return subprocess.call([sys.executable, str(sync), "--entry", args.entry, "--root", str(root)])


if __name__ == "__main__":
    sys.exit(main())
