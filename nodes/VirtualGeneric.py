"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

VirtualGeneric class
"""
# std libraries
pass

#external libraries
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
    "level":           FieldSpec(driver="OL", default=-1, data_type="state"),
    "level_stored":    FieldSpec(driver=None, default=100, data_type="state"),
}


class VirtualGeneric(Node):
    id = 'virtualgeneric'

    """ This class represents a simple virtual generic or dimmer switch / relay.
    This device can be made a controller/responder as part of a scene to
    provide easy indication or control. It can also be used as control
    or status in a program and manipulated by then or else.

    Drivers & commands:
    ST,OL 0,1: is used to report ON/OFF status in the ISY
    cmd_DON: Sets the node to ON, last level, with ramp
    cmd_DOF: Sets the node to OFF, 0, with ramp
    cmd_DFON: Sets the node to 100, fast
    cmd_DFOF: Sets the node to 0, fast
    cmd_BRT: Increase the level +3
    cmd_DIM: Decrease the level -3
    cmd_set_OL: Set the level to a percentage or value 0-100
    
    Query: Is used to report status of the node

    """
    def __init__(self, polyglot, primary, address, name):
        """ Sent by the Controller class node.
        :param polyglot: Reference to the Interface class
        :param primary: Parent address
        :param address: This nodes address
        :param name: This nodes name
        
        class variables:
        self.switchStatus internal storage of 0,1 ON/OFF

        subscribes:
        START: used to create/check/load DB file
        NOTE: POLL: not needed as no timed updates for this node
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
        LOGGER.info(f'start: generic/dimmer:{self.name}')

        # wait for controller start ready
        self.controller.ready_event.wait()
        
        # get persistent data from polyglot or depreciated: old db file, then delete db file
        load_persistent_data(self, FIELDS)
        self.query()
        LOGGER.info(f"data:{self.data}")

    def DON_cmd(self, command=None):
        LOGGER.info(f"{self.name}, {command}")
        if self.data.get('level_stored', 0) > 0:
            self.data['level'] = self.data.get('level_stored')
        else:
            self.data['level'] = 100
        self.setDriver('OL', self.data.get('level'))
        self.reportCmd("DON")
        store_values(self)
        LOGGER.debug("Exit")


    def DOF_cmd(self, command=None):
        LOGGER.info(f"{self.name}, {command}")
        level = self.data.get('level', 0)
        if level not in [0, 100]:
            self.data['level_stored'] = level
        self.data['level'] = 0
        self.setDriver('OL', 0)
        self.reportCmd("DOF")
        store_values(self)
        LOGGER.debug("Exit")


    def DFON_cmd(self, command=None):
        LOGGER.info(f"{self.name}, {command}")
        self.data['level'] = 100
        self.setDriver('OL', 100)
        self.reportCmd("DFON")
        store_values(self)
        LOGGER.debug("Exit")


    def DFOF_cmd(self, command=None):
        LOGGER.info(f"{self.name}, {command}")
        level = self.data.get('level', 0)
        if level not in [None, 0, 100]:
            self.data['level_stored'] = level 
        self.data['level'] = 0
        self.setDriver('OL', 0)
        self.reportCmd("DFOF")
        store_values(self)
        LOGGER.debug("Exit")


    def BRT_cmd(self, command=None):
        LOGGER.info(f"{self.name}, {command}")
        level = int(self.data.get('level', 0)) + 2
        if level > 100: level = 100
        self.data['level_stored'] = level
        self.data['level'] = level
        self.setDriver('OL', level)
        self.reportCmd("BRT")
        store_values(self)
        LOGGER.debug("Exit")


    def DIM_cmd(self, command=None):
        LOGGER.info(f"{self.name}, {command}")
        level = int(self.data.get('level', 100)) - 2
        if level <= 0:
            level = 0
            self.data['level_stored'] = 10 # keep stored to a minimum level
        else:
            self.data['level_stored'] = level
        self.data['level'] = level
        self.setDriver('OL', level)
        self.reportCmd("DIM")
        store_values(self)
        LOGGER.debug("Exit")


    def set_OL_cmd(self, command):
        LOGGER.info(f"{self.name}, {command}")
        level = int(command.get('value'))
        if level != 0:
            self.data['level_stored'] = level
        else:
            self.data['level_stored'] = 10
        self.data['level'] = level
        self.setDriver('OL', level)
        self.reportCmd("OL", value=level)
        store_values(self)
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
        

    hint = '0x01020900'
    # home, controller, dimmer switch
    # Hints See: https://github.com/UniversalDevicesInc/hints

    
    """
    This is an array of dictionary items containing the variable names(drivers)
    values and uoms(units of measure) from ISY. This is how ISY knows what kind
    of variable to display. Check the UOM's in the WSDK for a complete list.
    UOM 2 is boolean so the ISY will display 'True/False'
    """
    drivers = [
        {'driver': 'OL', 'value': 0, 'uom': 56, 'name': "Level"},
    ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
                    'DON': DON_cmd,
                    'DOF': DOF_cmd,
                    'DFON': DFON_cmd,
                    'DFOF': DFOF_cmd,
                    'BRT': BRT_cmd,
                    'DIM': DIM_cmd,
                    'OL': set_OL_cmd,
                    'QUERY': query,
                }

