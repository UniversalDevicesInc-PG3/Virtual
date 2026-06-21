"""Pytest configuration shared across the test suite.

Node tests import node classes at module scope, before per-test fixtures run.
If udi_interface fails to initialize in a dev environment (partial import leaving
no ``Node`` export), collection fails before any mocks apply. Install a lightweight
stub when the real package is missing or incomplete.

Stub types must be real classes/objects, not MagicMock instances, because tests
patch imported names with autospec=True.
"""

import logging
import sys
import types
from unittest.mock import MagicMock


class _MockNode:
    """Minimal stand-in for udi_interface.Node during test collection."""

    def __init__(self, poly=None, controller=None, address=None, name=None):
        self.poly = poly
        self.address = address
        self.name = name


class _StubCustom:
    """Stand-in for udi_interface.Custom."""

    def __init__(self, *args, **kwargs):
        pass


class _StubISY:
    """Stand-in for udi_interface.ISY."""

    def __init__(self, *args, **kwargs):
        pass


class _StubLogHandler:
    """Stand-in for udi_interface.LOG_HANDLER."""


def _udi_interface_stub():
    stub = types.ModuleType("udi_interface")
    stub.Node = _MockNode
    stub.LOGGER = logging.getLogger("udi_interface.stub")
    stub.ISY = _StubISY
    stub.Custom = _StubCustom
    stub.LOG_HANDLER = _StubLogHandler
    stub.Interface = MagicMock(name="Interface")
    return stub


def _node_import_is_valid():
    try:
        from udi_interface import Node
    except ImportError:
        return False
    return isinstance(Node, type) and not isinstance(Node, MagicMock)


def _ensure_udi_interface():
    if _node_import_is_valid():
        return

    sys.modules.pop("udi_interface", None)
    if _node_import_is_valid():
        return

    sys.modules["udi_interface"] = _udi_interface_stub()


_ensure_udi_interface()
