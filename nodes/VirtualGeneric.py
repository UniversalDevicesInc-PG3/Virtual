"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

VirtualGeneric class
"""
# std libraries
import time
import os.path
import shelve
import subprocess

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
    ST 0,1: is used to report ON/OFF status in the ISY
    setOn: Sets the node to ON
    setOFF: Sets the node to OFF
    setLevelUp: Increase the level +3
    setLevelDown: Decrease the level -3
    setDim: Set the level to a percentage or value 0-100
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
        specific node
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
          self.getDataFromId() every longPoll
          self.deleteDB() when ISY deletes the node or discovers it gone
        """
        super().__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.primary = primary
        self.controller = polyglot.getNode(self.primary)
        self.address = address
        self.name = name

        self.level = 0 # create as zero

        self.poly.subscribe(self.poly.START, self.start, address)
        # self.poly.subscribe(self.poly.POLL, self.poll)

    def start(self):
        """ START event subscription above """
        self.createDBfile()
        
    # poll NOT required in this node, keeping as comment for easy debugging
    """
    def poll(self, flag):
        if 'longPoll' in flag:
            LOGGER.debug(f"longPoll {self.name}")
        else:
            LOGGER.debug(f"shortPoll {self.name}")
    """

    def createDBfile(self):
        """
        DB file is used to store switch status across ISY & Polyglot reboots.
        """
        try:
            _key = 'key' + str(self.address)
            _name = str(self.name).replace(" ","_")
            _file = f"db/{_name}.db"
            LOGGER.info(f'Checking to see existence of db file: {_file}')
            if os.path.exists(_file):
                LOGGER.info('...file exists')
                self.retrieveValues()
            else:
                s = shelve.open(f"db/{_name}", writeback=False)
                s[_key] = { 'switchStatus': self.level }
                time.sleep(2)
                s.close()
                LOGGER.info("...file didn\'t exist, created successfully")
        except Exception as ex:
                LOGGER.error(f"createDBfile error: {ex}")

    def deleteDB(self):
        """ Called from Controller when node is deleted """
        _name = str(self.name).replace(" ","_")
        _file = f"db/{_name}.db"
        if os.path.exists(_file):
            LOGGER.debug(f'Deleting db: {_file}')
            subprocess.run(["rm", _file])

    def storeValues(self):
        _key = 'key' + str(self.address)
        _name = str(self.name).replace(" ","_")
        s = shelve.open(f"db/{_name}", writeback=False)
        try:
            s[_key] = { 'switchStatus': self.level}
        finally:
            s.close()
        LOGGER.debug('Values Stored')
        
    def retrieveValues(self):
        _key = 'key' + str(self.address)
        _name = str(self.name).replace(" ","_")
        s = shelve.open(f"db/{_name}", writeback=False)
        try:
            existing = s[_key]
        finally:
            s.close()
        LOGGER.info('Retrieving Values %s', existing)
        self.level = existing['switchStatus']
        self.setDriver('ST', self.level)

    def setOn(self, command=None):
        LOGGER.debug(command)
        self.setDriver('ST', 100)
        self.level = 100
        self.storeValues()

    def setOff(self, command=None):
        LOGGER.debug(command)
        self.setDriver('ST', 0)
        self.level = 0
        self.storeValues()

    def setLevelUp(self, command=None):
        LOGGER.debug(command)
        _level = int(self.level) + 3
        if _level > 100: _level = 100
        self.setDriver('ST', _level)
        self.level = _level
        self.storeValues()

    def setLevelDown(self, command=None):
        LOGGER.debug(command)
        _level = int(self.level) - 3
        if _level < 0: _level = 0
        self.setDriver('ST', _level)
        self.level = _level
        self.storeValues()

    def setDim(self, command):
        LOGGER.debug(command)
        _level = int(command.get('value'))
        self.setDriver('ST', _level)
        self.level = _level
        self.storeValues()

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
        {'driver': 'ST', 'value': 0, 'uom': 56, 'name': "Status"},
    ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
                    'DON': setOn,
                    'DOF': setOff,
                    'BRT': setLevelUp,
                    'DIM': setLevelDown,
                    'setDim': setDim,
                    'QUERY': query,
                }

