"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

VirtualGarage class
"""
# standard imports
import time, shelve, ipaddress, asyncio
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, Optional, Tuple
from xml.dom.minidom import parseString
from dataclasses import dataclass
from pathlib import Path
from threading import Thread, Event, Lock

# external imports
import udi_interface
import requests
import json

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

# Dispatch map to select the correct tag and index based on var_type.
# Using a dictionary for dispatch is more extensible and readable than a long if/elif chain.
_VARIABLE_TYPE_MAP = {
    # Key: ISY var_type, Value : (INDEX, XML_TAG, SET_TAG)
    '1': ('2', 'val', 'set'),
    '2': ('2', 'init', 'init'),
    '3': ('1', 'val', 'set'),
    '4': ('1', 'init', 'init'),
}

@dataclass(frozen=True)
class FieldSpec:
    driver: Optional[str]  # e.g., "GV1" or None if not pushed to a driver
    default: Any           # per-field default
    data_type: str         # denote data type (state or config)

# Single source of truth for field names, driver codes, and defaults
FIELDS: dict[str, FieldSpec] = {
    # State variables (pushed to drivers)
    "light":           FieldSpec(driver="GV0", default=0, data_type="state"),
    "door":            FieldSpec(driver="GV1", default=0, data_type="state"),
    "dcommand":        FieldSpec(driver="GV2", default=0, data_type="state"),
    "motion":          FieldSpec(driver="GV3", default=0, data_type="state"),
    "lock":            FieldSpec(driver="GV4", default=0, data_type="state"),
    "obstruct":        FieldSpec(driver="GV5", default=0, data_type="state"),
    "lastUpdateTime":  FieldSpec(driver="GV6", default=0.0, data_type="state"),
    "openTime":        FieldSpec(driver="GV7", default=0.0, data_type="state"),
    "motor":           FieldSpec(driver="GV8", default=0, data_type="state"),
    "position":        FieldSpec(driver="GV9", default=0, data_type="state"),
    
    # Configuration variables (set during discovery/config, no driver)
    "lightT":          FieldSpec(driver=None, default=1, data_type="config"),
    "lightId":         FieldSpec(driver=None, default=0, data_type="config"),
    "doorT":           FieldSpec(driver=None, default=1, data_type="config"),
    "doorId":          FieldSpec(driver=None, default=0, data_type="config"),
    "dcommandT":       FieldSpec(driver=None, default=1, data_type="config"),
    "dcommandId":      FieldSpec(driver=None, default=0, data_type="config"),
    "motionT":         FieldSpec(driver=None, default=1, data_type="config"),
    "motionId":        FieldSpec(driver=None, default=0, data_type="config"),
    "lockT":           FieldSpec(driver=None, default=1, data_type="config"),
    "lockId":          FieldSpec(driver=None, default=0, data_type="config"),
    "obstructT":       FieldSpec(driver=None, default=1, data_type="config"),
    "obstructId":      FieldSpec(driver=None, default=0, data_type="config"),
    "motorT":          FieldSpec(driver=None, default=1, data_type="config"),
    "motorId":         FieldSpec(driver=None, default=0, data_type="config"),
    "positioT":        FieldSpec(driver=None, default=1, data_type="config"),
    "positionId":      FieldSpec(driver=None, default=0, data_type="config"),
}


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

# We need an event loop as we run in a
# thread which doesn't have a loop
mainloop = asyncio.get_event_loop()


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
    'GV9' : door position

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
    def __init__(self, polyglot, primary, address, name, *, default_ovr: Optional[Dict[str, Any]] = None):
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
        
        # default variables and drivers
        self.data = {field: spec.default for field, spec in FIELDS.items()}

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)
        self.poly.subscribe(self.poly.BONJOUR, self.bonjour)
        

    def start(self):
        """
        Start node and retrieve persistent data
        """
        LOGGER.info(f'start: garage:{self.name}')
        
        # wait for controller start ready
        self.controller.ready_event.wait()

        # get persistent data from polyglot or depreciated: old db file, then delete db file
        self.load_persistent_data()

        self.isy = ISY(self.poly)
        self.firstPass = True
        self.bonjourOnce = True

        # Set up a lock for ratgdo access
        self.ratgdo_lock = Lock()

        # set-up async loop
        self.mainloop = mainloop
        asyncio.set_event_loop(mainloop)
        self.connect_thread = Thread(target=mainloop.run_forever)
        self.connect_thread.start()

        self.getConfigData()
        self.resetTime()

        if self.ratgdo and self.ratgdo_do_events:
            # # Signal readiness and start the event processing in the background
            # asyncio.run_coroutine_threadsafe(self.getRatgdoEvents_async(), self.mainloop)            
            while not self.ratgdoOK:
                time.sleep(2)
            while True:
                self.getRatgdoEvents()
                LOGGER.error('start events dropped out')
                time.sleep(10)
                    
    async def _poll_ratgdo_via_executor(self):
        # Run the blocking call in a separate thread pool
        await asyncio.to_thread(self.getRatgdoDirect)

    async def getRatgdoEvents_async(self):
        # Your original event loop logic, but with async await and event.is_set()
        while not self.controller.stop_polling_event.is_set():
            # Use async methods for I/O
            await asyncio.sleep(1)
            # Process ratgdo events

                
    def poll(self, flag):
        """ POLL event subscription above """
        if 'longPoll' in flag:
            LOGGER.info(f"POLLING: {flag} {self.name}")
            if self.ratgdo and self.ratgdoOK:
                if self.ratgdo_do_poll and not self.updatingAll:
                    self.updatingAll = True
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

    def _push_drivers(self) -> None:
        """
        Push only fields that have a driver mapping
        """
        for field, spec in FIELDS.items():
            if spec.driver and spec.data_type == "state":
                self.setDriver(spec.driver, self.data[field], report=True, force=True)

                
    def _apply_state(self, src: Dict[str, Any]) -> None:
        """
        Apply values from src; fall back to per-instance defaults
        """
        for field in FIELDS.keys():
            self.data[field] = src.get(field, self.data.get(field))

            
    def _shelve_file_candidates(self, base: Path) -> Iterable[Path]:
        """
        Include the base and any shelve artifacts (base, base.*)
        """
        patterns = [base.name, f"{base.name}.*"]
        seen: set[Path] = set()
        for pattern in patterns:
            for p in base.parent.glob(pattern):
                if p.exists():
                    seen.add(p)
        return sorted(seen)


    def _check_db_files_and_migrate(self) -> Tuple[bool, Dict[str, Any] | None]:
        """
        Check for deprecated shelve DB files, migrate data, then delete old files.
        Called by load_persistent_data once during startup.
        """
        name_safe = self.name.replace(" ", "_")
        base = Path("db") / name_safe  # shelve base path (no extension)

        candidates = list(self._shelve_file_candidates(base))
        if not candidates:
            LOGGER.info("[%s] No old DB files found at base: %s", self.name, base)
            return False, None

        LOGGER.info("[%s] Old DB files found, migrating data...", self.name)

        key = f"key{self.address}"
        existing_data = None
        try:
            with shelve.open(str(base), flag="r") as s:
                existing_data = s.get(key)
        except Exception as ex:
                    LOGGER.exception("[%s] Unexpected error during shelve migration", self.name)
                    return False, None

        # Delete all shelve artifacts after a successful read attempt
        errors = []
        for p in candidates:
            try:
                p.unlink()
            except OSError as ex:
                errors.append((p, ex))
        if errors:
            for p, ex in errors:
                LOGGER.warning("[%s] Could not delete shelve file %s: %s", self.name, p, ex)
        else:
            LOGGER.info("[%s] Deleted old shelve files for base: %s", self.name, base)

        return True, existing_data


    def load_persistent_data(self) -> None:
        """
        Load state from Polyglot persistence or migrate from old shelve DB files.
        """
        data = self.controller.Data.get(self.name)

        if data is not None:
            self._apply_state(data)
            LOGGER.info("%s, Loaded from persistence", self.name)
        else:
            LOGGER.info("%s, No persistent data found. Checking for old DB files...", self.name)
            migrated, old_data = self._check_db_files_and_migrate()
            if migrated and old_data is not None:
                self._apply_state(old_data)
                LOGGER.info("%s, Migrated from old DB files.", self.name)
            else:
                self._apply_state({})  # initialize from defaults
                LOGGER.info("%s, No old DB files found.", self.name)

        # Persist and push drivers
        self.store_values()
        self._push_drivers()


    def store_values(self) -> None:
        """
        Store persistent data to Polyglot Data structure.
        """
        data_to_store = {field: self.data[field] for field in FIELDS.keys()}
        self.controller.Data[self.name] = data_to_store
        LOGGER.debug("Values stored for %s: %s", self.name, data_to_store)


    def getConfigData(self):
        """
        Retrieves and processes garage configuration data from the controller.
        """
        self.dev = next((dev for dev in self.controller.devlist 
                         if str(dev.get('type')) == 'garage' and dev.get('name') == self.name), None)

        if not self.dev:
            LOGGER.error('No configuration data found for this garage node.')
            return

        # Iterate through fields and update from self.dev if key exists
        for field, spec in FIELDS.items():
            # Use a safe get to retrieve config data
            if field in self.dev:
                self.data[field] = self.dev[field]
        
        # Process ratgdo
        self.process_ratgdo_config()
        

    def process_ratgdo_config(self):
        """Processes the ratgdo configuration specifically."""
        self.controller.Notices.delete('ratgdo')
        self.ratgdoOK = False
        if not self.dev:
            LOGGER.error('No configuration data found for this garage node.')
            return
        
        ratgdo_config: Any = self.dev.get('ratgdo', False)

        if ratgdo_config in [False, 'false', 'False']:
            self.ratgdo = False
        elif ratgdo_config in ['true', 'True', True, RATGDO, f"{RATGDO}.local"]:
            self.ratgdo = RATGDO
            self.bonjourOn = True
            warn = f"Searching for RATGDO IP: {RATGDO}"
            LOGGER.error(warn)
            self.controller.Notices['ratgdo'] = warn
        elif isinstance(ratgdo_config,str):
            try:
                self.ratgdo = ratgdo_config
                ipaddress.ip_address(self.ratgdo)
                self.ratgdoCheck()
                self.ratgdoOK = True
            except (ValueError, ipaddress.AddressValueError):
                error = f"RATGDO address error: {self.ratgdo}"
                LOGGER.error(error)
                self.controller.Notices['ratgdo'] = error
                self.ratgdo = False
            else:
                self.ratgdo = False

        LOGGER.info(f'self.ratgdo = {self.ratgdo}')

        
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
                self.controller.Notices.delete('ratgdo')
                self.ratgdoOK = True
                return True
        except Exception as ex:
            LOGGER.error(f"error: {ex}")
        self.ratgdoOK = False
        self.controller.Notices['ratgdo'] = "RATGDO deice communicatinos failure."
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

    def lt_on_cmd(self, command = None):
        LOGGER.info(f"{self.name}, {command}")
        self.data['light'] = 1
        self.setDriver('GV0', self.data['light'])
        self.reportCmd("LT_ON", 2)
        if self.data['lightId'] > 0: # type: ignore
            self.pushTheValue(self.data['lightT'], self.data['lightId'], self.data['light'])
        post = f"{self.ratgdo}{LIGHT}{TURN_ON}"
        self.ratgdoPost(post)
        self.store_values()
        self.resetTime()

    def lt_off_cmd(self, command = None):
        LOGGER.info(f"{self.name}, {command}")
        self.data['light'] = 0
        self.setDriver('GV0', self.data['light'])
        self.reportCmd("LT_OFF", 2)
        if self.data['lightId'] > 0:
            self.pushTheValue(self.data['lightT'], self.data['lightId'], self.data['light'])
        post = f"{self.ratgdo}{LIGHT}{TURN_OFF}"
        self.ratgdoPost(post)
        self.store_values()
        self.resetTime()
        
    def door_command(self, post):
        if self.data['dcommandId'] > 0:
            self.pushTheValue(self.data['dcommandT'], self.data['dcommandId'], self.data['dcommand'])
        self.setDriver('GV2', self.data['dcommand'])
        self.ratgdoPost(post)
        self.store_values()
        self.resetTime()
    
    def dr_open_cmd(self, command = None):
        LOGGER.info(f"{self.name}, {command}")
        self.data['dcommand'] = 1
        post = f"{self.ratgdo}{DOOR}{OPEN}"
        self.door_command(post)
        self.reportCmd("OPEN",25)
    
    def dr_close_cmd(self, command = None):
        LOGGER.info(f"{self.name}, {command}")
        self.data['dcommand'] = 2
        post = f"{self.ratgdo}{DOOR}{CLOSE}"
        self.door_command(post)
        self.reportCmd("CLOSE",25)
        
    def dr_trigger_cmd(self, command = None):
        LOGGER.info(f"{self.name}, {command}")
        self.data['dcommand'] = 3
        post = f"{self.ratgdo}{TRIGGER}"
        self.door_command(post)
        self.reportCmd("TRIGGER",25)
        
    def dr_stop_cmd(self, command = None):
        LOGGER.info(f"{self.name}, {command}")
        self.data['dcommand'] = 4
        post = f"{self.ratgdo}{DOOR}{STOP}"
        self.door_command(post)
        self.reportCmd("CLOSE",25)
        
    def lk_lock_cmd(self, command = None):
        LOGGER.info(f"{self.name}, {command}")
        self.data['lock'] = 1
        self.setDriver('GV4', self.data['lock'])
        self.reportCmd("LOCK",2)
        if self.data['lockId'] > 0:
            self.pushTheValue(self.data['lockT'], self.data['lockId'], self.data['lock'])
        post = f"{self.ratgdo}{LOCK_REMOTES}{LOCK}"
        self.ratgdoPost(post)
        self.store_values()
        self.resetTime()
        
    def lk_unlock_cmd(self, command = None):
        LOGGER.info(f"{self.name}, {command}")
        self.data['lock'] = 0
        self.setDriver('GV4', self.data['lock'])
        self.reportCmd("UNLOCK",2)
        if self.data['lockId'] > 0:
            self.pushTheValue(self.data['lockT'], self.data['lockId'], self.data['lock'])
        post = f"{self.ratgdo}{LOCK_REMOTES}{UNLOCK}"
        self.ratgdoPost(post)
        self.store_values()
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
        success, self.data['light'], change = self.updateVar('light', self.data['light'], self.data['lightT'], self.data['lightId'])
        success, self.data['door'], change = self.updateVar('door', self.data['door'], self.data['doorT'], self.data['doorId'])
        success, self.data['dcommand'], change = self.updateVar('dcommand', self.data['dcommand'], self.data['dcommandT'], self.data['dcommandId'])
        success, self.data['motion'], change = self.updateVar('motion', self.data['motion'], self.data['motionT'], self.data['motionId'])
        success, self.data['lock'], change = self.updateVar('lock', self.data['lock'], self.data['lockT'], self.data['lockId'])
        success, self.data['obstruct'], change = self.updateVar('obstruct', self.data['obstruct'], self.data['obstructT'], self.data['obstructId'])
        if success:
            self.store_values()
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
            _type = GETLIST[self.data['lightT']]
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
            self.data['light'] = 1
        elif state == 'OFF':
            self.data['light'] = 0

    def setRatgdoDoor(self, _data):
        state = _data['state']
        value = int(round(_data['value'] * 100))
        current_operation = _data['current_operation']
        LOGGER.debug(f"id: {_data['id']}, value: {value}, state: {state}, current: {current_operation}")

        if current_operation == 'IDLE':
            if state == 'CLOSED':
                self.data['door'] = 0
            elif state == 'OPEN':
                    self.data['door'] = 100
            elif state == 'OPENING':
                    self.data['door'] = 104
            elif state == 'STOPPED':
                    self.data['door'] = 102
            elif state == 'CLOSING':
                    self.data['door'] = 103
            else: # UNKNOWN
                    self.data['door'] = 101
        elif current_operation == 'OPENING':
            self.data['door'] = 104
        elif current_operation == 'CLOSING':
            self.data['door'] = 103
            
        # check position
        if 0 <= value <= 100:
            LOGGER.info(f"value True, value: {value}")
            self.data['position'] = value
        else:
            LOGGER.info(f"value False, value: {value}")
            self.data['position'] = 101

    def setRatgdoMotor(self, _data):
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'ON':
            self.data['motor'] = 1
            self.reportCmd('MOTORON',2)
        elif state =='OFF':
            self.data['motor'] = 0
            self.reportCmd('MOTOROFF',2)

    def setRatgdoMotion(self, _data):
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'ON':
            self.data['motion'] = 1
            self.reportCmd('MOTION',2)
        elif state =='OFF':
            self.data['motion'] = 0
            self.reportCmd('NOMOTION',2)

    def setRatgdoLock(self, _data):
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'LOCKED':
            self.data['lock'] = 1
        elif state == 'UNLOCKED':
            self.data['lock'] = 0

    def setRatgdoObstruct(self, _data):
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'ON':
            self.data['obstruct'] = 1
            self.reportCmd('OBSTRUCTION',2)
        elif state == 'OFF':
            self.data['obstruct'] = 0
            self.reportCmd('NOOBSTRUCTION',2)
                                
    def updateISY(self):
        _currentTime = time.time()
        if self.firstPass:
            self.setDriver('GV0', self.data['light'])
            if self.getDriver('GV1') != self.data['door']:
                self.dcommand = 0
            self.setDriver('GV1', self.data['door'])
            self.setDriver('GV2', self.data['dcommand'])
            self.setDriver('GV8', self.data['motor'])
            self.setDriver('GV9', self.data['position'])
            self.setDriver('GV3', self.data['motion'])
            self.setDriver('GV4', self.data['lock'])
            self.setDriver('GV5', self.data['obstruct'])
            self.resetTime()
            self.firstPass = False
        else:
            if self.getDriver('GV0') != self.data['light']:
                self.setDriver('GV0', self.data['light'])
                self.resetTime()
            _doorOldStatus = self.getDriver('GV1')
            if _doorOldStatus != self.data['door']:
                self.data['dcommand'] = 0
                self.setDriver('GV1', self.data['door'])
                self.resetTime()
            if self.getDriver('GV2') != self.data['dcommand']:
                self.setDriver('GV2', self.data['dcommand'])
                self.resetTime()
            if self.getDriver('GV8') != self.data['motor']:
                self.setDriver('GV8', self.data['motor'])
                self.resetTime()
            if self.getDriver('GV9') != self.data['position']:
                self.setDriver('GV9', self.data['position'])
                self.resetTime()
            if self.getDriver('GV3') != self.data['motor']:
                self.setDriver('GV3', self.data['motor'])
                self.resetTime()
            if self.getDriver('GV3') != self.data['motion']:
                self.setDriver('GV3', self.data['motion'])
                self.resetTime()
            if self.getDriver('GV4') != self.data['lock']:
                self.setDriver('GV4', self.data['lock'])
                self.resetTime()
            if self.getDriver('GV5') != self.data['obstruct']:
                self.setDriver('GV5', self.data['obstruct'])
                self.resetTime()
        _sinceLastUpdate = round(((_currentTime - self.data['lastUpdateTime']) / 60), 1)
        if _sinceLastUpdate < 9999:
            self.setDriver('GV6', _sinceLastUpdate)
        else:
            self.setDriver('GV6', 9999)

        if self.data['door'] != 0:
            if self.data['openTime'] == 0.0:
                self.data['openTime'] = _currentTime
            _openTimeDelta = round((_currentTime - self.data['openTime']), 1)
        else:
            self.data['openTime'] = 0.0
            _openTimeDelta = 0
        self.setDriver('GV7', _openTimeDelta)

    def reset_stats_cmd(self, command = None):
        LOGGER.info(f"{self.name}, {command}")
        self.firstPass = True
        self.resetTime()
        self.store_values()

    def resetTime(self):
        """ Reset the last update time to now """
        self.data['lastUpdateTime'] = time.time()
        self.setDriver('GV6', 0.0)
        
    def query(self, command = None):
        """ Query for updated values """ 
        LOGGER.info(f"{self.name}, {command}")
        self.reportDrivers()


    hint = '0x01120100'
    # home, barrier, None
    # Hints See: https://github.com/UniversalDevicesInc/hints
    
    """
    This is an array of dictionary items containing the variable names(drivers)
    values and uoms(units of measure) from ISY. This is how ISY knows what kind
    of variable to display. Check the UOM's in the WSDK for a complete list.
    UOM 2 is boolean so the ISY will display 'True/False'
    """
    drivers = [
        {"driver": "GV0", "value": 0, "uom": 2},  #light
        {"driver": "GV1", "value": 0, "uom": 97}, #door status
        {"driver": "GV2", "value": 0, "uom": 25}, #door command
        {"driver": "GV3", "value": 0, "uom": 2},  #motion
        {"driver": "GV4", "value": 0, "uom": 2},  #lock
        {"driver": "GV5", "value": 0, "uom": 2},  #obstruction
        {'driver': 'GV6', 'value': 0, 'uom': 45}, #update time
        {'driver': 'GV7', 'value': 0, 'uom': 58}, #open time
        {'driver': 'GV8', 'value': 0, 'uom': 2},  #motor
        {"driver": "GV9", "value": 0, "uom": 97}, #door position
    ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
        "QUERY": query,
        "LT_ON": lt_on_cmd,
        "LT_OFF": lt_off_cmd,
        "OPEN": dr_open_cmd,
        "CLOSE": dr_close_cmd,
        "TRIGGER": dr_trigger_cmd,
        "STOP": dr_stop_cmd,
        "LOCK": lk_lock_cmd,
        "UNLOCK": lk_unlock_cmd,
        'resetStats': reset_stats_cmd,
        }

