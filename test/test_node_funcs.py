"""Tests for the node_funcs utility module.

(C) 2025 Stephen Jenkins
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from utils.node_funcs import (
    FieldSpec,
    load_persistent_data,
    store_values,
    push_to_isy_var,
    pull_from_isy_var,
    _apply_state,
    _check_db_files_and_migrate,
    _push_drivers,
    _shelve_file_candidates,
    _VARIABLE_TYPE_MAP,
)


class TestFieldSpec:
    """Tests for FieldSpec dataclass."""

    def test_field_spec_creation(self):
        """Test creating a FieldSpec instance."""
        field = FieldSpec(driver="GV1", default=0, data_type="state")

        assert field.driver == "GV1"
        assert field.default == 0
        assert field.data_type == "state"

    def test_field_spec_frozen(self):
        """Test that FieldSpec is immutable (frozen)."""
        field = FieldSpec(driver="GV1", default=0, data_type="state")

        # Frozen dataclass raises FrozenInstanceError on assignment
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            field.driver = "GV2"  # type: ignore

    def test_should_update_true_for_state_with_driver(self):
        """Test should_update returns True for state fields with driver."""
        field = FieldSpec(driver="GV1", default=0, data_type="state")

        assert field.should_update() is True

    def test_should_update_false_for_config(self):
        """Test should_update returns False for config fields."""
        field = FieldSpec(driver="GV1", default=0, data_type="config")

        assert field.should_update() is False

    def test_should_update_false_for_none_driver(self):
        """Test should_update returns False when driver is None."""
        field = FieldSpec(driver=None, default=0, data_type="state")

        assert field.should_update() is False

    def test_field_spec_with_none_driver(self):
        """Test FieldSpec with None driver."""
        field = FieldSpec(driver=None, default="default_value", data_type="config")

        assert field.driver is None
        assert field.default == "default_value"
        assert field.should_update() is False


class TestVariableTypeMap:
    """Tests for _VARIABLE_TYPE_MAP constant."""

    def test_variable_type_map_structure(self):
        """Test that variable type map has expected structure."""
        assert isinstance(_VARIABLE_TYPE_MAP, dict)
        assert len(_VARIABLE_TYPE_MAP) == 4

    def test_variable_type_1(self):
        """Test state integer variable type."""
        index, tag, set_tag = _VARIABLE_TYPE_MAP["1"]
        assert index == "2"
        assert tag == "val"
        assert set_tag == "set"

    def test_variable_type_2(self):
        """Test state init variable type."""
        index, tag, set_tag = _VARIABLE_TYPE_MAP["2"]
        assert index == "2"
        assert tag == "init"
        assert set_tag == "init"

    def test_variable_type_3(self):
        """Test program integer variable type."""
        index, tag, set_tag = _VARIABLE_TYPE_MAP["3"]
        assert index == "1"
        assert tag == "val"
        assert set_tag == "set"

    def test_variable_type_4(self):
        """Test program init variable type."""
        index, tag, set_tag = _VARIABLE_TYPE_MAP["4"]
        assert index == "1"
        assert tag == "init"
        assert set_tag == "init"


class TestApplyState:
    """Tests for _apply_state function."""

    def test_apply_state_with_existing_data(self):
        """Test applying state from source data."""
        # Create mock self object
        mock_self = Mock()
        mock_self.data = {"field1": "default1", "field2": "default2"}

        # Create FIELDS
        FIELDS = {
            "field1": FieldSpec(driver="GV1", default="default1", data_type="state"),
            "field2": FieldSpec(driver="GV2", default="default2", data_type="state"),
        }

        # Source data
        src = {"field1": "new_value1", "field2": "new_value2"}

        _apply_state(mock_self, src, FIELDS)

        assert mock_self.data["field1"] == "new_value1"
        assert mock_self.data["field2"] == "new_value2"

    def test_apply_state_uses_defaults_for_missing_fields(self):
        """Test that apply_state uses existing data for missing fields."""
        mock_self = Mock()
        mock_self.data = {"field1": "default1", "field2": "default2"}

        FIELDS = {
            "field1": FieldSpec(driver="GV1", default="default1", data_type="state"),
            "field2": FieldSpec(driver="GV2", default="default2", data_type="state"),
        }

        # Source only has field1
        src = {"field1": "new_value1"}

        _apply_state(mock_self, src, FIELDS)

        assert mock_self.data["field1"] == "new_value1"
        assert mock_self.data["field2"] == "default2"  # Keeps existing value

    def test_apply_state_with_empty_source(self):
        """Test applying state with empty source."""
        mock_self = Mock()
        mock_self.data = {"field1": "default1"}

        FIELDS = {
            "field1": FieldSpec(driver="GV1", default="default1", data_type="state")
        }

        _apply_state(mock_self, {}, FIELDS)

        assert mock_self.data["field1"] == "default1"


class TestStoreValues:
    """Tests for store_values function."""

    def test_store_values_saves_to_controller_data(self):
        """Test that store_values saves data to controller."""
        mock_controller = Mock()
        mock_controller.Data = {}

        mock_self = Mock()
        mock_self.controller = mock_controller
        mock_self.name = "TestNode"
        mock_self.data = {"field1": "value1", "field2": "value2"}

        store_values(mock_self)

        assert mock_controller.Data["TestNode"] == {
            "field1": "value1",
            "field2": "value2",
        }

    def test_store_values_overwrites_existing(self):
        """Test that store_values overwrites existing data."""
        mock_controller = Mock()
        mock_controller.Data = {"TestNode": {"old": "data"}}

        mock_self = Mock()
        mock_self.controller = mock_controller
        mock_self.name = "TestNode"
        mock_self.data = {"new": "data"}

        store_values(mock_self)

        assert mock_controller.Data["TestNode"] == {"new": "data"}


class TestPushDrivers:
    """Tests for _push_drivers function."""

    def test_push_drivers_updates_state_fields(self):
        """Test that _push_drivers updates drivers for state fields."""
        mock_self = Mock()
        mock_self.data = {"state_field": 100, "config_field": 200}
        mock_self.setDriver = Mock()

        FIELDS = {
            "state_field": FieldSpec(driver="GV1", default=0, data_type="state"),
            "config_field": FieldSpec(driver="GV2", default=0, data_type="config"),
        }

        _push_drivers(mock_self, FIELDS)

        # Should only push state field (force=True is the actual behavior)
        mock_self.setDriver.assert_called_once_with("GV1", 100, report=True, force=True)

    def test_push_drivers_skips_none_driver(self):
        """Test that fields with None driver are not pushed."""
        mock_self = Mock()
        mock_self.data = {"field1": 100}
        mock_self.setDriver = Mock()

        FIELDS = {
            "field1": FieldSpec(driver=None, default=0, data_type="state"),
        }

        _push_drivers(mock_self, FIELDS)

        mock_self.setDriver.assert_not_called()

    def test_push_drivers_with_multiple_state_fields(self):
        """Test pushing multiple state fields."""
        mock_self = Mock()
        mock_self.data = {"field1": 10, "field2": 20, "field3": 30}
        mock_self.setDriver = Mock()

        FIELDS = {
            "field1": FieldSpec(driver="GV1", default=0, data_type="state"),
            "field2": FieldSpec(driver="GV2", default=0, data_type="state"),
            "field3": FieldSpec(driver=None, default=0, data_type="state"),
        }

        _push_drivers(mock_self, FIELDS)

        assert mock_self.setDriver.call_count == 2


class TestShelveFileCandidates:
    """Tests for _shelve_file_candidates function."""

    def test_shelve_file_candidates_finds_db_file(self):
        """Test finding shelve .db file."""
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            base = Path("db/test_node")

            candidates = list(_shelve_file_candidates(base))

            # Should check for .db, .bak, .dat, .dir extensions
            assert len(candidates) >= 1

    def test_shelve_file_candidates_with_no_files(self):
        """Test when no shelve files exist."""
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False
            base = Path("db/test_node")

            candidates = list(_shelve_file_candidates(base))

            assert len(candidates) == 0


class TestPushToIsyVar:
    """Tests for push_to_isy_var function."""

    def test_push_to_isy_var_invalid_type(self):
        """Test push_to_isy_var with invalid var_type."""
        mock_self = Mock()

        # Should return early without raising
        push_to_isy_var(mock_self, var_type="99", var_id="1", var_value="100")

        # No ISY command should be called
        assert not hasattr(mock_self, "isy") or not mock_self.isy.cmd.called

    def test_push_to_isy_var_invalid_id(self):
        """Test push_to_isy_var with invalid var_id."""
        mock_self = Mock()

        # Invalid ID (not convertible to int)
        push_to_isy_var(mock_self, var_type="1", var_id="invalid", var_value="100")

        # No ISY command should be called
        assert not hasattr(mock_self, "isy") or not mock_self.isy.cmd.called

    def test_push_to_isy_var_zero_id(self):
        """Test push_to_isy_var with zero var_id."""
        mock_self = Mock()

        push_to_isy_var(mock_self, var_type="1", var_id="0", var_value="100")

        # No ISY command should be called (ID must be positive)
        assert not hasattr(mock_self, "isy") or not mock_self.isy.cmd.called

    def test_push_to_isy_var_invalid_value(self):
        """Test push_to_isy_var with non-numeric value."""
        mock_self = Mock()

        push_to_isy_var(mock_self, var_type="1", var_id="1", var_value="not_a_number")

        # No ISY command should be called
        assert not hasattr(mock_self, "isy") or not mock_self.isy.cmd.called


class TestPullFromIsyVar:
    """Tests for pull_from_isy_var function."""

    def test_pull_from_isy_var_invalid_type(self):
        """Test pull_from_isy_var with invalid var_type."""
        mock_self = Mock()

        result = pull_from_isy_var(mock_self, var_type="99", var_id="1", CALC=False)

        assert result is None

    def test_pull_from_isy_var_invalid_id(self):
        """Test pull_from_isy_var with invalid var_id."""
        mock_self = Mock()

        result = pull_from_isy_var(
            mock_self, var_type="1", var_id="invalid", CALC=False
        )

        assert result is None

    def test_pull_from_isy_var_zero_id(self):
        """Test pull_from_isy_var with zero var_id."""
        mock_self = Mock()

        result = pull_from_isy_var(mock_self, var_type="1", var_id="0", CALC=False)

        assert result is None

    def test_pull_from_isy_var_success_returns_raw(self):
        """Test successful pull returning raw value."""
        mock_self = Mock()
        mock_self.isy = Mock()
        xml_response = b"""<?xml version="1.0"?>
        <var>
            <val>1000</val>
            <prec>2</prec>
        </var>"""
        mock_self.isy.cmd = Mock(return_value=xml_response)

        result = pull_from_isy_var(mock_self, var_type="1", var_id="5", CALC=False)

        assert result == 1000

    def test_pull_from_isy_var_success_returns_calc(self):
        """Test successful pull returning calculated value."""
        mock_self = Mock()
        mock_self.isy = Mock()
        xml_response = b"""<?xml version="1.0"?>
        <var>
            <val>1000</val>
            <prec>2</prec>
        </var>"""
        mock_self.isy.cmd = Mock(return_value=xml_response)

        result = pull_from_isy_var(mock_self, var_type="1", var_id="5", CALC=True)

        # 1000 / (2 * 10) = 1000 / 20 = 50.0
        assert result == 50.0


class TestLoadPersistentData:
    """Tests for load_persistent_data function."""

    @patch("utils.node_funcs._push_drivers")
    @patch("utils.node_funcs.store_values")
    @patch("utils.node_funcs._check_db_files_and_migrate")
    def test_load_persistent_data_from_polyglot(
        self, mock_migrate, mock_store, mock_push
    ):
        """Test loading data from Polyglot persistence."""
        mock_controller = Mock()
        mock_controller.Data = Mock()
        mock_controller.Data.get = Mock(return_value={"field1": "value1"})

        mock_self = Mock()
        mock_self.controller = mock_controller
        mock_self.name = "TestNode"
        mock_self.data = {"field1": "default"}

        FIELDS = {
            "field1": FieldSpec(driver="GV1", default="default", data_type="state")
        }

        load_persistent_data(mock_self, FIELDS)

        # Should load from persistence
        assert mock_self.data["field1"] == "value1"
        # Should not check for migration
        mock_migrate.assert_not_called()
        # Should store and push
        mock_store.assert_called_once()
        mock_push.assert_called_once()

    @patch("utils.node_funcs._push_drivers")
    @patch("utils.node_funcs.store_values")
    @patch("utils.node_funcs._check_db_files_and_migrate")
    def test_load_persistent_data_migration(
        self, mock_migrate, _mock_store, _mock_push
    ):
        """Test loading data from migrated shelve files."""
        mock_controller = Mock()
        mock_controller.Data = Mock()
        mock_controller.Data.get = Mock(return_value=None)  # No Polyglot data

        mock_self = Mock()
        mock_self.controller = mock_controller
        mock_self.name = "TestNode"
        mock_self.data = {"field1": "default"}

        FIELDS = {
            "field1": FieldSpec(driver="GV1", default="default", data_type="state")
        }

        # Simulate successful migration
        mock_migrate.return_value = (True, {"field1": "migrated_value"})

        load_persistent_data(mock_self, FIELDS)

        # Should load from migrated data
        assert mock_self.data["field1"] == "migrated_value"
        mock_migrate.assert_called_once()

    @patch("utils.node_funcs._push_drivers")
    @patch("utils.node_funcs.store_values")
    @patch("utils.node_funcs._check_db_files_and_migrate")
    def test_load_persistent_data_defaults(self, mock_migrate, _mock_store, _mock_push):
        """Test loading with no data uses defaults."""
        mock_controller = Mock()
        mock_controller.Data = Mock()
        mock_controller.Data.get = Mock(return_value=None)

        mock_self = Mock()
        mock_self.controller = mock_controller
        mock_self.name = "TestNode"
        mock_self.data = {"field1": "default"}

        FIELDS = {
            "field1": FieldSpec(driver="GV1", default="default", data_type="state")
        }

        # No migration data
        mock_migrate.return_value = (False, None)

        load_persistent_data(mock_self, FIELDS)

        # Should keep defaults
        assert mock_self.data["field1"] == "default"


class TestCheckDbFilesAndMigrate:
    """Tests for _check_db_files_and_migrate function."""

    def test_check_db_files_no_files(self):
        """Test when no old DB files exist."""
        with patch("utils.node_funcs._shelve_file_candidates") as mock_candidates:
            mock_candidates.return_value = []

            mock_self = Mock()
            mock_self.name = "TestNode"
            mock_self.address = "addr123"

            migrated, data = _check_db_files_and_migrate(mock_self)

            assert migrated is False
            assert data is None

    @patch("shelve.open")
    @patch("utils.node_funcs._shelve_file_candidates")
    def test_check_db_files_successful_migration(
        self, mock_candidates, mock_shelve_open
    ):
        """Test successful migration from shelve files."""
        # Mock file candidates
        mock_file = Mock(spec=Path)
        mock_file.unlink = Mock()
        mock_candidates.return_value = [mock_file]

        # Mock shelve data
        mock_shelf = {"keyaddr123": {"field1": "old_value"}}
        mock_shelve_open.return_value.__enter__.return_value.get = (
            lambda k: mock_shelf.get(k)
        )

        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.address = "addr123"

        migrated, data = _check_db_files_and_migrate(mock_self)

        assert migrated is True
        assert data == {"field1": "old_value"}
        # Should delete the file
        mock_file.unlink.assert_called_once()

    @patch("shelve.open")
    @patch("utils.node_funcs._shelve_file_candidates")
    def test_check_db_files_shelve_exception(self, mock_candidates, mock_shelve_open):
        """Test shelve.open raises exception during migration."""
        mock_file = Mock(spec=Path)
        mock_candidates.return_value = [mock_file]

        # Mock shelve.open to raise exception
        mock_shelve_open.side_effect = Exception("Shelve error")

        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.address = "addr123"

        migrated, data = _check_db_files_and_migrate(mock_self)

        assert migrated is False
        assert data is None

    @patch("shelve.open")
    @patch("utils.node_funcs._shelve_file_candidates")
    def test_check_db_files_unlink_error(self, mock_candidates, mock_shelve_open):
        """Test file deletion errors during migration."""
        mock_file = Mock(spec=Path)
        mock_file.unlink = Mock(side_effect=OSError("Cannot delete"))
        mock_candidates.return_value = [mock_file]

        # Mock shelve data
        mock_shelf = {"keyaddr123": {"field1": "value"}}
        mock_shelve_open.return_value.__enter__.return_value.get = (
            lambda k: mock_shelf.get(k)
        )

        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.address = "addr123"

        migrated, data = _check_db_files_and_migrate(mock_self)

        # Should still succeed migration, just log warning about deletion
        assert migrated is True
        assert data == {"field1": "value"}


class TestGetConfigData:
    """Tests for get_config_data function."""

    def test_get_config_data_success(self):
        """Test successful config data retrieval."""
        from utils.node_funcs import get_config_data

        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.address = "addr123"
        mock_self.data = {"field1": "default1", "field2": "default2"}
        mock_self.controller = Mock()
        mock_self.controller.devlist = [
            {"id": "other", "field1": "wrong"},
            {"id": "addr123", "field1": "config_value1", "field2": "config_value2"},
        ]
        mock_self.setDriver = Mock()
        mock_self.controller.Data = {}

        FIELDS = {
            "field1": FieldSpec(driver="GV1", default="default1", data_type="state"),
            "field2": FieldSpec(driver="GV2", default="default2", data_type="config"),
        }

        result = get_config_data(mock_self, FIELDS)

        assert result is True
        assert mock_self.data["field1"] == "config_value1"
        assert mock_self.data["field2"] == "config_value2"

    def test_get_config_data_no_device_found(self):
        """Test get_config_data when device not in devlist."""
        from utils.node_funcs import get_config_data

        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.address = "addr123"
        mock_self.controller = Mock()
        mock_self.controller.devlist = [{"id": "other", "field1": "value"}]

        FIELDS = {"field1": FieldSpec(driver="GV1", default=0, data_type="state")}

        result = get_config_data(mock_self, FIELDS)

        assert result is False

    def test_get_config_data_value_error(self):
        """Test get_config_data handles ValueError."""
        from utils.node_funcs import get_config_data

        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.address = "addr123"
        mock_self.data = {"field1": 0}
        mock_self.controller = Mock()
        mock_self.controller.devlist = [{"id": "addr123", "field1": "not_an_int"}]
        mock_self.setDriver = Mock(side_effect=ValueError("Invalid value"))
        mock_self.controller.Data = {}

        FIELDS = {"field1": FieldSpec(driver="GV1", default=0, data_type="state")}

        result = get_config_data(mock_self, FIELDS)

        assert result is False


class TestPushToIsyVarSuccess:
    """Tests for successful push_to_isy_var operations."""

    @patch("utils.node_funcs.pull_from_isy_var")
    def test_push_to_isy_var_success(self, mock_pull):
        """Test successful push to ISY variable."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        mock_self.isy.cmd = Mock(
            return_value=b"<RestResponse><status>200</status></RestResponse>"
        )

        # Mock pull to return different value (so push proceeds)
        mock_pull.return_value = 50.0

        push_to_isy_var(mock_self, var_type="1", var_id="10", var_value=100.0)

        # Should call isy.cmd with correct path
        mock_self.isy.cmd.assert_called_once()
        call_args = mock_self.isy.cmd.call_args[0][0]
        assert "/rest/vars/set/2/10/100.0" in call_args

    @patch("utils.node_funcs.pull_from_isy_var")
    def test_push_to_isy_var_no_change(self, mock_pull):
        """Test push when value hasn't changed."""
        mock_self = Mock()
        mock_self.isy = Mock()

        # Mock pull to return same value
        mock_pull.return_value = 100.0

        push_to_isy_var(mock_self, var_type="1", var_id="10", var_value=100.0)

        # Should not call isy.cmd since value unchanged
        mock_self.isy.cmd.assert_not_called()

    @patch("utils.node_funcs.pull_from_isy_var")
    def test_push_to_isy_var_runtime_error_isy_not_available(self, mock_pull):
        """Test push handles RuntimeError when ISY not available."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        mock_self.isy.cmd = Mock(side_effect=RuntimeError("ISY info not available"))
        mock_pull.return_value = 50.0

        # Should handle error gracefully
        push_to_isy_var(mock_self, var_type="1", var_id="10", var_value=100.0)

        # No exception should be raised

    @patch("utils.node_funcs.pull_from_isy_var")
    def test_push_to_isy_var_runtime_error_other(self, mock_pull):
        """Test push handles other RuntimeError."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        mock_self.isy.cmd = Mock(side_effect=RuntimeError("Other error"))
        mock_pull.return_value = 50.0

        # Should handle error gracefully
        push_to_isy_var(mock_self, var_type="1", var_id="10", var_value=100.0)

        # No exception should be raised

    @patch("utils.node_funcs.pull_from_isy_var")
    def test_push_to_isy_var_generic_exception(self, mock_pull):
        """Test push handles generic exception."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        mock_self.isy.cmd = Mock(side_effect=Exception("Network error"))
        mock_pull.return_value = 50.0

        # Should handle error gracefully
        push_to_isy_var(mock_self, var_type="1", var_id="10", var_value=100.0)

        # No exception should be raised


class TestPullFromIsyVarExceptions:
    """Tests for pull_from_isy_var exception handling."""

    def test_pull_from_isy_var_permission_error(self):
        """Test pull handles PermissionError."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        mock_self.isy.cmd = Mock(side_effect=PermissionError("Access denied"))
        mock_self.controller = Mock()
        mock_self.controller.Notices = {}

        result = pull_from_isy_var(mock_self, var_type="1", var_id="10", CALC=False)

        assert result is None
        assert "permission" in mock_self.controller.Notices

    def test_pull_from_isy_var_runtime_error_isy_not_available(self):
        """Test pull handles RuntimeError when ISY not available."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        mock_self.isy.cmd = Mock(side_effect=RuntimeError("ISY info not available"))

        result = pull_from_isy_var(mock_self, var_type="1", var_id="10", CALC=False)

        assert result is None

    def test_pull_from_isy_var_runtime_error_other(self):
        """Test pull handles other RuntimeError."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        mock_self.isy.cmd = Mock(side_effect=RuntimeError("Other error"))

        result = pull_from_isy_var(mock_self, var_type="1", var_id="10", CALC=False)

        assert result is None

    def test_pull_from_isy_var_generic_exception(self):
        """Test pull handles generic exception."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        mock_self.isy.cmd = Mock(side_effect=Exception("Network error"))

        result = pull_from_isy_var(mock_self, var_type="1", var_id="10", CALC=False)

        assert result is None

    def test_pull_from_isy_var_xml_parse_error(self):
        """Test pull handles XML parsing errors."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        mock_self.isy.cmd = Mock(return_value=b"<invalid xml")

        result = pull_from_isy_var(mock_self, var_type="1", var_id="10", CALC=False)

        assert result is None

    def test_pull_from_isy_var_missing_val_element(self):
        """Test pull when XML is missing required element."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        xml_response = b"""<?xml version="1.0"?>
        <var>
            <other>1000</other>
        </var>"""
        mock_self.isy.cmd = Mock(return_value=xml_response)

        result = pull_from_isy_var(mock_self, var_type="1", var_id="10", CALC=False)

        assert result is None

    def test_pull_from_isy_var_non_int_value(self):
        """Test pull when val element contains non-integer."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        xml_response = b"""<?xml version="1.0"?>
        <var>
            <val>not_a_number</val>
        </var>"""
        mock_self.isy.cmd = Mock(return_value=xml_response)

        result = pull_from_isy_var(mock_self, var_type="1", var_id="10", CALC=False)

        assert result is None

    def test_pull_from_isy_var_with_invalid_prec(self):
        """Test pull with invalid precision value."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        xml_response = b"""<?xml version="1.0"?>
        <var>
            <val>1000</val>
            <prec>not_a_number</prec>
        </var>"""
        mock_self.isy.cmd = Mock(return_value=xml_response)

        result = pull_from_isy_var(mock_self, var_type="1", var_id="10", CALC=False)

        assert result is None

    def test_pull_from_isy_var_with_zero_prec(self):
        """Test pull with zero or negative precision (edge case)."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()
        xml_response = b"""<?xml version="1.0"?>
        <var>
            <val>1000</val>
            <prec>0</prec>
        </var>"""
        mock_self.isy.cmd = Mock(return_value=xml_response)

        result = pull_from_isy_var(mock_self, var_type="1", var_id="10", CALC=False)

        # Should handle prec=0 by using prec_div=1
        assert result == 1000

    def test_pull_from_isy_var_generic_parsing_exception(self):
        """Test pull handles generic exception during parsing."""
        mock_self = Mock()
        mock_self.name = "TestNode"
        mock_self.isy = Mock()

        # Create an XML response that will cause an unexpected error
        xml_response = b"""<?xml version="1.0"?>
        <var>
            <val>1000</val>
        </var>"""

        mock_self.isy.cmd = Mock(return_value=xml_response)

        # Mock ET.fromstring to raise an unexpected exception
        with patch(
            "utils.node_funcs.ET.fromstring", side_effect=Exception("Unexpected error")
        ):
            result = pull_from_isy_var(mock_self, var_type="1", var_id="10", CALC=False)

        assert result is None
