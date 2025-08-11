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
import json
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
MOTOR = "/binary_sensor/motor"
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
    'GV8' : motor status On/Off
    'GV8' : door position

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
        self.motor = 0
        self.motorT = 1
        self.motorId = 0
        self.position = 0
        self.positionT = 1
        self.positionId = 0
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
        self.updatingAll = False

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
        self.ratgdo_do_events = True
        
        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)
        self.poly.subscribe(self.poly.BONJOUR, self.bonjour)

    def start(self):
        """ START event subscription above """
        self.isy = ISY(self.poly)
        self.firstPass = True
        self.dCommand = 0
        self.bonjourOnce = True
        self.getConfigData()
        self.resetTime()
        self.createDBfile()
        if self.ratgdo and self.ratgdo_do_events:
            while not self.ratgdoOK:
                time.sleep(2)
            while True:
                self.getRatgdoEvents()
                LOGGER.error('start events dropped out')
                time.sleep(10)
        
    def poll(self, flag):
        """ POLL event subscription above """
        if 'longPoll' in flag:
            LOGGER.info(f"POLLING: {flag} {self.name}")
            if self.ratgdo and self.ratgdoOK:
                if self.ratgdo_do_poll and not self.updatingAll:
                    success = self.getRatgdoDirect()
                    LOGGER.info(f"getRadgdoDirect success = {success}")
                    self.updatingAll = False
        else:
            if self.bonjourOnce and self.bonjourOn:
                self.bonjourOnce = False
                self.poly.bonjour('http', None, None)
            if not self.ratgdo:
                self.updateVars()
            self.updateISY()

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
        # repull config data for var data, light, door, dcommand, motor, motion, lock, obstruction
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
                self.positionT = self.dev['positionT']
                LOGGER.debug(f'self.positionT = {self.positionT}')
            except:
                self.positionT = 1
            try:
                self.positionId = self.dev['positionId']
                LOGGER.debug(f'self.positionId = {self.positionId}')
            except:
                self.positionId = 0
            try:
                self.motorT = self.dev['motorT']
                LOGGER.debug(f'self.motorT = {self.motorT}')
            except:
                self.motorT = 1
            try:
                self.motorId = self.dev['motorId']
                LOGGER.debug(f'self.motorId = {self.motorId}')
            except:
                self.motorId = 0
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
                        LOGGER.warning(f"FOUND RATGDO@'{self.ratgdo}':ip: {addr['addresses']}, name: {addr['name']}")
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
        
    def getRatgdoEvents(self):
        timer = 0
        msg = {}
        while True:
            LOGGER.debug(f'gIN: {timer}')
            try:
                i = self.sseEvent()
            except:
                break
            if not i:
                timer += 1
            else:
                timer = 0
                LOGGER.info(self.ratgdo_event)
            if timer >= 1000:
                break
            while self.ratgdo_event != []:
                try:
                    event = self.ratgdo_event[0]
                    if event['event'] == 'ping':
                        LOGGER.info('event:ping')
                        self.ratgdo_event.remove(event)
                    elif event['event'] == 'state':
                        try:
                            msg = json.loads(event['data'])
                            id = msg['id']
                        except:
                            LOGGER.error(f'bad event data {event}')
                            id = 'bad'
                        finally:
                            LOGGER.info(f"event:state: {id}")
                            if id == 'light-light':
                                self.setRatgdoLight(msg)
                            elif id == 'cover-door':
                                self.setRatgdoDoor(msg)
                            elif id == 'binary_sensor-motor':
                                self.setRatgdoMotor(msg)
                            elif id == 'binary_sensor-motion':
                                self.setRatgdoMotion(msg)
                            elif id == 'lock-lock_remotes':
                                self.setRatgdoLock(msg)
                            elif id == 'binary_sensor-obstruction': 
                                self.setRatgdoObstruct(msg)
                            else:
                                LOGGER.warning(f'event:state - NO ACTION - {id}')
                        self.ratgdo_event.remove(event)
                    elif event['event'] == 'error':
                        LOGGER.info('event:error')
                        self.ratgdo_event.remove(event)
                    elif event['event'] == 'log':
                        LOGGER.info('event:log')
                        self.ratgdo_event.remove(event)
                        if 'Rebooting...' in event['data']:
                            LOGGER.warning('API Rebooting...')
                            break
                    elif event['event'] == 'other':
                        LOGGER.info('event:other')
                        self.ratgdo_event.remove(event)
                    elif event['event'] == 'id':
                        LOGGER.info(f'event:id={event["data"]}')
                        self.ratgdo_event.remove(event)
                    elif event['event'] == 'retry':
                        LOGGER.info('event:retry')
                        self.ratgdo_event.remove(event)
                    else:
                        LOGGER.error(f'event - NONE FOUND - <{event}>')
                        self.ratgdo_event.remove(event)
                except:
                    LOGGER.error("event parse error")
                    break
            LOGGER.info('Done processing getRatgdoEvents')
            
    def sseEvent(self):
        success = False
        url = f"http://{self.ratgdo}{EVENTS}"
        try:
            LOGGER.debug(f"GET: {url}")
            s = requests.Session()
            e = {}
            with s.get(url,headers=None, stream=True, timeout=3) as gateway_sse:
                for val in gateway_sse.iter_lines():
                    dval = val.decode('utf-8')
                    #LOGGER.debug(f"raw decode:[{dval}]")
                    if val:                            
                        if e:
                            try:
                                i = dict(event = e, data = dval.replace('data: ',''))
                            except:
                                i = dict(event = e, data = 'error')
                            self.ratgdo_event.append(i)
                            success = True
                            e = None
                        else:
                            if 'event: ' in dval:
                                e = dval.replace('event: ','')
                                continue
                            else:
                                try:
                                    i = dict(event = dval.split(":")[0], data = dval.split(":")[1])
                                    #LOGGER.debug(f"raw dict:[{i}]")
                                    self.ratgdo_event.append(i)
                                    success = True
                                except:
                                    LOGGER.error(f"raw dict parse error")
        except requests.exceptions.Timeout:
            LOGGER.debug(f"see timeout")
        except requests.exceptions.RequestException as e:
            LOGGER.debug(f"sse other exception: {e}")
        return success

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

    def pullFromRatgdo(self, get):
        _data = {}
        resTxt = f'{self.ratgdo}{get}'
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

    def getRatgdoDirect(self):
        try:
            res = requests.get(f"http://{self.ratgdo}{LIGHT}")
            if not res.ok:
                LOGGER.error(f"LIGHT: res.status_code = {res.status_code}")
                return False
            else:
                self.setRatgdoLight(res.json())
        except Exception as ex:
            LOGGER.error(f"LIGHT error: {ex}")
            return False

        time.sleep(.2)
                
        try:
            res = requests.get(f"http://{self.ratgdo}{DOOR}")
            if not res.ok:
                LOGGER.error(f"DOOR: res.status_code = {res.status_code}")
                return False
            else:
                self.setRatgdoDoor(res.json())
        except Exception as ex:
            LOGGER.error(f"DOOR error: {ex}")
            return False

        time.sleep(.2)
                
        try:
            res = requests.get(f"http://{self.ratgdo}{MOTION}")
            if not res.ok:
                LOGGER.error(f"MOTION: res.status_code = {res.status_code}")
                return False
            else:
                self.setRatgdoMotion(res.json())
        except Exception as ex:
            LOGGER.error(f"MOTION error: {ex}")
            return False

        time.sleep(.2)
                
        try:
            res = requests.get(f"http://{self.ratgdo}{MOTOR}")
            if not res.ok:
                LOGGER.error(f"MOTOR: res.status_code = {res.status_code}")
                return False
            else:
                self.setRatgdoMotor(res.json())
        except Exception as ex:
            LOGGER.error(f"MOTOR error: {ex}")
            return False

        time.sleep(.2)
                
        try:
            res = requests.get(f"http://{self.ratgdo}{LOCK_REMOTES}")
            if not res.ok:
                LOGGER.error(f"LOCK_REMOTES: res.status_code = {res.status_code}")
                return False
            else:
                self.setRatgdoLock(res.json())
        except Exception as ex:
            LOGGER.error(f"LOCK_REMOTES error: {ex}")
            return False

        time.sleep(.2)
                
        try:
            res = requests.get(f"http://{self.ratgdo}{OBSTRUCT}")
            if not res.ok:
                LOGGER.error(f"OBSTRUCT: res.status_code = {res.status_code}")
                return False
            else:
                self.setRatgdoObstruct(res.json())
        except Exception as ex:
            LOGGER.error(f"OBSTRUCT error: {ex}")
            return False

        LOGGER.info('getRatgdoDirect success!')
        return True
                                
    def setRatgdoLight(self, _data):
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, state: {state}")
        if state == 'ON':
            self.light = 1
        elif state == 'OFF':
            self.light = 0

    def setRatgdoDoor(self, _data):
        state = _data['state']
        value = int(round(_data['value'] * 100))
        current_operation = _data['current_operation']
        LOGGER.debug(f"id: {_data['id']}, value: {value}, state: {state}, current: {current_operation}")

        if current_operation == 'IDLE':
            if state == 'CLOSED':
                self.door = 0
            elif state == 'OPEN':
                    self.door = 100
            elif state == 'OPENING':
                    self.door = 104
            elif state == 'STOPPED':
                    self.door = 102
            elif state == 'CLOSING':
                    self.door = 103
            else: # UNKNOWN
                    self.door = 101
        elif current_operation == 'OPENING':
            self.door = 104
        elif current_operation == 'CLOSING':
            self.door = 103
            
        # check position
        if 0 <= value <= 100:
            LOGGER.info(f"value True, value: {value}")
            self.position = value
        else:
            LOGGER.info(f"value False, value: {value}")
            self.position = 101

    def setRatgdoMotor(self, _data):
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'ON':
            self.motor = 1
        elif state =='OFF':
            self.motor = 0

    def setRatgdoMotion(self, _data):
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'ON':
            self.motion = 1
        elif state =='OFF':
            self.motion = 0

    def setRatgdoLock(self, _data):
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'LOCKED':
            self.lock = 1
        elif state == 'UNLOCKED':
            self.lock = 0

    def setRatgdoObstruct(self, _data):
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'ON':
            self.obstruct = 1
        elif state == 'OFF':
            self.obstruct = 0
                                
    def updateISY(self):
        _currentTime = time.time()
        if self.firstPass:
            self.setDriver('GV0', self.light)
            if self.getDriver('GV1') != self.door:
                self.dcommand = 0
            self.setDriver('GV1', self.door)
            self.setDriver('GV2', self.dcommand)
            self.setDriver('GV8', self.motor)
            self.setDriver('GV9', self.position)
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
            if self.getDriver('GV8') != self.motor:
                self.setDriver('GV8', self.motor)
                self.resetTime()
            if self.getDriver('GV9') != self.position:
                self.setDriver('GV9', self.position)
                self.resetTime()
            if self.getDriver('GV3') != self.motor:
                self.setDriver('GV3', self.motor)
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

    def resetStats(self, command = None):
        LOGGER.info('Resetting Stats')
        LOGGER.debug(f'command:{command}')
        self.firstPass = True
        self.resetTime()
        self.storeValues()

    def resetTime(self):
        """ Reset the last update time to now """
        self.lastUpdateTime = time.time()
        self.setDriver('GV6', 0.0)
        
    def query(self, command = None):
        """ Query for updated values """ 
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
        {"driver": "GV1", "value": 0, "uom": 97}, #door status
        {'driver': 'GV8', 'value': 0, 'uom': 2},  #motor
        {"driver": "GV9", "value": 0, "uom": 97}, #door position
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

