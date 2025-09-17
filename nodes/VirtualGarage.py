"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

VirtualGarage class
"""
# standard imports
import time, ipaddress, asyncio, json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple
from threading import Thread, Event, Lock, Condition

# external imports
from udi_interface import ISY, Node, LOGGER
import requests
import aiohttp

# local imports
from utils.node_funcs import FieldSpec, load_persistent_data, store_values
# from utils.node_funcs import _push_drivers, _apply_state, _shelve_file_candidates, _check_db_files_and_migrate, store_values  

# Dispatch map to select the correct tag and index based on var_type.
# Using a dictionary for dispatch is more extensible and readable than a long if/elif chain.
_VARIABLE_TYPE_MAP = {
    # Key: ISY var_type, Value : (INDEX, XML_TAG, SET_TAG)
    '1': ('2', 'val', 'set'),
    '2': ('2', 'init', 'init'),
    '3': ('1', 'val', 'set'),
    '4': ('1', 'init', 'init'),
}

# @dataclass(frozen=True)
# class FieldSpec:
#     driver: Optional[str]  # e.g., "GV1" or None if not pushed to a driver
#     default: Any           # per-field default
#     data_type: str         # denote data type (state or config)
#     def should_update(self) -> bool:
#             """Return True if this field should be pushed to a driver."""
#             return self.driver is not None and self.data_type == "state"
        
# Single source of truth for field names, driver codes, and defaults
FIELDS: dict[str, FieldSpec] = {
    # State variables (pushed to drivers)
    "light":           FieldSpec(driver="GV0", default=0, data_type="state"),
    "door":            FieldSpec(driver="GV1", default=0, data_type="state"),
    "dcommand":        FieldSpec(driver="GV2", default=0, data_type="state"),
    "motion":          FieldSpec(driver="GV3", default=0, data_type="state"),
    "lock":            FieldSpec(driver="GV4", default=0, data_type="state"),
    "obstruct":        FieldSpec(driver="GV5", default=0, data_type="state"),
    "lastUpdateTime":  FieldSpec(driver="GV6", default=0.0, data_type="calc"),
    "openTime":        FieldSpec(driver="GV7", default=0.0, data_type="calc"),
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


class VirtualGarage(Node):
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
        self.name = name # node name
        self.hb = 0 # heartbeat

        # Bonjour checking vars
        self.bonjourCommand = None
        self.bonjourOn = False
        self.bonjourOnce = True
        
        self.ratgdo = False # False, True, ip of Ratgdo
        self.ratgdoOK = False # checker for Ratgdo device

        # storage arrays, events, conditions, locks
        self.ratgdo_event = [] # array, keeper of the Ratgdo events, json / dictionary
        self.ratgdo_event_condition = Condition() # condition to wait / hold event pollng for new events
        self.stop_sse_client_event = Event() # graceful exit for sse client and ratgdo_event thread
        self.first_pass_event = Event() # just to make sure first write of drivers happens
        self._event_polling_thread = None # thread to run event polling
        self.ratgdo_poll_lock = Lock() # lock to prevent re-running ratgdo direct polling
        self.sse_lock = Lock()

        # debug flags
        self.ratgdo_do_events = True # debug flag to turn on/off events
        self.ratgdo_do_poll = True # debug flag to turn on/off ratgdo periodic polling of data
                
        # default variables and drivers
        self.data = {field: spec.default for field, spec in FIELDS.items()}

        # subscriptions
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

        # get isy address
        self.isy = ISY(self.poly)

        # this is first pass
        self.first_pass_event.set()

        # set-up async loop
        self.mainloop = mainloop
        asyncio.set_event_loop(mainloop)
        self.connect_thread = Thread(target=mainloop.run_forever)
        self.connect_thread.start()

        # get persistent data from polyglot or depreciated: old db file, then delete db file
        load_persistent_data(self)

        # retrieve configuration data
        self.get_config_data()
        self.reset_time()

        # try bonjour
        self.bonjourOnce = True
        if self.bonjourOnce and self.bonjourOn:
            self.poly.bonjour('http', None, None)

        # if we have Ratgdo device, set up the event sse client & event retrieval loop
        if self.ratgdo and self.ratgdo_do_events:
            # first start of sse client via the async loop
            self.start_sse_client()
            # start event polling loop    
            self.start_event_polling()

        LOGGER.info(f"{self.name} exit start")
                
                    
    def poll(self, flag):
        """
        Called by POLL event subscription above.
        longPoll, if good Ratgdo, re-starts sse client & event polling,
                  also calls direct poll protected by a lock
        shortPoll, heartbeat, bonjour check, ISY variable push/pull if no Ratgdo,
                   update ISY drivers & timers
        """
        if 'longPoll' in flag:
            # update ratgdo device if being used
            if self.ratgdo and self.ratgdoOK and self.ratgdo_do_poll:
                LOGGER.info(f"POLLING: {flag} {self.name}")
                # if needed check for re-start of sse client via the async loop
                self.start_sse_client()
                # if needed check for re-start event polling loop    
                self.start_event_polling()
                # verify we are not in direct polling
                if self.ratgdo_poll_lock.acquire(blocking = False):
                    try:
                        # get Ratgdo data directly to validate sse events
                        success = self.get_ratgdo_direct()
                        LOGGER.info(f"getRadgdoDirect success = {success}")
                    except Exception as ex:
                        LOGGER.error(f"Error during getRadgdoDirect: {ex}", exc_info=True)
                    finally:
                        self.ratgdo_poll_lock.release()
            LOGGER.debug('longPoll exit')
        else:
            self.heartbeat() # send cmd DON/DOF
            # no Ratgdo, so get/set data from ISY variables
            if not self.ratgdo:
                self.update_vars() # update variables
            self.update_isy() # update ISY
            LOGGER.debug('shortPoll exit')

            
    def get_config_data(self):
        """
        Retrieves and processes garage configuration data from the controller.
        Calls helper to process Ratgdo config.
        """
        self.dev = next((dev for dev in self.controller.devlist 
                         if str(dev.get('type')) == 'garage' and dev.get('name') == self.name), None)

        if not self.dev:
            LOGGER.error('No configuration data found for this garage node.')
            return

        # Iterate through fields and update from self.dev if key exists
        for field, _ in FIELDS.items():
            # Use a safe get to retrieve config data
            if field in self.dev:
                self.data[field] = self.dev[field]
        
        # Process ratgdo
        self.process_ratgdo_config()
        

    def process_ratgdo_config(self):
        """
        This function parses the configuration which is specifically for the
        Ratgdo.  The variable ratgdo can be false (none used), true (use default address),
        or have an ip address (most reliable and quick to set-up).  Finally,
        the checking routine is called & ratgdoOK is set
        TODO better separation between config processing & checking
        """
        self.controller.Notices.delete('ratgdo')
        self.ratgdoOK = False
        if not self.dev:
            LOGGER.error('No configuration data found for this garage node.')
            return
        
        ratgdo_config: Any = self.dev.get('ratgdo', False)
        LOGGER.info(f"{self.name}: ratgdo_config:{ratgdo_config}, str:{isinstance(ratgdo_config,str)}")

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
                if self.ratgdo_check():
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
        """
        Takes RATGDO default name, usually like ratgdov25i-fad8fd.local,
        and tries to find it using bonjour.  I have not had good luck
        with this on EISY, even if other browsers find it. YMMV.
        """
        # bonjour(self, type, subtypes, protocol)
        LOGGER.info(f"BonjourMessage")
        if not self.bonjourOn or not self.bonjourOnce:
            return
        try:
            if command['success']:
                mdns = command['mdns']
                for addr in mdns:
                    LOGGER.info(f"addr: {addr['name']}, type:{addr['type']}")
                    if addr['name'] == RATGDO:
                        self.controller.Notices.delete('ratgdo')
                        self.ratgdo = addr['addresses'][0]
                        LOGGER.warning(f"FOUND RATGDO@'{self.ratgdo}':ip: {addr['addresses']}, name: {addr['name']}")
                        if self.ratgdo_check():
                            self.bonjourOn = False
                        break
        except Exception as ex:
            LOGGER.error(f"error: {ex}, command: {command}", exc_info=True)
        self.bonjourOnce = True

        
    def ratgdo_check(self):
        """
        Function to validate good ip, existence and running of Ratgdo garage
        controller. Setting or resetting ratgdoOK based on simple pulse check,
        which asks for the status of the light.
        """
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

    
    def ratgdo_post(self, post):
        """
        Post content, usually commands or request of status,
        to Ratgdo garage controller, if device has been validated with ratgdoOK.
        """
        if self.ratgdoOK:
            LOGGER.info(f'post:{post}')
            try:
                rpost = requests.post(f"http://{post}")
                if not rpost.ok:
                    LOGGER.error(f"{post}: {rpost.status_code}")
            except Exception as ex:
                LOGGER.error(f"{post}: {ex}")
                
        
    def get_ratgdo_event(self) -> list[dict]:
        """
        Called by consumer fuctions to efficiently wait for events to process.
        """
        with self.ratgdo_event_condition:
            while not self.ratgdo_event:
                self.ratgdo_event_condition.wait()
            return self.ratgdo_event  # return reference, not a copy


    def append_ratgdo_event(self, event):
        """
        Called by sse to append to gateway_event array & signal that there is an event to process.
        """
        with self.ratgdo_event_condition:
            self.ratgdo_event.append(event)
            self.ratgdo_event_condition.notify_all()  # Wake up all waiting consumers


    def remove_ratgdo_event(self, event):
        """
        Called by consumer functions (Controller, Shades, Scenes) to remove processed events.
        """
        with self.ratgdo_event_condition:
            if event in self.ratgdo_event:
                self.ratgdo_event.remove(event)


    def start_event_polling(self):
        """
        Run routine in a separate thread to retrieve events from array loaded by sse client from gateway.
        """
        LOGGER.debug(f"start")
        if self._event_polling_thread and self._event_polling_thread.is_alive():
           LOGGER.debug("event polling running, skip")
        else:
            try:
                self.stop_sse_client_event.clear()
                self._event_polling_thread = Thread(
                    target=self._poll_events,
                    name="EventPollingThread",
                    daemon=True)
                self._event_polling_thread.start()
                LOGGER.info("event polling started")
            except Exception as ex:
                LOGGER.error(f"failed to start event polling thread, {ex}", exc_info=True)                
        LOGGER.debug("exit")


    def _poll_events(self):
        """
        Handles Ratgdo SSE Events like state changes.
        Removes unacted events when isoDate is older than 2 minutes or invalid.
        Loop is triggered by condition function, which monitors ratgdo_events array,
        which is populated by the sse client.
        """

        while not self.stop_sse_client_event.is_set():
            # wait for events to process
            ratgdo_events = self.get_ratgdo_event()
            
            # handle the rest of events in isoDate order
            try:
                # get most recent isoDate
                event = min(ratgdo_events, key=lambda x: x['timestamp'], default={})

            except (ValueError, TypeError) as ex: # Catch specific exceptions
                LOGGER.error(f"Error filtering or finding minimum event: {ex}")
                event = {}

            acted_upon = False

            # retry
            if event.get('retry'):
                LOGGER.info('retry - {}'.format(event))
                self.remove_ratgdo_event(event)
                acted_upon = True

            # id
            if event.get('id'):
                LOGGER.info('id - {}'.format(event))
                self.remove_ratgdo_event(event)
                acted_upon = True

            # events
            is_event = event.get('event')
            if is_event:
                    # event - ping
                    if is_event == "ping":
                        LOGGER.info('event - ping - {}'.format(event))
                        self.remove_ratgdo_event(event)
                        acted_upon = True

                    # event - error
                    elif is_event == "error":
                        LOGGER.info('event - eror -{}'.format(event))
                        self.remove_ratgdo_event(event)
                        acted_upon = True

                    # event - log
                    elif is_event == "log":
                        LOGGER.info('event - log -{}'.format(event))
                        if 'No clients: rebooting' in event['data']:
                            LOGGER.warning('API Rebooting...')
                        self.remove_ratgdo_event(event)
                        acted_upon = True

                    # event - unknown
                    elif is_event == "unknown":
                        LOGGER.info('event - unknown -{}'.format(event))
                        self.remove_ratgdo_event(event)
                        acted_upon = True
                        
                    # event - state
                    elif is_event == "state":
                        try:
                            msg = event.get('data')
                            if msg:
                                id = msg.get('id')
                                if id == 'light-light':
                                    self.set_ratgdo_light(msg)
                                    LOGGER.info('event:state - processed id:{}'.format(id))
                                elif id == 'cover-door':
                                    self.set_ratgdo_door(msg)
                                    LOGGER.info('event:state - processed id:{}'.format(id))
                                elif id == 'binary_sensor-motor':
                                    self.set_ratgdo_motor(msg)
                                    LOGGER.info('event:state - processed id:{}'.format(id))
                                elif id == 'binary_sensor-motion':
                                    self.set_ratgdo_motion(msg)
                                    LOGGER.info('event:state - processed id:{}'.format(id))
                                elif id == 'lock-lock_remotes':
                                    self.set_ratgdo_lock(msg)
                                    LOGGER.info('event:state - processed id:{}'.format(id))
                                elif id == 'binary_sensor-obstruction': 
                                    self.set_ratgdo_obstruct(msg)
                                    LOGGER.info('event:state - processed id:{}'.format(id))
                                else:
                                    LOGGER.info(f'event:state - no action - {id}')                    
                            else:
                                LOGGER.info('event - state data bad:{}'.format(event))
                        except Exception as ex:
                            LOGGER.error(f"bad json {event.get('data')}  ex:{ex}", exc_info=True)                
                        self.remove_ratgdo_event(event)
                        acted_upon = True
                    else:
                        LOGGER.info('event - REALLY unknown -{}'.format(event))
                        self.remove_ratgdo_event(event)
                        acted_upon = True
                        
            #If not acted upon, remove if older than 2 minutes to prevent blocking of other events
            if not acted_upon and event:
                try:
                    # Compare the current timestamp
                    now = datetime.now(timezone.utc)
                    cutoff = now - timedelta(minutes=2)
                    ts = event.get('timestamp', now.isoformat())
                    if ts >= cutoff:
                        LOGGER.warning(f"Unacted event!!! removed due to age > 2 min: {event}")
                        self.ratgdo_event.remove(event)
                except (TypeError, ValueError) as ex:
                    LOGGER.error(f"Invalid 'isoDate' in unacted event: {event}. Error: {ex}")
                    self.ratgdo_event.remove(event)

        LOGGER.info(f"controller sse client event exiting while")                            


    def start_sse_client(self):
        """
        Run sse client in a thread-safe loop for gateway events polling which then loads the events to an array.
        """
        LOGGER.debug(f"start")
        if self.sse_lock.acquire(blocking=False):
                self.stop_sse_client_event.clear()
                future = asyncio.run_coroutine_threadsafe(self._client_sse(), self.mainloop)
                LOGGER.info(f"sse client started: {future}")        
        else:
            LOGGER.debug("sse client running, skipping.")
        LOGGER.debug("exit")        


    async def _client_sse(self):
        """
        Polls the SSE endpoint with aiohttp for events.
        Parses SSE-style lines into structured JSON objects.
        Includes robust retry logic with exponential backoff.
        """
        LOGGER.info("controller start poll events")
        url = f"http://{self.ratgdo}{EVENTS}"
        retries = 0
        max_retries = 5
        base_delay = 1

        current_event = None

        try:
            while not self.stop_sse_client_event.is_set():
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as response:
                            retries = 0  # Reset retries on successful connection
                            async for val in response.content:
                                line = val.decode().strip()
                                if not line:
                                    continue

                                LOGGER.debug(f"Received: {line}")

                                # Normalize line format: remove << >> if present
                                clean_line = line
                                if line.startswith("<<") and line.endswith(">>"):
                                    clean_line = line[2:-2]

                                # Split key and value
                                if ':' not in clean_line:
                                    LOGGER.warning(f"Malformed line: {line}")
                                    continue

                                key, value = clean_line.split(":", 1)
                                key = key.strip()
                                value = value.strip()

                                timestamp = datetime.now(timezone.utc).isoformat()

                                try:
                                    if key == "retry" or key == "id":
                                        parsed = {
                                            key: int(value) if value.isdigit() else value,
                                            "timestamp": timestamp
                                        }
                                        self.append_ratgdo_event(parsed)

                                    elif key == "event":
                                        current_event = value

                                    elif key == "data":
                                        if not value:
                                            LOGGER.warning("Received empty data line, skipping")
                                            continue
                                        try:
                                            data_obj = json.loads(value)
                                            parsed = {
                                                "event": current_event if current_event else "unknown",
                                                "data": data_obj,
                                                "timestamp": timestamp
                                            }                                            
                                        except json.JSONDecodeError as e:
                                            # Not JSON—store as raw string
                                            parsed = {
                                                "event": current_event if current_event else "log",
                                                "data": value,
                                                "timestamp": timestamp
                                            }
                                            LOGGER.debug(f"Stored raw data line: {value}")
                                        self.append_ratgdo_event(parsed)
                                        current_event = None
                                            
                                    else:
                                        LOGGER.warning(f"Unknown key: {key}")

                                except Exception as ex:
                                    LOGGER.error(f"sse client error: {ex}")

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    LOGGER.error(f"Connection to sse error: {e}")
                    if retries >= max_retries:
                        LOGGER.error("Max retries reached. Stopping SSE client.")
                        break

                    delay = base_delay * (2 ** retries)
                    LOGGER.warning(f"Reconnecting in {delay}s")
                    await asyncio.sleep(delay)
                    retries += 1

        finally:
               if self.sse_lock.locked():
                   self.sse_lock.release()
               LOGGER.info("SSE client exiting and lock released")


    def lt_on_cmd(self, command = None):
        """
        Light on command, update persistent data, push to vars, store values,
        send LT_ON to ISY, post Light turn_on to Ratgdo, reset last update time
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['light'] = 1
        self.setDriver('GV0', self.data['light'])
        self.reportCmd("LT_ON", 2)
        if self.data['lightId'] > 0: # type: ignore
            self.push_the_value(self.data['lightT'], self.data['lightId'], self.data['light'])
        post = f"{self.ratgdo}{LIGHT}{TURN_ON}"
        self.ratgdo_post(post)
        store_values(self)
        self.reset_time()

        
    def lt_off_cmd(self, command = None):
        """
        Light off command, update persistent data, push to vars, store values,
        send LT_OFF to ISY, post Light turn_off to Ratgdo, reset last update time
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['light'] = 0
        self.setDriver('GV0', self.data['light'])
        self.reportCmd("LT_OFF", 2)
        if self.data['lightId'] > 0:
            self.push_the_value(self.data['lightT'], self.data['lightId'], self.data['light'])
        post = f"{self.ratgdo}{LIGHT}{TURN_OFF}"
        self.ratgdo_post(post)
        store_values(self)
        self.reset_time()

        
    def door_command(self, post):
        """
        Door helper function, taken from specific command, store values,
        send motor command to ISY, post motor command to Ratgdo, reset last update time
        """
        if self.data['dcommandId'] > 0:
            self.push_the_value(self.data['dcommandT'], self.data['dcommandId'], self.data['dcommand'])
        self.setDriver('GV2', self.data['dcommand'])
        self.ratgdo_post(post)
        store_values(self)
        self.reset_time()

        
    def dr_open_cmd(self, command = None):
        """
        Door open command, update persistent data,
        calculate Ratgdo post, send to door helper function.
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['dcommand'] = 1
        post = f"{self.ratgdo}{DOOR}{OPEN}"
        self.door_command(post)
        self.reportCmd("OPEN",25)

        
    def dr_close_cmd(self, command = None):
        """
        Door close command, update persistent data,
        calculate Ratgdo post, send to door helper function.
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['dcommand'] = 2
        post = f"{self.ratgdo}{DOOR}{CLOSE}"
        self.door_command(post)
        self.reportCmd("CLOSE",25)

        
    def dr_trigger_cmd(self, command = None):
        """
        Door trigger command, update persistent data,
        calculate Ratgdo post, send to door helper function.
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['dcommand'] = 3
        post = f"{self.ratgdo}{TRIGGER}"
        self.door_command(post)
        self.reportCmd("TRIGGER",25)

        
    def dr_stop_cmd(self, command = None):
        """
        Door stop command, update persistent data,
        calculate Ratgdo post, send to door helper function.
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['dcommand'] = 4
        post = f"{self.ratgdo}{DOOR}{STOP}"
        self.door_command(post)
        self.reportCmd("CLOSE",25)
        
        
    def lk_lock_cmd(self, command = None):
        """
        Remote lock command, update persistent data, push to vars, store values,
        send Lock to ISY, post lock to Ratgdo, reset last update time
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['lock'] = 1
        self.setDriver('GV4', self.data['lock'])
        self.reportCmd("LOCK",2)
        if self.data['lockId'] > 0:
            self.push_the_value(self.data['lockT'], self.data['lockId'], self.data['lock'])
        post = f"{self.ratgdo}{LOCK_REMOTES}{LOCK}"
        self.ratgdo_post(post)
        store_values(self)
        self.reset_time()
        
        
    def lk_unlock_cmd(self, command = None):
        """
        Remote unlock command, update persistent data, push to vars, store values,
        send unLock to ISY, post unlock to Ratgdo, reset last update time
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['lock'] = 0
        self.setDriver('GV4', self.data['lock'])
        self.reportCmd("UNLOCK",2)
        if self.data['lockId'] > 0:
            self.push_the_value(self.data['lockT'], self.data['lockId'], self.data['lock'])
        post = f"{self.ratgdo}{LOCK_REMOTES}{UNLOCK}"
        self.ratgdo_post(post)
        store_values(self)
        self.reset_time()

        
    def push_the_value(self, type, id, value):
        """
        Push to ISY variable the value,
        based on variable type (1 = integer, 2 = state),
        variable id (1 - defined var)
        Access to do this is based on plugin configuration tick-box
        which is currently below the shortPoll/longPoll fields"""
        _type = str(type)
        _id = str(id)
        _value = str(value)
        LOGGER.info(f'Pushing to {self.isy}, type: {_type}, id: {_id}, value: {_value}')
        self.isy.cmd('/rest/vars' + _type + _id + '/' + str(value))

        
    def update_vars(self) -> None:
        """
        Uses FIELDS definitions to pulling data from ISY, then storing values
        """
        for var_name, spec in FIELDS.items():
            # Only process fields that are of type "state"
            if spec.should_update():
                # Safely get the type and ID from the data dictionary
                var_type = self.data.get(f'{var_name}T')
                var_id = self.data.get(f'{var_name}Id')

                # Only proceed if both type and ID are present and non-zero
                if var_type and var_id:
                    new_val = self.update_var_from_id(var_type, var_id)
                    if new_val is not None:
                        self.data[var_name] = new_val
        store_values(self)


    def update_var_from_id(self, var_type: Any, var_id: Any) -> int | float | None:
        """
        Pulls data using pull_from_id and handles errors.
        """
        # Guard clause for invalid input
        if not var_type or not var_id:
            return None

        try:
            result: Tuple[bool, int | float] | None = self.pull_from_id(var_type, var_id)
            if result is None:
                return None

            success, _data = result
            if success:
                return _data
            return None
        except Exception as ex:
            LOGGER.error(f"Error pulling from ID {var_id} with type {var_type}: {ex}", exc_info=True)
            return None


    def pull_from_id(self, var_type: int | str, var_id: int | str, prec_flag = False) -> tuple[bool, int | float] | None:
        """
        Pull a variable from ISY using path segments,
        parse the XML, and update state if the transformed value changed.
        """
        LOGGER.debug(f"Pull from ID")
        try:
            vid = int(var_id)
        except (TypeError, ValueError):
            LOGGER.error("Invalid var_id: %r", var_id)
            return

        if vid == 0:
            LOGGER.debug("var_id is 0; skipping pull.")
            return

        vtype_str = str(var_type).strip()

        # Use dictionary dispatch to get both the index and the XML tag.
        try:
            getlist_segment, tag_to_find, _ = _VARIABLE_TYPE_MAP[vtype_str]
        except KeyError:
            LOGGER.error("Invalid or unsupported var_type: %r", vtype_str)
            return

        path = f"/rest/vars/get/{getlist_segment}/{vid}"

        # Fetch
        try:
            resp = self.isy.cmd(path)
        except RuntimeError as exc:
            if 'ISY info not available' in str(exc):
                LOGGER.info(f"{self.name}: ISY info not available on {path}")
            else:
                LOGGER.exception("RuntimeError on path {path}")
            return
        except Exception as exc:
            LOGGER.exception("%s:, ISY push failed for %s: %s", self.name, path, exc)
            return

        text = resp.decode("utf-8", errors="replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
        LOGGER.debug("ISY response for %s: %s", path, text)

        # Parse XML based on the determined tag
        val_str: Optional[str] = None
        prec_str: Optional[str] = None
        try:
            root = ET.fromstring(text)
            # parse val or init
            val_str = root.findtext(f".//{tag_to_find}")
            if val_str is None:
                LOGGER.error("No <%s> element in ISY response for %s", tag_to_find, path)
                return
            new_raw = int(val_str.strip())

            # consider precision of ISY variable only if prec_flag == True
            if prec_flag:
                # parse prec            
                prec_div = 1
                prec_str = root.findtext(f".//prec")
                if prec_str:
                    prec_div = int(prec_str.strip()) * 10
                    if prec_div <= 0:
                        prec_div = 1
                calc = new_raw / prec_div
                LOGGER.debug(f"NO UPDATE: raw:{new_raw}, prec:{prec_div}, calc{calc}")
                return True, calc
            else:
                return True, new_raw

        except ET.ParseError as exc:
            LOGGER.exception("Failed to parse XML for %s: %s", path, exc)
            return
        except ValueError as exc:
            LOGGER.exception("Value in <%s> is not an int for %s (val=%r): %s", tag_to_find, path, val_str, exc)
            return
        except Exception as ex:
            LOGGER.error(f"{self.name}: parse error {ex}", exc_info = True)
            return

    
    def pull_from_ratgdo(self, get):
        """
        Generic get function to return Ratgdo data to calling function.
        Not currently used.  Was written to test.
        """
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

        
    def get_ratgdo_direct(self):
        """
        Poll Ratgdo for current status of key garage variables:
        Light, door, motion, motor, remote lock, and obstruction.
        """
        endpoints = [
            (LIGHT, self.set_ratgdo_light, "LIGHT"),
            (DOOR, self.set_ratgdo_door, "DOOR"),
            (MOTION, self.set_ratgdo_motion, "MOTION"),
            (MOTOR, self.set_ratgdo_motor, "MOTOR"),
            (LOCK_REMOTES, self.set_ratgdo_lock, "LOCK_REMOTES"),
            (OBSTRUCT, self.set_ratgdo_obstruct, "OBSTRUCT"),
        ]

        for path, handler, label in endpoints:
            try:
                res = requests.get(f"http://{self.ratgdo}{path}")
                if not res.ok:
                    LOGGER.error(f"{label}: res.status_code = {res.status_code}")
                    return False
                handler(res.json())
            except Exception as ex:
                LOGGER.error(f"{label} error: {ex}")
                return False
            time.sleep(0.2)

        LOGGER.info("get_ratgdo_direct success!")
        return True
    
                                
    def set_ratgdo_light(self, _data):
        """
        Update persistent data as well as send command.
        Called by either poll or event.
        """
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, state: {state}")
        if state == 'ON':
            self.data['light'] = 1
        elif state == 'OFF':
            self.data['light'] = 0
            

    def set_ratgdo_door(self, _data):
        """
        Update persistent data as well as send command.
        Called by either poll or event.
        Both percent door position & state of door are updated.
        """
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
            LOGGER.debug(f"value True, value: {value}")
            self.data['position'] = value
        else:
            LOGGER.error(f"value False, value: {value}")
            self.data['position'] = 101

            
    def set_ratgdo_motor(self, _data):
        """
        Update persistent data as well as send command.
        Called by either poll or event.
        """
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'ON':
            self.data['motor'] = 1
            self.reportCmd('MOTORON',2)
        elif state =='OFF':
            self.data['motor'] = 0
            self.reportCmd('MOTOROFF',2)

            
    def set_ratgdo_motion(self, _data):
        """
        Update persistent data as well as send command.
        Called by either poll or event.
        """
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'ON':
            self.data['motion'] = 1
            self.reportCmd('MOTION',2)
        elif state =='OFF':
            self.data['motion'] = 0
            self.reportCmd('NOMOTION',2)

            
    def set_ratgdo_lock(self, _data):
        """
        Update persistent data as well as send command.
        Called by either poll or event.
        """
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'LOCKED':
            self.data['lock'] = 1
        elif state == 'UNLOCKED':
            self.data['lock'] = 0

            
    def set_ratgdo_obstruct(self, _data):
        """
        Update persistent data as well as send command.
        Called by either poll or event.
        """
        state = _data['state']
        LOGGER.debug(f"id: {_data['id']}, value: {_data['value']}, state: {state}")
        if state == 'ON':
            self.data['obstruct'] = 1
            self.reportCmd('OBSTRUCTION',2)
        elif state == 'OFF':
            self.data['obstruct'] = 0
            self.reportCmd('NOOBSTRUCTION',2)

            
    def update_isy(self):
        """
        Update ISY drivers and process both lastUpdateTime & door openTime.
        First pass is signaled by and event, which then pushes all the fields to their drivers.
        """
        current_time: datetime = datetime.now()

        def update_driver(field_name):
            spec = FIELDS[field_name]
            if spec.driver is None:
                return  # Skip config-only fields
            if self.getDriver(spec.driver) != self.data[field_name]:
                self.setDriver(spec.driver, self.data[field_name])
                self.reset_time()

        if self.first_pass_event.is_set():
            for field_name, spec in FIELDS.items():
                if spec.should_update():
                    self.setDriver(spec.driver, self.data[field_name])
            if self.getDriver(FIELDS["door"].driver) != self.data["door"]:
                self.data["dcommand"] = 0
            self.reset_time()
            self.first_pass_event.clear()
        else:
            # Door change logic
            if self.getDriver(FIELDS["door"].driver) != self.data["door"]:
                self.data["dcommand"] = 0
                update_driver("door")

            # Update all other state fields
            for field_name, spec in FIELDS.items():
                if spec.should_update():
                    update_driver(field_name)

        # Time since last update
        if self.data['lastUpdateTime'] == 0.0:
            self.reset_time()
        since_last_update = round(((current_time - self.data["lastUpdateTime"]).total_seconds())/60,1)
        self.setDriver(FIELDS["lastUpdateTime"].driver, min(since_last_update, 9999))

        # Door open time tracking
        if not self.data["openTime"] or self.data["openTime"] == 0.0:
            self.data["openTime"] = current_time
            
        if self.data["door"] == 0:
            self.data["openTime"] = current_time

        open_time_delta = round((current_time - self.data['openTime']).total_seconds(),1)
        self.setDriver(FIELDS["openTime"].driver, min(open_time_delta, 9999))

       
    def reset_stats_cmd(self, command = None):
        """
        Command to reset lastUpdateTime, & drive values
        """
        LOGGER.info(f"{self.name}, {command}")
        self.first_pass_event.set() # reset first pass to push values
        self.reset_time()
        store_values(self)


    def reset_time(self):
        """
        Reset the last update time to now
        """
        self.data['lastUpdateTime'] = datetime.now()
        self.setDriver('GV6', 0.0)

        
    def heartbeat(self):
        """
        Heartbeat function uses the long poll interval to alternately send a ON and OFF
        command back to the ISY.  Programs on the ISY can then monitor this.
        """
        LOGGER.debug(f'heartbeat: hb={self.hb}')
        command = "DOF" if self.hb else "DON"
        self.reportCmd(command, 2)
        self.hb = not self.hb
        LOGGER.debug("Exit")


    def query(self, command = None):
        """
        Query for updated values
        """ 
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

