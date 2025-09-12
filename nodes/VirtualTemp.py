"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

VirtualTemp class
"""
# std libraries
import time, os.path, shelve
from xml.dom.minidom import parseString

# external libraries
import udi_interface

# constants
LOGGER = udi_interface.LOGGER
ISY = udi_interface.ISY
TYPELIST = ['/set/2/',  #1
            '/init/2/', #2
            '/set/1/',  #3
            'init/1/'   #4
           ]
GETLIST = [' ',
           '/2/',
           '/2/',
           '/1/',
           '/1/'
          ]

class VirtualTemp(udi_interface.Node):
    id = 'virtualtemp'

    """ This class represents a simple virtual temperature sensor.
    This device can be populated directly or from variables.
    Conversion to/from raw or F/C is supported.  Finally, the data can
    be sent to a variable or used directly.  Programs can use the data
    as well.

    Drivers & commands:
    'ST'  : current temperature        
    'GV1' : previous temperature       
    'GV2' : time since last update
    'GV3' : high temperature           
    'GV4' : low temperature            
    'GV5' : average of  high to low 
    'GV6' : action1 push to or pull from variable   
    'GV7' : variable type integer or state
    'GV8' : variable id
    'GV9' : action 2 push to or pull from variable  
    'GV10': variable type 2 integer or state, current value or init value
    'GV11': variable id 2   
    'GV12': raw to precision
    'GV13': Fahrenheit to Celsius

    'setTemp'           : set temperature to specific number
    'setAction[1,2]'    : set Action 1,2 None, push, pull
    'setAction[1,2]id'  : set Action 1,2 id
    'setAction[1,2]type': set Action 1,2 type
    'setCtoF'           : set Celsius to Fahrenheit
    'setRawToPrec'      : set Raw To Precision
    'resetStats'        : reset Statistics
    'deleteDB'          : delete Database
    
    Class Methods (generic):
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
        self.prevVal, tempVal storage of last, current temperature value
        self.lastUpdateTime timestamp
        self.highTemp, lowTemp range of high temp, set to None on init
         self.previousHigh, previousLow storage of previous range
        self.prevAvgTemp, currentAvgTemp storage of averages
        self.action1, action2 none, push, pull
        self.action1id, action1id id of variable,  0=None, 1 - 400
        self.action1type, action2type  State var or init, Int var or init, 1 - 4
        self.RtoPrec Raw to precision conversion
        self.CtoF Celsius to Fahrenheit conversion
        self.pullError True or False

        subscribes:
        START: used to create/check/load DB file
        POLL: shortPoll for updates
        """
        super().__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.primary = primary
        self.controller = polyglot.getNode(self.primary)
        self.address = address
        self.name = name

        self.prevVal = 0.0
        self.tempVal = 0.0
        self.lastUpdateTime = 0.0
        self.highTemp = None
        self.lowTemp = None
        self.previousHigh = None
        self.previousLow = None
        self.prevAvgTemp = 0.0
        self.currentAvgTemp = 0.0
        self.action1 = 0
        self.action1id = 0
        self.action1type = 0
        self.action2 = 0
        self.action2id = 0
        self.action2type = 0
        self.RtoPrec = 0
        self.CtoF = 0
        self.pullError = False

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)
        

    def start(self):
        """
        Start node and retrieve persistent data
        """
        LOGGER.info(f'start: switch:{self.name}')

        # wait for controller start ready
        self.controller.ready_event.wait()

        # get persistent data from polyglot or depreciated: old db file, then delete db file
        self.load_persistent_data()

        self.isy = ISY(self.poly)
        self.lastUpdateTime = time.time()
        self.setDriver('GV2', 0.0)

        
    def poll(self, flag):
        """ POLL event subscription above """
        if 'shortPoll' in flag:
            LOGGER.debug(f"shortPoll {self.name}")
            self.update()
            

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
                self.prevVal = old_data.get('prevVal', 0)
                self.tempVal = old_data.get('tempVal', 0)
                self.highTemp = old_data.get('highTemp', 0)
                self.lowTemp = old_data.get('lowTemp', 0)
                self.previousHigh = old_data.get('previousHigh', 0)
                self.previousLow = old_data.get('previousLow', 0)
                self.prevAvgTemp = old_data.get('prevAvgTemp', 0)
                self.currentAvgTemp = old_data.get('currentAvgTemp', 0)
                self.action1 = old_data.get('action1', 0)
                self.action1id = old_data.get('action1id', 0)
                self.action1type = old_data.get('action1type', 0)
                self.action2 = old_data.get('action2', 0) 
                self.action2id = old_data.get('action2id', 0)
                self.action2type = old_data.get('action2type', 0)
                self.RtoPrec = old_data.get('RtoPrec', 0)
                self.CtoF = old_data.get('CtoF', 0)
                # Store the migrated data in the new persistence format
                self.storeValues()
                LOGGER.info(f"{self.name}, Migrated from old DB file. status={self.switchStatus}")
            else:
                LOGGER.info(f"{self.name}, No old DB file found.")
                # Set initial values if no data exists
                self.switchStatus = 0
        self.setDriver('ST', self.tempVal)
        self.setDriver('GV1', self.prevVal)
        self.setDriver('GV3', self.highTemp)
        self.setDriver('GV4', self.lowTemp)
        self.setDriver('GV5', self.currentAvgTemp)
        self.setDriver('GV6', self.action1)
        self.setDriver('GV8', self.action1id)
        self.setDriver('GV7', self.action1type)
        self.setDriver('GV9', self.action2)
        self.setDriver('GV11', self.action2id)
        self.setDriver('GV10', self.action2type)
        self.setDriver('GV12', self.RtoPrec)
        self.setDriver('GV13', self.CtoF)


    def storeValues(self):
        """
        Store persistent data to Polyglot Data structure.
        """
        data_to_store = {
            'action1': self.action1,
            'action1type': self.action1type,
            'action1id': self.action1id,
            'action2': self.action2,
            'action2type': self.action2type,
            'action2id': self.action2id,
            'RtoPrec': self.RtoPrec,
            'CtoF': self.CtoF,
            'prevVal': self.prevVal,
            'tempVal': self.tempVal,
            'highTemp': self.highTemp,
            'lowTemp': self.lowTemp,
            'previousHigh': self.previousHigh,
            'previousLow': self.previousLow,
            'prevAvgTemp': self.prevAvgTemp,
            'currentAvgTemp': self.currentAvgTemp,
           }
        self.controller.Data[self.name] = data_to_store
        LOGGER.debug(f'Values stored for {self.name}: {data_to_store}')


    def setAction1(self, command):
        self.action1 = int(command.get('value'))
        self.setDriver('GV6', self.action1)
        self.storeValues()
        

    def setAction1id(self, command):
        self.action1id = int(command.get('value'))
        self.setDriver('GV8', self.action1id)
        self.storeValues()
        

    def setAction1type(self, command):
        self.action1type = int(command.get('value'))
        self.setDriver('GV7', self.action1type)
        self.storeValues()
        

    def setAction2(self, command):
        self.action2 = int(command.get('value'))
        self.setDriver('GV9', self.action2)
        self.storeValues()
        

    def setAction2id(self, command):
        self.action2id = int(command.get('value'))
        self.setDriver('GV11', self.action2id)
        self.storeValues()
        

    def setAction2type(self, command):
        self.action2type = int(command.get('value'))
        self.setDriver('GV10', self.action2type)
        self.storeValues()
        

    def setCtoF(self, command):
        self.CtoF = int(command.get('value'))
        self.setDriver('GV13', self.CtoF)
        self.resetStats()
        self.storeValues()
        

    def setRawToPrec(self, command):
        self.RtoPrec = int(command.get('value'))
        self.setDriver('GV12', self.RtoPrec)
        self.resetStats()
        self.storeValues()
        

    def pushTheValue(self, command1, command2):
        _type = str(command1)
        _id = str(command2)
        LOGGER.info(f'Pushing to ISY /rest/vars/{_type}{_id}/{self.tempVal}')
        self.isy.cmd(f'/rest/vars/{_type}{_id}/{self.tempVal}')
        

    def pullFromID(self, command1, command2):
        _type = str(command1)
        _id = str(command2)
        _newTemp = 0
        r = ""
        if command2 == 0:
            pass
        else:
            try:
                #LOGGER.info('Pulling from http://%s/rest/vars/get%s%s/', self.parent.isy, _type, _id)
                r = str(self.isy.cmd('/rest/vars/get' + _type + _id))
                LOGGER.debug(f"get value: {r}")
                rx = parseString(r)
                rx = rx.getElementsByTagName("var")[0]
                rx = rx.getElementsByTagName("val")[0]
                rx = rx.firstChild
                r = rx.toxml(encoding=None, standalone=None)
                # _content = (r.getElementsByTagName("var")[0].getElementsByTagName("val")[0].firstChild).toxml()
                LOGGER.info(f'Type-Id:{_type}-{_id}, Content: {r}')
            except Exception as e:
                LOGGER.error('There was an error with the value pull: ' + str(e))
                self.pullError = True
            try:
                _newTemp = int(r)
            except Exception as e:
                LOGGER.error('An error occured during the content parse: ' + str(e))
                self.pullError = True
            if not self.pullError:
                _testValRtoP = (_newTemp / 10)
                _testValRtoPandCtoF = round(((_testValRtoP * 1.8) + 32), 1)
                _testValCtoF = round(((_newTemp * 1.8) + 32), 1)
                if self.tempVal not in [_testValRtoP, _testValCtoF, _testValRtoPandCtoF, _newTemp]:
                    self.setTemp({'cmd': 'data', 'value': _newTemp})
            self.pullError = False
            

    def setTemp(self, command):
        LOGGER.debug(command)
        self.setDriver('GV2', 0.0)
        self.lastUpdateTime = time.time()
        self.prevVal = self.tempVal
        self.setDriver('GV1', self.prevVal)
        self.tempVal = float(command.get('value'))

        if command.get('cmd') == 'data':
            if self.RtoPrec == 1:
                LOGGER.info('Converting from raw')
                self.tempVal = round((self.tempVal / 10), 1)
            if self.CtoF == 1:
                LOGGER.info('converting C to F')
                self.tempVal = round(((self.tempVal * 1.8) + 32), 1)
            
        self.setDriver('ST', self.tempVal)
        self.checkHighLow(self.tempVal)
        self.storeValues()

        if self.action1 == 1:
            _type = TYPELIST[(self.action1type - 1)]
            self.pushTheValue(_type, self.action1id)
            LOGGER.info('Action 1 Pushing')

        if self.action2 == 1:
            _type = TYPELIST[(self.action2type - 1)]
            self.pushTheValue(_type, self.action2id)
            LOGGER.info('Action 2 Pushing')
            

    def checkHighLow(self, command):
        LOGGER.info(f"{command}, low:{self.lowTemp}, high:{self.highTemp}")
        if command != None:
            self.previousHigh = self.highTemp
            self.previousLow = self.lowTemp
            if self.highTemp == None:
                comp = -1000.0
            else:
                comp = self.highTemp
            if command > comp:
                self.setDriver('GV3', command)
                self.highTemp = command
            if self.lowTemp == None:
                comp = 1000.0
            else:
                comp = self.lowTemp
            if command < comp:
                self.setDriver('GV4', command)
                self.lowTemp = command
            if self.highTemp != None and self.lowTemp != None:
                self.prevAvgTemp = self.currentAvgTemp
                self.currentAvgTemp = round(((self.highTemp + self.lowTemp) / 2), 1)
                self.setDriver('GV5', self.currentAvgTemp)
                

    def resetStats(self, command=None):
        LOGGER.info(f'Resetting Stats: {command}')
        self.lowTemp = None
        self.highTemp = None
        self.prevAvgTemp = 0
        self.currentAvgTemp = 0
        self.prevTemp = None
        self.tempVal = None
        self.setDriver('GV1', 0)
        self.setDriver('GV5', 0)
        self.setDriver('GV3', 0)
        self.setDriver('GV4', 0)
        self.setDriver('ST', 0)
        self.storeValues()
        

    def update(self):
        """ called by Node shortPoll """
        _sinceLastUpdate = round(((time.time() - self.lastUpdateTime) / 60), 1)
        if _sinceLastUpdate < 1440:
            self.setDriver('GV2', _sinceLastUpdate)
        else:
            self.setDriver('GV2', 1440)
        if self.action1 == 2:
            self.pullFromID(GETLIST[self.action1type], self.action1id)
        if self.action2 == 2:
            self.pullFromID(GETLIST[self.action2type], self.action2id)
            
            
    def query(self, command=None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        LOGGER.debug(command)
        self.reportDrivers()


    # Hints See: https://github.com/UniversalDevicesInc/hints
    #hint = [1,2,3,4]
    
    
    """
    This is an array of dictionary items containing the variable names(drivers)
    values and uoms(units of measure) from ISY. This is how ISY knows what kind
    of variable to display. Check the UOM's in the WSDK for a complete list.
    UOM 2 is boolean so the ISY will display 'True/False'
    """
    drivers = [
               {'driver': 'ST', 'value': 0, 'uom': 17},   #current
               {'driver': 'GV1', 'value': 0, 'uom': 17},  #previous
               {'driver': 'GV2', 'value': 0, 'uom': 45},  #update time
               {'driver': 'GV3', 'value': 0, 'uom': 17},  #high
               {'driver': 'GV4', 'value': 0, 'uom': 17},  #low
               {'driver': 'GV5', 'value': 0, 'uom': 17},  #avg high - low
               {'driver': 'GV6', 'value': 0, 'uom': 25},  #action1 type
               {'driver': 'GV7', 'value': 0, 'uom': 25},  #variable type
               {'driver': 'GV8', 'value': 0, 'uom': 56},  #variable id
               {'driver': 'GV9', 'value': 0, 'uom': 25},  #action 2
               {'driver': 'GV10', 'value': 0, 'uom': 25}, #variable type
               {'driver': 'GV11', 'value': 0, 'uom': 56}, #variable id
               {'driver': 'GV12', 'value': 0, 'uom': 25}, #r to p
               {'driver': 'GV13', 'value': 0, 'uom': 25}, #f to c         
              ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
        'setTemp': setTemp,
        'setAction1': setAction1,
        'setAction1id': setAction1id,
        'setAction1type': setAction1type,
        'setAction2': setAction2,
        'setAction2id': setAction2id,
        'setAction2type': setAction2type,
        'setCtoF': setCtoF,
        'setRawToPrec': setRawToPrec,
        'resetStats': resetStats,
                }


