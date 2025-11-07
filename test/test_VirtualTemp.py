"""
Unit tests for the VirtualTemp node.
"""

import pytest
from unittest.mock import MagicMock, patch

from nodes.VirtualTemp import VirtualTemp, FIELDS


# This fixture automatically mocks the udi_interface dependencies for all tests.
@pytest.fixture(autouse=True)
def mock_udi_interface():
    """Automatically mock udi_interface.Node, LOGGER, and ISY."""
    with patch("nodes.VirtualTemp.Node", autospec=True), patch(
        "nodes.VirtualTemp.LOGGER", autospec=True
    ), patch("nodes.VirtualTemp.ISY", autospec=True):
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
def temp_node(mock_polyglot):
    """
    Fixture to create a VirtualTemp instance for testing.
    It patches utility functions and time.time.
    """
    # Patch all external dependencies for this node
    with patch("nodes.VirtualTemp.load_persistent_data"), patch(
        "nodes.VirtualTemp.get_config_data"
    ), patch("nodes.VirtualTemp.store_values") as mock_store, patch(
        "nodes.VirtualTemp.push_to_isy_var"
    ) as mock_push, patch("nodes.VirtualTemp.pull_from_isy_var") as mock_pull, patch(
        "nodes.VirtualTemp.time"
    ) as mock_time:
        mock_time.time.return_value = 1000.0  # A fixed point in time

        node = VirtualTemp(mock_polyglot, "controller_addr", "temp_addr", "Test Temp")

        # Explicitly mock methods from the parent Node class
        node.setDriver = MagicMock()
        node.reportCmd = MagicMock()
        node.reportDrivers = MagicMock()

        # Simulate the effect of load_persistent_data for a clean slate
        node.data = {field: spec.default for field, spec in FIELDS.items()}

        yield (
            node,
            {
                "store": mock_store,
                "push": mock_push,
                "pull": mock_pull,
                "time": mock_time,
            },
        )


class TestVirtualTemp:
    """Test suite for the VirtualTemp node."""

    def test_init(self, temp_node):
        """Test the initialization of the VirtualTemp node."""
        node, _ = temp_node
        assert node.name == "Test Temp"
        assert node.id == "virtualtemp"

    @pytest.mark.parametrize(
        "raw, r_to_prec, c_to_f, f_to_c, expected",
        [
            (10, False, True, False, 50.0),  # C to F
            (50, False, False, True, 10.0),  # F to C
            (123, True, False, False, 12.3),  # Raw to Precision
            (123, True, True, False, 54.1),  # RtoP -> CtoF
        ],
    )
    def test_transform_value(self, temp_node, raw, r_to_prec, c_to_f, f_to_c, expected):
        """Test the _transform_value helper method."""
        node, _ = temp_node
        result = node._transform_value(raw, r_to_prec, c_to_f, f_to_c)
        assert result == expected

    def test_set_temp_cmd(self, temp_node):
        """Test the set_temp_cmd with a direct value."""
        node, mocks = temp_node
        node.data["tempVal"] = 70.0
        mocks["time"].time.return_value = 1100.0
        command = {"value": "75.0"}

        node.set_temp_cmd(command)

        assert node.data["tempVal"] == 75.0
        assert node.data["prevVal"] == 70.0
        assert node.data["lastUpdateTime"] == 1100.0
        node.setDriver.assert_any_call("ST", 75.0)
        node.setDriver.assert_any_call("GV1", 70.0)

    def test_check_high_low(self, temp_node):
        """Test the _check_high_low logic for stats."""
        node, _ = temp_node
        # First value sets high and low
        node._check_high_low(70)
        assert node.data["highTemp"] == 70
        assert node.data["lowTemp"] == 70
        # New high
        node._check_high_low(80)
        assert node.data["highTemp"] == 80
        assert node.data["lowTemp"] == 70
        # New low
        node._check_high_low(60)
        assert node.data["highTemp"] == 80
        assert node.data["lowTemp"] == 60
        # Average
        assert node.data["currentAvgTemp"] == 70.0

    def test_reset_stats_cmd(self, temp_node):
        """Test that reset_stats_cmd clears all statistics."""
        node, _ = temp_node
        node.data["highTemp"] = 80
        node.reset_stats_cmd()
        assert node.data["highTemp"] is None
        assert node.data["lowTemp"] is None
        assert node.data["currentAvgTemp"] is None

    def test_update_push_action(self, temp_node):
        """Test the poll/update cycle with a push action."""
        node, mocks = temp_node
        node.data["action1"] = 1  # Push
        node.data["action1type"] = 2
        node.data["action1id"] = 123
        node.data["tempVal"] = 75.5

        node._update()

        mocks["push"].assert_called_with(node, 2, 123, 75.5)

    def test_update_pull_action(self, temp_node):
        """Test the poll/update cycle with a pull action."""
        node, mocks = temp_node
        mocks["pull"].return_value = 80.0
        node.data["action2"] = 2  # Pull
        node.data["action2type"] = 1
        node.data["action2id"] = 456

        with patch.object(node, "set_temp_cmd") as mock_set_temp:
            node._update()
            mocks["pull"].assert_called_with(node, 1, 456)
            mock_set_temp.assert_called_with({"cmd": "data", "value": 80.0})
