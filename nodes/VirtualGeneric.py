"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

VirtualGeneric class
"""
import time
import os.path
import shelve
import subprocess

import udi_interface

LOGGER = udi_interface.LOGGER

class VirtualGeneric(udi_interface.Node):
    id = 'virtualgeneric'

    """
    This is the class that all the Nodes will be represented by. You will
    add this to Polyglot/ISY with the interface.addNode method.

    Class Variables:
    self.primary: String address of the parent node.
    self.address: String address of this Node 14 character limit.
                  (ISY limitation)
    self.added: Boolean Confirmed added to ISY

    Class Methods:
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
        """
        Optional.
        Super runs all the parent class necessities. You do NOT have
        to override the __init__ method, but if you do, you MUST call super.

        :param polyglot: Reference to the Interface class
        :param primary: Parent address
        :param address: This nodes address
        :param name: This nodes name
        """
        super().__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.primary = primary
        self.controller = polyglot.getNode(self.primary)
        self.address = address
        self.name = name

        self.level = 0

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)

    def start(self):
        """
        Optional.
        This method is called after Polyglot has added the node per the
        START event subscription above
        """
        self.createDBfile()
        
    def poll(self, flag):
        if 'longPoll' in flag:
            LOGGER.debug(f"longPoll {self.name}")
        else:
            LOGGER.debug(f"shortPoll {self.name}")

    def createDBfile(self):
        try:
            _name = str(self.name).replace(" ","_")
            _key = 'key' + str(self.address)
            _check = _name + '.db'
            LOGGER.info(f'Checking to see existence of db file: {_check}')
            if os.path.exists(_check):
                LOGGER.info('...file exists')
                self.retrieveValues()
            else:
                s = shelve.open(_name, writeback=True)
                s[_key] = { 'switchStatus': self.level }
                time.sleep(2)
                s.close()
                LOGGER.info("...file didn\'t exist, created successfully")
        except Exception as ex:
                LOGGER.error(f"createDBfile error: {ex}")

    def deleteDB(self, command):
        _name = str(self.name)
        _name = _name.replace(" ","_")
        _key = 'key' + str(self.address)
        _check = _name + '.db'
        if os.path.exists(_check):
            LOGGER.debug('Deleting db')
            subprocess.run(["rm", _check])
        time.sleep(1)
        self.firstPass = True
        self.start()

    def storeValues(self):
        _name = str(self.name)
        _name = _name.replace(" ","_")
        _key = 'key' + str(self.address)
        s = shelve.open(_name, writeback=True)
        try:
            s[_key] = { 'switchStatus': self.level}
        finally:
            s.close()
        LOGGER.info('Storing Values')
        self.listValues()

    def listValues(self):
        _name = str(self.name)
        _name = _name.replace(" ","_")
        _key = 'key' + str(self.address)
        s = shelve.open(_name, writeback=True)
        try:
            existing = s[_key]
        finally:
            s.close()
        LOGGER.info(existing)

    def retrieveValues(self):
        _name = str(self.name)
        _name = _name.replace(" ","_")
        _key = 'key' + str(self.address)
        s = shelve.open(_name, writeback=True)
        try:
            existing = s[_key]
        finally:
            s.close()
        LOGGER.info('Retrieving Values %s', existing)
        self.level = existing['switchStatus']
        self.setDriver('ST', self.level)

    def setOn(self, command):
        self.setDriver('ST', 100)
        self.level = 100
        self.storeValues()

    def setOff(self, command):
        self.setDriver('ST', 0)
        self.level = 0
        self.storeValues()

    def setLevelUp(self, command):
        _level = int(self.level) + 3
        if _level > 100: _level = 100
        self.setDriver('ST', _level)
        self.level = _level
        self.storeValues()

    def setLevelDown(self, command):
        _level = int(self.level) - 3
        if _level < 0: _level = 0
        self.setDriver('ST', _level)
        self.level = _level
        self.storeValues()

    def setDim(self, command):
        _level = int(command.get('value'))
        self.setDriver('ST', _level)
        self.level = _level
        self.storeValues()

    def getDataFromID(self):
        pass

    def query(self, command=None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
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

