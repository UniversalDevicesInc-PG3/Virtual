#!/usr/bin/env python3
"""Convert static profile XML + NLS into a dynamic JSON profile.

Source of truth remains profile/ in the repo; this script generates
data/base_profile.json for polyglot.updateJsonProfile().

(C) 2026 Stephen Jenkins
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _parse_nls(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        entries[key.strip()] = value.strip()
    return entries


def _nls_names(
    nls: dict[str, str], prefix: str, subset: str | None
) -> dict[str, str] | None:
    if not subset or not prefix:
        return None
    names: dict[str, str] = {}
    for part in subset.replace(" ", "").split(","):
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            values = range(int(start_s), int(end_s) + 1)
        else:
            values = [int(part)]
        for value in values:
            key = f"{prefix}-{value}"
            if key in nls:
                names[str(value)] = nls[key]
    return names or None


def _range_element(range_el: ET.Element, nls: dict[str, str]) -> dict[str, Any]:
    item: dict[str, Any] = {}
    uom = range_el.attrib.get("uom")
    if uom is not None:
        item["uom"] = uom
    for attr in ("min", "max", "prec", "step", "subset"):
        if attr in range_el.attrib:
            value = range_el.attrib[attr]
            if attr in ("min", "max", "prec", "step"):
                if "." in value:
                    item[attr] = float(value) if attr == "step" else float(value)
                else:
                    item[attr] = int(value)
            else:
                item[attr] = value
    nls_key = range_el.attrib.get("nls")
    if nls_key and "subset" in item:
        names = _nls_names(nls, nls_key, item["subset"])
        if names:
            item["names"] = names
    return item


def _editors(editors_path: Path, nls: dict[str, str]) -> list[dict[str, Any]]:
    tree = ET.parse(editors_path)
    editors: list[dict[str, Any]] = []
    for editor_el in tree.getroot().findall("editor"):
        editor_id = editor_el.attrib["id"]
        ranges = [_range_element(r, nls) for r in editor_el.findall("range")]
        editors.append({"id": editor_id, "ranges": ranges})
    return editors


def _parameter(param_el: ET.Element, nls: dict[str, str]) -> dict[str, Any]:
    param: dict[str, Any] = {
        "id": param_el.attrib.get("id", ""),
        "editor": param_el.attrib["editor"],
    }
    if "init" in param_el.attrib:
        param["init"] = param_el.attrib["init"]
    param_id = param_el.attrib.get("id", "")
    if param_id:
        name_key = f"CMDP-{param_id}-NAME"
        if name_key in nls:
            param["name"] = nls[name_key]
    return param


def _command(
    cmd_el: ET.Element, nls_key: str, nls: dict[str, str]
) -> dict[str, Any]:
    cmd_id = cmd_el.attrib["id"]
    cmd: dict[str, Any] = {"id": cmd_id}
    name_key = f"CMD-{nls_key}-{cmd_id}-NAME"
    if name_key in nls:
        cmd["name"] = nls[name_key]
    fmt_key = f"PGM-CMD-{cmd_id}-FMT"
    if fmt_key in nls:
        cmd["format"] = nls[fmt_key]
    params = [_parameter(p, nls) for p in cmd_el.findall("p")]
    if params:
        cmd["parameters"] = params
    return cmd


def _properties(
    node_el: ET.Element, nls_key: str, nls: dict[str, str]
) -> list[dict[str, Any]]:
    properties: list[dict[str, Any]] = []
    for st_el in node_el.findall("sts/st"):
        st_id = st_el.attrib["id"]
        prop: dict[str, Any] = {
            "id": st_id,
            "editor": st_el.attrib["editor"],
        }
        name_key = f"ST-{nls_key}-{st_id}-NAME"
        if name_key in nls:
            prop["name"] = nls[name_key]
        properties.append(prop)
    return properties


def _nodedefs(nodedefs_path: Path, nls: dict[str, str]) -> list[dict[str, Any]]:
    tree = ET.parse(nodedefs_path)
    nodedefs: list[dict[str, Any]] = []
    for node_el in tree.getroot().findall("nodeDef"):
        node_id = node_el.attrib["id"]
        nls_key = node_el.attrib.get("nls", node_id)
        node: dict[str, Any] = {"id": node_id}
        name_key = f"ND-{node_id}-NAME"
        if name_key in nls:
            node["name"] = nls[name_key]
        icon_key = f"ND-{node_id}-ICON"
        if icon_key in nls:
            node["icon"] = nls[icon_key]

        properties = _properties(node_el, nls_key, nls)
        if properties:
            node["properties"] = properties

        cmds: dict[str, list[dict[str, Any]]] = {}
        for section in ("sends", "accepts"):
            container = node_el.find(f"cmds/{section}")
            if container is None:
                continue
            cmds[section] = [
                _command(cmd_el, nls_key, nls) for cmd_el in container.findall("cmd")
            ]
        if cmds:
            node["cmds"] = cmds
        nodedefs.append(node)
    return nodedefs


def build_profile(profile_dir: Path) -> dict[str, Any]:
    nls = _parse_nls(profile_dir / "nls" / "en_us.txt")
    return {
        "editors": _editors(profile_dir / "editor" / "editors.xml", nls),
        "nodedefs": _nodedefs(profile_dir / "nodedef" / "nodedefs.xml", nls),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "profile",
        help="Static profile directory (default: repo profile/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "base_profile.json",
        help="Output JSON path (default: data/base_profile.json)",
    )
    args = parser.parse_args()

    profile = build_profile(args.profile_dir.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(profile['editors'])} editors, "
          f"{len(profile['nodedefs'])} nodedefs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
