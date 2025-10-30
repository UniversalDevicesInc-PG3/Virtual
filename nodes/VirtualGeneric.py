"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

VirtualGeneric class
"""
# std libraries
pass

#external libraries
from udi_interface import Node, LOGGER

# personal libraries
from utils.node_funcs import FieldSpec, load_persistent_data, store_values, get_config_data

# constants
OFF = 0
FULL = 100
INC = 2
DIMLOWERLIMIT = 5 # Dimmer, keep onlevel to a minimum level

STATIC = 0
DYNAMIC = 1


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
    "status":           FieldSpec(driver="ST", default=FULL, data_type="state"),
    "onlevel":    FieldSpec(driver="OL", default=FULL, data_type="state"),
    "onleveltype":    FieldSpec(driver="GV0", default=STATIC, data_type="state"),
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
    def __init__(self, poly, primary, address, name):
        """ Sent by the Controller class node.
        :param polyglot: Reference to the Interface class
        :param primary: Parent address
        :param address: This nodes address
        :param name: This nodes name
        
        subscribes:
        START: used to create/check/load DB file
        NOTE: POLL: not needed as no timed updates for this node
        """
        super().__init__(poly, primary, address, name)

        self.poly = poly
        self.primary = primary
        self.controller = poly.getNode(self.primary)
        self.address = address
        self.name = name
        self.lpfx = f'{address}:{name}'
        
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

        # retrieve configuration data
        get_config_data(self, FIELDS)

        self.query()
        LOGGER.info(f"data:{self.data}")
        

    def DON_cmd(self, command=None):
        LOGGER.info(f"{self.lpfx}, {command}")
        onlevel = self.data.get('onlevel', FULL)
        self.data['status'] = onlevel if onlevel > OFF else FULL
        self.setDriver('ST', self.data['status'])
        self.setDriver('OL', self.data['onlevel'])
        self.reportCmd("DON")
        store_values(self)
        LOGGER.debug("Exit")


    def DOF_cmd(self, command=None):
        LOGGER.info(f"{self.lpfx}, {command}")
        status = self.data.get('status', OFF)
        # set onlevel if onleveltype = dynamic
        if status not in (OFF, FULL) and self.data['onleveltype'] == DYNAMIC:
            self.data['onlevel'] = status
            self.setDriver('OL', self.data.get('onlevel'))
        self.data['status'] = OFF
        self.setDriver('ST', OFF)
        self.reportCmd("DOF")
        store_values(self)
        LOGGER.debug("Exit")


    def DFON_cmd(self, command=None):
        LOGGER.info(f"{self.lpfx}, {command}")
        self.data['status'] = FULL
        self.setDriver('ST', FULL)
        self.setDriver('OL', self.data.get('onlevel'))
        self.reportCmd("DFON")
        store_values(self)
        LOGGER.debug("Exit")


    def DFOF_cmd(self, command=None):
        LOGGER.info(f"{self.lpfx}, {command}")
        status = self.data.get('status', OFF)
        # set onlevel if onleveltype = dynamic
        if status not in (OFF, FULL) and self.data['onleveltype'] == DYNAMIC:
            self.data['onlevel'] = status
            self.setDriver('OL', self.data.get('onlevel'))
        self.data['status'] = OFF
        self.setDriver('ST', OFF)
        self.reportCmd("DFOF")
        store_values(self)
        LOGGER.debug("Exit")


    def BRT_cmd(self, command=None):
        LOGGER.info(f"{self.lpfx}, {command}")
        status = min(int(self.data.get('status', OFF)) + INC, FULL)
        if self.data['onleveltype'] == DYNAMIC:
            self.data['onlevel'] = status
            self.setDriver('OL', self.data.get('onlevel'))
        self.data['status'] = status
        self.setDriver('ST', status)
        self.reportCmd("BRT")
        store_values(self)
        LOGGER.debug("Exit")


    def DIM_cmd(self, command=None):
        LOGGER.info(f"{self.lpfx}, {command}")
        status = max(int(self.data.get('status', FULL)) - INC, OFF)
        if status == OFF:
            onlevel = DIMLOWERLIMIT if self.data['onleveltype'] == DYNAMIC else None
        else:
            onlevel = status if self.data['onleveltype'] == DYNAMIC else None
        if onlevel:    
            self.setDriver('OL', onlevel)
            self.data['onlevel'] = onlevel
        self.data['status'] = status
        self.setDriver('ST', status)
        self.reportCmd("DIM")
        store_values(self)
        LOGGER.debug("Exit")


    def set_ST_cmd(self, command):
        LOGGER.info(f"{self.lpfx}, {command}")
        status = int(command.get('value'))
        if status == OFF:
            status = DIMLOWERLIMIT
        self.data['status'] = status
        self.setDriver('ST', status)
        self.setDriver('OL', self.data.get('onlevel'))
        self.reportCmd("ST", value=status)
        store_values(self)
        LOGGER.debug("Exit")


    def set_OL_cmd(self, command):
        LOGGER.info(f"{self.lpfx}, {command}")
        level = int(command.get('value'))
        if level == OFF:
            self.data['onlevel'] = DIMLOWERLIMIT
        self.data['onlevel'] = level
        self.setDriver('OL', level)
        self.reportCmd("OL", value=level)
        store_values(self)
        LOGGER.debug("Exit")


    def OL_toggle_type_cmd(self, command=None):
        """
        Toggle the onlovel driver, report OLTT command, store values in db for persistence.
        """
        LOGGER.info(f"{self.lpfx}, {command}")
        # Toggle between 0[STATIC] and 1[DYNAMIC]
        self.data['onleveltype'] ^= 1
        onleveltype = self.data['onleveltype']
        self.setDriver('GV0', onleveltype)
        self.reportCmd("OLTT", value=onleveltype)
        store_values(self)        
        LOGGER.debug("Exit")


    def query(self, command=None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        LOGGER.info(f"{self.lpfx}, {command}")
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
        {'driver': 'ST', 'value': OFF, 'uom': 56, 'name': "State"},
        {'driver': 'OL', 'value': FULL, 'uom': 56, 'name': "onLevel"},
        {'driver': 'GV0', 'value': STATIC, 'uom': 2, 'name': "onLevelType"},
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
                    'SETST': set_ST_cmd,
                    'SETOL': set_OL_cmd,
                    'OLTT': OL_toggle_type_cmd,
                    'QUERY': query,
                }

