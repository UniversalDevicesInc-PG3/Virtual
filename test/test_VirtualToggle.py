"""
Unit tests for the VirtualToggle node.
"""

import pytest
from unittest.mock import MagicMock, patch

from nodes.VirtualToggle import VirtualToggle, ON, OFF, ONTIMER, OFFTIMER, FIELDS


# This fixture automatically mocks the udi_interface dependencies for all tests.
@pytest.fixture(autouse=True)
def mock_udi_interface():
    """Automatically mock udi_interface.Node and LOGGER."""
    with patch("nodes.VirtualToggle.Node", autospec=True), patch(
        "nodes.VirtualToggle.LOGGER", autospec=True
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
def toggle_node(mock_polyglot):
    """
    Fixture to create a VirtualToggle instance for testing.
    It patches utility functions and threading.Timer.
    """
    with patch("nodes.VirtualToggle.load_persistent_data"), patch(
        "nodes.VirtualToggle.get_config_data"
    ), patch("nodes.VirtualToggle.store_values") as mock_store, patch(
        "nodes.VirtualToggle.Timer"
    ) as mock_timer_class:
        mock_timer_instance = MagicMock()
        mock_timer_class.return_value = mock_timer_instance

        node = VirtualToggle(
            mock_polyglot, "controller_addr", "toggle_addr", "Test Toggle"
        )

        # Explicitly mock methods from the parent Node class
        node.setDriver = MagicMock()
        node.reportCmd = MagicMock()
        node.reportDrivers = MagicMock()

        # Simulate the effect of load_persistent_data for a clean slate
        node.data = {field: spec.default for field, spec in FIELDS.items()}

        yield node, {"store": mock_store, "timer_class": mock_timer_class}


class TestVirtualToggle:
    """Test suite for the VirtualToggle node."""

    def test_init(self, toggle_node):
        """Test the initialization of the VirtualToggle node."""
        node, _ = toggle_node
        assert node.name == "Test Toggle"
        assert node.id == "virtualtoggle"
        assert node.data["switch"] == OFF

    def test_don_cmd_starts_oscillation(self, toggle_node):
        """Test DON command starts the on-timer cycle."""
        node, mocks = toggle_node
        node.data["ondelay"] = 5

        node.DON_cmd()

        assert node.data["switch"] == ONTIMER
        node.setDriver.assert_called_with("ST", ONTIMER)
        node.reportCmd.assert_called_with("DON")
        mocks["timer_class"].assert_called_with(5, node._on_delay)
        timer_instance = mocks["timer_class"].return_value
        timer_instance.start.assert_called_once()

    def test_on_delay_callback(self, toggle_node):
        """Test the _on_delay callback, which should start the off-timer cycle."""
        node, mocks = toggle_node
        node.data["offdelay"] = 10

        node._on_delay()

        assert node.data["switch"] == OFFTIMER
        node.setDriver.assert_called_with("ST", OFFTIMER)
        node.reportCmd.assert_called_with("DOF")
        mocks["timer_class"].assert_called_with(10, node._off_delay)
        # Check that start was called for the new timer instance
        latest_timer_instance = mocks["timer_class"].call_args.return_value
        latest_timer_instance.start.assert_called_once()

    def test_off_delay_callback(self, toggle_node):
        """Test the _off_delay callback, which should loop back to the on-timer cycle."""
        node, mocks = toggle_node
        node.data["ondelay"] = 5

        node._off_delay()

        assert node.data["switch"] == ONTIMER
        node.setDriver.assert_called_with("ST", ONTIMER)
        node.reportCmd.assert_called_with("DON")
        mocks["timer_class"].assert_called_with(5, node._on_delay)
        # Check that start was called for the new timer instance
        latest_timer_instance = mocks["timer_class"].call_args.return_value
        latest_timer_instance.start.assert_called_once()

    def test_dfon_cmd_stops_oscillation(self, toggle_node):
        """Test DFON command cancels an active timer and sets state to ON."""
        node, _ = toggle_node
        node.timer.is_alive.return_value = True

        node.DFON_cmd()

        node.timer.cancel.assert_called_once()
        assert node.data["switch"] == ON
        node.setDriver.assert_called_with("ST", ON)
        node.reportCmd.assert_called_with("DFON")

    def test_dfof_cmd_stops_oscillation(self, toggle_node):
        """Test DFOF command cancels an active timer and sets state to OFF."""
        node, _ = toggle_node
        node.timer.is_alive.return_value = True

        node.DFOF_cmd()

        node.timer.cancel.assert_called_once()
        assert node.data["switch"] == OFF
        node.setDriver.assert_called_with("ST", OFF)
        node.reportCmd.assert_called_with("DFOF")

    @pytest.mark.parametrize("input_val, expected_val", [(5, 5), (0, 1), (-1, 1)])
    def test_set_on_dur_cmd(self, toggle_node, input_val, expected_val):
        """Test the SETONDUR command, ensuring value is at least 1."""
        node, _ = toggle_node
        command = {"value": str(input_val)}
        node.set_on_dur_cmd(command)
        assert node.data["ondelay"] == expected_val
        node.setDriver.assert_called_with("DUR", expected_val)
