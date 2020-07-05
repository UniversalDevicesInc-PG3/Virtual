#!/usr/bin/env python

import polyinterface
import sys
import time
import requests
import logging
import subprocess

LOGGER = polyinterface.LOGGER
logging.getLogger('urllib3').setLevel(logging.ERROR)

class Controller(polyinterface.Controller):
    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        self.name = 'VirtualSwitch Controller'
        self.poly.onConfig(self.process_config)
        self.user = 'none'
        self.password = 'none'
        self.isy = 'none'
        
    def start(self):
        LOGGER.info('Started VirtualSwitch NodeServer')
        self.check_params()
        self.discover()
        self.poly.add_custom_config_docs("<b>And this is some custom config data</b>")

    def shortPoll(self):
        pass

    def longPoll(self):
        pass

    def query(self):
        self.check_params()
        for node in self.nodes:
            self.nodes[node].reportDrivers()

    def discover(self, *args, **kwargs):
        pass

    def delete(self):
        LOGGER.info('Deleting VirtulaSwitch Nodeserver')

    def stop(self):
        LOGGER.debug('NodeServer stopped.')

    def process_config(self, config):
        #LOGGER.info("process_config: Enter config={}".format(config));
        #LOGGER.info("process_config: Exit");
        pass
    
    def check_params(self):
        for key,val in self.polyConfig['customParams'].items():
            a = key
            if a.isdigit():
                LOGGER.debug('Is a digit')
                _name = str(val) + ' ' + str(key)
                LOGGER.debug(_name)
                #_addr = str(key) + ' ' + str(val)
                #LOGGER.debug(_addr)
                self.addNode(VirtualSwitch(self, self.address, key, _name))
                
            if a == "isy":
                LOGGER.debug('ISY ip address is %s ', val)
                self.isy = str(val)
                
            if a == "user":
                LOGGER.debug('ISY user is %s', val)
                self.user = str(val)
                
            if a == "password":
                LOGGER.debug('ISY password is %s', val)
                self.password = str(val)
                
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
        
    def query(self):
        self.reportDrivers()

    "Hints See: https://github.com/UniversalDevicesInc/hints"
    hint = [1,2,3,4]
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 25}]

    id = 'virtualswitch'

    commands = {
                    'DON': setOn, 'DOF': setOff
                }
    
class VirtualDimmer(polyinterface.Node):
    def __init__(self, controller, primary, address, name):
        super(VirtualDimmer, self).__init__(controller, primary, address, name)

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
        
    def query(self):
        self.reportDrivers()

    "Hints See: https://github.com/UniversalDevicesInc/hints"
    hint = [1,2,3,4]
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 56}]

    id = 'virtualdimmer'

    commands = {
                    'DON': setOn, 'DOF': setOff
                }
    
class VirtualTemp(polyinterface.Node):
    def __init__(self, controller, primary, address, name):
        super(VirtualTemp, self).__init__(controller, primary, address, name)

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
        
    def query(self):
        self.reportDrivers()

    "Hints See: https://github.com/UniversalDevicesInc/hints"
    hint = [1,2,3,4]
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 17}]

    id = 'virtualtemp'

    commands = {
                    'DON': setOn, 'DOF': setOff
                }    

if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('Template')

        polyglot.start()

        control = Controller(polyglot)

        control.runForever()

    except (KeyboardInterrupt, SystemExit):
        polyglot.stop()
        sys.exit(0)


