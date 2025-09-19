"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

VirtualSwitch class
"""
# std libraries
pass

# external libraries
from udi_interface import Node, LOGGER

# local imports
from utils.node_funcs import FieldSpec, load_persistent_data, store_values

# constants

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
	"switch":           FieldSpec(driver="ST", default=0, data_type="state"),
}


class VirtualSwitch(Node):
    id = 'virtualswitch'

    """ This class represents a simple virtual switch / relay / light.
    This device can be made a controller/responder as part of a scene to
    provide easy indication or control.  It can also be used as control
    or status in a program and manipulated by then or else.

    Drivers & commands:
    ST 0,1: is used to report ON/OFF status in the ISY
    setOn: Sets the node to ON
    setOFF: Sets the node to OFF
    Query: Is used to report status of the node

    Class Methods(generic):
    setDriver('ST', 1, report = True, force = False):
        This sets the driver 'ST' to 1. If report is False we do not report
        it to Polyglot/ISY. If force is True, we send a report even if the
        value hasn't changed.
    reportDriver(driver, force): report the driver value to Polyglot/ISY if
        it has changed.  if force is true, send regardless.
    reportDrivers(): Forces a full update of all drivers to Polyglot/ISY.
    query(): Called when ISY sends a query request to Polyglot for this
        specific node.
    """
    
    def __init__(self, polyglot, primary, address, name):
        """ Sent by the Controller class node.
        :param polyglot: Reference to the Interface class
        :param primary: Parent address
        :param address: This nodes address
        :param name: This nodes name
        
        class variables:
        self.data['switch'] internal storage of 0,1 ON/OFF

        subscribes:
        START: used to create/check/load DB file
        
        NOTE: POLL: not needed as no timed updates for this node
        
        Controller node calls:
          self.deleteDB() when ISY deletes the node or discovers it gone
        """
        super().__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.primary = primary
        self.controller = polyglot.getNode(self.primary)
        self.address = address
        self.name = name

        # default variables and drivers
        self.data = {field: spec.default for field, spec in FIELDS.items()}

        self.poly.subscribe(self.poly.START, self.start, address)


    def start(self):
        """
        Start node and retrieve persistent data
        """
        LOGGER.info(f'start: switch:{self.name}')

        # wait for controller start ready
        self.controller.ready_event.wait()

        # get persistent data from polyglot or depreciated: old db file, then delete db file
        load_persistent_data(self, FIELDS)
        LOGGER.info(f"data:{self.data}")
        

    def set_on_cmd(self, command=None):
        """
        Turn the driver on, report cmd DON, store values in db for persistence.
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['switch'] = 1
        self.setDriver('ST', 1)
        self.reportCmd("DON")
        store_values(self)
        LOGGER.debug("Exit")

        
    def set_off_cmd(self, command=None):
        """
        Turn the driver off, report cmd DOF, store values in db for persistence.
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['switch'] = 0
        self.setDriver('ST', 0)
        self.reportCmd("DOF")
        store_values(self)
        LOGGER.debug("Exit")

        
    def toggle_cmd(self, command=None):
        """
        Toggle the driver, report cmd DON/DOF as appropriate, store values in db for persistence.
        """
        LOGGER.info(f"{self.name}, {command}")
        if self.data.get('switch'):
            self.set_off_cmd()
        else:
            self.set_on_cmd()                
        LOGGER.debug("Exit")


    def query(self, command=None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        LOGGER.info(f"{self.name}, {command}")
        self.reportDrivers()
        LOGGER.debug("Exit")
        

    hint = '0x01020700'
    # home, controller, scene controller
    # Hints See: https://github.com/UniversalDevicesInc/hints
    
    
    """
    This is an array of dictionary items containing the variable names(drivers)
    values and uoms(units of measure) from ISY. This is how ISY knows what kind
    of variable to display. Check the UOM's in the WSDK for a complete list.
    UOM 2 is boolean so the ISY will display 'True/False'
    """
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 25, 'name': "Status"},
    ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
                    'DON': set_on_cmd,
                    'DOF': set_off_cmd,
                    'TOGGLE': toggle_cmd,
                    'QUERY': query,
                }

