

#!/usr/bin/env python
"""
This is a NodeServer created for Polyglot v2 from a template by Einstein.42 (James Miline)
This NodeServer was created by markv58 (Mark Vittes) markv58git@gmail.com
v1.0.7
"""

import polyinterface
import sys
import time
import requests
import logging

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
        self.CtoFconvert = False

    def start(self):
        pass

    def setOn(self, command):
        pass

    def setOff(self, command):
        pass

    def setTemp(self, command):
        self.prevVal = self.tempVal
        self.setDriver('GV1', self.prevVal)
        self.CtoFconvert = False
        _temp = float(command.get('value'))
        self.setDriver('ST', _temp)
        requests.get('http://' + self.parent.isy + '/rest/vars/set/2/' + self.address + '/' + str(_temp), auth=(self.parent.user, self.parent.password))
        requests.get('http://' + self.parent.isy + '/rest/vars/init/2/' + self.address + '/' + str(_temp), auth=(self.parent.user, self.parent.password))
        self.tempVal = _temp

    def setCtoF(self, command):
        if not self.CtoFconvert:
            LOGGER.info('converting C to F')
            _CtoFtemp = round(((self.tempVal * 1.8) + 32), 1)
            self.setDriver('ST', _CtoFtemp)
            self.tempVal = _CtoFtemp
            self.CtoFconvert = True
        else:
            pass
    def update(self):
        pass
    
    def query(self):
        self.reportDrivers()

    #"Hints See: https://github.com/UniversalDevicesInc/hints"
    #hint = [1,2,3,4]
    drivers = [
                {'driver': 'ST', 'value': 0, 'uom': 17},
               {'driver': 'GV1', 'value': 0, 'uom': 17}
              ]

    id = 'virtualtemp'

    commands = {
                    'setTemp': setTemp, 'setCtoF': setCtoF
                }
    
class VirtualTempC(polyinterface.Node):
    def __init__(self, controller, primary, address, name):
        super(VirtualTempC, self).__init__(controller, primary, address, name)
        self.prevVal = 0.0
        self.tempVal = 0.0
        self.Rconvert = False
        self.FtoCconvert = False
        self.firstRun = True
        
        self.currentTime = 0.0
        self.lastUpdateTime = 0.0
        
        self.highTemp = -60.0
        self.lowTemp = 129.0
        
    def start(self):
        self.currentTime = time.time()
        self.lastUpdateTime = time.time()
        self.setDriver('GV2', 0.0)
        self.setDriver('GV3', self.highTemp)
        self.setDriver('GV4', self.lowTemp)

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
        if not self.Rconvert and not self.FtoCconvert:
            LOGGER.info('converting from raw')
            _command = self.tempVal / 10
            self.setDriver('ST', _command)
            self.tempVal = _command
            self.Rconvert = True
        else:
            pass

    def FtoC(self, command):
        if not self.FtoCconvert:
            LOGGER.info('converting F to C')
            _FtoCtemp = round(((self.tempVal - 32) / 1.80), 1)
            self.setDriver('ST', _FtoCtemp)
            self.tempVal = _FtoCtemp
            self.FtoCconvert = True
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
    
    
    def query(self):
        self.reportDrivers()

    #"Hints See: https://github.com/UniversalDevicesInc/hints"
    #hint = [1,2,3,4]
    drivers = [
               {'driver': 'ST', 'value': 0, 'uom': 4},
               {'driver': 'GV1', 'value': 0, 'uom': 4},
               {'driver': 'GV2', 'value': 0, 'uom': 45},
               {'driver': 'GV3', 'value': 0, 'uom': 4},
               {'driver': 'GV4', 'value': 0, 'uom': 4}        
              ]

    id = 'virtualtempc'

    commands = {
                    'setTemp': setTemp, 'setRaw': setTempRaw, 'setFtoC': FtoC
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
        requests.get('http://' + self.parent.isy + '/rest/vars/init/2/' + self.address + '/' + str(_level), auth=(self.parent.user, self.parent.password))
        
    def update(self):
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
        
