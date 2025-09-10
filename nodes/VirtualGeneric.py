"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

VirtualGeneric class
"""
# std libraries
import os.path, shelve

#external libraries
import udi_interface

# constants
LOGGER = udi_interface.LOGGER

class VirtualGeneric(udi_interface.Node):
    id = 'virtualgeneric'

    """ This class represents a simple virtual generic or dimmer switch / relay.
    This device can be made a part of a scene to provide easy indication
    for the scene.  It can also be used as control or status in a program
    and manipulated by then or else.

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
        POLL: not needed as no timed updates for this node
        Controller node calls:
          self.deleteDB() when ISY deletes the node or discovers it gone
        """
        super().__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.primary = primary
        self.controller = polyglot.getNode(self.primary)
        self.address = address
        self.name = name

        self.level = 0 # create as zero
        self.level_stored = 100 # create as zero

        self.poly.subscribe(self.poly.START, self.start, address)
        # self.poly.subscribe(self.poly.POLL, self.poll)

    def start(self):
        """
        Start node and retrieve persistent data
        """
        # wait for controller start ready
        self.controller.ready_event.wait()
        
        # get persistent data from polyglot or depreciated: old db file, then delete db file
        self.load_persistent_data()
        
    # poll NOT required in this node, keeping as comment for easy debugging
    """
    def poll(self, flag):
        if 'longPoll' in flag:
            LOGGER.debug(f"longPoll {self.name}")
        else:
            LOGGER.debug(f"shortPoll {self.name}")
    """


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
            self.level = data.get('switchStatus', 0)
            self.level_stored = data.get('switchStored', 0)
            LOGGER.info(f"switch:{self.name}, Loaded from persistence: level={self.level}, stored={self.level_stored}")
        else:
            LOGGER.info(f"switch:{self.name}, No persistent data found. Checking for old DB file...")
            is_migrated, old_data = self._checkDBfile_and_migrate()
            if is_migrated and old_data:
                self.level = old_data.get('switchStatus', 0)
                self.level_stored = old_data.get('switchStored', 0)
                # Store the migrated data in the new persistence format
                self.storeValues()
                LOGGER.info(f"switch:{self.name}, Migrated from old DB file. level={self.level}, stored={self.level_stored}")
            else:
                LOGGER.info(f"switch:{self.name}, No old DB file found.")
                # Set initial values if no data exists
                self.level = 0
                self.level_stored = 0
                

    def storeValues(self):
        """
        Store persistent data to Polyglot Data structure.
        """
        data_to_store = {
            'switchStatus': self.level,
            'switchStored': self.level_stored
        }
        self.controller.Data[self.name] = data_to_store
        LOGGER.debug(f'Values stored for {self.name}: {data_to_store}')

             
    def cmd_DON(self, command=None):
        LOGGER.debug(command)
        if self.level_stored > 0:
            self.level = self.level_stored
        else:
            self.level = 100
        self.setDriver('OL', self.level)
        self.reportCmd("DON", 2)
        self.storeValues()
        LOGGER.info(f"{self.name}:{command}, level:{self.level}, level_stored:{self.level_stored}")

    def cmd_DOF(self, command=None):
        LOGGER.debug(command)
        if self.level not in [0, 100]:
            self.level_stored = self.level
        self.level = 0
        self.setDriver('OL', self.level)
        self.reportCmd("DOF", 2)
        self.storeValues()
        LOGGER.info(f"{self.name}:{command}, level:{self.level}, level_stored:{self.level_stored}")

    def cmd_DFON(self, command=None):
        LOGGER.debug(command)
        self.level = 100
        self.setDriver('OL', self.level)
        self.reportCmd("DFON", 2)
        self.storeValues()
        LOGGER.info(f"{self.name}:{command}, level:{self.level}, level_stored:{self.level_stored}")

    def cmd_DFOF(self, command=None):
        LOGGER.debug(command)
        if self.level not in [0, 100]:
            self.level_stored = self.level
        self.level = 0
        self.setDriver('OL', self.level)
        self.reportCmd("DFOF", 2)
        self.storeValues()
        LOGGER.info(f"{self.name}:{command}, level:{self.level}, level_stored:{self.level_stored}")

    def cmd_BRT(self, command=None):
        LOGGER.debug(command)
        self.level = int(self.level) + 2
        if self.level > 100: self.level = 100
        self.level_stored = self.level
        self.setDriver('OL', self.level)
        self.reportCmd("BRT",2)
        self.storeValues()
        LOGGER.info(f"{self.name}:{command}, level:{self.level}, level_stored:{self.level_stored}")

    def cmd_DIM(self, command=None):
        LOGGER.debug(command)
        self.level = int(self.level) - 2
        if self.level <= 0:
            self.level = 0
            self.level_stored = 10
        else:
            self.level_stored = self.level
        self.setDriver('OL', self.level)
        self.reportCmd("DIM",2)
        self.storeValues()
        LOGGER.info(f"{self.name}:{command}, level:{self.level}, level_stored:{self.level_stored}")

    def cmd_set_OL(self, command):
        LOGGER.debug(command)
        self.level = int(command.get('value'))
        if self.level != 0:
            self.level_stored = self.level
        else:
            self.level_stored = 10
        self.setDriver('OL', self.level)
        self.reportCmd("OL", value=self.level)
        self.storeValues()
        LOGGER.info(f"{self.name}:{command}, level:{self.level}, level_stored:{self.level_stored}")

    def query(self, command=None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        LOGGER.debug(command)
        self.reportDrivers()

    # Hints See: https://github.com/UniversalDevicesInc/hints
    hint = '0x01020900'

    
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
                    'DON': cmd_DON,
                    'DOF': cmd_DOF,
                    'DFON': cmd_DFON,
                    'DFOF': cmd_DFOF,
                    'BRT': cmd_BRT,
                    'DIM': cmd_DIM,
                    'OL': cmd_set_OL,
                    'QUERY': query,
                }

