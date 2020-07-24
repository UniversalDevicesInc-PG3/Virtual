

#!/usr/bin/env python
"""
This is a NodeServer created for Polyglot v2 from a template by Einstein.42 (James Miline)
This NodeServer was created by markv58 (Mark Vittes) markv58git@gmail.com
v1.0.16
"""

import polyinterface
import sys
import time
import requests
import logging
import re
import shelve
import os.path
import subprocess

TYPELIST = ['/set/2/', #1
            '/init/2/',#2
            '/set/1/', #3
            'init/1/'  #4
           ]

GETLIST = [' ',
           '/2/',
           '/2/',
           '/1/',
           '/1/'
          ]
            
LOGGER = polyinterface.LOGGER
logging.getLogger('urllib3').setLevel(logging.ERROR)

class Controller(polyinterface.Controller):
    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        self.name = 'Virtual Device Controller'
        self.poly.onConfig(self.process_config)
        self.user = 'none'
        self.password = 'none'
        self.isy = 'none'
        self.parseDelay = 0.0

    def start(self):
        LOGGER.info('Started Virtual Device NodeServer')
        self.check_params()
        self.discover()
        self.poly.add_custom_config_docs("<b>And this is some custom config data</b>")

    def shortPoll(self):
        for node in self.nodes:
            self.nodes[node].update()

    def longPoll(self):
        for node in self.nodes:
            self.nodes[node].getDataFromID()
            
    def query(self):
        #self.check_params()
        for node in self.nodes:
            self.nodes[node].reportDrivers()

    def discover(self, *args, **kwargs):
        pass

    def delete(self):
        LOGGER.info('Deleting Virtual Device Nodeserver')

    def stop(self):
        LOGGER.debug('NodeServer stopped.')

    def process_config(self, config):
        #LOGGER.info("process_config: Enter config={}".format(config));
        #LOGGER.info("process_config: Exit");
        pass

    def check_params(self):
        for key,val in self.polyConfig['customParams'].items():
            a = key
            if a == "isy":
                #LOGGER.debug('ISY ip address is %s ', val)
                self.isy = str(val)
            elif a == "user":
                #LOGGER.debug('ISY user is %s', val)
                self.user = str(val)
            elif a == "password":
                #LOGGER.debug('ISY password is %s', val)
                self.password = str(val)
            elif a == "parseDelay":
                self.parseDelay = int(val)
            elif a.isdigit(): 
                if val == 'switch':
                    _name = str(val) + ' ' + str(key)
                    self.addNode(VirtualSwitch(self, self.address, key, _name))
                elif val == 'temperature':
                    _name = str(val) + ' ' + str(key)
                    self.addNode(VirtualTemp(self, self.address, key, _name))
                elif val == 'temperaturec' or val == 'temperaturecr':
                    _name = str(val) + ' ' + str(key)
                    self.addNode(VirtualTempC(self, self.address, key, _name))
                elif val == 'generic' or val == 'dimmer':
                    _name = str(val) + ' ' + str(key)
                    self.addNode(VirtualGeneric(self, self.address, key, _name))
                else:
                    pass
            else:
                pass
        LOGGER.info('Check Params is complete')

    def remove_notice_test(self,command):
        LOGGER.info('remove_notice_test: notices={}'.format(self.poly.config['notices']))
        # Remove all existing notices
        self.removeNotice('test')

    def remove_notices_all(self,command):
        LOGGER.info('remove_notices_all: notices={}'.format(self.poly.config['notices']))
        # Remove all existing notices
        self.removeNoticesAll()

    def update_profile(self,command):
        LOGGER.info('update_profile:')
        st = self.poly.installprofile()
        return st
    
    def update(self):
        pass

    def getDataFromID(self):
        pass

        id = 'controller'
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'UPDATE_PROFILE': update_profile,
        'REMOVE_NOTICES_ALL': remove_notices_all,
        'REMOVE_NOTICE_TEST': remove_notice_test
    }
    drivers = [{'driver': 'ST', 'value': 1, 'uom': 2}]
    
class VirtualSwitch(polyinterface.Node):
    def __init__(self, controller, primary, address, name):
        super(VirtualSwitch, self).__init__(controller, primary, address, name)

    def start(self):
        pass

    def setOn(self, command):
        self.setDriver('ST', 1)
        requests.get('http://' + self.parent.isy + '/rest/vars/set/2/' + self.address + '/1', auth=(self.parent.user, self.parent.password))
        requests.get('http://' + self.parent.isy + '/rest/vars/init/2/' + self.address + '/1', auth=(self.parent.user, self.parent.password))

    def setOff(self, command):
        self.setDriver('ST', 0)
        requests.get('http://' + self.parent.isy + '/rest/vars/set/2/' + self.address + '/0', auth=(self.parent.user, self.parent.password))
        requests.get('http://' + self.parent.isy + '/rest/vars/init/2/' + self.address + '/0', auth=(self.parent.user, self.parent.password))
        
    def update(self):
        pass

    def getDataFromID(self):
        pass
        
    def query(self):
        self.reportDrivers()

    #"Hints See: https://github.com/UniversalDevicesInc/hints"
    #hint = [1,2,3,4]
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 25}]

    id = 'virtualswitch'

    commands = {
                    'DON': setOn, 'DOF': setOff
                }
 ###################################            ######################         #####################       ###################   
class VirtualTemp(polyinterface.Node):
    def __init__(self, controller, primary, address, name):
        super(VirtualTemp, self).__init__(controller, primary, address, name)
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
        
    def start(self):
        self.currentTime = time.time()
        self.lastUpdateTime = time.time()
        self.setDriver('GV2', 0.0)
        self.createDBfile()
        if self.firstPass: self.resetStats(1)

    def setOn(self, command):
        pass

    def setOff(self, command):
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
        #LOGGER.debug(_name)
        #LOGGER.debug(_key)
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
        #LOGGER.debug(_name)
        #LOGGER.debug(_key)
        s = shelve.open(_name, writeback=True)            
        try:
            existing = s[_key]
        finally:
            s.close()
        LOGGER.info('Retrieving Values')
        LOGGER.info(existing)
            
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
                       
        self.action1id = existing['action1id'] # 0 - 400
        self.setDriver('GV8', self.action1id) 

        self.action1type = existing['action1type'] # State var, State init, Int var, Int init
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
        self.setDriver('GV1', self.prevVal) # set prev from current
        _temp = float(command.get('value'))
        self.setDriver('ST', _temp)
        self.tempVal = _temp
        self.convertTempFromRaw()
        self.convertCtoF()

        if self.action1 == 1:
            _type = TYPELIST[(self.action1type - 1)]
            self.pushTheValue(_type, self.action1id)
        #    LOGGER.debug('Action 1 Pushing')
        
        if self.action2 == 1:
            _type = TYPELIST[(self.action2type - 1)]
            self.pushTheValue(_type, self.action2id)
        #    LOGGER.debug('Action 2 Pushing')
            
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
        self.storeValues()
                    
    def setRawToPrec(self, command):
        self.RtoPrec = int(command.get('value'))
        self.setDriver('GV12', self.RtoPrec)
        self.storeValues()
                    
    def pushTheValue(self, command1, command2):
        _type = str(command1)
        _id = str(command2)
        LOGGER.debug('Pushing to http://%s/rest/vars%s%s/%s', self.parent.isy, _type, _id, self.tempVal)
        requests.get('http://' + self.parent.isy + '/rest/vars' + _type + _id + '/' + str(self.tempVal), auth=(self.parent.user, self.parent.password))
            
    def getDataFromID(self):
        if self.action1 == 2:
            _type = GETLIST[self.action1type]
            self.pullFromID(_type, self.action1id)                
        if self.action2 == 2:
            _type = GETLIST[self.action2type]
            self.pullFromID(_type, self.action2id)            
            
    def pullFromID(self, command1, command2): # this pulls but does not set temp yet
        if command2 == 0:
            pass
        else:
            _type = str(command1)
            _id = str(command2)
            try:
                #LOGGER.debug('Pulling from http://%s/rest/vars/get%s%s/', self.parent.isy, _type, _id)
                r = requests.get('http://' + self.parent.isy + '/rest/vars/get' + _type + _id, auth=(self.parent.user, self.parent.password))
                _content = str(r.content)
                #LOGGER.debug(_content)
                _value =  re.split('.*<init>(\d+).*<prec>(\d).*<val>(\d+)',_content)
                LOGGER.info(_value)
                #LOGGER.debug(_type)
                _newTemp = 0
                time.sleep(int(self.parent.parseDelay))
                LOGGER.debug('Parse delay: %s', self.parent.parseDelay)
            except Exception as e:
                LOGGER.error('There was an error with the value pull: ' + str(e))
            try:                 
                if command1 == '/2/' : _newTemp = int(_value[3])
                if command1 == '/1/' : _newTemp = int(_value[1])
            except Exception as e:
                LOGGER.error('An error occured during the content parse: ' + str(e))             
            self.setTempFromData(_newTemp)         
            
    def setTempFromData(self, command):
        self.checkHighLow(self.tempVal)
        self.storeValues()
        self.setDriver('GV2', 0.0)
        self.lastUpdateTime = time.time()        
        self.prevVal = self.tempVal
        self.setDriver('GV1', self.prevVal) # set prev from current
        self.tempVal = command
        #self.convertTempFromRaw()
        if self.RtoPrec == 1:
            LOGGER.info('Converting from raw')
            self.tempVal = (self.tempVal / 10)
        if self.CtoF == 1:
            LOGGER.info('converting C to F')
            self.tempVal = round(((self.tempVal * 1.8) + 32), 1)         
        #self.convertFtoC()            
        self.setDriver('ST', self.tempVal)
        #self.tempVal = command
        #self.convertTempFromRaw()
        #self.convertFtoC()            
            
        if self.action1 == 1:
            _type = TYPELIST[(self.action1type - 1)]
            self.pushTheValue(_type, self.action1id)
            LOGGER.debug('Action 1 Pushing')
        else:
            pass
        
        if self.action2 == 1:
            _type = TYPELIST[(self.action2type - 1)]
            self.pushTheValue(_type, self.action2id)
            LOGGER.debug('Action 2 Pushing')
        else:
            pass             
            
    def convertTempFromRaw(self):
        if self.RtoPrec == 1:
            LOGGER.info('Converting from raw')
            _command = self.tempVal / 10
            self.setDriver('ST', _command)
            self.tempVal = _command
            self.Rconvert = True
        else:
            pass
        
    def convertCtoF(self):
        if self.CtoF == 1:
            LOGGER.info('converting C to F')
            _CtoFtemp = round(((self.tempVal * 1.8) + 32), 1)
            LOGGER.debug(_CtoFtemp)
            self.tempVal = _CtoFtemp
            time.sleep(1)
            self.setDriver('ST', self.tempVal)
        else:
            pass

    def checkLastUpdate(self): # happens on the short poll
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
            #    LOGGER.debug('check high')
                self.setDriver('GV3', command)
                self.highTemp = command            
            if command < self.lowTemp:
            #    LOGGER.debug('check low')
                self.setDriver('GV4', command)
                self.lowTemp = command
            self.avgHighLow()
            
    def avgHighLow(self):
        if self.highTemp != -60 and self.lowTemp != 129: # make sure values have been set from startup
            #LOGGER.debug('Updating the average temperatue')
            self.prevAvgTemp = self.currentAvgTemp
            self.currentAvgTemp = round(((self.highTemp + self.lowTemp) / 2), 1)
            self.setDriver('GV5', self.currentAvgTemp)            
            
    def resetStats(self, command):
        LOGGER.debug('Resetting Stats')
        self.firstPass = True
        self.lowTemp = 129
        self.highTemp = -60
        self.currentAvgTemp = 0
        self.prevTemp = 0
        self.tempVal = 0
        self.setDriver('GV1', 0)
        time.sleep(.1)
        self.setDriver('GV5', 0)
        time.sleep(.1)                    
        self.setDriver('GV3', 0)
        time.sleep(.1)
        self.setDriver('GV4', 0)
        time.sleep(.1)
        self.setDriver('ST', 0)
        self.firstPass = True
        self.storeValues()

    def update(self):
        self.checkLastUpdate()
  
    def query(self):
        self.reportDrivers()

    #"Hints See: https://github.com/UniversalDevicesInc/hints"
    #hint = [1,2,3,4]
    drivers = [
               {'driver': 'ST', 'value': 0, 'uom': 17},  #current
               {'driver': 'GV1', 'value': 0, 'uom': 17}, #previous
               {'driver': 'GV2', 'value': 0, 'uom': 45},#update time
               {'driver': 'GV3', 'value': 0, 'uom': 17}, #high
               {'driver': 'GV4', 'value': 0, 'uom': 17}, #low
               {'driver': 'GV5', 'value': 0, 'uom': 17}, #avg high - low
               {'driver': 'GV6', 'value': 0, 'uom': 25}, #action1 type
               {'driver': 'GV7', 'value': 0, 'uom': 25}, #variable type
               {'driver': 'GV8', 'value': 0, 'uom': 56},#variable id
               {'driver': 'GV9', 'value': 0, 'uom': 25}, #action 2
               {'driver': 'GV10', 'value': 0, 'uom': 25},#variable type
               {'driver': 'GV11', 'value': 0, 'uom': 56},#variable id
               {'driver': 'GV12', 'value': 0, 'uom': 25},#r to p
               {'driver': 'GV13', 'value': 0, 'uom': 25},#f to c
              ]

    id = 'virtualtemp'

    commands = {
                    'setTemp': setTemp, 'setAction1': setAction1, 'setAction1id': setAction1id, 'setAction1type': setAction1type,
                                        'setAction2': setAction2, 'setAction2id': setAction2id, 'setAction2type': setAction2type,
                                        'setCtoF': setCtoF, 'setRawToPrec': setRawToPrec,
                    'resetStats': resetStats, 'deleteDB': deleteDB #bottom   
                }
################################################################################################################################    
class VirtualTempC(polyinterface.Node):
    def __init__(self, controller, primary, address, name):
        super(VirtualTempC, self).__init__(controller, primary, address, name)
        
        self.firstPass = True
            
        self.prevVal = 0.0
        self.tempVal = 0.0
        
        self.currentTime = 0.0
        self.lastUpdateTime = 0.0
        
        self.highTemp = -60.0
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
        self.FtoC = 0
        
    def start(self):
        self.currentTime = time.time()
        self.lastUpdateTime = time.time()
        self.setDriver('GV2', 0.0)
        self.createDBfile()
        if self.firstPass: self.resetStats(1)
            
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
            LOGGER.info('Creating %s', _check)
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
        #LOGGER.debug(_name)
        #LOGGER.debug(_key)
        s = shelve.open(_name, writeback=True)
        try:
            s[_key] = { 'action1': self.action1, 'action1type': self.action1type, 'action1id': self.action1id,
                        'action2': self.action2, 'action2type': self.action2type, 'action2id': self.action2id,
                        'RtoPrec': self.RtoPrec, 'FtoC': self.FtoC, 'prevVal': self.prevVal, 'tempVal': self.tempVal,
                        'highTemp': self.highTemp, 'lowTemp': self.lowTemp, 'previousHigh': self.previousHigh, 'previousLow': self.previousLow,
                        'prevAvgTemp': self.prevAvgTemp, 'currentAvgTemp': self.currentAvgTemp, 'firstPass': self.firstPass }
        finally:
            s.close()
        #LOGGER.info('Storing Values')
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
        #LOGGER.debug(_name)
        #LOGGER.debug(_key)
        s = shelve.open(_name, writeback=True)            
        try:
            existing = s[_key]
        finally:
            s.close()
        LOGGER.info('Retrieving Values')
        LOGGER.info(existing)
            
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
                       
        self.action1id = existing['action1id'] # 0 - 400
        self.setDriver('GV8', self.action1id) 
                       
        self.action1type = existing['action1type'] # State var, State init, Int var, Int init
        self.setDriver('GV7', self.action1type)
            
        self.action2 = existing['action2'] 
        self.setDriver('GV9', self.action2)
            
        self.action2id = existing['action2id']
        self.setDriver('GV11', self.action2id)
            
        self.action2type = existing['action2type']
        self.setDriver('GV10', self.action2type)
            
        self.RtoPrec = existing['RtoPrec']
        self.setDriver('GV12', self.RtoPrec)
            
        self.FtoC = existing['FtoC']
        self.setDriver('GV13', self.FtoC)
            
        self.firstPass = existing['firstPass']    

    def setTemp(self, command):
        self.checkHighLow(self.tempVal)
        self.storeValues()
        self.setDriver('GV2', 0.0)
        self.lastUpdateTime = time.time()        
        self.prevVal = self.tempVal
        self.setDriver('GV1', self.prevVal) # set prev from current
        _temp = float(command.get('value'))
        self.setDriver('ST', _temp)
        self.tempVal = _temp
        self.convertTempFromRaw()
        self.convertFtoC()

            
        if self.action1 == 1:
            _type = TYPELIST[(self.action1type - 1)]
            self.pushTheValue(_type, self.action1id)
            LOGGER.debug('Action 1 Pushing')
        
        if self.action2 == 1:
            _type = TYPELIST[(self.action2type - 1)]
            self.pushTheValue(_type, self.action2id)
            LOGGER.debug('Action 2 Pushing')
 
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

    def setFtoC(self, command):
        self.FtoC = int(command.get('value'))
        self.setDriver('GV13', self.FtoC)
        self.storeValues()

    def setRawToPrec(self, command):
        self.RtoPrec = int(command.get('value'))
        self.setDriver('GV12', self.RtoPrec)
        self.storeValues()

    def pushTheValue(self, command1, command2):
        _type = str(command1)
        _id = str(command2)
        LOGGER.debug('Pushing to http://%s/rest/vars%s%s/%s', self.parent.isy, _type, _id, self.tempVal)
        requests.get('http://' + self.parent.isy + '/rest/vars' + _type + _id + '/' + str(self.tempVal), auth=(self.parent.user, self.parent.password))
            
    def getDataFromID(self):
        if self.action1 == 2:
            _type = GETLIST[self.action1type]
            self.pullFromID(_type, self.action1id)                
        if self.action2 == 2:
            _type = GETLIST[self.action2type]
            self.pullFromID(_type, self.action2id)
            
    def pullFromID(self, command1, command2): # this pulls but does not set temp yet
        if command2 == 0:
            pass
        else:
            _type = str(command1)
            _id = str(command2)
            try:
                #LOGGER.debug('Pulling from http://%s/rest/vars/get%s%s/', self.parent.isy, _type, _id)
                r = requests.get('http://' + self.parent.isy + '/rest/vars/get' + _type + _id, auth=(self.parent.user, self.parent.password))
                _content = str(r.content)
                #LOGGER.debug(_content)
                _value =  re.split('.*<init>(\d+).*<prec>(\d).*<val>(\d+)',_content)
                LOGGER.info(_value)
                #LOGGER.debug(_type)
                _newTemp = 0
                time.sleep(int(self.parent.parseDelay))
                LOGGER.debug('Parse delay: %s', self.parent.parseDelay)
            except Exception as e:
                LOGGER.error('There was an error with the value pull: ' + str(e))
            try:                 
                if command1 == '/2/' : _newTemp = int(_value[3])
                if command1 == '/1/' : _newTemp = int(_value[1])
            except Exception as e:
                LOGGER.error('An error occured during the content parse: ' + str(e))             
            self.setTempFromData(_newTemp)

    def setTempFromData(self, command):
        self.checkHighLow(self.tempVal)
        self.storeValues()
        self.setDriver('GV2', 0.0)
        self.lastUpdateTime = time.time()        
        self.prevVal = self.tempVal
        self.setDriver('GV1', self.prevVal) # set prev from current
        self.tempVal = command
        #self.convertTempFromRaw()
        if self.RtoPrec == 1:
            LOGGER.info('Converting from raw')
            self.tempVal = (self.tempVal / 10)
        if self.FtoC == 1:
            LOGGER.info('converting F to C')
            self.tempVal = round(((self.tempVal - 32) / 1.80), 1)          
        #self.convertFtoC()            
        self.setDriver('ST', self.tempVal)
        #self.tempVal = command
        #self.convertTempFromRaw()
        #self.convertFtoC()
 

        if self.action1 == 1:
            _type = TYPELIST[(self.action1type - 1)]
            self.pushTheValue(_type, self.action1id)
            LOGGER.debug('Action 1 Pushing')
        else:
            pass
        
        if self.action2 == 1:
            _type = TYPELIST[(self.action2type - 1)]
            self.pushTheValue(_type, self.action2id)
            LOGGER.debug('Action 2 Pushing')
        else:
            pass                        
                        
    def convertTempFromRaw(self):
        if self.RtoPrec == 1:
            LOGGER.info('Converting from raw')
            _command = self.tempVal / 10
            self.setDriver('ST', _command)
            self.tempVal = _command
            self.Rconvert = True
        else:
            pass

    def convertFtoC(self):
        if self.FtoC == 1:
            LOGGER.info('converting F to C')
            _FtoCtemp = round(((self.tempVal - 32) / 1.80), 1)
            LOGGER.debug(_FtoCtemp)
            self.tempVal = _FtoCtemp
            time.sleep(1)
            self.setDriver('ST', self.tempVal)
        else:
            pass

    def checkLastUpdate(self): # happens on the short poll
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
                LOGGER.debug('check high')
                self.setDriver('GV3', command)
                self.highTemp = command            
            if command < self.lowTemp:
                LOGGER.debug('check low')
                self.setDriver('GV4', command)
                self.lowTemp = command
            self.avgHighLow()
    
    def avgHighLow(self):
        if self.highTemp != -60 and self.lowTemp != 129: # make sure values have been set from startup
            LOGGER.debug('Updating the average temperatue')
            self.prevAvgTemp = self.currentAvgTemp
            self.currentAvgTemp = round(((self.highTemp + self.lowTemp) / 2), 1)
            self.setDriver('GV5', self.currentAvgTemp)
        
    def resetStats(self, command):
        LOGGER.debug('Resetting Stats')
        self.firstPass = True
        self.lowTemp = 129
        self.highTemp = -60
        self.currentAvgTemp = 0
        self.prevTemp = 0
        self.tempVal = 0
        self.setDriver('GV1', 0)
        time.sleep(.1)   
        self.setDriver('GV5', 0)
        time.sleep(.1)    
        self.setDriver('GV3', 0)
        time.sleep(.1)        
        self.setDriver('GV4', 0)
        time.sleep(.1)
        self.setDriver('ST', self.tempVal)
        self.firstPass = True
        self.storeValues()
            
    def update(self):
        self.checkLastUpdate()

    def query(self):
        self.reportDrivers()

    #"Hints See: https://github.com/UniversalDevicesInc/hints"
    #hint = [1,2,3,4]
    drivers = [
               {'driver': 'ST', 'value': 0, 'uom': 4},  #current
               {'driver': 'GV1', 'value': 0, 'uom': 4}, #previous
               {'driver': 'GV2', 'value': 0, 'uom': 45},#update time
               {'driver': 'GV3', 'value': 0, 'uom': 4}, #high
               {'driver': 'GV4', 'value': 0, 'uom': 4}, #low
               {'driver': 'GV5', 'value': 0, 'uom': 4}, #avg high - low
               {'driver': 'GV6', 'value': 0, 'uom': 25}, #action1 type
               {'driver': 'GV7', 'value': 0, 'uom': 25}, #variable type
               {'driver': 'GV8', 'value': 0, 'uom': 56},#variable id
               {'driver': 'GV9', 'value': 0, 'uom': 25}, #action 2
               {'driver': 'GV10', 'value': 0, 'uom': 25},#variable type
               {'driver': 'GV11', 'value': 0, 'uom': 56},#variable id
               {'driver': 'GV12', 'value': 0, 'uom': 25},#r to p
               {'driver': 'GV13', 'value': 0, 'uom': 25},#f to c
              ]

    id = 'virtualtempc'

    commands = {
                    'setTemp': setTemp, 'setAction1': setAction1, 'setAction1id': setAction1id, 'setAction1type': setAction1type,
                                        'setAction2': setAction2, 'setAction2id': setAction2id, 'setAction2type': setAction2type,
                                        'setFtoC': setFtoC, 'setRawToPrec': setRawToPrec,
                    'resetStats': resetStats, 'deleteDB': deleteDB #bottom   
                }
    
class VirtualGeneric(polyinterface.Node):
    def __init__(self, controller, primary, address, name):
        super(VirtualGeneric, self).__init__(controller, primary, address, name)

    def start(self):
        pass

    def setOn(self, command):
        self.setDriver('ST', 100)
        requests.get('http://' + self.parent.isy + '/rest/vars/set/2/' + self.address + '/100', auth=(self.parent.user, self.parent.password))
        requests.get('http://' + self.parent.isy + '/rest/vars/init/2/' + self.address + '/100', auth=(self.parent.user, self.parent.password))

    def setOff(self, command):
        self.setDriver('ST', 0)
        requests.get('http://' + self.parent.isy + '/rest/vars/set/2/' + self.address + '/0', auth=(self.parent.user, self.parent.password))
        requests.get('http://' + self.parent.isy + '/rest/vars/init/2/' + self.address + '/0', auth=(self.parent.user, self.parent.password))

    def setDim(self, command):
        _level = int(command.get('value'))
        self.setDriver('ST', _level)
        requests.get('http://' + self.parent.isy + '/rest/vars/set/2/' + self.address + '/' + str(_level), auth=(self.parent.user, self.parent.password))
        r = requests.get('http://' + self.parent.isy + '/rest/vars/get/2/' + self.address, auth=(self.parent.user, self.parent.password))
        LOGGER.info(r.headers)
        
    def update(self):
        pass

    def getDataFromID(self):
        pass
    
    def query(self):
        self.reportDrivers()

    #"Hints See: https://github.com/UniversalDevicesInc/hints"
    #hint = [1,2,3,4]
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 56}]

    id = 'virtualgeneric'

    commands = {
                    'DON': setOn, 'DOF': setOff, 'setDim': setDim
                }
    
if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('Virtual')

        polyglot.start()

        control = Controller(polyglot)

        control.runForever()

    except (KeyboardInterrupt, SystemExit):
        polyglot.stop()
        sys.exit(0)
        
