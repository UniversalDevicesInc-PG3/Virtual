"""
This module defines the VirtualToggle class for the udi-Virtual-pg3 NodeServer.

This node represents a virtual toggling switch that cycles on and off
at configurable intervals.

(C) 2025 Stephen Jenkins
"""

# std libraries
from threading import Timer

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
ONTIMER = 2
OFFTIMER = 3

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
    "ondelay": FieldSpec(driver="DUR", default=1, data_type="state"),
    "offdelay": FieldSpec(driver="GV0", default=1, data_type="state"),
}


class VirtualToggle(Node):
    id = "virtualtoggle"

    """Represents a virtual toggling switch that cycles on and off.

    This node uses two configurable delays for 'on' and 'off' durations,
    creating a continuous toggling effect until a 'DOF' command is received.
    """

    def __init__(self, poly, primary, address, name):
        """Initializes the VirtualToggle node.

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

        # timer
        self.timer = None
        self._initialize_timer()

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.STOP, self.stop, address)

    def start(self):
        """Performs startup tasks, loads persistent data, and retrieves configuration."""
        LOGGER.info(f"start: toggle:{self.name}")

        # wait for controller start ready
        self.controller.ready_event.wait()

        # get persistent data from polyglot or depreciated: old db file, then delete db file
        load_persistent_data(self, FIELDS)

        # retrieve configuration data
        get_config_data(self, FIELDS)

        LOGGER.info(f"data:{self.data}")

    def _initialize_timer(self) -> None:
        """Initializes the internal timer object with error handling."""
        try:
            self.timer = Timer(0, self._on_delay)
        except Exception as ex:
            LOGGER.error(f"Failed to initialize timer: {ex}")
            self.timer = None

    def stop(self):
        """Cleans up the timer and sets the final state upon node stop."""
        LOGGER.info(f"stop: ondelay:{self.name}")
        if self.timer:
            self.timer.cancel()
        # for onDelay we want to end up on
        if self.data["switch"] == ONTIMER:
            self.data["switch"] = ON
        elif self.data["switch"] == OFFTIMER:
            self.data["switch"] = OFF
        store_values(self)
        LOGGER.info(f"stopping:{self.name}")

    def DON_cmd(self, command=None):
        """Starts the toggling sequence, beginning with the ON state."""
        LOGGER.info(f"{self.name}, {command}")
        ondelay = max(self.data.get("ondelay", 1), 1)
        try:
            if self.timer and self.timer.is_alive():
                self.timer.cancel()
            self.timer = Timer(ondelay, self._on_delay)
            self.timer.start()
        except Exception as ex:
            LOGGER.error(f"Error in DON_cmd:{ex}")
            return
        self.data["switch"] = ONTIMER
        self.setDriver("ST", ONTIMER)
        self.reportCmd("DON")
        store_values(self)
        LOGGER.debug("Exit")

    def _on_delay(self):
        """Callback function to transition from ON to the OFF timer state."""
        LOGGER.info("enter on delay")
        self.data["switch"] = OFFTIMER
        self.setDriver("ST", OFFTIMER)
        self.reportCmd("DOF")
        store_values(self)
        offdelay = max(self.data.get("offdelay", 1), 1)
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.timer = Timer(offdelay, self._off_delay)
        self.timer.start()
        LOGGER.debug("Exit")

    def _off_delay(self):
        """Callback function to transition from OFF to the ON timer state."""
        LOGGER.info("enter off delay")
        self.data["switch"] = ONTIMER
        self.setDriver("ST", ONTIMER)
        self.reportCmd("DON")
        store_values(self)
        ondelay = max(self.data.get("ondelay", 1), 1)
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.timer = Timer(ondelay, self._on_delay)
        self.timer.start()
        LOGGER.debug("Exit")

    def DOF_cmd(self, command=None):
        """Sets the switch to OFF, but only if it is not currently in a timer state."""
        LOGGER.info(f"{self.name}, {command}")
        if self.timer and self.timer.is_alive():
            LOGGER.info("Switch, is mid TIMER, waiting for DON/DOF")
        else:
            self.data["switch"] = OFF
            self.setDriver("ST", OFF)
            self.reportCmd("DOF")
        store_values(self)
        LOGGER.debug("Exit")

    def DFON_cmd(self, command=None):
        """Forcibly sets the switch to ON and stops the toggling sequence."""
        LOGGER.info(f"{self.name}, {command}")
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.data["switch"] = ON
        self.setDriver("ST", ON)
        self.reportCmd("DON")
        store_values(self)
        LOGGER.debug("Exit")

    def DFOF_cmd(self, command=None):
        """Forcibly sets the switch to OFF and stops the toggling sequence."""
        LOGGER.info(f"{self.name}, {command}")
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.data["switch"] = OFF
        self.setDriver("ST", OFF)
        self.reportCmd("DOF")
        store_values(self)
        LOGGER.debug("Exit")

    def set_on_dur_cmd(self, command):
        """Sets the ON duration for the toggle sequence."""
        LOGGER.info(f"{self.name}, {command}")
        ondelay = max(int(command.get("value", 1)), 1)
        self.data["ondelay"] = ondelay
        self.setDriver("DUR", ondelay)
        self.reportCmd("DUR", value=ondelay)
        store_values(self)
        LOGGER.debug("Exit")

    def set_off_dur_cmd(self, command):
        """Sets the OFF duration for the toggle sequence."""
        LOGGER.info(f"{self.name}, {command}")
        offdelay = max(int(command.get("value", 1)), 1)
        self.data["offdelay"] = offdelay
        self.setDriver("GV0", offdelay)
        self.reportCmd("GV0", value=offdelay)
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
    58: Duration in seconds

    Driver controls:
    ST: Status (Status)
    DUR: Duration (onDuration)
    GV0: Custom Control 0 (offDuration)
    """
    drivers = [
        {"driver": "ST", "value": OFF, "uom": 25, "name": "Status"},
        {
            "driver": "DUR",
            "value": 1,
            "uom": 58,
            "name": "onDuration",
        },  # uom 58, duration in seconds
        {
            "driver": "GV0",
            "value": 1,
            "uom": 58,
            "name": "offDuration",
        },  # uom 58, duration in seconds
    ]

    """
    Commands that this node can handle.
    Should match the 'accepts' section of the nodedef file.
    """
    commands = {
        "DON": DON_cmd,
        "DOF": DOF_cmd,
        "DFON": DFON_cmd,
        "DFOF": DFOF_cmd,
        "SETONDUR": set_on_dur_cmd,
        "SETOFFDUR": set_off_dur_cmd,
        "QUERY": query,
    }
