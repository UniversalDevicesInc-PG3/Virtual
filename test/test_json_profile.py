"""Validate dynamic JSON profile against static XML profile sources."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile"
BASE_JSON = ROOT / "data" / "base_profile.json"
NODEDEFS = PROFILE / "nodedef" / "nodedefs.xml"
EDITORS = PROFILE / "editor" / "editors.xml"

EXPECTED_NODEDEFS = {
    "controller",
    "virtualswitch",
    "virtualononly",
    "virtualondelay",
    "virtualoffdelay",
    "virtualtoggle",
    "virtualtemp",
    "virtualtempc",
    "virtualgeneric",
    "virtualgarage",
}


def _parse_nodedef_commands() -> dict[str, dict[str, set[str]]]:
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


def _editor_ids_xml() -> set[str]:
    tree = ET.parse(EDITORS)
    return {editor.attrib["id"] for editor in tree.getroot().findall("editor")}


@pytest.fixture(scope="module")
def base_profile() -> dict:
    assert BASE_JSON.exists(), "Run scripts/xml_profile_to_json.py to generate base profile"
    return json.loads(BASE_JSON.read_text(encoding="utf-8"))


def test_base_profile_has_expected_nodedefs(base_profile: dict):
    ids = {node["id"] for node in base_profile["nodedefs"]}
    assert ids == EXPECTED_NODEDEFS


def test_base_profile_editors_match_xml(base_profile: dict):
    xml_ids = _editor_ids_xml()
    json_ids = {editor["id"] for editor in base_profile["editors"]}
    assert json_ids == xml_ids


@pytest.mark.parametrize("section", ["sends", "accepts"])
def test_nodedef_commands_match_xml(base_profile: dict, section: str):
    xml_cmds = _parse_nodedef_commands()
    json_by_id = {node["id"]: node for node in base_profile["nodedefs"]}
    for node_id, xml in xml_cmds.items():
        json_cmds = json_by_id[node_id]["cmds"][section]
        json_ids = {cmd["id"] for cmd in json_cmds}
        assert json_ids == xml[section], f"{node_id}.{section}"
