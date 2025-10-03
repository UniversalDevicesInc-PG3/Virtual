"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

VirtualonDelay class
"""
# std libraries
from threading import Timer

# external libraries
from udi_interface import Node, LOGGER

# local imports
from utils.node_funcs import FieldSpec, load_persistent_data, store_values

# constants

OFF = 0
ON = 1
TIMER = 2

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
	"switch":      FieldSpec(driver="ST", default=OFF, data_type="state"),
	"delay":       FieldSpec(driver="DUR", default=OFF, data_type="state"),
}


class VirtualonDelay(Node):
    id = 'virtualondelay'

    """ This class represents an onDelay virtual switch / relay / light.
    This device can be made a controller/responder as part of a scene to
    provide easy indication or control.  It can also be used as control
    or status in a program and manipulated by then or else.
    It will receive DON, then DUR seconds later send DON.
    DOF received is immediate DOF send
    DOF needed to reset ST to zero or OFF
    If DUR = 0, acts as normal switch.
    ST will follow input DON/DOF

    Drivers & commands:
    ST 0,1: is used to report ON/OFF status in the ISY
    DUR: integer, time delay duration in seconds
    setOn: Sets the node to ON delayed by onDelay
    setOFF: Sets the node to OFF, immediate
    SetOnDelay: set the onDelay
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
    
    def __init__(self, poly, primary, address, name):
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
        super().__init__(poly, primary, address, name)

        self.poly = poly
        self.primary = primary
        self.controller = poly.getNode(self.primary)
        self.address = address
        self.name = name

        # timer
        self.timer = Timer(0, self._on_delay)

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
        if self.data['switch'] == TIMER:
            self.data['switch'] = ON
        LOGGER.info(f"data:{self.data}")
        

    def set_on_cmd(self, command=None):
        """
        Turn the driver on, report cmd DON, store values in db for persistence.
        """
        LOGGER.info(f"{self.name}, {command}")
        switch = self.data['switch']
        delay = self.data['delay']
        if switch == 1:
            LOGGER.info('Switch already on, return')
            return
        
        self.data['switch'] = TIMER
        self.setDriver('ST', TIMER)
        store_values(self)
        if delay > 0:
            self.timer = Timer(delay, self._on_delay)
            self.timer.start()
        else:
            self.reportCmd("DON")
        LOGGER.debug("Exit")

        
    def _on_delay(self):
        LOGGER.info('enter on delay')
        self.data['switch'] = ON
        self.setDriver('ST', ON)
        store_values(self)
        self.reportCmd("DON")
        LOGGER.debug("Exit")
        
        
    def set_off_cmd(self, command=None):
        """
        Turn the driver off, report cmd DOF, store values in db for persistence.
        """
        LOGGER.info(f"{self.name}, {command}")
        switch = self.data['switch']
        if switch == OFF:
            LOGGER.info('Switch already off, return')
            return
        self.timer.cancel()
        self.data['switch'] = OFF
        self.setDriver('ST', OFF)
        self.reportCmd("DOF")
        store_values(self)
        LOGGER.debug("Exit")

        
    def set_delay_cmd(self, command):
        LOGGER.info(f"{self.name}, {command}")
        delay = int(command.get('value'))
        self.data['delay'] = delay
        self.setDriver('DUR', delay)
        self.reportCmd("DUR", value=delay)
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
        {'driver': 'ST', 'value': OFF, 'uom': 25, 'name': "Status"},
        {'driver': 'DUR', 'value': OFF, 'uom': 58, 'name': "Delay"}, # uom 58, duration in seconds
    ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
                    'DON': set_on_cmd,
                    'DOF': set_off_cmd,
                    'SETDELAY': set_delay_cmd,
                    'QUERY': query,
                }
    
