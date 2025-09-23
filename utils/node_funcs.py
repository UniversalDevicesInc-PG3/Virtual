
# standard imports
import re, shelve
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass

# external imports
from udi_interface import LOGGER

@dataclass(frozen=True)
class FieldSpec:
    driver: Optional[str]  # e.g., "GV1" or None if not pushed to a driver
    default: Any           # per-field default
    data_type: str         # denote data type (state or config)
    def should_update(self) -> bool:
            """Return True if this field should be pushed to a driver."""
            return self.driver is not None and self.data_type == "state"

# Single source of truth for field names, driver codes, and defaults
# below is an example
    # FIELDS: dict[str, FieldSpec] = {
    #     #State variables (pushed to drivers)
    #     "name":           FieldSpec(driver="GV0", default=0, data_type="state"),
    #     "nameT":          FieldSpec(driver=None, default=0, data_type="config"),
    # }

# Dispatch map to select the correct tag and index based on var_type.
# Using a dictionary for dispatch is more extensible and readable than a long if/elif chain.
_VARIABLE_TYPE_MAP = {
    # Key: ISY var_type, Value : (INDEX, XML_TAG, SET_TAG)
    '1': ('2', 'val', 'set'),
    '2': ('2', 'init', 'init'),
    '3': ('1', 'val', 'set'),
    '4': ('1', 'init', 'init'),
}


def get_valid_node_address(name,max_length=14):
    offset = max_length * -1
    # Only allow utf-8 characters
    #  https://stackoverflow.com/questions/26541968/delete-every-non-utf-8-symbols-froms-string
    name = bytes(name, 'utf-8').decode('utf-8','ignore')
    # Remove <>`~!@#$%^&*(){}[]?/\;:"'` characters from name
    sname = re.sub(r"[<>`~!@#$%^&*(){}[\]?/\\;:\"']+", "", name)
    # And return last part of name of over max_length
    return sname[offset:].lower()


def get_valid_node_name(name,max_length=32):
    offset = max_length * -1
    # Only allow utf-8 characters
    #  https://stackoverflow.com/questions/26541968/delete-every-non-utf-8-symbols-froms-string
    name = bytes(name, 'utf-8').decode('utf-8','ignore')
    # Remove <>`~!@#$%^&*(){}[]?/\;:"'` characters from name
    sname = re.sub(r"[<>`~!@#$%^&*(){}[\]?/\\;:\"']+", "", name)
    # And return last part of name of over max_length
    return sname[offset:]


def load_persistent_data(self, FIELDS) -> None:
    """
    Load state from Polyglot persistence or migrate from old shelve DB files.
    """
    data = self.controller.Data.get(self.name)

    if data is not None:
        _apply_state(self, data, FIELDS)
        LOGGER.info("%s, Loaded from persistence", self.name)
    else:
        LOGGER.info("%s, No persistent data found. Checking for old DB files...", self.name)
        migrated, old_data = _check_db_files_and_migrate(self)
        if migrated and old_data is not None:
            _apply_state(self, old_data, FIELDS)
            LOGGER.info("%s, Migrated from old DB files.", self.name)
        else:
            _apply_state(self,{}, FIELDS)  # initialize from defaults
            LOGGER.info("%s, No old DB files found.", self.name)

    # Persist and push drivers
    store_values(self)
    _push_drivers(self, FIELDS)


def _apply_state(self, src: Dict[str, Any], FIELDS) -> None:
    """
    Apply values from src; fall back to per-instance defaults
    """
    for field in FIELDS.keys():
        self.data[field] = src.get(field, self.data[field])

        
def _check_db_files_and_migrate(self) -> Tuple[bool, Dict[str, Any] | None]:
    """
    Check for deprecated shelve DB files, migrate data, then delete old files.
    Called by load_persistent_data once during startup.
    """
    name_safe = self.name.replace(" ", "_")
    base = Path("db") / name_safe  # shelve base path (no extension)

    candidates = list(_shelve_file_candidates(base))
    if not candidates:
        LOGGER.info("[%s] No old DB files found at base: %s", self.name, base)
        return False, None

    LOGGER.info("[%s] Old DB files found, migrating data...", self.name)

    key = f"key{self.address}"
    existing_data = None
    try:
        with shelve.open(str(base), flag="r") as s:
            existing_data = s.get(key)
    except Exception as ex:
                LOGGER.exception("[%s] Unexpected error during shelve migration", self.name)
                return False, None

    # Delete all shelve artifacts after a successful read attempt
    errors = []
    for p in candidates:
        try:
            p.unlink()
        except OSError as ex:
            errors.append((p, ex))
    if errors:
        for p, ex in errors:
            LOGGER.warning("[%s] Could not delete shelve file %s: %s", self.name, p, ex)
    else:
        LOGGER.info("[%s] Deleted old shelve files for base: %s", self.name, base)

    return True, existing_data


def store_values(self) -> None:
    """
    Store persistent data to Polyglot Data structure.
    """
    self.controller.Data[self.name] = self.data



def _push_drivers(self, FIELDS) -> None:
    """
    Push only fields that have a driver mapping
    """
    for field, spec in FIELDS.items():
        if spec.should_update():
            self.setDriver(spec.driver, self.data[field], report=True, force=True)


def _shelve_file_candidates(base: Path) -> Iterable[Path]:
    """
    Include the base and any shelve artifacts (base, base.*)
    """
    patterns = [base.name, f"{base.name}.*"]
    seen: set[Path] = set()
    for pattern in patterns:
        for p in base.parent.glob(pattern):
            if p.exists():
                seen.add(p)
    return sorted(seen)


def push_to_isy_var(self, var_type: str | int, var_id: int | str, var_value: int | float | str) -> None:
    """
    Push self.tempVal to an ISY variable.
    var_type = 0-4
    var_id should be a positive integer, within the bounds of defined ISY variables.
    """
    LOGGER.debug(f"Push to isy var_type:{var_type}, var_id:{var_id}, var_value:{var_value}")

    # validate var_type
    var_type_str = str(var_type).strip()

    # Use dictionary dispatch to get both the index and the XML tag.
    try:
        get_type_segment, _, tag_to_set = _VARIABLE_TYPE_MAP[var_type_str]
    except KeyError:
        LOGGER.error("Invalid or unsupported var_type: %r", var_type_str)
        return

    # validate var_id
    try:
        var_id_int = int(var_id)
    except (TypeError, ValueError):
        LOGGER.error("Invalid var_id: %r", var_id)
        return
    if var_id_int <= 0:
        LOGGER.error("var_id must be positive, got: %s", var_id)
        return

    # Validate value to push
    try:
        float(var_value)
    except (TypeError, ValueError):
        LOGGER.error(f"Value: {var_value} is not valid or None; nothing to push for var_id={var_id}")
        return

    # check if there is a change to write location
    current_val= pull_from_isy_var(self, var_type, var_id, CALC = True)

    # only write if required
    if current_val != float(var_value):        
        # Build canonical path without double slashes
        path = f"/rest/vars/{tag_to_set}/{get_type_segment}/{var_id}/{var_value}"
        LOGGER.info(f"Pushing cur:{current_val} new:{var_value} path:{path}")
        try:
            resp = self.isy.cmd(path)
            # Optional: log response for diagnostics
            rtxt = resp.decode("utf-8", errors="replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
            LOGGER.debug("ISY push response for %s: %s", path, rtxt)
        except RuntimeError as exc:
            if 'ISY info not available' in str(exc):
                LOGGER.info(f"ISY info not available on {path}")
            else:
                LOGGER.exception("RuntimeError on path {path}")
            return
        except Exception as exc:
            LOGGER.exception("%s:, ISY push failed for %s: %s", self.name, path, exc)


def pull_from_isy_var(self, var_type: int | str, var_id: int | str, CALC = False):
    """
    Pull a variable from ISY using path segments,
    parse the XML, and update state if the transformed value changed.
    """
    LOGGER.debug(f"Pull from isy var_type:{var_type}, var_id:{var_id}, CALC={CALC}")

    # validate var_type
    var_type_str = str(var_type).strip()

    # Use dictionary dispatch to get both the index and the XML tag.
    try:
        get_type_segment, tag_to_find, _ = _VARIABLE_TYPE_MAP[var_type_str]
    except KeyError:
        LOGGER.error("Invalid or unsupported var_type: %r", var_type_str)
        return

    # validate var_id
    try:
        var_id_int = int(var_id)
    except (TypeError, ValueError):
        LOGGER.error("Invalid var_id: %r", var_id)
        return
    if var_id_int <= 0:
        LOGGER.error("var_id must be positive, got: %s", var_id)
        return

    path = f"/rest/vars/get/{get_type_segment}/{var_id}"

    # Fetch
    try:
        resp = self.isy.cmd(path)
        # Optional: log response for diagnostics
        rtxt = resp.decode("utf-8", errors="replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
        LOGGER.debug("ISY get response for %s: %s", path, rtxt)
    except RuntimeError as exc:
        if 'ISY info not available' in str(exc):
            LOGGER.info(f"ISY info not available on {path}")
        else:
            LOGGER.exception("RuntimeError on path {path}")
        return
    except Exception as exc:
        LOGGER.exception("%s:, ISY get failed for %s", path, exc)
        return

    # Parse XML based on the determined tag
    val_str: Optional[str] = None
    prec_str: Optional[str] = None
    try:
        root = ET.fromstring(rtxt)
        # parse val or init
        val_str = root.findtext(f".//{tag_to_find}")
        if val_str is None:
            LOGGER.error("No <%s> element in ISY response for %s", tag_to_find, path)
            return
        new_raw = int(val_str.strip())

        # parse prec            
        prec_div = 1
        prec_str = root.findtext(f".//prec")
        if prec_str:
            prec_div = int(prec_str.strip()) * 10
            if prec_div <= 0:
                prec_div = 1
        calc = new_raw / prec_div

        # Update only if UPDATE == True & changed versus the currently stored transformed value
        LOGGER.debug(f"NO UPDATE: raw:{new_raw}, prec:{prec_div}, calc{calc}")
        if CALC:
            return calc
        else:
            return new_raw

    except ET.ParseError as exc:
        LOGGER.exception("Failed to parse XML for %s: %s", path, exc)
        return
    except ValueError as exc:
        LOGGER.exception("Value in <%s> is not an int for %s (val=%r): %s", tag_to_find, path, val_str, exc)
        return
    except Exception as ex:
        LOGGER.error(f"{self.name}: parse error {ex}", exc_info = True)
        return
