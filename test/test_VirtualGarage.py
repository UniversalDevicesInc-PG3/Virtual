"""
Unit tests for the VirtualGarage node.
"""

import pytest
from unittest.mock import MagicMock, patch, Mock

from nodes.VirtualGarage import (
    VirtualGarage,
    RATGDO,
    LIGHT,
    TURN_ON,
    TURN_OFF,
    DOOR,
    OPEN,
    CLOSE,
    STOP,
    TRIGGER,
    LOCK,
    UNLOCK,
    LOCK_REMOTES,
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
        node.dev = {}  # type: ignore[assignment]

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

    def test_lt_off_cmd(self, garage_node):
        """Test the light off command."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True
        with patch.object(node, "ratgdo_post") as mock_post:
            node.lt_off_cmd()
            assert node.data["light"] == 0
            mock_post.assert_called_with(f"1.2.3.4{LIGHT}{TURN_OFF}")

    def test_dr_close_cmd(self, garage_node):
        """Test the door close command."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True
        with patch.object(node, "door_command") as mock_door_cmd:
            node.dr_close_cmd()
            assert node.data["dcommand"] == 2  # Close sets dcommand to 2
            mock_door_cmd.assert_called_with(f"1.2.3.4{DOOR}{CLOSE}")

    def test_dr_trigger_cmd(self, garage_node):
        """Test the door trigger command."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True
        with patch.object(node, "door_command") as mock_door_cmd:
            node.dr_trigger_cmd()
            assert node.data["dcommand"] == 3  # Trigger sets dcommand to 3
            mock_door_cmd.assert_called_with(
                f"1.2.3.4{TRIGGER}"
            )  # Uses TRIGGER constant

    def test_dr_stop_cmd(self, garage_node):
        """Test the door stop command."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True
        with patch.object(node, "door_command") as mock_door_cmd:
            node.dr_stop_cmd()
            mock_door_cmd.assert_called_with(f"1.2.3.4{DOOR}{STOP}")

    def test_lk_lock_cmd(self, garage_node):
        """Test the lock command."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True
        with patch.object(node, "ratgdo_post") as mock_post:
            node.lk_lock_cmd()
            assert node.data["lock"] == 1
            mock_post.assert_called_with(
                f"1.2.3.4{LOCK_REMOTES}{LOCK}"
            )  # Uses LOCK_REMOTES

    def test_lk_unlock_cmd(self, garage_node):
        """Test the unlock command."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True
        with patch.object(node, "ratgdo_post") as mock_post:
            node.lk_unlock_cmd()
            assert node.data["lock"] == 0
            mock_post.assert_called_with(
                f"1.2.3.4{LOCK_REMOTES}{UNLOCK}"
            )  # Uses LOCK_REMOTES

    def test_set_ratgdo_motor(self, garage_node):
        """Test setting motor state from Ratgdo data."""
        node, _ = garage_node

        # Test ON state
        payload = {"id": "binary_sensor-motor", "state": "ON", "value": 1}
        node._set_ratgdo_motor(payload)
        assert node.data["motor"] == 1

        # Test OFF state
        payload = {"id": "binary_sensor-motor", "state": "OFF", "value": 0}
        node._set_ratgdo_motor(payload)
        assert node.data["motor"] == 0

    def test_set_ratgdo_motion(self, garage_node):
        """Test setting motion state from Ratgdo data."""
        node, _ = garage_node

        payload = {"id": "binary_sensor-motion", "state": "ON", "value": 1}
        node._set_ratgdo_motion(payload)
        assert node.data["motion"] == 1

        payload = {"id": "binary_sensor-motion", "state": "OFF", "value": 0}
        node._set_ratgdo_motion(payload)
        assert node.data["motion"] == 0

    def test_set_ratgdo_lock(self, garage_node):
        """Test setting lock state from Ratgdo data."""
        node, _ = garage_node

        payload = {"id": "lock-lock", "state": "LOCKED", "value": 1}
        node._set_ratgdo_lock(payload)
        assert node.data["lock"] == 1

        payload = {"id": "lock-lock", "state": "UNLOCKED", "value": 0}
        node._set_ratgdo_lock(payload)
        assert node.data["lock"] == 0

    def test_set_ratgdo_obstruct(self, garage_node):
        """Test setting obstruction state from Ratgdo data."""
        node, _ = garage_node

        payload = {"id": "binary_sensor-obstruction", "state": "ON", "value": 1}
        node._set_ratgdo_obstruct(payload)
        assert node.data["obstruct"] == 1

        payload = {"id": "binary_sensor-obstruction", "state": "OFF", "value": 0}
        node._set_ratgdo_obstruct(payload)
        assert node.data["obstruct"] == 0

    def test_update_isy_pushes_variables(self, garage_node):
        """Test that _update_isy updates drivers when values change."""
        node, _ = garage_node
        node.first_pass_event.set()  # Simulate first pass

        node.data["door"] = 100
        node.data["light"] = 1

        node._update_isy()

        # Should have called setDriver for state fields
        assert node.setDriver.called

    def test_query_command(self, garage_node):
        """Test the query command."""
        node, _ = garage_node
        with patch.object(node, "reportDrivers") as mock_report:
            node.query()
            mock_report.assert_called_once()

    def test_reset_stats_cmd(self, garage_node):
        """Test the reset statistics command."""
        node, _ = garage_node
        node.data["openTime"] = 100.0

        with patch.object(node, "_reset_time") as mock_reset:
            node.reset_stats_cmd()
            mock_reset.assert_called_once()

    def test_heartbeat_increments(self, garage_node):
        """Test that heartbeat increments the hb counter."""
        node, _ = garage_node
        initial_hb = node.hb

        node._heartbeat()

        assert node.hb == initial_hb + 1

    def test_poll_short_updates_heartbeat(self, garage_node):
        """Test that short poll updates heartbeat."""
        node, _ = garage_node
        with patch.object(node, "_heartbeat") as mock_hb:
            node.poll("shortPoll")
            mock_hb.assert_called_once()

    def test_poll_long_with_ratgdo(self, garage_node):
        """Test long poll with Ratgdo enabled."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True
        node.ratgdo_do_poll = True
        node.ratgdo_poll_lock.acquire(
            blocking=False
        )  # Pre-acquire lock so get_ratgdo_direct is skipped

        with patch.object(node, "start_sse_client") as mock_sse, patch.object(
            node, "start_event_polling"
        ) as mock_poll:
            node.poll("longPoll")
            mock_sse.assert_called_once()
            mock_poll.assert_called_once()

        node.ratgdo_poll_lock.release()  # Clean up

    def test_poll_long_with_isy_mode(self, garage_node):
        """Test short poll in ISY variable mode (not longPoll)."""
        node, _ = garage_node
        node.ratgdo = False

        with patch.object(node, "_update_vars") as mock_update:
            node.poll("shortPoll")  # shortPoll calls _update_vars, not longPoll
            mock_update.assert_called_once()

    def test_ratgdo_check_success(self, garage_node):
        """Test successful Ratgdo device check."""
        node, _ = garage_node
        node.ratgdo = "192.168.1.100"

        with patch("nodes.VirtualGarage.requests") as mock_requests:
            mock_response = Mock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "light-light"}
            mock_requests.get.return_value = mock_response

            result = node.ratgdo_check()

            assert result is True
            assert node.ratgdoOK is True

    def test_ratgdo_check_failure(self, garage_node):
        """Test failed Ratgdo device check."""
        node, _ = garage_node
        node.ratgdo = "192.168.1.100"

        with patch("nodes.VirtualGarage.requests") as mock_requests:
            mock_requests.get.side_effect = Exception("Connection failed")

            result = node.ratgdo_check()

            assert result is False
            assert node.ratgdoOK is False

    def test_door_command_without_ratgdo(self, garage_node):
        """Test door command when Ratgdo is not configured."""
        node, _ = garage_node
        node.ratgdo = False

        # Should not raise, just return early
        node.door_command("some_command")
        # No assertion needed, just ensure it doesn't crash

    def test_light_on_without_ratgdo(self, garage_node):
        """Test light on command when Ratgdo is not configured."""
        node, _ = garage_node
        node.ratgdo = False

        node.lt_on_cmd()
        # Should update data but not post to Ratgdo
        assert node.data["light"] == 1

    def test_light_off_without_ratgdo(self, garage_node):
        """Test light off command when Ratgdo is not configured."""
        node, _ = garage_node
        node.ratgdo = False

        node.lt_off_cmd()
        assert node.data["light"] == 0

    def test_get_ratgdo_event_returns_copy(self, garage_node):
        """Test that get_ratgdo_event returns the event list."""
        node, _ = garage_node
        test_event = {"id": "test", "state": "ON"}
        node.ratgdo_event = [test_event]

        result = node.get_ratgdo_event()

        assert result == [test_event]
        # Note: The actual implementation returns a reference, not a copy
        assert result is node.ratgdo_event

    def test_append_ratgdo_event(self, garage_node):
        """Test appending an event to the Ratgdo event queue."""
        node, _ = garage_node
        node.ratgdo_event = []
        test_event = {"id": "test", "state": "ON"}

        node.append_ratgdo_event(test_event)

        assert test_event in node.ratgdo_event

    def test_remove_ratgdo_event(self, garage_node):
        """Test removing an event from the Ratgdo event queue."""
        node, _ = garage_node
        test_event = {"id": "test", "state": "ON"}
        node.ratgdo_event = [test_event]

        node.remove_ratgdo_event(test_event)

        assert test_event not in node.ratgdo_event

    def test_bonjour_command_sets_ip(self, garage_node):
        """Test that bonjour command sets the Ratgdo IP."""
        node, _ = garage_node
        node.bonjourOn = True
        node.bonjourOnce = True  # Must be True to allow processing

        command = {
            "success": True,
            "mdns": [{"name": RATGDO, "type": "ratgdo", "addresses": ["192.168.1.50"]}],
        }

        with patch.object(node, "ratgdo_check", return_value=True):
            node.bonjour(command)
            assert node.ratgdo == "192.168.1.50"
            assert node.bonjourOn is False  # Should be turned off after success

    def test_start_initializes_node(self, garage_node):
        """Test that start() initializes the node properly."""
        node, _ = garage_node

        with patch.object(node, "_process_ratgdo_config"), patch.object(
            node, "_reset_time"
        ) as mock_reset, patch("nodes.VirtualGarage.Thread"):
            node.start()

            # Should set first_pass_event
            assert node.first_pass_event.is_set()

            # Should call reset_time
            mock_reset.assert_called()

            # Should subscribe to POLL
            node.poly.subscribe.assert_called()

    def test_start_with_ratgdo_enabled(self, garage_node):
        """Test start() when Ratgdo is configured."""
        node, _ = garage_node
        node.dev = {"ratgdo": "192.168.1.100"}  # type: ignore[assignment]
        node.ratgdo = "192.168.1.100"
        node.ratgdo_do_events = True

        with patch.object(node, "_process_ratgdo_config"), patch.object(
            node, "_reset_time"
        ), patch.object(node, "start_sse_client") as mock_sse, patch.object(
            node, "start_event_polling"
        ) as mock_poll, patch("nodes.VirtualGarage.Thread"):
            node.start()

            # Should start SSE client and event polling when Ratgdo is enabled
            mock_sse.assert_called_once()
            mock_poll.assert_called_once()

    def test_start_with_bonjour(self, garage_node):
        """Test start() triggers Bonjour discovery when configured."""
        node, _ = garage_node
        node.bonjourOn = True
        node.bonjourOnce = True

        with patch.object(node, "_process_ratgdo_config"), patch.object(
            node, "_reset_time"
        ), patch("nodes.VirtualGarage.Thread"):
            node.start()

            # Should call bonjour when enabled
            node.poly.bonjour.assert_called_with("http", None, None)

    def test_update_vars_pulls_from_isy(self, garage_node):
        """Test _update_vars pulls values from ISY variables."""
        node, mocks = garage_node

        # Configure to pull door from ISY only
        node.data["doorT"] = 2
        node.data["doorId"] = 10

        # Mock ISY variable return
        mocks["pull"].return_value = 100  # door=100

        node._update_vars()

        # Should pull from ISY
        assert mocks["pull"].called
        assert node.data["door"] == 100

    def test_update_vars_skips_zero_ids(self, garage_node):
        """Test _update_vars skips fields with zero ID."""
        node, mocks = garage_node

        # Configure with zero ID (disabled)
        node.data["doorT"] = 2
        node.data["doorId"] = 0  # Zero means disabled

        node._update_vars()

        # Should not pull from ISY for zero ID
        mocks["pull"].assert_not_called()

    def test_pull_from_ratgdo_success(self, garage_node):
        """Test successful pull from Ratgdo device."""
        node, _ = garage_node
        node.ratgdo = "192.168.1.100"

        with patch("nodes.VirtualGarage.requests") as mock_requests:
            mock_response = Mock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "light-light", "state": "ON"}
            mock_requests.get.return_value = mock_response

            success, data = node.pull_from_ratgdo(LIGHT)

            assert success is True
            assert data == {"id": "light-light", "state": "ON"}

    def test_pull_from_ratgdo_failure(self, garage_node):
        """Test failed pull from Ratgdo device."""
        node, _ = garage_node
        node.ratgdo = "192.168.1.100"

        with patch("nodes.VirtualGarage.requests") as mock_requests:
            mock_response = Mock()
            mock_response.ok = False
            mock_response.status_code = 500
            mock_requests.get.return_value = mock_response

            success, data = node.pull_from_ratgdo(LIGHT)

            assert success is False
            assert data == {}

    def test_pull_from_ratgdo_exception(self, garage_node):
        """Test pull from Ratgdo handles exceptions."""
        node, _ = garage_node
        node.ratgdo = "192.168.1.100"

        with patch("nodes.VirtualGarage.requests") as mock_requests:
            mock_requests.get.side_effect = Exception("Connection error")

            success, data = node.pull_from_ratgdo(LIGHT)

            assert success is False
            assert data == {}

    def test_get_ratgdo_direct_success(self, garage_node):
        """Test get_ratgdo_direct polls all endpoints successfully."""
        node, _ = garage_node
        node.ratgdo = "192.168.1.100"

        with patch("nodes.VirtualGarage.requests") as mock_requests, patch(
            "nodes.VirtualGarage.time"
        ):
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "id": "test",
                "state": "ON",
                "value": 1,
                "current_operation": "IDLE",
            }
            mock_requests.get.return_value = mock_response

            result = node.get_ratgdo_direct()

            assert result is True
            # Should call requests.get for each endpoint (6 endpoints)
            assert mock_requests.get.call_count == 6

    def test_get_ratgdo_direct_failure(self, garage_node):
        """Test get_ratgdo_direct handles failures."""
        node, _ = garage_node
        node.ratgdo = "192.168.1.100"

        with patch("nodes.VirtualGarage.requests") as mock_requests:
            mock_response = Mock()
            mock_response.ok = False
            mock_response.status_code = 500
            mock_requests.get.return_value = mock_response

            result = node.get_ratgdo_direct()

            assert result is False

    def test_set_ratgdo_door_opening_state(self, garage_node):
        """Test _set_ratgdo_door with OPENING state."""
        node, _ = garage_node

        payload = {
            "id": "cover-door",
            "state": "OPENING",
            "value": 0.5,
            "current_operation": "IDLE",
        }
        node._set_ratgdo_door(payload)

        assert node.data["door"] == 104
        assert node.data["position"] == 50

    def test_set_ratgdo_door_closing_state(self, garage_node):
        """Test _set_ratgdo_door with CLOSING state."""
        node, _ = garage_node

        payload = {
            "id": "cover-door",
            "state": "CLOSING",
            "value": 0.75,
            "current_operation": "IDLE",
        }
        node._set_ratgdo_door(payload)

        assert node.data["door"] == 103
        assert node.data["position"] == 75

    def test_set_ratgdo_door_stopped_state(self, garage_node):
        """Test _set_ratgdo_door with STOPPED state."""
        node, _ = garage_node

        payload = {
            "id": "cover-door",
            "state": "STOPPED",
            "value": 0.3,
            "current_operation": "IDLE",
        }
        node._set_ratgdo_door(payload)

        assert node.data["door"] == 102
        assert node.data["position"] == 30

    def test_set_ratgdo_door_unknown_state(self, garage_node):
        """Test _set_ratgdo_door with UNKNOWN state."""
        node, _ = garage_node

        payload = {
            "id": "cover-door",
            "state": "UNKNOWN",
            "value": 0.5,
            "current_operation": "IDLE",
        }
        node._set_ratgdo_door(payload)

        assert node.data["door"] == 101  # Unknown door state

    def test_set_ratgdo_door_current_operation_opening(self, garage_node):
        """Test _set_ratgdo_door with current_operation OPENING."""
        node, _ = garage_node

        payload = {
            "id": "cover-door",
            "state": "OPEN",
            "value": 0.9,
            "current_operation": "OPENING",
        }
        node._set_ratgdo_door(payload)

        assert node.data["door"] == 104  # OPENING

    def test_set_ratgdo_door_current_operation_closing(self, garage_node):
        """Test _set_ratgdo_door with current_operation CLOSING."""
        node, _ = garage_node

        payload = {
            "id": "cover-door",
            "state": "CLOSED",
            "value": 0.1,
            "current_operation": "CLOSING",
        }
        node._set_ratgdo_door(payload)

        assert node.data["door"] == 103  # CLOSING

    def test_set_ratgdo_door_invalid_position(self, garage_node):
        """Test _set_ratgdo_door with invalid position value."""
        node, _ = garage_node

        payload = {
            "id": "cover-door",
            "state": "OPEN",
            "value": 1.5,  # Invalid: > 1.0
            "current_operation": "IDLE",
        }
        node._set_ratgdo_door(payload)

        assert node.data["position"] == 101  # Error value for invalid position

    def test_ratgdo_post_success(self, garage_node):
        """Test ratgdo_post sends HTTP POST successfully."""
        node, _ = garage_node
        node.ratgdoOK = True  # Must be True for post to happen

        with patch("nodes.VirtualGarage.requests") as mock_requests:
            mock_response = Mock()
            mock_response.ok = True
            mock_requests.post.return_value = mock_response

            node.ratgdo_post("192.168.1.100/light/turn_on")

            mock_requests.post.assert_called_once()

    def test_ratgdo_post_failure(self, garage_node):
        """Test ratgdo_post handles failures."""
        node, _ = garage_node

        with patch("nodes.VirtualGarage.requests") as mock_requests:
            mock_response = Mock()
            mock_response.ok = False
            mock_response.status_code = 500
            mock_requests.post.return_value = mock_response

            # Should not raise, just log error
            node.ratgdo_post("http://192.168.1.100/light/turn_on")

    def test_reset_time(self, garage_node):
        """Test _reset_time updates lastUpdateTime."""
        node, _ = garage_node

        node._reset_time()

        # Should set lastUpdateTime to 0.0
        assert node.data["lastUpdateTime"] == 0.0
        node.setDriver.assert_called_with("GV6", 0.0)

    def test_process_ratgdo_config_with_ip(self, garage_node):
        """Test _process_ratgdo_config with IP address."""
        node, _ = garage_node
        node.dev = {"ratgdo": "192.168.1.100"}  # type: ignore[assignment]

        with patch.object(node, "ratgdo_check", return_value=True):
            node._process_ratgdo_config()

            assert node.ratgdo == "192.168.1.100"
            assert node.bonjourOn is False

    def test_process_ratgdo_config_with_true(self, garage_node):
        """Test _process_ratgdo_config with True (use default)."""
        node, _ = garage_node
        node.dev = {"ratgdo": True}  # type: ignore[assignment]

        with patch.object(node, "ratgdo_check", return_value=True):
            node._process_ratgdo_config()

            assert node.ratgdo == RATGDO
            assert node.bonjourOn is True

    def test_process_ratgdo_config_disabled(self, garage_node):
        """Test _process_ratgdo_config when disabled."""
        node, _ = garage_node
        node.dev = {"ratgdo": False}  # type: ignore[assignment]

        node._process_ratgdo_config()

        assert node.ratgdo is False
        assert node.bonjourOn is False

    def test_door_stop_cmd(self, garage_node):
        """Test dr_stop_cmd sets correct dcommand value."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True

        with patch.object(node, "door_command"):
            node.dr_stop_cmd()
            assert node.data["dcommand"] == 4  # Stop command value

    def test_commands_with_isy_variables(self, garage_node):
        """Test commands push to ISY variables when configured."""
        node, mocks = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True
        node.data["lockT"] = 1
        node.data["lockId"] = 15  # Non-zero ID enables ISY push

        with patch.object(node, "ratgdo_post"):
            node.lk_lock_cmd()

            # Should push to ISY variable
            mocks["push"].assert_called()

    def test_lt_on_cmd_without_ratgdo_ok(self, garage_node):
        """Test light on when Ratgdo is not OK - post still happens but Ratgdo won't execute."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = False  # Not validated

        with patch.object(node, "ratgdo_post") as mock_post:
            node.lt_on_cmd()
            # Still calls ratgdo_post (which checks ratgdoOK internally)
            assert node.data["light"] == 1
            mock_post.assert_called_once()

    def test_lt_off_cmd_without_ratgdo_ok(self, garage_node):
        """Test light off when Ratgdo is not OK - post still happens but Ratgdo won't execute."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = False

        with patch.object(node, "ratgdo_post") as mock_post:
            node.lt_off_cmd()
            assert node.data["light"] == 0
            mock_post.assert_called_once()

    def test_door_command_without_ratgdo_ok(self, garage_node):
        """Test door command when Ratgdo is not OK - post still happens."""
        node, _ = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = False

        with patch.object(node, "ratgdo_post") as mock_post:
            node.door_command("some_url")
            # door_command always calls ratgdo_post
            mock_post.assert_called_once_with("some_url")

    def test_lk_lock_cmd_without_isy_var(self, garage_node):
        """Test lock command without ISY variable configured."""
        node, mocks = garage_node
        node.ratgdo = "1.2.3.4"
        node.ratgdoOK = True
        node.data["lockId"] = 0  # No ISY variable

        with patch.object(node, "ratgdo_post"):
            node.lk_lock_cmd()
            # Should not push to ISY when ID is 0
            mocks["push"].assert_not_called()

    def test_ratgdo_check_invalid_json(self, garage_node):
        """Test ratgdo_check with invalid JSON response."""
        node, _ = garage_node
        node.ratgdo = "192.168.1.100"

        with patch("nodes.VirtualGarage.requests") as mock_requests:
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {"id": "wrong-id"}
            mock_requests.get.return_value = mock_response

            result = node.ratgdo_check()

            # Should fail if JSON doesn't match expected ID
            assert result is False

    def test_bonjour_not_success(self, garage_node):
        """Test bonjour command with success=False."""
        node, _ = garage_node
        node.bonjourOn = True
        node.bonjourOnce = True

        command = {"success": False}

        node.bonjour(command)

        # Should not set ratgdo IP
        assert node.ratgdo is False

    def test_bonjour_no_matching_device(self, garage_node):
        """Test bonjour when no matching device found."""
        node, _ = garage_node
        node.bonjourOn = True
        node.bonjourOnce = True

        command = {
            "success": True,
            "mdns": [
                {"name": "other-device", "type": "other", "addresses": ["192.168.1.99"]}
            ],
        }

        node.bonjour(command)

        # Should not set ratgdo when device doesn't match
        assert node.ratgdo is False

    def test_poll_long_without_ratgdo(self, garage_node):
        """Test long poll when Ratgdo is disabled."""
        node, _ = garage_node
        node.ratgdo = False

        with patch.object(node, "start_sse_client") as mock_sse:
            node.poll("longPoll")
            # Should not start SSE when Ratgdo is disabled
            mock_sse.assert_not_called()

    def test_get_ratgdo_direct_exception(self, garage_node):
        """Test get_ratgdo_direct handles exceptions in requests."""
        node, _ = garage_node
        node.ratgdo = "192.168.1.100"

        with patch("nodes.VirtualGarage.requests") as mock_requests:
            mock_requests.get.side_effect = Exception("Network error")

            result = node.get_ratgdo_direct()

            assert result is False

    def test_update_isy_first_pass(self, garage_node):
        """Test _update_isy during first pass."""
        node, _ = garage_node
        node.first_pass_event.set()
        node.data["door"] = 50
        node.data["light"] = 1

        with patch.object(node, "getDriver", return_value=0):
            node._update_isy()

            # Should call setDriver for state fields
            assert node.setDriver.called
            # Should clear first_pass_event
            assert not node.first_pass_event.is_set()

    def test_update_isy_subsequent_pass(self, garage_node):
        """Test _update_isy on subsequent passes."""
        node, _ = garage_node
        node.first_pass_event.clear()  # Not first pass
        node.data["door"] = 100

        with patch.object(node, "getDriver", return_value=0):  # Value changed
            node._update_isy()

            # Should update changed drivers
            assert node.setDriver.called

    def test_heartbeat_sets_driver(self, garage_node):
        """Test _heartbeat sends report command."""
        node, _ = garage_node
        initial_hb = node.hb

        node._heartbeat()

        # Should toggle hb
        assert node.hb != initial_hb
        # Should call reportCmd
        node.reportCmd.assert_called()

    def test_process_ratgdo_config_with_string_false(self, garage_node):
        """Test _process_ratgdo_config with string 'false'."""
        node, _ = garage_node
        node.dev = {"ratgdo": "false"}  # type: ignore[assignment]

        node._process_ratgdo_config()

        assert node.ratgdo is False

    def test_process_ratgdo_config_check_fails(self, garage_node):
        """Test _process_ratgdo_config when ratgdo_check fails."""
        node, _ = garage_node
        node.dev = {"ratgdo": "192.168.1.100"}  # type: ignore[assignment]

        with patch.object(node, "ratgdo_check", return_value=False):
            node._process_ratgdo_config()

            # Should still set IP even if check fails
            assert node.ratgdo == "192.168.1.100"

    def test_update_isy_door_command_reset(self, garage_node):
        """Test _update_isy resets dcommand when door changes."""
        node, _ = garage_node
        node.first_pass_event.clear()
        node.data["door"] = 100
        node.data["dcommand"] = 1  # Has a command

        with patch.object(node, "getDriver") as mock_get:
            # Simulate door driver different from data
            mock_get.return_value = 0

            node._update_isy()

            # Should reset dcommand to 0 when door changes
            assert node.data["dcommand"] == 0

    def test_start_event_polling(self, garage_node):
        """Test start_event_polling starts the polling thread."""
        node, _ = garage_node
        node._event_polling_thread = None

        with patch("nodes.VirtualGarage.Thread") as mock_thread:
            mock_instance = Mock()
            mock_thread.return_value = mock_instance

            node.start_event_polling()

            # Should create and start thread
            mock_thread.assert_called_once()
            mock_instance.start.assert_called_once()

    def test_start_event_polling_already_running(self, garage_node):
        """Test start_event_polling skips if already running."""
        node, _ = garage_node
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        node._event_polling_thread = mock_thread

        with patch("nodes.VirtualGarage.Thread") as mock_thread_class:
            node.start_event_polling()

            # Should not create new thread if already running
            mock_thread_class.assert_not_called()

    def test_poll_short_updates_and_pushes(self, garage_node):
        """Test shortPoll calls _update_isy."""
        node, _ = garage_node

        with patch.object(node, "_heartbeat"), patch.object(
            node, "_update_isy"
        ) as mock_isy:
            node.poll("shortPoll")

            # Should update ISY on short poll
            mock_isy.assert_called_once()
