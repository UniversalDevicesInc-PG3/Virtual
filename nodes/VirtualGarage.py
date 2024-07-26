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
import json
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
OBSTRUCT = "/binary_sensor/obstruction"
TRIGGER = "/button/toggle_door/press"
EVENTS = "/events"

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

    """ This class is meant to represent a virtual garage device.
    Taking values from variables and allowing control back to said variables.
    Optionally, the virtual device can interact with a Ratgdo board which is running
    ESPHome and is connected to a physical garage opener.

    Drivers & commands:
    'GV0' : light status On/Off
    'GV1' : door status Closed/Open/Opening/Stopped/Closing
    'GV2' : door command None/Open/Close/Trigger/Stop
    'GV3' : motion Clear/Detected
    'GV4' : remote-lock Unlocked/Locked      
    'GV5' : obstruction Clear/Obstructed
    'GV6' : time since last update in minutes
    'GV7' : time garage open = not closed

    'query'         : query all vars
    'ltOn'          : light on
    'ltOff'         : light off
    'drOpen'        : door open
    'drClose'       : door close
    'drTrigger'     : door trigger
    'drStop'        : door stop
    'lkLock'        : remote lock
    'lkUnlock'      : remove unlock
    'resetStats'    : reset Statistics
    
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
        self.lastUpdateTime timestamp
        self.light, door, motion, lock, obstruct represented by 0/1
        self.lightT, doorT, motionT, lockT, obstructT State var or init, Int var or init, 1 - 4
        self.lightId, doorId, motionId, lockId, obstructId represented by 0=None, 1-400

        subscribes:
        START: used to create/check/load DB file
        POLL: shortPoll for updates
        Controller node calls:
          self.deleteDB() when ISY deletes the node or discovers it gone
        """
        super().__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.primary = primary
        self.controller = polyglot.getNode(self.primary)
        self.address = address
        self.name = name

        self.lastUpdateTime = 0.0
        self.openTime = 0.0

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

        self.firstPass = True
        self.updatingAll = 0

        self.bonjourCommand = None
        self.bonjourOn = False
        self.bonjourOnce = True
        self.ratgdo = False
        self.ratgdoOK = False
        self.ratgdo_array = []
        self.ratgdo_event = []
        self.eventTimeout = 720
        self.eventTimer = 0

        self.ratgdo_do_poll = True
        self.ratgdo_do_events = False
        
        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)
        self.poly.subscribe(self.poly.BONJOUR, self.bonjour)

    def start(self):
        """ START event subscription above """
        self.isy = ISY(self.poly)
        self.dCommand = 0
        self.bonjourOnce = True
        self.getConfigData()
        self.resetTime()
        self.createDBfile()
        
    def poll(self, flag):
        """ POLL event subscription above """
        LOGGER.debug(f"POLLING: {flag} {self.name}")
        if 'longPoll' in flag:
            pass
        else:
            if self.bonjourOnce and self.bonjourOn:
                self.bonjourOnce = False
                self.poly.bonjour('http', None, None)
            if self.updatingAll <= 0:
                self.updateAll()
            elif 1 == self.updatingAll <=3:
                self.updatingAll += 1
            else:
                self.updatingAll = 0

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
                s[_key] = { 'created': 'yes'}
                time.sleep(2)
                s.close()
                LOGGER.info("...file didn\'t exist, created successfully")
                self.resetStats()
        except Exception as ex:
                LOGGER.error(f"createDBfile error: {ex}")

    def deleteDB(self, command=None):
        """ Called from Controller when node is deleted """
        LOGGER.debug(f"deleteDB, {self.name} {command}")
        _name = str(self.name).replace(" ","_")
        _file = f"db/{_name}.db"
        if os.path.exists(_file):
            LOGGER.info(f'Deleting db: {_file}')
            subprocess.run(["rm", _file])

    def storeValues(self):
        _key = 'key' + str(self.address)
        _name = str(self.name).replace(" ","_")
        s = shelve.open(f"db/{_name}", writeback=False)
        try:
            s[_key] = { 'light': self.light,
                        'door': self.door,
                        'motion': self.motion,
                        'lock': self.lock,
                        'obstruct': self.obstruct,
                       }
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
        self.light = existing['light']
        self.door = existing['door']
        self.motion = existing['motion']
        self.lock = existing['lock']
        self.obstruct = existing['obstruct']

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
                ratgdoTemp = self.dev['ratgdo']
                if ratgdoTemp in ['true', 'True', True, RATGDO, f"{RATGDO}.local"]:
                    if self.ratgdoOK == False:
                        self.ratgdo = RATGDO
                        self.bonjourOn = True
                        warn = f"Searching for RATGDO IP: {RATGDO}"
                        LOGGER.error(warn)
                        self.controller.Notices['ratgdo'] = warn
                elif ratgdoTemp in [False, 'false', 'False']:
                    self.ratgdo = False
                else:
                    try:
                        self.ratgdo = ratgdoTemp
                        ipaddress.ip_address(self.ratgdo)
                        self.ratgdoCheck()
                    except:
                        error = f"RATGDO address error: {self.ratgdo}"
                        LOGGER.error(error)
                        self.controller.Notices['ratgdo'] = error
                        self.ratgdo = False
            except:
                self.ratgdo = False
            LOGGER.info(f'self.ratgdo = {self.ratgdo}')                        
        else:
            LOGGER.error('no self.dev data')
        
    def bonjour(self, command):
        # bonjour(self, type, subtypes, protocol)
        LOGGER.info(f"BonjourMessage")
        try:
            if command['success']:
                mdns = command['mdns']
                for addr in mdns:
                    LOGGER.info(f"addr: {addr['name']}, type:{addr['type']}")
                    if addr['name'] == RATGDO:
                        self.controller.Notices.delete('ratgdo')
                        self.ratgdo = addr['addresses'][0]
                        LOGGER.warn(f"FOUND RATGDO@'{self.ratgdo}':ip: {addr['addresses']}, name: {addr['name']}")
                        if self.ratgdoCheck():
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

    def ratgdoPost(self, post):
        if self.ratgdoOK:
            LOGGER.info(f'post:{post}')
            try:
                rpost = requests.post(f"http://{post}")
                if not rpost.ok:
                    LOGGER.error(f"{post}: {rpost.status_code}")
            except Exception as ex:
                LOGGER.error(f"{post}: {ex}")
        
    def sseProcess(self):
        if not self.ratgdo:
            self.ratgdo_sse = self.sseInit()
        yy = str(self.ratgdo_sse)
        try:
            while True:
                LOGGER.info(yy)
                yy = str(yy) + str(next(self.ratgdo_sse))
        except:
            pass
        LOGGER.info(f"yy:{yy}")
        return yy
                    
    def sseInit(self):
        """ connect and pull from the ratgdo stream of events """
        self.ratgdo_event = []

        url = f"http://{self.ratgdo}{EVENTS}"
        LOGGER.info(f"url: {url}")
        try:
            sse = requests.get(url, headers={"Accept": "application/x-ldjson"}, stream=True)
            x = (s.rstrip() for s in sse)
            # y = str("raw = {}".format(next(x)))
            # LOGGER.info(y)
        except:
            x = False
        return str(x)

    def ltOn(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.light = 1
        self.setDriver('GV0', self.light)
        if self.lightId > 0:
            self.pushTheValue(self.lightT, self.lightId, self.light)
        post = f"{self.ratgdo}{LIGHT}{TURN_ON}"
        self.ratgdoPost(post)
        self.storeValues()
        self.resetTime()

    def ltOff(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.light = 0
        self.setDriver('GV0', self.light)
        if self.lightId > 0:
            self.pushTheValue(self.lightT, self.lightId, self.light)
        post = f"{self.ratgdo}{LIGHT}{TURN_OFF}"
        self.ratgdoPost(post)
        self.storeValues()
        self.resetTime()
        
    def drCommand(self, post):
        if self.dcommandId > 0:
            self.pushTheValue(self.dcommandT, self.dcommandId, self.dcommand)
        self.setDriver('GV2', self.dcommand)
        self.ratgdoPost(post)
        self.storeValues()
        self.resetTime()
    
    def drOpen(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.dcommand = 1
        post = f"{self.ratgdo}{DOOR}{OPEN}"
        self.drCommand(post)
    
    def drClose(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.dcommand = 2
        post = f"{self.ratgdo}{DOOR}{CLOSE}"
        self.drCommand(post)
        
    def drTrigger(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.dcommand = 3
        post = f"{self.ratgdo}{TRIGGER}"
        self.drCommand(post)
        
    def drStop(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.dcommand = 4
        post = f"{self.ratgdo}{DOOR}{STOP}"
        self.drCommand(post)
        
    def lkLock(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.lock = 1
        self.setDriver('GV4', self.lock)
        if self.lockId > 0:
            self.pushTheValue(self.lockT, self.lockId, self.lock)
        post = f"{self.ratgdo}{LOCK_REMOTES}{LOCK}"
        self.ratgdoPost(post)
        self.storeValues()
        self.resetTime()
        
    def lkUnlock(self, command = None):
        LOGGER.debug(f'command:{command}')
        self.lock = 0
        self.setDriver('GV4', self.lock)
        if self.lockId > 0:
            self.pushTheValue(self.lockT, self.lockId, self.lock)
        post = f"{self.ratgdo}{LOCK_REMOTES}{UNLOCK}"
        self.ratgdoPost(post)
        self.storeValues()
        self.resetTime()

    def pushTheValue(self, type, id, value):
        _type = str(type)
        _id = str(id)
        _value = str(value)
        LOGGER.info(f'Pushing to {self.isy}, type: {_type}, id: {_id}, value: {_value}')
        self.isy.cmd('/rest/vars' + _type + _id + '/' + str(value))
    
    def updateVars(self):
        success = False
        change = False
        if self.ratgdo and self.ratgdoOK:
            if self.ratgdo_do_poll:
                success = self.getRatgdoDirect()
            if self.ratgdo_do_events:
                success = self.getRatgdoEvents()
        else:
            success, self.light, change = self.updateVar('light', self.light, self.lightT, self.lightId)
            success, self.door, change = self.updateVar('door', self.door, self.doorT, self.doorId)
            success, self.dcommand, change = self.updateVar('dcommand', self.dcommand, self.dcommandT, self.dcommandId)
            success, self.motion, change = self.updateVar('motion', self.motion, self.motionT, self.motionId)
            success, self.lock, change = self.updateVar('lock', self.lock, self.lockT, self.lockId)
            success, self.obstruct, change = self.updateVar('obstruct', self.obstruct, self.obstructT, self.obstructId)
        if success:
            self.storeValues()
        return change
    
    def updateVar(self, name, dev, T, Id):
        success = False
        change = False
        _data = 0
        try:
            if T > 0 and Id > 0:
                success, _data = self.pullFromISY(T, Id)
                if success:
                    LOGGER.debug(f'{name} success: {success}, _data: {_data}')
                    if dev != _data:
                        LOGGER.info(f'changed {name} = {dev}')
                        change = True
                        dev = _data
        except Exception as ex:
            LOGGER.error(f"Error: {ex}")
        return success, dev, change
    
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
                time.sleep(2)
        return success, _data

    def getRatgdoDirect(self):
        success = False
        _data = 0
        state = None
        success, _data = self.pullFromRatgdo(LIGHT)
        if success:
            state = _data['state']
            LOGGER.debug(f"id: {_data['id']}, state: {state}")
            if state == 'ON':
                self.light = 1
            elif state == 'OFF':
                self.light = 0
            success, _data = self.pullFromRatgdo(DOOR)
            if success:
                state = _data['state']
                LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
                if state == 'CLOSED':
                    self.door = 0
                elif state == 'OPEN':
                        self.door = 1
                elif state == 'OPENING':
                        self.door = 2
                elif state == 'STOPPED':
                        self.door = 3
                elif state == 'CLOSING':
                        self.door = 4
                success, _data = self.pullFromRatgdo(MOTION)
                if success:
                    state = _data['state']
                    LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {_data['state']}")
                    if state == 'ON':
                        self.motion = 1
                    elif state =='OFF':
                        self.motion = 0
                    success, _data = self.pullFromRatgdo(LOCK_REMOTES)
                    if success:
                        state = _data['state']
                        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
                        if state == 'LOCKED':
                            self.lock = 1
                        elif state == 'UNLOCKED':
                            self.lock = 0
                        success, _data = self.pullFromRatgdo(OBSTRUCT)
                        if success:
                            state = _data['state']
                            LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {_data['state']}")
                            if state == 'ON':
                                self.obstruct = 1
                            elif state == 'OFF':
                                self.obstruct = 0
        return success
    
    def pullFromRatgdo(self, get):
        _data = {}
        resTxt = f'{self.ratgdo}{get}'
        # LOGGER.debug(f'get {resTxt}')
        try:
            res = requests.get(f"http://{resTxt}")
            if res.ok:
                LOGGER.debug(f"res.status_code = {res.status_code}")
            else:
                LOGGER.error(f"res.status_code = {res.status_code}")
                return False, {}
            _data = res.json()
            LOGGER.debug(f"{get} = {_data}")
            return True, _data
        except Exception as ex:
            LOGGER.error(f"error: {ex}")
            return False, {}

    def getRatgdoEvents(self):
        try:
            event = list(filter(lambda events: events['event'] == 'ping', self.ratgdo_event))
            if event:
                event = event[0]
                LOGGER.warn('event - ping - {}'.format(event))
                self.ratgdo_event.remove(event)
            event = list(filter(lambda events: events['event'] == 'state', self.ratgdo_event))
            if event:
                event = event[0]
                LOGGER.warn('event - state - {}'.format(event))
                self.ratgdo_event.remove(event)
        except:
            LOGGER.error("LongPoll event error")
        LOGGER.info("event(total) = {}".format(self.ratgdo_event))
        try:
            if self.ratgdoOK:
                yy = self.sseProcess()
                # if yy != {}:
                #     self.ratgdo_event.append(yy)
                LOGGER.info(f"{self.eventTimer} new event = {yy}")
                self.eventTimer = 0
        except:
            self.eventTimer += 1
            LOGGER.info(f"increment eventTimer = {self.eventTimer}")
            if self.eventTimer > self.eventTimeout:
                self.ratgdo_sse = self.sseInit()
                LOGGER.info(f"eventTimeout")
                self.eventTimer = 0
        return True # success

    def updateAll(self):
        self.updatingAll = 1
        _currentTime = time.time()
        if self.updateVars() or self.firstPass:
            self.setDriver('GV0', self.light)
            if self.getDriver('GV1') != self.door:
                self.dcommand = 0
            self.setDriver('GV1', self.door)
            self.setDriver('GV2', self.dcommand)
            self.setDriver('GV3', self.motion)
            self.setDriver('GV4', self.lock)
            self.setDriver('GV5', self.obstruct)
            self.resetTime()
            self.firstPass = False
        else:
            if self.getDriver('GV0') != self.light:
                self.setDriver('GV0', self.light)
                self.resetTime()
            _doorOldStatus = self.getDriver('GV1')
            if _doorOldStatus != self.door:
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
            if self.openTime == 0.0:
                self.openTime = _currentTime
            _openTimeDelta = round((_currentTime - self.openTime), 1)
        else:
            self.openTime = 0.0
            _openTimeDelta = 0
        self.setDriver('GV7', _openTimeDelta)
        self.updatingAll = 0

    def resetStats(self, command = None):
        LOGGER.info('Resetting Stats')
        LOGGER.debug(f'command:{command}')
        self.firstPass = True
        self.resetTime()
        self.storeValues()

    def resetTime(self):
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

