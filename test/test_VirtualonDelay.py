"""
Unit tests for the VirtualonDelay node.
"""

import pytest
from unittest.mock import MagicMock, patch

from nodes.VirtualonDelay import VirtualonDelay, ON, OFF, TIMER, RESET, FIELDS


# This fixture automatically mocks the udi_interface dependencies for all tests.
@pytest.fixture(autouse=True)
def mock_udi_interface():
    """Automatically mock udi_interface.Node and LOGGER."""
    with patch("nodes.VirtualonDelay.Node", autospec=True), patch(
        "nodes.VirtualonDelay.LOGGER", autospec=True
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
def ondelay_node(mock_polyglot):
    """
    Fixture to create a VirtualonDelay instance for testing.
    It patches utility functions and, crucially, threading.Timer.
    """
    with patch("nodes.VirtualonDelay.load_persistent_data"), patch(
        "nodes.VirtualonDelay.get_config_data"
    ), patch("nodes.VirtualonDelay.store_values") as mock_store, patch(
        "nodes.VirtualonDelay.Timer"
    ) as mock_timer_class:
        # The mock timer instance needs to be created for the __init__ call
        mock_timer_instance = MagicMock()
        mock_timer_class.return_value = mock_timer_instance

        node = VirtualonDelay(
            mock_polyglot, "controller_addr", "ondelay_addr", "Test OnDelay"
        )

        # Explicitly mock methods from the parent Node class
        node.setDriver = MagicMock()
        node.reportCmd = MagicMock()
        node.reportDrivers = MagicMock()

        # Simulate the effect of load_persistent_data for a clean slate
        node.data = {field: spec.default for field, spec in FIELDS.items()}

        yield node, {"store": mock_store, "timer_class": mock_timer_class}


class TestVirtualonDelay:
    """Test suite for the VirtualonDelay node."""

    def test_init(self, ondelay_node, mock_polyglot):
        """Test the initialization of the VirtualonDelay node."""
        node, _ = ondelay_node
        assert node.name == "Test OnDelay"
        assert node.id == "virtualondelay"
        assert node.data["switch"] == OFF

    def test_don_cmd_with_delay(self, ondelay_node):
        """Test DON command when delay > 0, should start a timer."""
        node, mocks = ondelay_node
        node.data["delay"] = 10

        node.DON_cmd()

        assert node.data["switch"] == TIMER
        node.setDriver.assert_called_with("ST", TIMER)
        mocks["timer_class"].assert_called_with(10, node._on_delay)
        timer_instance = mocks["timer_class"].return_value
        timer_instance.start.assert_called_once()

    def test_don_cmd_with_zero_delay(self, ondelay_node):
        """Test DON command when delay is 0, should turn on immediately."""
        node, _ = ondelay_node
        node.data["delay"] = 0

        node.DON_cmd()

        assert node.data["switch"] == ON
        node.setDriver.assert_called_with("ST", ON)
        node.reportCmd.assert_called_with("DON")

    def test_timer_callback_on_delay(self, ondelay_node):
        """Test the _on_delay callback that the timer triggers."""
        node, _ = ondelay_node
        node._on_delay()
        assert node.data["switch"] == ON
        node.setDriver.assert_called_with("ST", ON)
        node.reportCmd.assert_called_with("DON")

    def test_dof_cmd_when_on(self, ondelay_node):
        """Test DOF command when the switch is already ON."""
        node, _ = ondelay_node
        node.data["switch"] = ON
        # Ensure timer is not alive
        node.timer.is_alive.return_value = False

        node.DOF_cmd()

        assert node.data["switch"] == OFF
        node.setDriver.assert_called_with("ST", OFF)
        node.reportCmd.assert_called_with("DOF")

    def test_dof_cmd_when_timer_active(self, ondelay_node):
        """Test DOF command does nothing when a timer is active."""
        node, _ = ondelay_node
        node.data["switch"] = TIMER
        node.timer.is_alive.return_value = True

        node.DOF_cmd()

        assert node.data["switch"] == TIMER  # Should not change
        node.reportCmd.assert_not_called()

    def test_dfof_cmd_when_timer_active(self, ondelay_node):
        """Test DFOF command cancels an active timer and turns off."""
        node, _ = ondelay_node
        node.data["switch"] = TIMER
        node.timer.is_alive.return_value = True

        node.DFOF_cmd()

        node.timer.cancel.assert_called_once()
        assert node.data["switch"] == OFF
        node.setDriver.assert_called_with("ST", OFF)
        node.reportCmd.assert_called_with("DFOF")

    def test_set_delay_cmd(self, ondelay_node):
        """Test the SETDELAY command."""
        node, _ = ondelay_node
        command = {"value": "30"}
        node.set_delay_cmd(command)
        assert node.data["delay"] == 30
        node.setDriver.assert_called_with("DUR", 30)

    def test_stop_cancels_timer(self, ondelay_node):
        """Test that the stop method cancels an active timer."""
        node, _ = ondelay_node
        node.timer.is_alive.return_value = True
        node.stop()
        node.timer.cancel.assert_called_once()

    def test_stop_resets_from_timer_state(self, ondelay_node):
        """Test stop method sets state to ON if it was in TIMER."""
        node, _ = ondelay_node
        node.data["switch"] = TIMER
        node.stop()
        assert node.data["switch"] == RESET  # RESET is an alias for ON
