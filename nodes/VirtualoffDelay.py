"""
This module defines the VirtualoffDelay class for the udi-Virtual-pg3 NodeServer.

This node represents a virtual switch that automatically turns off after a
configurable delay.

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
TIMER = 2
RESET = OFF

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
    "delay": FieldSpec(driver="DUR", default=0, data_type="state"),
}


class VirtualoffDelay(Node):
    id = "virtualoffdelay"

    """Represents a virtual switch that automatically turns off after a delay.

    When turned on, this node starts a timer for a configurable duration.
    Once the timer expires, the node automatically turns itself off.
    """

    def __init__(self, poly, primary, address, name):
        """Initializes the VirtualoffDelay node.

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

        # Timer
        self.timer = None
        self._initialize_timer()

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.STOP, self.stop, address)

    def start(self):
        """Performs startup tasks, loads persistent data, and retrieves configuration."""
        LOGGER.info(f"start: delayswitch:{self.name}")

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
            self.timer = Timer(0, self._off_delay)
        except Exception as ex:
            LOGGER.error(f"Failed to initialize timer: {ex}")
            self.timer = None

    def stop(self):
        """Cleans up the timer and sets the final state upon node stop."""
        LOGGER.info(f"stop: ondelay:{self.name}")
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        # for onDelay we want to end up on
        if self.data["switch"] == TIMER:
            self.data["switch"] = RESET
            store_values(self)
        LOGGER.info(f"stopping:{self.name}")

    def DON_cmd(self, command=None):
        """Starts the off-delay timer; turns off immediately if delay is zero."""
        LOGGER.info(f"{self.name}, {command}")
        delay = self.data["delay"]
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        try:
            if delay > 0:
                self.timer = Timer(delay, self._off_delay)
                self.timer.start()
                self.data["switch"] = TIMER
                self.setDriver("ST", TIMER)
                self.reportCmd("TIMER")
            else:
                self.setDriver("ST", ON)
                self.reportCmd("DON")
                self._off_delay()
        except Exception as ex:
            LOGGER.error(f"Error in DON_cmd:{ex}")
            return
        store_values(self)
        LOGGER.debug("Exit")

    def _off_delay(self):
        """Callback function executed by the timer to turn the switch off."""
        LOGGER.info("enter off delay")
        self.data["switch"] = OFF
        self.setDriver("ST", OFF)
        self.reportCmd("DOF")
        store_values(self)
        LOGGER.debug("Exit")

    def DOF_cmd(self, command=None):
        """Forcibly sets the switch to OFF and cancels any active timer."""
        LOGGER.info(f"{self.name}, {command}")
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.data["switch"] = OFF
        self.setDriver("ST", OFF)
        self.reportCmd("DOF")
        store_values(self)
        LOGGER.debug("Exit")

    def set_delay_cmd(self, command):
        """Sets the off-delay duration in seconds."""
        LOGGER.info(f"{self.name}, {command}")
        delay = int(command.get("value"))
        self.data["delay"] = delay
        self.setDriver("DUR", delay)
        self.reportCmd("DUR", value=delay)
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
    DUR: Duration (Delay)
    """
    drivers = [
        {"driver": "ST", "value": OFF, "uom": 25, "name": "Status"},
        {
            "driver": "DUR",
            "value": OFF,
            "uom": 58,
            "name": "Delay",
        },  # uom 58, duration in seconds
    ]

    """
    Commands that this node can handle.
    Should match the 'accepts' section of the nodedef file.
    """
    commands = {
        "DON": DON_cmd,
        "DOF": DOF_cmd,
        "SETDELAY": set_delay_cmd,
        "QUERY": query,
    }
