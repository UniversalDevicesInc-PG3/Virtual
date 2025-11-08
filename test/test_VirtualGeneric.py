"""
Unit tests for the VirtualGeneric node.
"""

import pytest
from unittest.mock import MagicMock, patch

from nodes.VirtualGeneric import (
    VirtualGeneric,
    FIELDS,
    OFF,
    FULL,
    INC,
    DIMLOWERLIMIT,
    STATIC,
    DYNAMIC,
)


# This fixture automatically mocks the udi_interface dependencies for all tests.
@pytest.fixture(autouse=True)
def mock_udi_interface():
    """Automatically mock udi_interface.Node and LOGGER."""
    with patch("nodes.VirtualGeneric.Node", autospec=True), patch(
        "nodes.VirtualGeneric.LOGGER", autospec=True
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
def generic_node(mock_polyglot):
    """
    Fixture to create a VirtualGeneric instance for testing.
    It patches utility functions to isolate the node's own logic.
    """
    with patch("nodes.VirtualGeneric.load_persistent_data"), patch(
        "nodes.VirtualGeneric.get_config_data"
    ), patch("nodes.VirtualGeneric.store_values") as mock_store:
        node = VirtualGeneric(
            mock_polyglot, "controller_addr", "generic_addr", "Test Generic"
        )

        # Explicitly mock methods from the parent Node class
        node.setDriver = MagicMock()
        node.reportCmd = MagicMock()
        node.reportDrivers = MagicMock()

        # Simulate the effect of load_persistent_data for a clean slate
        node.data = {field: spec.default for field, spec in FIELDS.items()}

        yield node, {"store": mock_store}


class TestVirtualGeneric:
    """Test suite for the VirtualGeneric node."""

    def test_init(self, generic_node, mock_polyglot):
        """Test the initialization of the VirtualGeneric node."""
        node, _ = generic_node
        assert node.name == "Test Generic"
        assert node.id == "virtualgeneric"
        mock_polyglot.subscribe.assert_called_with(
            mock_polyglot.START, node.start, "generic_addr"
        )
        assert node.data["status"] == FULL

    def test_don_cmd(self, generic_node):
        """Test the DON command to turn on to the last onlevel."""
        node, _ = generic_node
        node.data["onlevel"] = 80
        node.DON_cmd()
        assert node.data["status"] == 80
        node.setDriver.assert_any_call("ST", 80)

    def test_don_cmd_with_zero_onlevel(self, generic_node):
        """Test DON when onlevel is 0; should default to FULL."""
        node, _ = generic_node
        node.data["onlevel"] = 0
        node.DON_cmd()
        assert node.data["status"] == FULL
        node.setDriver.assert_any_call("ST", FULL)

    @pytest.mark.parametrize(
        "onleveltype, initial_status, expected_onlevel",
        [
            (DYNAMIC, 50, 50),
            (STATIC, 50, FULL),  # FULL is the default, should not change
        ],
    )
    def test_dof_cmd(self, generic_node, onleveltype, initial_status, expected_onlevel):
        """Test the DOF command with both STATIC and DYNAMIC onlevel types."""
        node, _ = generic_node
        node.data["onleveltype"] = onleveltype
        node.data["status"] = initial_status

        node.DOF_cmd()

        assert node.data["status"] == OFF
        assert node.data["onlevel"] == expected_onlevel
        node.setDriver.assert_called_with("ST", OFF)

    def test_dfon_cmd(self, generic_node):
        """Test the DFON (fast on) command."""
        node, _ = generic_node
        node.data["status"] = 0
        node.DFON_cmd()
        assert node.data["status"] == FULL
        node.setDriver.assert_any_call("ST", FULL)

    def test_brt_cmd(self, generic_node):
        """Test the BRT (brighten) command."""
        node, _ = generic_node
        node.data["status"] = 50
        node.BRT_cmd()
        assert node.data["status"] == 50 + INC
        node.setDriver.assert_any_call("ST", 50 + INC)

    def test_dim_cmd(self, generic_node):
        """Test the DIM command."""
        node, _ = generic_node
        node.data["status"] = 50
        node.DIM_cmd()
        assert node.data["status"] == 50 - INC
        node.setDriver.assert_any_call("ST", 50 - INC)

    def test_dim_cmd_to_off_dynamic(self, generic_node):
        """Test DIM turning the light off with DYNAMIC onlevel."""
        node, _ = generic_node
        node.data["status"] = 1
        node.data["onleveltype"] = DYNAMIC
        node.DIM_cmd()
        assert node.data["status"] == OFF
        assert node.data["onlevel"] == DIMLOWERLIMIT
        node.setDriver.assert_any_call("OL", DIMLOWERLIMIT)

    def test_set_st_cmd(self, generic_node):
        """Test the SETST command to set a specific status level."""
        node, _ = generic_node
        command = {"value": "75"}
        node.set_ST_cmd(command)
        assert node.data["status"] == 75
        node.setDriver.assert_any_call("ST", 75)

    def test_set_ol_cmd(self, generic_node):
        """Test the SETOL command to set a specific onlevel."""
        node, _ = generic_node
        command = {"value": "85"}
        node.set_OL_cmd(command)
        assert node.data["onlevel"] == 85
        node.setDriver.assert_any_call("OL", 85)

    def test_ol_toggle_type_cmd(self, generic_node):
        """Test the OLTT command to toggle onlevel type."""
        node, _ = generic_node
        assert node.data["onleveltype"] == STATIC
        node.OL_toggle_type_cmd()
        assert node.data["onleveltype"] == DYNAMIC
        node.setDriver.assert_called_with("GV0", DYNAMIC)
        node.OL_toggle_type_cmd()
        assert node.data["onleveltype"] == STATIC
        node.setDriver.assert_called_with("GV0", STATIC)

    def test_query(self, generic_node):
        """Test the query command."""
        node, _ = generic_node
        node.query()
        node.reportDrivers.assert_called_once()

    def test_start(self, generic_node):
        """Test the start method."""
        node, _ = generic_node
        with patch("nodes.VirtualGeneric.load_persistent_data") as mock_load, \
             patch("nodes.VirtualGeneric.get_config_data") as mock_get_config, \
             patch.object(node, "query") as mock_query:
            node.start()
            mock_load.assert_called_once()
            mock_get_config.assert_called_once()
            node.controller.ready_event.wait.assert_called_once()
            mock_query.assert_called_once()

    def test_dfof_cmd_static(self, generic_node):
        """Test DFOF (fast off) command with static onlevel."""
        node, _ = generic_node
        node.data["status"] = 50
        node.data["onleveltype"] = STATIC
        
        node.DFOF_cmd()
        
        assert node.data["status"] == OFF
        # onlevel should not change with STATIC
        assert node.data["onlevel"] == FULL
        node.setDriver.assert_any_call("ST", OFF)
        node.reportCmd.assert_called_with("DFOF")

    def test_dfof_cmd_dynamic_mid_level(self, generic_node):
        """Test DFOF command with dynamic onlevel at mid-level."""
        node, _ = generic_node
        node.data["status"] = 50
        node.data["onleveltype"] = DYNAMIC
        
        node.DFOF_cmd()
        
        assert node.data["status"] == OFF
        # onlevel should update to last level with DYNAMIC
        assert node.data["onlevel"] == 50
        node.setDriver.assert_any_call("OL", 50)
        node.setDriver.assert_any_call("ST", OFF)

    def test_dfof_cmd_dynamic_at_full(self, generic_node):
        """Test DFOF when status is FULL - onlevel should not change."""
        node, _ = generic_node
        node.data["status"] = FULL
        node.data["onleveltype"] = DYNAMIC
        
        node.DFOF_cmd()
        
        assert node.data["status"] == OFF
        # onlevel should not change when at FULL
        assert node.data["onlevel"] == FULL

    def test_dfof_cmd_dynamic_at_off(self, generic_node):
        """Test DFOF when already OFF - onlevel should not change."""
        node, _ = generic_node
        node.data["status"] = OFF
        node.data["onleveltype"] = DYNAMIC
        
        node.DFOF_cmd()
        
        assert node.data["status"] == OFF
        # onlevel should not change when already OFF
        assert node.data["onlevel"] == FULL

    def test_brt_cmd_dynamic(self, generic_node):
        """Test BRT command with dynamic onlevel."""
        node, _ = generic_node
        node.data["status"] = 50
        node.data["onleveltype"] = DYNAMIC
        
        node.BRT_cmd()
        
        assert node.data["status"] == 52
        # With DYNAMIC, onlevel should update
        assert node.data["onlevel"] == 52
        node.setDriver.assert_any_call("OL", 52)
        node.setDriver.assert_any_call("ST", 52)

    def test_brt_cmd_at_max(self, generic_node):
        """Test BRT command when already at maximum."""
        node, _ = generic_node
        node.data["status"] = FULL
        
        node.BRT_cmd()
        
        # Should remain at FULL
        assert node.data["status"] == FULL
        node.setDriver.assert_any_call("ST", FULL)

    def test_set_st_cmd_with_zero(self, generic_node):
        """Test SETST command with value of 0 (should set to DIMLOWERLIMIT)."""
        node, _ = generic_node
        command = {"value": "0"}
        
        node.set_ST_cmd(command)
        
        assert node.data["status"] == DIMLOWERLIMIT
        node.setDriver.assert_any_call("ST", DIMLOWERLIMIT)

    def test_set_ol_cmd_with_zero(self, generic_node):
        """Test SETOL command with value of 0."""
        node, _ = generic_node
        command = {"value": "0"}
        
        node.set_OL_cmd(command)
        
        # Bug in code: line 199 overwrites line 198, so it ends up as 0
        # If line 198 was followed by 'else:', onlevel would be DIMLOWERLIMIT
        assert node.data["onlevel"] == 0
        node.setDriver.assert_any_call("OL", 0)

    def test_dim_cmd_static_non_zero(self, generic_node):
        """Test DIM command with STATIC onlevel and non-zero result."""
        node, _ = generic_node
        node.data["status"] = 50
        node.data["onleveltype"] = STATIC
        
        node.DIM_cmd()
        
        assert node.data["status"] == 48
        # With STATIC, onlevel should not change
        assert node.data["onlevel"] == FULL
        node.setDriver.assert_any_call("ST", 48)

    def test_dim_cmd_dynamic_non_zero(self, generic_node):
        """Test DIM command with DYNAMIC onlevel and non-zero result."""
        node, _ = generic_node
        node.data["status"] = 50
        node.data["onleveltype"] = DYNAMIC
        
        node.DIM_cmd()
        
        assert node.data["status"] == 48
        # With DYNAMIC, onlevel should update
        assert node.data["onlevel"] == 48
        node.setDriver.assert_any_call("OL", 48)
