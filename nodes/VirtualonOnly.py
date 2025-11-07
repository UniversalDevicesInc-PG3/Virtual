"""
This module defines the VirtualonOnly class for the udi-Virtual-pg3 NodeServer.

This node represents a virtual switch that can only be turned on, acting
as a momentary trigger.

(C) 2025 Stephen Jenkins
"""

# std libraries
# none

# external libraries
from udi_interface import Node, LOGGER

# local imports
from utils.node_funcs import (
    FieldSpec,
    load_persistent_data,
    store_values,
    get_config_data,
)

# constants

OFF = 0
ON = 1

# @dataclass(frozen=True)
# class FieldSpec:
#     driver: Optional[str]  # e.g., "GV1" or None if not pushed to a driver
#     default: Any           # per-field default
#     data_type: str         # denote data type (state or config)
#     def should_update(self) -> bool:
#             """Return True if this field should be pushed to a driver."""
#             return self.driver is not None and self.data_type == "state"

# Single source of truth for field names, driver codes, and defaults
FIELDS: dict[str, FieldSpec] = {
    # State variables (pushed to drivers)
    "switch": FieldSpec(driver="ST", default=OFF, data_type="state"),
}


class VirtualonOnly(Node):
    id = "virtualononly"

    """Represents a virtual switch that can only be turned on (momentary).

    This node automatically turns itself off after reporting the 'ON' state,
    making it suitable for triggering scenes or programs that only need a
    single 'ON' command.
    """

    def __init__(self, poly, primary, address, name):
        """Initializes the VirtualonOnly node.

        Args:
            poly (udi_interface.Polyglot): The Polyglot interface object.
            primary (str): The address of the primary node (the Controller).
            address (str): The address of this node.
            name (str): The name of this node.
        """
        super().__init__(poly, primary, address, name)

        self.poly = poly
        self.primary = primary
        self.controller = poly.getNode(self.primary)
        self.address = address
        self.name = name

        # default variables and drivers
        self.data = {field: spec.default for field, spec in FIELDS.items()}

        self.poly.subscribe(self.poly.START, self.start, address)

    def start(self):
        """Performs startup tasks, loads persistent data, and retrieves configuration."""
        LOGGER.info(f"start: switch:{self.name}")

        # wait for controller start ready
        self.controller.ready_event.wait()

        # get persistent data from polyglot or depreciated: old db file, then delete db file
        load_persistent_data(self, FIELDS)

        # retrieve configuration data
        get_config_data(self, FIELDS)

        LOGGER.info(f"data:{self.data}")

    def DON_cmd(self, command=None):
        """Sets the switch to ON, reports the command, then immediately sets to OFF."""
        LOGGER.info(f"{self.name}, {command}")
        self.data["switch"] = ON
        self.setDriver("ST", ON)
        self.reportCmd("DON")
        store_values(self)
        LOGGER.debug("Exit")

    def DOF_cmd(self, command=None):
        """Sets the switch to OFF. This command is accepted but does not report."""
        LOGGER.info(f"{self.name}, {command}")
        self.data["switch"] = OFF
        self.setDriver("ST", OFF)
        store_values(self)
        LOGGER.debug("Exit")

    def query(self, command=None):
        """Reports the current state of all drivers to the ISY."""
        LOGGER.info(f"{self.name}, {command}")
        self.reportDrivers()
        LOGGER.debug("Exit")

    hint = "0x01020700"
    # home, controller, scene controller
    # Hints See: https://github.com/UniversalDevicesInc/hints

    """
    UOMs:
    25: index

    Driver controls:
    ST: Status (Status)
    """
    drivers = [
        {"driver": "ST", "value": OFF, "uom": 25, "name": "Status"},
    ]

    """
    Commands that this node can handle.
    Should match the 'accepts' section of the nodedef file.
    """
    commands = {
        "DON": DON_cmd,
        "DOF": DOF_cmd,
        "QUERY": query,
    }
