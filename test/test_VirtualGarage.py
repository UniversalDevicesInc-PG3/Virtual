"""
Unit tests for the VirtualGarage node.
"""

import pytest
from unittest.mock import MagicMock, patch

from nodes.VirtualGarage import (
    VirtualGarage,
    RATGDO,
    LIGHT,
    TURN_ON,
    DOOR,
    OPEN,
)


# This fixture automatically mocks all external dependencies for all tests.
@pytest.fixture(autouse=True)
def mock_externals():
    """Mock udi_interface, requests, aiohttp, asyncio, and threading."""
    with patch("nodes.VirtualGarage.Node", autospec=True), patch(
        "nodes.VirtualGarage.LOGGER", autospec=True
    ), patch("nodes.VirtualGarage.ISY", autospec=True), patch(
        "nodes.VirtualGarage.requests", autospec=True
    ), patch("nodes.VirtualGarage.aiohttp", autospec=True), patch(
        "nodes.VirtualGarage.asyncio", autospec=True
    ), patch("nodes.VirtualGarage.Thread", autospec=True):
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
def garage_node(mock_polyglot):
    """
    Fixture to create a VirtualGarage instance for testing.
    It patches utility functions.
    """
    with patch("nodes.VirtualGarage.load_persistent_data"), patch(
        "nodes.VirtualGarage.get_config_data"
    ) as mock_get_config, patch("nodes.VirtualGarage.store_values"), patch(
        "nodes.VirtualGarage.push_to_isy_var"
    ) as mock_push, patch("nodes.VirtualGarage.pull_from_isy_var") as mock_pull:
        # Simulate get_config_data returning True to allow processing
        mock_get_config.return_value = True

        node = VirtualGarage(
            mock_polyglot, "controller_addr", "garage_addr", "Test Garage"
        )

        # Explicitly mock methods from the parent Node class
        node.setDriver = MagicMock()
        node.reportCmd = MagicMock()
        node.reportDrivers = MagicMock()

        # Simulate the node having a config dictionary
        node.dev = {}

        yield node, {"push": mock_push, "pull": mock_pull}


class TestVirtualGarage:
    """Test suite for the VirtualGarage node."""

    def test_init(self, garage_node):
        """Test the initialization of the VirtualGarage node."""
        node, _ = garage_node
        assert node.name == "Test Garage"
        assert node.id == "virtualgarage"

    @pytest.mark.parametrize(
        "config_val, expected_ip, bonjour_on",
        [
            (False, False, False),  # Disabled
            ("false", False, False),  # Disabled (string)
            (True, RATGDO, True),  # Enabled, use default
            ("192.168.1.100", "192.168.1.100", False),  # Enabled with IP
        ],
    )
    def test_process_ratgdo_config(
        self, garage_node, config_val, expected_ip, bonjour_on
    ):
        """Test the logic for processing the 'ratgdo' config value."""
        node, _ = garage_node
        node.dev["ratgdo"] = config_val
        # Mock ratgdo_check to always pass for this test
        with patch.object(node, "ratgdo_check", return_value=True):
            node._process_ratgdo_config()
            assert node.ratgdo == expected_ip
            assert node.bonjourOn == bonjour_on

    def test_lt_on_cmd(self, garage_node):
        """Test the light on command."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True
        with patch.object(node, "ratgdo_post") as mock_post:
            node.lt_on_cmd()
            assert node.data["light"] == 1
            mock_post.assert_called_with(f"1.2.3.4{LIGHT}{TURN_ON}")

    def test_dr_open_cmd(self, garage_node):
        """Test the door open command."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True
        with patch.object(node, "door_command") as mock_door_cmd:
            node.dr_open_cmd()
            assert node.data["dcommand"] == 1
            mock_door_cmd.assert_called_with(f"1.2.3.4{DOOR}{OPEN}")

    def test_set_ratgdo_light_state(self, garage_node):
        """Test the internal method for setting light state from Ratgdo data."""
        node, _ = garage_node
        payload = {"id": "light-light", "state": "ON"}
        node._set_ratgdo_light(payload)
        assert node.data["light"] == 1

        payload = {"id": "light-light", "state": "OFF"}
        node._set_ratgdo_light(payload)
        assert node.data["light"] == 0

    def test_set_ratgdo_door_state(self, garage_node):
        """Test the internal method for setting door state from Ratgdo data."""
        node, _ = garage_node
        payload = {
            "id": "cover-door",
            "state": "OPEN",
            "value": 1.0,
            "current_operation": "IDLE",
        }
        node._set_ratgdo_door(payload)
        assert node.data["door"] == 100
        assert node.data["position"] == 100

        payload = {
            "id": "cover-door",
            "state": "CLOSED",
            "value": 0.0,
            "current_operation": "IDLE",
        }
        node._set_ratgdo_door(payload)
        assert node.data["door"] == 0
        assert node.data["position"] == 0

    def test_update_vars_from_isy(self, garage_node):
        """Test pulling values from ISY variables when not in Ratgdo mode."""
        node, mocks = garage_node
        node.ratgdo = False  # Ensure not in Ratgdo mode
        # Configure to pull from ISY variable
        node.data["doorT"] = 2
        node.data["doorId"] = 10
        mocks["pull"].return_value = 100  # Simulate ISY var having value 100 (Open)

        node._update_vars()

        mocks["pull"].assert_called_with(node, 2, 10)
        assert node.data["door"] == 100
