"""
Unit tests for the VirtualSwitch node.
"""

import pytest
from unittest.mock import MagicMock, patch

# To allow imports from the 'nodes' directory, you might need a conftest.py
# or to run pytest from the project root directory.
from nodes.VirtualSwitch import VirtualSwitch, ON, OFF, FIELDS


# This fixture automatically mocks the udi_interface dependencies for all tests
# in this file. This prevents the tests from needing the actual library.
@pytest.fixture(autouse=True)
def mock_udi_interface():
    """Automatically mock udi_interface.Node and LOGGER."""
    with patch("nodes.VirtualSwitch.Node", autospec=True), patch(
        "nodes.VirtualSwitch.LOGGER", autospec=True
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
def switch_node(mock_polyglot):
    """
    Fixture to create a VirtualSwitch instance for testing.
    It patches the utility functions to isolate the node's own logic.
    """
    with patch("nodes.VirtualSwitch.load_persistent_data") as mock_load, patch(
        "nodes.VirtualSwitch.get_config_data"
    ) as mock_get_config, patch("nodes.VirtualSwitch.store_values") as mock_store:
        node = VirtualSwitch(
            mock_polyglot, "controller_addr", "switch_addr", "Test Switch"
        )

        # Explicitly mock methods from the parent Node class that are used directly
        node.setDriver = MagicMock()
        node.reportCmd = MagicMock()
        node.reportDrivers = MagicMock()

        # Simulate the effect of load_persistent_data for a clean slate
        node.data = {field: spec.default for field, spec in FIELDS.items()}

        # Yield the node and the mocks so tests can use them
        yield (
            node,
            {
                "load": mock_load,
                "get_config": mock_get_config,
                "store": mock_store,
            },
        )


class TestVirtualSwitch:
    """Test suite for the VirtualSwitch node."""

    def test_init(self, switch_node, mock_polyglot):
        """
        Test the initialization of the VirtualSwitch node.
        """
        node, _ = switch_node
        assert node.name == "Test Switch"
        assert node.address == "switch_addr"
        assert node.primary == "controller_addr"

        # Verify it subscribes to the START event correctly
        mock_polyglot.subscribe.assert_called_with(
            mock_polyglot.START, node.start, "switch_addr"
        )

        # Check that the initial state is OFF
        assert node.data["switch"] == OFF

    def test_start(self, switch_node):
        """
        Test the start method logic.
        """
        node, mocks = switch_node
        node.start()

        # It should wait for the controller to be ready
        node.controller.ready_event.wait.assert_called_once()

        # It should call the data loading functions
        mocks["load"].assert_called_once_with(node, FIELDS)
        mocks["get_config"].assert_called_once_with(node, FIELDS)

    def test_don_cmd(self, switch_node):
        """
        Test the DON (On) command.
        """
        node, mocks = switch_node
        node.data["switch"] = OFF  # Arrange: ensure switch is off

        node.DON_cmd()  # Act

        # Assert
        assert node.data["switch"] == ON
        node.setDriver.assert_called_with("ST", ON)
        node.reportCmd.assert_called_with("DON")
        mocks["store"].assert_called_with(node)

    def test_dof_cmd(self, switch_node):
        """
        Test the DOF (Off) command.
        """
        node, mocks = switch_node
        node.data["switch"] = ON  # Arrange: ensure switch is on

        node.DOF_cmd()  # Act

        # Assert
        assert node.data["switch"] == OFF
        node.setDriver.assert_called_with("ST", OFF)
        node.reportCmd.assert_called_with("DOF")
        mocks["store"].assert_called_with(node)

    def test_toggle_cmd_from_off_to_on(self, switch_node):
        """
        Test the TOGGLE command when the switch is initially off.
        """
        node, _ = switch_node
        node.data["switch"] = OFF  # Arrange
        node.DON_cmd = MagicMock(name="DON_cmd")
        node.DOF_cmd = MagicMock(name="DOF_cmd")

        node.toggle_cmd()  # Act

        # Assert
        node.DON_cmd.assert_called_once()
        node.DOF_cmd.assert_not_called()

    def test_toggle_cmd_from_on_to_off(self, switch_node):
        """
        Test the TOGGLE command when the switch is initially on.
        """
        node, _ = switch_node
        node.data["switch"] = ON  # Arrange
        node.DON_cmd = MagicMock(name="DON_cmd")
        node.DOF_cmd = MagicMock(name="DOF_cmd")

        node.toggle_cmd()  # Act

        # Assert
        node.DOF_cmd.assert_called_once()
        node.DON_cmd.assert_not_called()

    def test_query(self, switch_node):
        """
        Test the query command.
        """
        node, _ = switch_node
        node.query()
        node.reportDrivers.assert_called_once()

    def test_node_definition_attributes(self, switch_node):
        """
        Test that the node's defining attributes (id, drivers, commands) are correct.
        """
        node, _ = switch_node
        assert node.id == "virtualswitch"
        assert node.hint == "0x01020700"

        # Check that the 'ST' driver is defined
        assert any(d["driver"] == "ST" for d in node.drivers)

        # Check that all expected commands are present
        expected_commands = ["DON", "DOF", "TOGGLE", "QUERY"]
        for cmd in expected_commands:
            assert cmd in node.commands
