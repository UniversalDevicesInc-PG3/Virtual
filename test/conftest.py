"""Pytest configuration shared across the test suite.

Node tests import node classes at module scope, before per-test fixtures run.
If udi_interface fails to initialize in a dev environment (partial import leaving
no ``Node`` export), collection fails before any mocks apply. Install a lightweight
stub when the real package is missing or incomplete.
"""

import sys
from unittest.mock import MagicMock


class _MockNode:
    """Minimal stand-in for udi_interface.Node during test collection."""

    def __init__(self, poly=None, controller=None, address=None, name=None):
        self.poly = poly
        self.address = address
        self.name = name


def _udi_interface_stub():
    stub = MagicMock(name="udi_interface_module")
    stub.Node = _MockNode
    stub.LOGGER = MagicMock(name="LOGGER")
    stub.ISY = MagicMock(name="ISY")
    stub.Custom = MagicMock(name="Custom")
    stub.LOG_HANDLER = MagicMock(name="LOG_HANDLER")
    stub.Interface = MagicMock(name="Interface")
    return stub


def _ensure_udi_interface():
    try:
        from udi_interface import Node  # noqa: F401
    except ImportError:
        sys.modules.pop("udi_interface", None)
        try:
            from udi_interface import Node  # noqa: F401
        except ImportError:
            sys.modules["udi_interface"] = _udi_interface_stub()


_ensure_udi_interface()
