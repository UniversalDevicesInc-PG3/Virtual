"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

VirtualTemp class
"""
# system imports
import os
import time
from datetime import datetime
import re
import shelve
import os.path
import subprocess
from xml.dom.minidom import parseString

# external imports
import udi_interface

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

        self.firstPass = True
        self.prevVal = 0.0
        self.tempVal = 0.0
        self.currentTime = 0.0
        self.lastUpdateTime = 0.0
        self.highTemp = -30.0
        self.lowTemp = 129.0
        self.previousHigh = 0
        self.previousLow = 0
        self.prevAvgTemp = 0
        self.currentAvgTemp = 0
        self.action1 = 0  # none, push, pull
        self.action1id = 0 # 0 - 400
        self.action1type = 0 # State var, State init, Int var, Int init
        self.action2 = 0
        self.action2id = 0
        self.action2type = 0
        self.RtoPrec = 0
        self.CtoF = 0
        self.pullError = False
        self.lastUpdate = '0000'

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)

    def start(self):
        """
        Optional.
        This method is called after Polyglot has added the node per the
        START event subscription above
        """
        self.isy = ISY(self.poly)
        self.currentTime = time.time()
        self.lastUpdateTime = time.time()
        self.setDriver('GV2', 0.0)
        self.createDBfile()
        if self.firstPass: self.resetStats(1)
        
    def poll(self, flag):
        if 'longPoll' in flag:
            LOGGER.debug(f"longPoll {self.name}")
        else:
            LOGGER.debug(f"shortPoll {self.name}")
            self.update()

    def setOn(self, command = None):
        pass

    def setOff(self, command = None):
        pass

    def createDBfile(self):
        _name = str(self.name)
        _name = _name.replace(" ","_")
        _key = 'key' + str(self.address)
        _check = _name + '.db'
        LOGGER.debug('Checking to see if %s exists', _check)
        if os.path.exists(_check):
            LOGGER.debug('The file does exists')
            self.retrieveValues()
            pass
        else:
            s = shelve.open(_name, writeback=True)
            s[_key] = { 'created': 'yes'}
            time.sleep(2)
            s.close()

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
            s[_key] = { 'action1': self.action1, 'action1type': self.action1type, 'action1id': self.action1id,
                        'action2': self.action2, 'action2type': self.action2type, 'action2id': self.action2id,
                        'RtoPrec': self.RtoPrec, 'CtoF': self.CtoF, 'prevVal': self.prevVal, 'tempVal': self.tempVal,
                        'highTemp': self.highTemp, 'lowTemp': self.lowTemp, 'previousHigh': self.previousHigh, 'previousLow': self.previousLow,
                        'prevAvgTemp': self.prevAvgTemp, 'currentAvgTemp': self.currentAvgTemp, 'firstPass': self.firstPass }
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
        self.prevVal = existing['prevVal']
        self.setDriver('GV1', self.prevVal)
        self.tempVal = existing['tempVal']
        self.setDriver('ST', self.tempVal)
        self.highTemp = existing['highTemp']
        self.setDriver('GV3', self.highTemp)
        self.lowTemp = existing['lowTemp']
        self.setDriver('GV4', self.lowTemp)
        self.previousHigh = existing['previousHigh']
        self.previousLow = existing['previousLow']
        self.prevAvgTemp = existing['prevAvgTemp']
        self.currentAvgTemp = existing['currentAvgTemp']
        self.setDriver('GV5', self.currentAvgTemp)
        self.action1 = existing['action1']# none, push, pull
        self.setDriver('GV6', self.action1)
        self.action1id = existing['action1id']
        self.setDriver('GV8', self.action1id)
        self.action1type = existing['action1type']
        self.setDriver('GV7', self.action1type)
        self.action2 = existing['action2'] 
        self.setDriver('GV9', self.action2)
        self.action2id = existing['action2id']
        self.setDriver('GV11', self.action2id)
        self.action2type = existing['action2type']
        self.setDriver('GV10', self.action2type)
        self.RtoPrec = existing['RtoPrec']
        self.setDriver('GV12', self.RtoPrec)
        self.CtoF = existing['CtoF']
        self.setDriver('GV13', self.CtoF)
        self.firstPass = existing['firstPass']

    def setTemp(self, command):
        self.checkHighLow(self.tempVal)
        self.storeValues()
        self.setDriver('GV2', 0.0)
        self.lastUpdateTime = time.time()
        self.prevVal = self.tempVal
        self.setDriver('GV1', self.prevVal)
        _temp = float(command.get('value'))

        self.tempVal = _temp

        _now = str(datetime.now())
        LOGGER.info(_now)

        if self.RtoPrec == 1:
            LOGGER.info('Converting from raw')
            self.tempVal = round((self.tempVal / 10), 1)
        if self.CtoF == 1:
            LOGGER.info('converting C to F')
            self.tempVal = round(((self.tempVal * 1.8) + 32), 1)
        self.setDriver('ST', _temp)
        self.tempVal = _temp

        if self.action1 == 1:
            _type = TYPELIST[(self.action1type - 1)]
            self.pushTheValue(_type, self.action1id)
            LOGGER.info('Action 1 Pushing')

        if self.action2 == 1:
            _type = TYPELIST[(self.action2type - 1)]
            self.pushTheValue(_type, self.action2id)
            LOGGER.info('Action 2 Pushing')

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
        self.resetStats(1)
        self.storeValues()

    def setRawToPrec(self, command):
        self.RtoPrec = int(command.get('value'))
        self.setDriver('GV12', self.RtoPrec)
        self.resetStats(1)
        self.storeValues()

    def pushTheValue(self, command1, command2):
        _type = str(command1)
        _id = str(command2)
        #LOGGER.info('Pushing to http://%s/rest/vars%s%s/%s', self.parent.isy, _type, _id, self.tempVal)
        self.isy.cmd('/rest/vars' + _type + _id + '/' + str(self.tempVal))

    def getDataFromID(self):
        if self.action1 == 2:
            _type = GETLIST[self.action1type]
            self.pullFromID(_type, self.action1id)
        if self.action2 == 2:
            _type = GETLIST[self.action2type]
            self.pullFromID(_type, self.action2id)

    def pullFromID(self, command1, command2):
        if command2 == 0:
            pass
        else:
            _type = str(command1)
            _id = str(command2)
            try:
                #LOGGER.info('Pulling from http://%s/rest/vars/get%s%s/', self.parent.isy, _type, _id)
                r = self.isy.cmd('/rest/vars/get' + _type + _id)
                LOGGER.debug(f'get value: {r}')
                r = parseString(r)
                # _content = str(r.content)p
                _content = r.getElementsByTagName("var")[0].getElementsByTagName("val")[0].firstChild.toxml()
                LOGGER.info('Content: %s', _content)
                time.sleep(float(self.controller.parseDelay))
                # _value = re.findall(r'(\d+|\-\d+)', _content)
                # LOGGER.info('Parsed: %s',_value)
                _newTemp = 0
            except Exception as e:
                LOGGER.error('There was an error with the value pull: ' + str(e))
                self.pullError = True
            try:
                # if command1 == '/2/' : _newTemp = int(_value[7])
                # if command1 == '/1/' : _newTemp = int(_value[5])
                _newTemp = int(_content)
            except Exception as e:
                LOGGER.error('An error occured during the content parse: ' + str(e))
                self.pullError = True
            if self.pullError:
                pass
            else:
                _testValRtoP = (_newTemp / 10)
                _testValRtoPandCtoF = round(((_testValRtoP * 1.8) + 32), 1)
                _testValCtoF = round(((_newTemp * 1.8) + 32), 1)
                if self.tempVal == _testValRtoP or self.tempVal == _testValCtoF or self.tempVal == _testValRtoPandCtoF or self.tempVal == _newTemp:
                    pass
                else:
                    # _lastUpdate = (str(_value[8])+'-'+str(_value[9])+':'+str(_value[10])+':'+str(_value[11]))
                    # _content = r.getElementsByTagName("var")[0].getElementsByTagName("ts")[0].firstChild.toxml()
                    # LOGGER.info(f'lastUpdate raw: {_content}')
                    # _lastUpdate = (str(_value[8])+'-'+str(_value[9])+':'+str(_value[10])+':'+str(_value[11]))
                    # self.lastUpdate = (_lastUpdate)
                    self.setTempFromData(_newTemp)
            self.pullError = False

    def setTempFromData(self, command):
        LOGGER.info('Last update: %s ', self.lastUpdate)
        #self.setDriver('GV14', self.lastUpdate)
        self.checkHighLow(self.tempVal)
        self.storeValues()
        self.setDriver('GV2', 0.0)
        self.lastUpdateTime = time.time()
        self.prevVal = self.tempVal
        self.setDriver('GV1', self.prevVal)
        self.tempVal = command
        if self.RtoPrec == 1:
            LOGGER.info('Converting from raw')
            self.tempVal = round((self.tempVal / 10), 1)
        if self.CtoF == 1:
            LOGGER.info('converting C to F')
            self.tempVal = round(((self.tempVal * 1.8) + 32), 1)
        self.setDriver('ST', self.tempVal)

        if self.action1 == 1:
            _type = TYPELIST[(self.action1type - 1)]
            self.pushTheValue(_type, self.action1id)
            LOGGER.info('Action 1 Pushing')
        else:
            pass

        if self.action2 == 1:
            _type = TYPELIST[(self.action2type - 1)]
            self.pushTheValue(_type, self.action2id)
            LOGGER.info('Action 2 Pushing')
        else:
            pass

    def checkLastUpdate(self):
        _currentTime = time.time()
        _sinceLastUpdate = round(((_currentTime - self.lastUpdateTime) / 60), 1)
        if _sinceLastUpdate < 1440:
            self.setDriver('GV2', _sinceLastUpdate)
        else:
            self.setDriver('GV2', 1440)

    def checkHighLow(self, command):
        if self.firstPass:
            self.firstPass = False
            LOGGER.debug('First pass skip')
            pass
        else:
            self.previousHigh = self.highTemp
            self.previousLow = self.lowTemp
            if command > self.highTemp:
                self.setDriver('GV3', command)
                self.highTemp = command
            if command < self.lowTemp:
                self.setDriver('GV4', command)
                self.lowTemp = command
            self.avgHighLow()

    def avgHighLow(self):
        if self.highTemp != -60 and self.lowTemp != 129:
            self.prevAvgTemp = self.currentAvgTemp
            self.currentAvgTemp = round(((self.highTemp + self.lowTemp) / 2), 1)
            self.setDriver('GV5', self.currentAvgTemp)

    def resetStats(self, command):
        LOGGER.info('Resetting Stats')
        self.firstPass = True
        self.lowTemp = 129
        self.highTemp = -60
        self.currentAvgTemp = 0
        self.prevTemp = 0
        self.tempVal = 0
        self.setDriver('GV1', 0)
        #time.sleep(.1)
        self.setDriver('GV5', 0)
        #time.sleep(.1)
        self.setDriver('GV3', 0)
        #time.sleep(.1)
        self.setDriver('GV4', 0)
        #time.sleep(.1)
        self.setDriver('ST', 0)
        self.firstPass = True
        self.storeValues()

    def update(self):
        self.checkLastUpdate()

    def query(self, command=None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
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
               {'driver': 'GV13', 'value': 0, 'uom': 25}  #f to c
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
        'deleteDB': deleteDB
                }


