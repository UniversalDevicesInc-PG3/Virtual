
# standard imports
import re, shelve
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
        migrated, old_data = _check_db_files_and_migrate(data)
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
        if spec.driver and spec.data_type == "state":
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




    


