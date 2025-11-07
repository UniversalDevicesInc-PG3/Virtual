"""
Unit tests for the VirtualonOnly node.
"""

import pytest
from unittest.mock import MagicMock, patch

from nodes.VirtualonOnly import VirtualonOnly, ON, OFF, FIELDS


# This fixture automatically mocks the udi_interface dependencies for all tests.
@pytest.fixture(autouse=True)
def mock_udi_interface():
    """Automatically mock udi_interface.Node and LOGGER."""
    with patch("nodes.VirtualonOnly.Node", autospec=True), patch(
        "nodes.VirtualonOnly.LOGGER", autospec=True
    ):
        yield


@pytest.fixture
def mock_polyglot():
    """Fixture for a mocked Polyglot interface object."""
    poly = MagicMock(name="Polyglot")
    controller_node = MagicMock(name="ControllerNode")
    controller_node.ready_event.wait = MagicMock()
    poly.getNode.return_value = controller_node
    return poly


@pytest.fixture
def ononly_node(mock_polyglot):
    """
    Fixture to create a VirtualonOnly instance for testing.
    It patches utility functions to isolate the node's own logic.
    """
    with patch("nodes.VirtualonOnly.load_persistent_data"), patch(
        "nodes.VirtualonOnly.get_config_data"
    ), patch("nodes.VirtualonOnly.store_values") as mock_store:
        node = VirtualonOnly(
            mock_polyglot, "controller_addr", "ononly_addr", "Test OnOnly"
        )

        # Explicitly mock methods from the parent Node class
        node.setDriver = MagicMock()
        node.reportCmd = MagicMock()
        node.reportDrivers = MagicMock()

        # Simulate the effect of load_persistent_data for a clean slate
        node.data = {field: spec.default for field, spec in FIELDS.items()}

        yield node, {"store": mock_store}


class TestVirtualonOnly:
    """Test suite for the VirtualonOnly node."""

    def test_init(self, ononly_node, mock_polyglot):
        """Test the initialization of the VirtualonOnly node."""
        node, _ = ononly_node
        assert node.name == "Test OnOnly"
        assert node.id == "virtualononly"
        mock_polyglot.subscribe.assert_called_with(
            mock_polyglot.START, node.start, "ononly_addr"
        )
        assert node.data["switch"] == OFF

    def test_don_cmd(self, ononly_node):
        """Test the DON (On) command."""
        node, mocks = ononly_node
        node.data["switch"] = OFF  # Arrange: ensure switch is off

        node.DON_cmd()  # Act

        # Assert
        assert node.data["switch"] == ON
        node.setDriver.assert_called_with("ST", ON)
        node.reportCmd.assert_called_with("DON")
        mocks["store"].assert_called_with(node)

    def test_dof_cmd(self, ononly_node):
        """Test the DOF (Off) command, ensuring it does NOT report the command."""
        node, mocks = ononly_node
        node.data["switch"] = ON  # Arrange: ensure switch is on

        node.DOF_cmd()  # Act

        # Assert
        assert node.data["switch"] == OFF
        node.setDriver.assert_called_with("ST", OFF)
        node.reportCmd.assert_not_called()  # This is the key difference from VirtualSwitch
        mocks["store"].assert_called_with(node)

    def test_query(self, ononly_node):
        """Test the query command."""
        node, _ = ononly_node
        node.query()
        node.reportDrivers.assert_called_once()

    def test_node_definition_attributes(self, ononly_node):
        """Test that the node's defining attributes (id, drivers, commands) are correct."""
        node, _ = ononly_node
        assert node.id == "virtualononly"
        assert node.hint == "0x01020700"

        # Check that the 'ST' driver is defined
        assert any(d["driver"] == "ST" for d in node.drivers)

        # Check that all expected commands are present
        expected_commands = ["DON", "DOF", "QUERY"]
        for cmd in expected_commands:
            assert cmd in node.commands
