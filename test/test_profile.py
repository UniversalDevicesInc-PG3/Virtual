"""Validate ISY profile files and version sync for Virtual Devices."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile"
NODEDEFS = PROFILE / "nodedef" / "nodedefs.xml"
EDITORS = PROFILE / "editor" / "editors.xml"
VERSION_FILE = PROFILE / "version.txt"
ENTRY = ROOT / "udi-virtual-pg3x.py"

CONTROLLER_COMMANDS = {"QUERY", "DISCOVER"}
CONTROLLER_NODEDEF = "controller"


def _entry_version() -> str:
    text = ENTRY.read_text()
    match = re.search(r'^VERSION = "([^"]+)"', text, re.MULTILINE)
    assert match, f"VERSION not found in {ENTRY.name}"
    return match.group(1)


def _parse_nodedefs() -> dict[str, dict[str, set[str]]]:
    tree = ET.parse(NODEDEFS)
    result: dict[str, dict[str, set[str]]] = {}
    for node in tree.getroot().findall("nodeDef"):
        node_id = node.attrib["id"]
        cmds: dict[str, set[str]] = {"sends": set(), "accepts": set()}
        for section in ("sends", "accepts"):
            container = node.find(f"cmds/{section}")
            if container is None:
                continue
            for cmd in container.findall("cmd"):
                cmds[section].add(cmd.attrib["id"])
        result[node_id] = cmds
    return result


def _editor_ids() -> set[str]:
    tree = ET.parse(EDITORS)
    return {editor.attrib["id"] for editor in tree.getroot().findall("editor")}


def test_profile_version_matches_entry_script():
    assert VERSION_FILE.exists(), "profile/version.txt is required for ISY profile sync"
    assert VERSION_FILE.read_text().strip() == _entry_version()


def test_controller_nodedef_id():
    nodedefs = _parse_nodedefs()
    assert CONTROLLER_NODEDEF in nodedefs


def test_controller_commands_match_python():
    nodedefs = _parse_nodedefs()
    assert nodedefs[CONTROLLER_NODEDEF]["accepts"] == CONTROLLER_COMMANDS


def test_status_editors_exist():
    editors = _editor_ids()
    tree = ET.parse(NODEDEFS)
    used = {
        st.attrib["editor"]
        for node in tree.getroot().findall("nodeDef")
        for st in node.findall("sts/st")
    }
    missing = used - editors
    assert not missing, f"Missing editor definitions: {sorted(missing)}"
