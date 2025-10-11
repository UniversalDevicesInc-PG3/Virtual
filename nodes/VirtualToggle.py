"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

VirtualToggle class
"""
# std libraries
from threading import Timer

# external libraries
from udi_interface import Node, LOGGER

# local imports
from utils.node_funcs import FieldSpec, load_persistent_data, store_values, get_config_data

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
	"switch":      FieldSpec(driver="ST", default=OFF, data_type="state"),
	"ondelay":     FieldSpec(driver="DUR", default=1, data_type="state"),
	"offdelay":    FieldSpec(driver="GV0", default=1, data_type="state"),
}


class VirtualToggle(Node):
    id = 'virtualtoggle'

    """ This class is for DON/DOF virtual switches, which oscillate according
    to time duration On and Off. This device can be made a controller/responder
    as part of a scene to provide easy indication or control.  It can also be
    used as control or status in a program and manipulated by then or else.
    It will receive DON, ST will moved to ONTIMER(2) for DUR seconds,
    sending DON at the beginning, then moved to OFFTIMER(3), for GV0 seconds,
    immediately sending DOF.
    It will not accept DUR or GV0 = 0
    DFON will move ST to On and send DFON, cancelling oscillation.
    DFOF will move ST to Off and send DFOF, cancelling oscillation.    

    Drivers & commands:
    ST 0,1,2,3: is used to report ON/OFF/ONTIMER/OFFTIMER status in the ISY
    DUR: integer, time on delay duration in seconds, > 0
    GV0: integer, time off delay duration in seconds, > 0
    don_cmd: Sets the node to ON if ST = ON or OFF, if ON or OFF TIMER nothing
    dof_cmd: Sets the node to OFF, if ST = ON or OFF, if ON or OFF TIMER nothing
    dfon_cmd: Sets the node to ON, cancels further oscillations
    dfof_cmd: Sets the node to OFF, cancels further oscillations
    set_on_delay_cmd: set the onDelay
    set_off_delay_cmd: set the offDelay
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

        # default variables and drivers
        self.data = {field: spec.default for field, spec in FIELDS.items()}

        # timer
        self.timer = None
        self._initialize_timer()        

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.STOP, self.stop, address)


    def start(self):
        """
        Start node and retrieve persistent data
        """
        LOGGER.info(f'start: toggle:{self.name}')

        # wait for controller start ready
        self.controller.ready_event.wait()

        # get persistent data from polyglot or depreciated: old db file, then delete db file
        load_persistent_data(self, FIELDS)
        
        # retrieve configuration data
        get_config_data(self, FIELDS)

        LOGGER.info(f"data:{self.data}")
        

    def _initialize_timer(self) -> None:
        """Initialize timer with proper error handling."""
        try:
            self.timer = Timer(0, self._on_delay)
        except Exception as ex:
            LOGGER.error(f"Failed to initialize timer: {ex}")
            self.timer = None


    def stop(self):
        """
        Stop node and clean-up TIMER status
        """
        LOGGER.info(f'stop: ondelay:{self.name}')
        if self.timer:
            self.timer.cancel()
        # for onDelay we want to end up on
        if self.data['switch'] == ONTIMER:
            self.data['switch'] = ON
        elif self.data['switch'] == OFFTIMER:
            self.data['switch'] = OFF
        store_values(self)
        LOGGER.info(f"stopping:{self.name}")


    def DON_cmd(self, command=None):
        """
        Set the driver to ONTIMER, send DON, start the timer, store values in db for persistence.
        If delay is zero, change to 1.
        """
        LOGGER.info(f"{self.name}, {command}")
        ondelay = max(self.data.get('ondelay', 1), 1)
        try:
            if self.timer and self.timer.is_alive():
                self.timer.cancel()
            self.timer = Timer(ondelay, self._on_delay)
            self.timer.start()
        except Exception as ex:
            LOGGER.error(f"Error in DON_cmd:{ex}")
            return
        self.data['switch'] = ONTIMER
        self.setDriver('ST', ONTIMER)
        self.reportCmd("DON")
        store_values(self)
        LOGGER.debug("Exit")
        

    def _on_delay(self):
        """
        Helper fucntion which the thread Timer calls to turn off the switch.
        Send DOF command.
        """
        LOGGER.info('enter on delay')
        self.data['switch'] = OFFTIMER
        self.setDriver('ST', OFFTIMER)
        self.reportCmd("DOF")
        store_values(self)
        offdelay = max(self.data.get('offdelay', 1), 1)
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.timer = Timer(offdelay, self._off_delay)
        self.timer.start()
        LOGGER.debug("Exit")


    def _off_delay(self):
        """
        Helper fucntion which the thread Timer calls to turn on the switch.
        Send DON command.
        """
        LOGGER.info('enter off delay')
        self.data['switch'] = ONTIMER
        self.setDriver('ST', ONTIMER)
        self.reportCmd("DON")
        store_values(self)
        ondelay = max(self.data.get('ondelay', 1), 1)
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.timer = Timer(ondelay, self._on_delay)
        self.timer.start()
        LOGGER.debug("Exit")


    def DOF_cmd(self, command=None):
        """
        If not in TIMER, Turn the driver off, report cmd DOF, store values in db for persistence.
        """
        LOGGER.info(f"{self.name}, {command}")
        if self.timer and self.timer.is_alive():
            LOGGER.info("Switch, is mid TIMER, waiting for DON/DOF")
        else:
            self.data['switch'] = OFF
            self.setDriver('ST', OFF)
            self.reportCmd("DOF")
        store_values(self)
        LOGGER.debug("Exit")

        
    def DFON_cmd(self, command=None):
        """
        Force the driver on, report cmd DFON, store values in db for persistence.
        """
        LOGGER.info(f"{self.name}, {command}")
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.data['switch'] = ON
        self.setDriver('ST', ON)
        self.reportCmd("DFON")
        store_values(self)
        LOGGER.debug("Exit")


    def DFOF_cmd(self, command=None):
        """
        Force the driver off, report cmd DFOF, store values in db for persistence.
        """
        LOGGER.info(f"{self.name}, {command}")
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.data['switch'] = OFF
        self.setDriver('ST', OFF)
        self.reportCmd("DFOF")
        store_values(self)
        LOGGER.debug("Exit")


    def set_on_dur_cmd(self, command):
        """
        Setting of onDelay duration, 0-99999 sec
        """
        LOGGER.info(f"{self.name}, {command}")
        ondelay = max(int(command.get('value', 1)), 1)
        self.data['ondelay'] = ondelay
        self.setDriver('DUR', ondelay)
        self.reportCmd("DUR", value=ondelay)
        store_values(self)
        LOGGER.debug("Exit")


    def set_off_dur_cmd(self, command):
        """
        Setting of offDelay duration, 0-99999 sec
        """
        LOGGER.info(f"{self.name}, {command}")
        offdelay = max(int(command.get('value', 1)), 1)
        self.data['offdelay'] = offdelay
        self.setDriver('GV0', offdelay)
        self.reportCmd("GV0", value=offdelay)
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
        {'driver': 'DUR', 'value': 1, 'uom': 58, 'name': "onDuration"}, # uom 58, duration in seconds
        {'driver': 'GV0', 'value': 1, 'uom': 58, 'name': "offDuration"}, # uom 58, duration in seconds
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
        'SETONDUR': set_on_dur_cmd,
        'SETOFFDUR': set_off_dur_cmd,
        'QUERY': query,
    }

        
