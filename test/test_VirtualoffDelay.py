"""
Unit tests for the VirtualoffDelay node.
"""

import pytest
from unittest.mock import MagicMock, patch

from nodes.VirtualoffDelay import VirtualoffDelay, OFF, TIMER, RESET, FIELDS


# This fixture automatically mocks the udi_interface dependencies for all tests.
@pytest.fixture(autouse=True)
def mock_udi_interface():
    """Automatically mock udi_interface.Node and LOGGER."""
    with patch("nodes.VirtualoffDelay.Node", autospec=True), patch(
        "nodes.VirtualoffDelay.LOGGER", autospec=True
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
def offdelay_node(mock_polyglot):
    """
    Fixture to create a VirtualoffDelay instance for testing.
    It patches utility functions and threading.Timer.
    """
    with patch("nodes.VirtualoffDelay.load_persistent_data"), patch(
        "nodes.VirtualoffDelay.get_config_data"
    ), patch("nodes.VirtualoffDelay.store_values") as mock_store, patch(
        "nodes.VirtualoffDelay.Timer"
    ) as mock_timer_class:
        mock_timer_instance = MagicMock()
        mock_timer_class.return_value = mock_timer_instance

        node = VirtualoffDelay(
            mock_polyglot, "controller_addr", "offdelay_addr", "Test OffDelay"
        )

        # Explicitly mock methods from the parent Node class
        node.setDriver = MagicMock()
        node.reportCmd = MagicMock()
        node.reportDrivers = MagicMock()

        # Simulate the effect of load_persistent_data for a clean slate
        node.data = {field: spec.default for field, spec in FIELDS.items()}

        yield node, {"store": mock_store, "timer_class": mock_timer_class}


class TestVirtualoffDelay:
    """Test suite for the VirtualoffDelay node."""

    def test_init(self, offdelay_node):
        """Test the initialization of the VirtualoffDelay node."""
        node, _ = offdelay_node
        assert node.name == "Test OffDelay"
        assert node.id == "virtualoffdelay"
        assert node.data["switch"] == OFF

    def test_don_cmd_with_delay(self, offdelay_node):
        """Test DON command when delay > 0, should start a timer."""
        node, mocks = offdelay_node
        node.data["delay"] = 10

        node.DON_cmd()

        assert node.data["switch"] == TIMER
        node.setDriver.assert_called_with("ST", TIMER)
        node.reportCmd.assert_called_with("TIMER")
        mocks["timer_class"].assert_called_with(10, node._off_delay)
        timer_instance = mocks["timer_class"].return_value
        timer_instance.start.assert_called_once()

    def test_don_cmd_with_zero_delay(self, offdelay_node):
        """Test DON command when delay is 0, should turn off immediately."""
        node, _ = offdelay_node
        node.data["delay"] = 0

        node.DON_cmd()

        # It should report DON, then immediately call _off_delay which reports DOF
        node.reportCmd.assert_any_call("DON")
        node.reportCmd.assert_any_call("DOF")
        assert node.data["switch"] == OFF
        node.setDriver.assert_called_with("ST", OFF)

    def test_timer_callback_off_delay(self, offdelay_node):
        """Test the _off_delay callback that the timer triggers."""
        node, _ = offdelay_node
        node._off_delay()
        assert node.data["switch"] == OFF
        node.setDriver.assert_called_with("ST", OFF)
        node.reportCmd.assert_called_with("DOF")

    def test_dof_cmd_when_timer_active(self, offdelay_node):
        """Test DOF command cancels an active timer and turns off."""
        node, _ = offdelay_node
        node.data["switch"] = TIMER
        node.timer.is_alive.return_value = True

        node.DOF_cmd()

        node.timer.cancel.assert_called_once()
        assert node.data["switch"] == OFF
        node.setDriver.assert_called_with("ST", OFF)
        node.reportCmd.assert_called_with("DOF")

    def test_set_delay_cmd(self, offdelay_node):
        """Test the SETDELAY command."""
        node, _ = offdelay_node
        command = {"value": "30"}
        node.set_delay_cmd(command)
        assert node.data["delay"] == 30
        node.setDriver.assert_called_with("DUR", 30)

    def test_stop_cancels_timer(self, offdelay_node):
        """Test that the stop method cancels an active timer."""
        node, _ = offdelay_node
        node.timer.is_alive.return_value = True
        node.stop()
        node.timer.cancel.assert_called_once()

    def test_stop_resets_from_timer_state(self, offdelay_node):
        """Test stop method sets state to OFF if it was in TIMER."""
        node, _ = offdelay_node
        node.data["switch"] = TIMER
        node.stop()
        assert node.data["switch"] == RESET  # RESET is an alias for OFF

    def test_start(self, offdelay_node):
        """Test the start method loads data."""
        node, _ = offdelay_node
        with patch("nodes.VirtualoffDelay.load_persistent_data") as mock_load, patch(
            "nodes.VirtualoffDelay.get_config_data"
        ) as mock_get_config:
            node.start()
            mock_load.assert_called_once()
            mock_get_config.assert_called_once()
            node.controller.ready_event.wait.assert_called_once()

    def test_initialize_timer_exception(self, offdelay_node):
        """Test _initialize_timer handles exceptions."""
        node, _ = offdelay_node
        with patch("nodes.VirtualoffDelay.Timer", side_effect=Exception("Timer error")):
            node._initialize_timer()
            assert node.timer is None

    def test_don_cmd_with_exception(self, offdelay_node):
        """Test DON_cmd handles exceptions gracefully."""
        node, mocks = offdelay_node
        node.data["delay"] = 5
        # Simulate exception during timer creation
        mocks["timer_class"].side_effect = Exception("Timer creation failed")

        node.DON_cmd()

        # Should not crash and should return early, so store_values should NOT be called
        mocks["store"].assert_not_called()

    def test_query(self, offdelay_node):
        """Test the query command reports drivers."""
        node, _ = offdelay_node
        node.query()
        node.reportDrivers.assert_called_once()

    def test_stop_no_timer(self, offdelay_node):
        """Test stop method when timer is None."""
        node, _ = offdelay_node
        node.timer = None
        node.data["switch"] = OFF

        node.stop()

        # Should not crash

    def test_don_cmd_cancels_existing_timer(self, offdelay_node):
        """Test DON_cmd cancels existing timer before starting new one."""
        node, _ = offdelay_node
        node.timer.is_alive.return_value = True
        node.data["delay"] = 3

        node.DON_cmd()

        node.timer.cancel.assert_called_once()
        assert node.data["switch"] == TIMER

    def test_dof_cmd_no_active_timer(self, offdelay_node):
        """Test DOF_cmd when no timer is active."""
        node, _ = offdelay_node
        node.timer.is_alive.return_value = False

        node.DOF_cmd()

        assert node.data["switch"] == OFF
        node.setDriver.assert_called_with("ST", OFF)
        node.reportCmd.assert_called_with("DOF")
