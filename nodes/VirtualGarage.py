"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

VirtualGarage class
"""
# standard imports
import os
import time
import shelve
import os.path
import subprocess
import ipaddress
from xml.dom.minidom import parseString

# external imports
import requests
import udi_interface

# local imports
pass

LOGGER = udi_interface.LOGGER
ISY = udi_interface.ISY

# var constants
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

# ratdgo constants

RATGDO = "ratgdov25i-fad8fd"

BUTTON = "/binary_sensor/button"
LIGHT = "/light/light"
DOOR = "/cover/door"
LOCK_REMOTES = "/lock/lock_remotes"
MOTION = "/binary_sensor/motion"
MOTOR = "/binary_sensor/motor"
OBSTRUCTION = "/binary_sensor/obstruction"
TRIGGER = "/button/toggle_door/press"

LOCK = "/lock"
UNLOCK = "/unlock"

OPEN = "/open"
CLOSE = "/close"
STOP = "/stop"

TURN_ON = "/turn_on"
TURN_OFF = "/turn_off"
TOGGLE = "/toggle"

class VirtualGarage(udi_interface.Node):
    id = 'virtualgarage'

    """
    This class is meant to represent a garage device.
    Taking values from variables and allowing control back to said variables.
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

        self.currentTime = 0.0
        self.lastUpdateTime = 0.0
        self.dbConnect = False
        self.key = 'key' + str(self.address)
        self.file = self.key + '.db'

        self.light = 0
        self.lightT = 1
        self.lightId = 0
        self.door = 0
        self.doorT = 1
        self.doorId = 0
        self.dcommand = 0
        self.dcommandT = 1
        self.dcommandId = 0
        self.motion = 0
        self.motionT = 1
        self.motionId = 0
        self.lock = 0
        self.lockT = 1
        self.lockId = 0
        self.obstruct = 0
        self.obstructT = 1
        self.obstructId = 0

        self.lastUpdate = '0000'
        self.openTime = '0000'
        self.firstPass = True

        self.bonjourCommand = None
        self.bonjourOn = False
        self.bonjourOnce = True
        self.ratgdoOK = False
        
        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)
        self.poly.subscribe(self.poly.BONJOUR, self.bonjour)

    def start(self):
        """
        Optional.
        This method is called after Polyglot has added the node per the
        START event subscription above
        """
        self.firstPass = True
        self.isy = ISY(self.poly)

        self.bonjourOnce = True

        self.getConfigData()
        
        self.dbConnect = False
        try:
            if not self.createDB():
                raise Exception("Failed to find or create DB")
        except Exception as ex:
                LOGGER.error(f"Start DB retry DB delete/creation, {ex}")
                if not self.deleteDB():
                    LOGGER.error("Failed to delete DB")
                if not self.createDB():
                    LOGGER.error("Failed to find or create DB")
                else:
                    self.dbConnect = True
        else:
                self.dbConnect = True
        finally:
            self.resetTime()
            LOGGER.info(f"start complete...dbConnect = {self.dbConnect}")
        
    def getConfigData(self):
        # repull config data for var data, light, door, dcommand, motion, lock, obstruction
        # var type & ID are optional, also, will pull with only ID assuming type = 1
        # ratgdo = nonexist, false, true or ip address, true assumes http://ratgdov25i-fad8fd.local
        success = False
        for dev in self.controller.devlist:
            if str(dev['type']) == 'garage':
                if dev['name'] == self.name:
                    self.dev = dev
                    LOGGER.info(f'GARAGE: {self.dev}')
                    success = True
                    break
        if success:
            try:
                self.lightT = self.dev['lightT']
                LOGGER.debug(f'self.lightT = {self.lightT}')
            except:
                self.lightT = 1
            try:
                self.lightId = self.dev['lightId']
                LOGGER.debug(f'self.lightId = {self.lightId}')
            except:
                self.lightId = 0
            try:
                self.doorT = self.dev['doorT']
                LOGGER.debug(f'self.doorT = {self.doorT}')
            except:
                self.doorT = 1
            try:
                self.doorId = self.dev['doorId']
                LOGGER.debug(f'self.doorId = {self.doorId}')
            except:
                self.doorId = 0
            try:
                self.dcommandT = self.dev['dcommandT']
                LOGGER.debug(f'self.dcommandT = {self.dcommandT}')
            except:
                self.dcommandT = 1
            try:
                self.dcommandId = self.dev['dcommandId']
                LOGGER.debug(f'self.dcommandId = {self.dcommandId}')
            except:
                self.dcommandId = 0
            try:
                self.motionT = self.dev['motionT']
                LOGGER.debug(f'self.motionT = {self.motionT}')
            except:
                self.motionT = 1
            try:
                self.motionId = self.dev['motionId']
                LOGGER.debug(f'self.motionId = {self.motionId}')
            except:
                self.motionId = 0
            try:
                self.lockT = self.dev['lockT']
                LOGGER.debug(f'self.lockT = {self.lockT}')
            except:
                self.lockT = 1
            try:
                self.lockId = self.dev['lockId']
                LOGGER.debug(f'self.lockId = {self.lockId}')
            except:
                self.lockId = 0
            try:
                self.obstructT = self.dev['obstructT']
                LOGGER.debug(f'self.obstructT = {self.obstructT}')
            except:
                self.obstructT = 1
            try:
                self.obstructId = self.dev['obstructId']
                LOGGER.debug(f'self.obstructId = {self.obstructId}')
            except:
                self.obstructId = 0
            self.controller.Notices.delete('ratgdo')
            self.ratgdoOK = False
            try:
                self.ratgdo = self.dev['ratgdo']
                if self.ratgdo in ['true', True, RATGDO, f"{RATGDO}.local"]:
                    self.ratgdo = RATGDO
                    self.bonjourOn = True
                    warn = f"Searching for RATGDO IP: {RATGDO}"
                    LOGGER.error(warn)
                    self.controller.Notices['ratgdo'] = warn
                elif self.ratgdo == 'false':
                    self.ratgdo = False
                else:
                    try:
                        ipaddress.ip_address(self.ratgdo)
                        self.ratgdoCheck()
                    except:
                        self.ratgdo = False
                        error = f"RATGDO address error: {self.ratgdo}"
                        LOGGER.error(error)
                        self.controller.Notices['ratgdo'] = error
            except:
                self.ratgdo = False
            LOGGER.info(f'self.ratgdo = {self.ratgdo}')                        
        else:
            LOGGER.error('no self.dev data')
        
    def poll(self, flag):
        if 'longPoll' in flag:
            LOGGER.debug(f"longPoll {self.name}")
        else:
            LOGGER.debug(f"shortPoll {self.name}")
            if self.bonjourOnce and self.bonjourOn:
                self.bonjourOnce = False
                self.poly.bonjour(None, None, None)
            self.updateAll()

    def bonjour(self, command):
        # bonjour(self, type, subtypes, protocol)
        LOGGER.info(f"bonjour message")
        try:
            if command['success']:
                mdns = command['mdns']
                for addr in mdns:
                    LOGGER.info(f"addr: {addr['name']}")
                    if addr['name'] == RATGDO:
                        self.controller.Notices.delete('ratgdo')
                        self.ratgdo = addr['addresses'][0]
                        LOGGER.warn(f"FOUND RATGDO@'{self.ratgdo}': addresses: {addr['addresses']}, name: {addr['name']}")
                        self.ratgdoCheck()
                        self.bonjourOn = False
                        break
        except Exception as ex:
            LOGGER.error(f"error: {ex}, command: {command}")
        self.bonjourOnce = True

    def ratgdoCheck(self):
        try:
            ipaddress.ip_address(self.ratgdo)
            resTxt = f'http://{self.ratgdo}{LIGHT}'
            LOGGER.debug(f'get {resTxt}')
            res = requests.get(resTxt)
            if res.ok:
                LOGGER.debug(f"res.status_code = {res.status_code}")
            else:
                error = f"RATGDO communications error code: {res.status_code}"
                LOGGER.error(f"{error}")
                self.controller.Notices['ratgdo'] = error
            if res.json()['id'] == 'light-light':
                LOGGER.info('RATGDO communications good!')
                self.ratgdoOK = True
                return True
        except Exception as ex:
            LOGGER.error(f"error: {ex}")
        self.ratgdoOK = False
        return False

    def createDB(self):
        success = False
        try:
            LOGGER.info(f'Checking to see existence of db file: {self.file}')
            if os.path.exists(self.file):
                LOGGER.info('...file exists')
                self.retrieveValues()
            else:
                s = shelve.open(self.key, writeback=True)
                s[self.key] = { 'created': 'yes'}
                time.sleep(2)
                s.close()
                LOGGER.info("...file didn\'t exist, created successfully")
        except Exception as ex:
                LOGGER.error(f"createDBfile error: {ex}")
        else:
            success = True
        finally:
            LOGGER.info(f"createDB complete...success = {success}")
            return success

    def deleteDB(self):
        success = False
        try:
            if os.path.exists(self.file):
                LOGGER.info(f'Deleting db: {self.file}')
                subprocess.run(["rm", self.file])
        except Exception as ex:
                LOGGER.error(f"deleteDB error: {ex}")
        else:
            time.sleep(1)
            success = True
        finally:
            LOGGER.info(f"deleteDB complete...success = {success}")
            return success

    def storeValues(self):
        s = shelve.open(self.key, writeback=True)
        try:
            s[self.key] = { 'light': self.light,
                            'door': self.door,
                            'motion': self.motion,
                            'lock': self.lock,
                            'obstruct': self.obstruct}
        finally:
            s.close()
        LOGGER.info('Values Stored')
        self.listValues()

    def listValues(self):
        s = shelve.open(self.key, writeback=True)
        try:
            existing = s[self.key]
        finally:
            s.close()
        LOGGER.info(existing)

    def retrieveValues(self):
        s = shelve.open(self.key, writeback=True)
        try:
            existing = s[self.key]
        finally:
            s.close()
        LOGGER.info('Retrieving Values %s', existing)
        self.light = existing['light']
        self.door = existing['door']
        self.motion = existing['motion']
        self.lock = existing['lock']
        self.obstruct = existing['obstruct']

    def ratgdoPost(self, post):
        if self.ratgdoOK:
            LOGGER.info(f'post:{post}')
            try:
                rpost = requests.post(f"http://{post}")
                if not rpost.ok:
                    LOGGER.error(f"{post}: {rpost.status_code}")
            except Exception as ex:
                LOGGER.error(f"{post}: {ex}")
        
    def ltOn(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.light = 1
        self.setDriver('GV0', self.light)
        if self.lightId > 0:
            self.pushTheValue(self.lightT, self.lightId, self.light)
        self.storeValues()
        post = f"{self.ratgdo}{LIGHT}{TURN_ON}"
        self.ratgdoPost(post)
        self.resetTime()

    def ltOff(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.light = 0
        self.setDriver('GV0', self.light)
        if self.lightId > 0:
            self.pushTheValue(self.lightT, self.lightId, self.light)
        self.storeValues()
        post = f"{self.ratgdo}{LIGHT}{TURN_OFF}"
        self.ratgdoPost(post)
        self.resetTime()
        
    def drOpen(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.dcommand = 1
        self.setDriver('GV2', self.dcommand)
        if self.dcommandId > 0:
            self.pushTheValue(self.dcommandT, self.dcommandId, self.dcommand)
        self.storeValues()
        post = f"{self.ratgdo}{DOOR}{OPEN}"
        self.ratgdoPost(post)
        self.resetTime()
    
    def drClose(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.dcommand = 2
        self.setDriver('GV2', self.dcommand)
        if self.dcommandId > 0:
            self.pushTheValue(self.dcommandT, self.dcommandId, self.dcommand)
        self.storeValues()
        post = f"{self.ratgdo}{DOOR}{CLOSE}"
        self.ratgdoPost(post)
        self.resetTime()
        
    def drTrigger(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.dcommand = 3
        self.setDriver('GV2', self.dcommand)
        if self.dcommandId > 0:
            self.pushTheValue(self.dcommandT, self.dcommandId, self.dcommand)
        post = f"{self.ratgdo}{TRIGGER}"
        self.ratgdoPost(post)
        self.storeValues()
        self.resetTime()
        
    def drStop(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.dcommand = 4
        self.setDriver('GV2', self.dcommand)
        if self.dcommandId > 0:
            self.pushTheValue(self.dcommandT, self.dcommandId, self.dcommand)
        post = f"{self.ratgdo}{DOOR}{STOP}"
        self.ratgdoPost(post)
        self.storeValues()
        self.resetTime()
        
    def lkLock(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.lock = 1
        self.setDriver('GV4', self.lock)
        if self.lockId > 0:
            self.pushTheValue(self.lockT, self.lockId, self.lock)
        self.storeValues()
        post = f"{self.ratgdo}{LOCK_REMOTES}{LOCK}"
        self.ratgdoPost(post)
        self.resetTime()
    def lkUnlock(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.lock = 0
        self.setDriver('GV4', self.lock)
        if self.lockId > 0:
            self.pushTheValue(self.lockT, self.lockId, self.lock)
        self.storeValues()
        post = f"{self.ratgdo}{LOCK_REMOTES}{UNLOCK}"
        self.ratgdoPost(post)
        self.resetTime()

    def pushTheValue(self, type, id, value):
        _type = str(type)
        _id = str(id)
        _value = str(value)
        LOGGER.info(f'Pushing to {self.isy}, type: {_type}, id: {_id}, value: {_value}')
        self.isy.cmd('/rest/vars' + _type + _id + '/' + str(value))
    
    def getDataFromID(self):
        pass
    
    def UpdateVars(self):
        success = False
        change = False
        _data = 0
        if self.lightT > 0 and self.lightId > 0:
            success, _data = self.pullFromISY(self.lightT, self.lightId)
            LOGGER.debug(f'light success: {success}, _data: {_data}')
            if success:
                if self.light != _data:
                    self.light = _data
                    LOGGER.info(f'self.light = {self.light}')
                    change = True
            else:
                LOGGER.error('light, no success')
        if self.doorT > 0 and self.doorId > 0:
            success, _data = self.pullFromISY(self.doorT, self.doorId)
            LOGGER.debug(f'door success: {success}, _data: {_data}')
            if success:
                if self.door == 0 and _data != 0:
                    self.openTime = time.time()
                if self.door != _data:
                    self.door = _data
                    LOGGER.info(f'self.door = {self.door}')
                    change = True
            else:
                LOGGER.error('door, no success')
        if self.dcommandT > 0 and self.dcommandId > 0:
            success, _data = self.pullFromISY(self.dcommandT, self.dcommandId)
            LOGGER.debug(f'dcommand success: {success}, _data: {_data}')
            if success:
                if self.dcommand != _data:
                    self.dcommand = _data
                    LOGGER.info(f'self.dcommand = {self.dcommand}')
                    change = True
            else:
                LOGGER.error('dcommand, no success')
        if self.motionT > 0 and self.motionId > 0:
            success, _data = self.pullFromISY(self.motionT, self.motionId)
            LOGGER.debug(f'motion success: {success}, _data: {_data}')
            if success:
                if self.motion != _data:
                    self.motion = _data
                    LOGGER.info(f'self.motion = {self.motion}')
                    change = True
            else:
                LOGGER.error('motion, no success')
        if self.lockT > 0 and self.lockId > 0:
            success, _data = self.pullFromISY(self.lockT, self.lockId)
            LOGGER.debug(f'lock success: {success}, _data: {_data}')
            if success:
                if self.lock != _data:
                    self.lock = _data
                    LOGGER.info(f'self.lock = {self.lock}')
                    change = True
            else:
                LOGGER.error('lock, no success')
        if self.obstructT > 0 and self.obstructId > 0:
            success, _data = self.pullFromISY(self.obstructT, self.obstructId)
            LOGGER.debug(f'obstruct success: {success}, _data: {_data}')
            if success:
                if self.obstruct != _data:
                    self.obstruct = _data
                    LOGGER.info(f'self.obstruct = {self.obstruct}')
                    change = True
            else:
                LOGGER.error('obstruct, no success')
        if change:
            self.storeValues()
        return change
    
    def pullFromISY(self, type: int, id: int) -> tuple[bool, int]:
        success = False
        _data = 0
        if id == 0 or id == None:
            LOGGER.error(f'bad data id: {id}, _type: {type}')
        else:
            _type = GETLIST[self.lightT]
            _id = str(id)
            try:
                cmdString = '/rest/vars/get' + _type + _id
                LOGGER.debug(f'CMD Attempt: {self.isy}, type: {_type}, id: {_id},cmdString: {cmdString}')
                _r = self.isy.cmd(cmdString)
                LOGGER.debug(f'RES: {self.isy}, type: {_type}, id: {_id}, value: {_r}')
                if isinstance(_r, str):
                    r = parseString(_r)
                    if type == 1 or type == 3:
                        _content = r.getElementsByTagName("val")[0].firstChild
                    else:
                        _content = r.getElementsByTagName("init")[0].firstChild
                    if _content == None:
                        LOGGER.error(f'_content: {_content}')
                    else:                        
                        _data = int(_content.toxml())
                        LOGGER.debug(f'_data: {_data}')
                    success = True
                else:
                    LOGGER.error(f'r: {_r}')
            except Exception as ex:
                LOGGER.error(f'There was an error with the value pull or Parse: {ex}')
        return success, _data

    def pullFromRatgdo(self):
        pass
        # getDict = {
        #     LIGHT: self.light,
        #     DOOR: self.door,
        #     LOCK_REMOTES: self.lock,
        #     MOTION: self.motion,
        #     MOTOR: self.motor,
        #     OBSTRUCTION: self.obstruct,
        #     BUTTON: self.button,
        # }
        # for api in getDict:
        #     resTxt = f'http://{self.ratgdo}{api}'
        #     LOGGER.info(f'get {resTxt}')
        #     try:
        #         res = requests.get(resTxt)
        #         LOGGER.info(f"res.status_code = {res.status_code}")
        #         _data = getDict[api]
        # 
        # 
        # 
        #     if res.status_code == 200:
        #         try:
        #             self.ratgdo = res.json()['data']
        # 
        # for api in getArray:
        #     resTxt = f'http://{self.ratgdo}{api}'
        #     LOGGER.info(f'get {resTxt}')
        #     try:
        #         res = requests.get(resTxt)
        #         LOGGER.info(f"res.status_code = {res.status_code}")
        #         
        #     if res.json()['id'] == 'light-light':
        #         LOGGER.info('RATGDO communications good!')
        #         self.ratgdoOK = True
        #         return True
        # except Exception as ex:
        #     LOGGER.error(f"error: {ex}")
        #     LOGGER.error(f"res.status_code = {res.status_code}")
        #     error = f"RATGDO communications error code: {res.error}"
        #     self.controller.Notices['ratgdo'] = error
        #     LOGGER.error(error)
        # self.ratgdoOK = False
        # return False

    

    def updateAll(self):
        _currentTime = time.time()
        if self.UpdateVars() or self.firstPass:
            self.setDriver('GV0', self.light)
            if self.getDriver('GV1') != self.door:
                self.dcommand = 0
            self.setDriver('GV1', self.door)
            self.setDriver('GV2', self.dcommand)
            self.setDriver('GV3', self.motion)
            self.setDriver('GV4', self.lock)
            self.setDriver('GV5', self.obstruct)
            self.resetTime()
            if self.firstPass:
                self.openTime = time.time()
            self.firstPass = False
        else:
            if self.getDriver('GV0') != self.light:
                self.setDriver('GV0', self.light)
                self.resetTime()
                
            _doorOldStatus = self.getDriver('GV1')
            if _doorOldStatus != self.door:
                if _doorOldStatus == 0 and self.door != 0:
                    self.openTime = time.time()
                self.dcommand = 0
                self.setDriver('GV1', self.door)
                self.resetTime()
            if self.getDriver('GV2') != self.dcommand:
                self.setDriver('GV2', self.dcommand)
                self.resetTime()
            if self.getDriver('GV3') != self.motion:
                self.setDriver('GV3', self.motion)
                self.resetTime()
            if self.getDriver('GV4') != self.lock:
                self.setDriver('GV4', self.lock)
                self.resetTime()
            if self.getDriver('GV5') != self.obstruct:
                self.setDriver('GV5', self.obstruct)
                self.resetTime()

        _sinceLastUpdate = round(((_currentTime - self.lastUpdateTime) / 60), 1)
        if _sinceLastUpdate < 9999:
            self.setDriver('GV6', _sinceLastUpdate)
        else:
            self.setDriver('GV6', 9999)

        if self.door != 0:
            _openTimeDelta = round((_currentTime - self.lastUpdateTime), 1)
        else:
            _openTimeDelta = 0
        self.setDriver('GV7', _openTimeDelta)

    def resetStats(self, command = None):
        LOGGER.info('Resetting Stats')
        LOGGER.debug(f'command:{command}')
        self.firstPass = True
        self.resetTime()
        self.storeValues()

    def resetTime(self):
        self.currentTime = time.time()
        self.lastUpdateTime = time.time()
        self.setDriver('GV6', 0.0)
        
    def query(self, command = None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        LOGGER.debug(f'command:{command}')
        self.reportDrivers()


    # Hints See: https://github.com/UniversalDevicesInc/hints
    hint = [1,2,3,4]
    
    """
    This is an array of dictionary items containing the variable names(drivers)
    values and uoms(units of measure) from ISY. This is how ISY knows what kind
    of variable to display. Check the UOM's in the WSDK for a complete list.
    UOM 2 is boolean so the ISY will display 'True/False'
    """
    drivers = [
        {"driver": "GV0", "value": 0, "uom": 2},  #light
        {"driver": "GV1", "value": 0, "uom": 25}, #door status
        {"driver": "GV2", "value": 0, "uom": 25}, #door command
        {"driver": "GV3", "value": 0, "uom": 2},  #motion
        {"driver": "GV4", "value": 0, "uom": 2},  #lock
        {"driver": "GV5", "value": 0, "uom": 2},  #obstruction
        {'driver': 'GV6', 'value': 0, 'uom': 45}, #update time
        {'driver': 'GV7', 'value': 0, 'uom': 58}, #open time
    ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
        "QUERY": query,
        "LT_ON": ltOn,
        "LT_OFF": ltOff,
        "OPEN": drOpen,
        "CLOSE": drClose,
        "TRIGGER": drTrigger,
        "STOP": drStop,
        "LOCK": lkLock,
        "UNLOCK": lkUnlock,
        'resetStats': resetStats,
        }

