"""
Unit tests for the Controller node.
"""

import pytest
from unittest.mock import MagicMock, patch

# Since Controller imports all nodes, we need to patch them all
from nodes.Controller import Controller


# Mock all node classes that the Controller might instantiate
@pytest.fixture
def mock_polyglot():
    """Fixture for a heavily mocked Polyglot interface object."""
    poly = MagicMock(name="Polyglot")
    poly.START = "start"
    poly.POLL = "poll"
    poly.LOGLEVEL = "log_level"
    poly.CUSTOMPARAMS = "custom_params"
    poly.CUSTOMDATA = "custom_data"
    poly.STOP = "stop"
    poly.DISCOVER = "discover"
    poly.CUSTOMTYPEDDATA = "custom_typed_data"
    poly.CUSTOMTYPEDPARAMS = "custom_typed_params"
    poly.ADDNODEDONE = "add_node_done"
    poly.getNodes.return_value = {}
    poly.getNodesFromDb.return_value = []
    return poly


@pytest.fixture
def controller_node(mock_polyglot):
    """Fixture to create a Controller instance for testing."""
    with (
        patch("nodes.Controller.Custom", autospec=True) as mock_custom,
        patch("nodes.Controller.LOG_HANDLER", autospec=True),
        patch("nodes.Controller.DEVICE_TYPE_TO_NODE_CLASS") as mock_device_map,
    ):
        # This is important: make the mocks themselves mock constructors
        for key in mock_device_map:
            mock_device_map[key] = MagicMock()

        # Configure the mock map to handle the 'in' operator for the simple device test
        def mock_contains(key):
            return key in [
                "switch",
                "ononly",
                "temperature",
                "temperaturec",
                "temperaturecr",
                "generic",
                "dimmer",
                "garage",
                "ondelay",
                "offdelay",
                "toggle",
            ]

        mock_device_map.__contains__.side_effect = mock_contains

        # The controller expects Custom to be a class it can instantiate
        mock_custom.return_value = MagicMock()

        # Instantiate the controller
        controller = Controller(
            mock_polyglot, "controller", "controller", "Test Controller"
        )

        # Mock the wait_for_node_done to avoid actual waiting
        controller.wait_for_node_done = MagicMock()

        # Mock reportCmd on the controller instance itself
        controller.reportCmd = MagicMock()

        yield controller


class TestController:
    """Test suite for the Controller node."""

    def test_init(self, controller_node, mock_polyglot):
        """Test that the controller subscribes to all necessary events on init."""
        mock_polyglot.subscribe.assert_any_call(
            "start", controller_node.start, "controller"
        )
        mock_polyglot.subscribe.assert_any_call("poll", controller_node.poll)
        mock_polyglot.subscribe.assert_any_call(
            "discover", controller_node.discover_cmd
        )
        mock_polyglot.subscribe.assert_any_call("stop", controller_node.stop)

    def test_check_params_simple_device(self, controller_node):
        """Test parsing a simple device from custom parameters."""
        controller_node.Parameters.items.return_value = [("1", "switch")]
        assert controller_node.checkParams() is True
        assert len(controller_node.devlist) == 1
        assert controller_node.devlist[0]["type"] == "switch"
        assert controller_node.devlist[0]["id"] == "1"

    def test_check_params_json_device(self, controller_node):
        """Test parsing a complex JSON device from custom parameters."""
        json_string = '{"type": "garage", "name": "My Garage", "ratgdo": "1.2.3.4"}'
        controller_node.Parameters.items.return_value = [("2", json_string)]
        assert controller_node.checkParams() is True
        assert len(controller_node.devlist) == 1
        assert controller_node.devlist[0]["type"] == "garage"
        assert controller_node.devlist[0]["id"] == "2"  # ID from key should override

    def test_check_params_yaml_file(self, controller_node):
        """Test parsing devices from an external YAML file."""
        controller_node.Parameters.items.return_value = [("devfile", "my_devices.yaml")]

        # Mock the helper function that handles file reading
        with patch.object(
            controller_node, "_handle_file_devices", return_value=[{"id": "10"}]
        ) as mock_handle_file:
            assert controller_node.checkParams() is True
            # Assert that the file-handling function was called with the correct filename
            mock_handle_file.assert_called_with("my_devices.yaml")
            # Assert that the devlist was populated from the mock's return value
            assert len(controller_node.devlist) == 1
            assert controller_node.devlist[0]["id"] == "10"

    def test_discover_adds_new_node(self, controller_node, mock_polyglot):
        """Test that discovery adds a node that is in config but not present."""
        # Setup: A switch in config, but no nodes exist yet
        controller_node.devlist = [
            {"id": "switch1", "type": "switch", "name": "My Switch"}
        ]
        mock_polyglot.getNodes.return_value = {
            "controller": controller_node
        }  # Only controller exists

        controller_node._discover()

        # Assert: addNode should be called once for the new switch, plus once for the controller itself
        assert mock_polyglot.addNode.call_count == 2

    def test_discover_deletes_old_node(self, controller_node, mock_polyglot):
        """Test that discovery removes a node that exists but is no longer in config."""
        # Setup: No devices in config, but a switch node exists
        controller_node.devlist = []
        existing_nodes = {"controller": controller_node, "oldswitch": MagicMock()}
        mock_polyglot.getNodes.return_value = existing_nodes

        controller_node._discover()

        # Assert: delNode should be called for the old switch
        mock_polyglot.delNode.assert_called_with("oldswitch")

    def test_heartbeat(self, controller_node):
        """Test the heartbeat function alternates DON/DOF commands."""
        # First beat
        controller_node.hb = 0
        controller_node.heartbeat()
        controller_node.reportCmd.assert_called_with("DON", 2)
        assert controller_node.hb == 1

        # Second beat
        controller_node.heartbeat()
        controller_node.reportCmd.assert_called_with("DOF", 2)
        assert controller_node.hb == 0
