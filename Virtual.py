

#!/usr/bin/env python
"""
This is a NodeServer created for Polyglot v2 from a template by Einstein.42 (James Miline)
This NodeServer was created by markv58 (Mark Vittes) markv58git@gmail.com
v1.0.8
"""

import polyinterface
import sys
import time
import requests
import logging
import re

TYPELIST = ['/set/2/', #1
            '/init/2/',#2
            '/set/1/', #3
            'init/1/'  #4
           ]

GETLIST = ['/2/',
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

    def start(self):
        LOGGER.info('Started Virtual Device NodeServer')
        self.check_params()
        self.discover()
        self.poly.add_custom_config_docs("<b>And this is some custom config data</b>")

    def shortPoll(self):
        for node in self.nodes:
            self.nodes[node].update()
            self.nodes[node].getDataFromID()

    def longPoll(self):
        pass

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
                LOGGER.debug('ISY ip address is %s ', val)
                self.isy = str(val)
            elif a == "user":
                LOGGER.debug('ISY user is %s', val)
                self.user = str(val)
            elif a == "password":
                LOGGER.debug('ISY password is %s', val)
                self.password = str(val)
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
    
class VirtualTemp(polyinterface.Node):
    def __init__(self, controller, primary, address, name):
        super(VirtualTemp, self).__init__(controller, primary, address, name)
        self.prevVal = 0.0
        self.tempVal = 0.0
        self.Rconvert = False
        self.CtoFconvert = False
        self.firstRun = True
        
        self.currentTime = 0.0
        self.lastUpdateTime = 0.0
        
        self.highTemp = -30.0
        self.lowTemp = 129.0
        
    def start(self):
        self.currentTime = time.time()
        self.lastUpdateTime = time.time()
        self.setDriver('GV2', 0.0)

    def setOn(self, command):
        pass

    def setOff(self, command):
        pass

    def setTemp(self, command):
        self.checkHighLow(self.tempVal)
        self.setDriver('GV2', 0.0)
        self.lastUpdateTime = time.time()        
        self.prevVal = self.tempVal
        self.setDriver('GV1', self.prevVal) # set prev from current
        self.FtoCconvert = False
        self.Rconvert = False
        _temp = float(command.get('value'))
        self.setDriver('ST', _temp)
        requests.get('http://' + self.parent.isy + '/rest/vars/set/2/' + self.address + '/' + str(_temp), auth=(self.parent.user, self.parent.password))
        requests.get('http://' + self.parent.isy + '/rest/vars/init/2/' + self.address + '/' + str(_temp), auth=(self.parent.user, self.parent.password))
        self.tempVal = _temp

    def setTempRaw(self, command):
        if not self.Rconvert and not self.CtoFconvert:
            LOGGER.info('converting from raw')
            _command = self.tempVal / 10
            self.setDriver('ST', _command)
            self.tempVal = _command
            self.Rconvert = True
        else:
            pass
        
    def setCtoF(self, command):
        if not self.CtoFconvert:
            LOGGER.info('converting C to F')
            _CtoFtemp = round(((self.tempVal * 1.8) + 32), 1)
            self.setDriver('ST', _CtoFtemp)
            self.tempVal = _CtoFtemp
            self.CtoFconvert = True
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
        if self.firstRun:
            pass
        else:
            if command > self.highTemp:
                LOGGER.debug('check high')
                self.setDriver('GV3', command)
                self.highTemp = command            
            if command < self.lowTemp:
                LOGGER.debug('check low')
                self.setDriver('GV4', command)
                self.lowTemp = command
        self.firstRun = False

    def update(self):
        self.checkLastUpdate()

    def getDataFromID(self):
        pass
    
    def query(self):
        self.reportDrivers()

    #"Hints See: https://github.com/UniversalDevicesInc/hints"
    #hint = [1,2,3,4]
    drivers = [
               {'driver': 'ST', 'value': 0, 'uom': 17},
               {'driver': 'GV1', 'value': 0, 'uom': 17},
               {'driver': 'GV2', 'value': 0, 'uom': 45},
               {'driver': 'GV3', 'value': 0, 'uom': 17},
               {'driver': 'GV4', 'value': 0, 'uom': 17}
              ]

    id = 'virtualtemp'

    commands = {
                    'setTemp': setTemp, 'setCtoF': setCtoF, 'setRaw': setTempRaw
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
        self.resetStats(1)
        self.retrieveValues()
       
    def storeValues(self):
        LOGGER.info('Storing Values')
        pass
    
    def retrieveValues(self):
        LOGGER.info('Retrieving Values')
        pass
    
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
        else:
            pass
        
        if self.action2 == 1:
            _type = TYPELIST[(self.action2type - 1)]
            self.pushTheValue(_type, self.action2id)
            LOGGER.debug('Action 2 Pushing')
        else:
            pass
     
    
    def setAction1(self, command):
        self.action1 = int(command.get('value'))
        LOGGER.debug('Action 1 %s', self.action1)
            
    def setAction1id(self, command):
        self.action1id = int(command.get('value'))
        LOGGER.debug('Action 1 ID %s', self.action1id)
    
    def setAction1type(self, command):
        self.action1type = int(command.get('value'))
        LOGGER.debug('Action 1 type %s', self.action1type)
            
    def setAction2(self, command):
        self.action2 = int(command.get('value'))
        LOGGER.debug('Action 2 %s', self.action2)
            
    def setAction2id(self, command):
        self.action2id = int(command.get('value'))
        LOGGER.debug('Action 2 ID %s', self.action2id)
            
    def setAction2type(self, command):
        self.action2type = int(command.get('value'))
        LOGGER.debug('Action 2 type %s', self.action1type)
            
    def setFtoC(self, command):
        self.FtoC = int(command.get('value'))
        LOGGER.debug('F to C conversion %s', self.FtoC)
    
    def setRawToPrec(self, command):
        self.RtoPrec = int(command.get('value'))
        LOGGER.debug('Raw to Prec %s',self.RtoPrec)
        
    def pushTheValue(self, command1, command2):
        _type = str(command1)
        _id = str(command2)
        LOGGER.debug('Pushing to http://%s/rest/vars%s%s/%s', self.parent.isy, _type, _id, self.tempVal)
        requests.get('http://' + self.parent.isy + '/rest/vars' + _type + _id + '/' + str(self.tempVal), auth=(self.parent.user, self.parent.password))
            
    def getDataFromID(self):
        if self.action1 == 2:
            _type = GETLIST[(self.action1type - 1)]
            self.pullFromID(_type, self.action1id)                
        if self.action2 == 2:
            _type = GETLIST[self.action2type]
            self.pullFromID(_type, self.action2id)
            
    def pullFromID(self, command1, command2): # this pulls but does not set temp yet
        _type = str(command1)
        _id = str(command2)
        LOGGER.debug('Pulling from http://%s/rest/vars/get%s%s/', self.parent.isy, _type, _id)
        r = requests.get('http://' + self.parent.isy + '/rest/vars/get' + _type + _id, auth=(self.parent.user, self.parent.password))
        _content = str(r.content)
        LOGGER.debug(_content)
        _value =  re.split('.*<init>(\d+).*<prec>(\d).*<val>(\d+)',_content)
        LOGGER.info(_value)
        LOGGER.info('Init = %s Prec = %s Value = %s',_value[1], _value[2], _value[3])

           
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
            time.sleep(.5)
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
        self.setDriver('GV1', self.prevTemp)
        self.setDriver('GV5', self.currentAvgTemp)
        self.setDriver('GV3', 0)
        self.setDriver('GV4', 0)
        time.sleep(.5)
        self.setDriver('ST', self.tempVal)
            
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
               {'driver': 'GV5', 'value': 0, 'uom': 4}  #avg high - low
              ]

    id = 'virtualtempc'

    commands = {
                    'setTemp': setTemp, 'setAction1': setAction1, 'setAction1id': setAction1id, 'setAction1type': setAction1type,
                                        'setAction2': setAction2, 'setAction2id': setAction2id, 'setAction2type': setAction2type,
                                        'setFtoC': setFtoC, 'setRawToPrec': setRawToPrec,
                    'resetStats': resetStats #bottom   
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
        
