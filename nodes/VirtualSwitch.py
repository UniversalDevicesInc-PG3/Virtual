"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

VirtualSwitch class
"""
# std libraries
import time
import os.path
import shelve
import subprocess

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
        # self.poly.subscribe(self.poly.POLL, self.poll)

    def start(self):
        """
        Get off the ground and retrieve persistence data or create persistence db for node.
        """
        LOGGER.info(f'start: switch:{self.name}')
        self.createDBfile()
        LOGGER.info('started switch:{self.name}')
        
    """
    def poll(self, flag):
    # poll NOT required in this node, keeping as comment for easy debugging
        if 'longPoll' in flag:
            LOGGER.debug(f"longPoll {self.name}")
        else:
            LOGGER.debug(f"shortPoll {self.name}")
    """

    def createDBfile(self):
        """
        DB file is used to store switch status across ISY & Polyglot reboots.
        This function either retrieves or creates the db file with current status.
        """
        LOGGER.debug('start')
        try:
            _key = 'key' + str(self.address)
            _name = str(self.name).replace(" ","_")
            _file = f"db/{_name}.db"
            LOGGER.info(f'switch: {self.name}, checking for db file: {_file}')
            if os.path.exists(_file):
                LOGGER.info('...file exists')
                self.retrieveValues()
            else:
                s = shelve.open(f"db/{_name}", writeback=False)
                s[_key] = { 'switchStatus': self.switchStatus }
                time.sleep(2)
                s.close()
                LOGGER.info(f"switch:{self.name} file created")
        except Exception as ex:
                LOGGER.error(f"switch:{self.name} createDBfile error: {ex}", exc_info=True)
        LOGGER.debug('Exit')
                

    def deleteDB(self):
        """
        Called from Controller when node is deleted to keep things tidy.
        """
        LOGGER.debug('start')
        _name = str(self.name).replace(" ","_")
        _file = f"db/{_name}.db"
        if os.path.exists(_file):
            LOGGER.debug(f'Deleting db: {_file}')
            subprocess.run(["rm", _file])
        LOGGER.debug('Exit')
        
                
    def storeValues(self):
        """
        Called when status changes to store to db file for persistence.
        """
        LOGGER.debug('start')
        _key = 'key' + str(self.address)
        _name = str(self.name).replace(" ","_")
        s = shelve.open(f"db/{_name}", writeback=False)
        try:
            s[_key] = { 'switchStatus': self.switchStatus}
        finally:
            s.close()
        LOGGER.debug("Exit")
        
        
    def retrieveValues(self):
        """
        Pull from db file and set switchStatus for persistence.
        """
        _key = 'key' + str(self.address)
        _name = str(self.name).replace(" ","_")
        s = shelve.open(f"db/{_name}", writeback=False)
        try:
            existing = s[_key]
        finally:
            s.close()
        LOGGER.info('Retrieving Values %s', existing)
        self.switchStatus = existing['switchStatus']
        self.setDriver('ST', self.switchStatus)
        LOGGER.debug("Exit")

        
    def setOn(self, command=None):
        """
        Turn the driver on, report cmd DON, store values in db for persistence.
        """
        LOGGER.info(command)
        self.setDriver('ST', 1)
        self.reportCmd("DON", 2)
        self.switchStatus = 1
        self.storeValues()
        LOGGER.debug("Exit")

        
    def setOff(self, command=None):
        """
        Turn the driver off, report cmd DOF, store values in db for persistence.
        """
        LOGGER.info(command)
        self.setDriver('ST', 0)
        self.reportCmd("DOF", 2)
        self.switchStatus = 0
        self.storeValues()
        LOGGER.debug("Exit")

        
    def toggle(self, command=None):
        """
        Toggle the driver, report cmd DON/DOF as appropriate, store values in db for persistence.
        """
        LOGGER.info(command)
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
        LOGGER.info(command)
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

