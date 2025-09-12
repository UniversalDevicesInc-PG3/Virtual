"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

VirtualSwitch class
"""
# std libraries
import os.path, shelve

# external libraries
import udi_interface

# constants
LOGGER = udi_interface.LOGGER

class VirtualSwitch(udi_interface.Node):
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
        self.switchStatus internal storage of 0,1 ON/OFF

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

        self.switchStatus = 0 # create as OFF

        self.poly.subscribe(self.poly.START, self.start, address)


    def start(self):
        """
        Start node and retrieve persistent data
        """
        LOGGER.info(f'start: switch:{self.name}')

        # wait for controller start ready
        self.controller.ready_event.wait()

        # get persistent data from polyglot or depreciated: old db file, then delete db file
        self.load_persistent_data()
        

    def _checkDBfile_and_migrate(self):
        """
        Checks for the deprecated DB file, migrates data to Polyglot's
        persistent storage, and then deletes the old file.
        This helper function is called by load_persistent_data once during startup.
        """
        _name = str(self.name).replace(" ","_")
        old_file_path = os.path.join("db", f"{_name}.db")

        if not os.path.exists(old_file_path):
            LOGGER.info(f'[{self.name}] No old DB file found at: {old_file_path}')
            return False, None

        LOGGER.info(f'[{self.name}] Old DB file found, migrating data...')

        _key = 'key' + str(self.address)
        try:
            with shelve.open(os.path.join("db", _name), flag='r') as s:
                existing_data = s.get(_key)
        except Exception as ex:
            LOGGER.error(f"[{self.name}] Error opening or reading old shelve DB: {ex}")
            return False, None

        if existing_data:
            # Delete the old file after successful read
            try:
                LOGGER.info(f'[{self.name}] Deleting old DB file: {old_file_path}')
                os.remove(old_file_path)
            except OSError as ex:
                LOGGER.error(f"[{self.name}] Error deleting old DB file: {ex}")

        return True, existing_data


    def load_persistent_data(self):
        """
        Load state from Polyglot persistence or migrate from old DB file.
        """
        # Try to load from new persistence format first
        data = self.controller.Data.get(self.name)

        if data:
            self.switchStatus = data.get('switchStatus', 0)
            LOGGER.info(f"{self.name}, Loaded from persistence: status={self.switchStatus}")
        else:
            LOGGER.info(f"{self.name}, No persistent data found. Checking for old DB file...")
            is_migrated, old_data = self._checkDBfile_and_migrate()
            if is_migrated and old_data:
                self.switchStatus = old_data.get('switchStatus', 0)
                LOGGER.info(f"{self.name}, Migrated from old DB file. status={self.switchStatus}")
            else:
                LOGGER.info(f"{self.name}, No old DB file found.")
        # Store the migrated data in the new persistence format
        self.storeValues()
        # Initial of ISY
        self.setDriver('ST', self.switchStatus)


    def storeValues(self):
        """
        Store persistent data to Polyglot Data structure.
        """
        data_to_store = {
            'switchStatus': self.switchStatus
        }
        self.controller.Data[self.name] = data_to_store
        LOGGER.debug(f'Values stored for {self.name}: {data_to_store}')
        
        
    def setOn(self, command=None):
        """
        Turn the driver on, report cmd DON, store values in db for persistence.
        """
        LOGGER.info(f"{self.name}, {command}")
        self.switchStatus = 1
        self.setDriver('ST', 1)
        self.reportCmd("DON", 2)
        self.storeValues()
        LOGGER.debug("Exit")

        
    def setOff(self, command=None):
        """
        Turn the driver off, report cmd DOF, store values in db for persistence.
        """
        LOGGER.info(f"{self.name}, {command}")
        self.setDriver('ST', 0)
        self.reportCmd("DOF", 2)
        self.switchStatus = 0
        self.storeValues()
        LOGGER.debug("Exit")

        
    def toggle(self, command=None):
        """
        Toggle the driver, report cmd DON/DOF as appropriate, store values in db for persistence.
        """
        LOGGER.info(f"{self.name}, {command}")
        if self.switchStatus:
            self.setOff()
        else:
            self.setOn()                
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
                    'DON': setOn,
                    'DOF': setOff,
                    'TOGGLE': toggle,
                    'QUERY': query,
                }

