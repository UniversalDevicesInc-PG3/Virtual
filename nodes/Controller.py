"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

Controller class
"""

# std libraries
import time, json
from threading import Event, Condition
from typing import Dict, Any, List

# external libraries
import yaml
import udi_interface

# personal libraries
from nodes import VirtualSwitch
from nodes import VirtualTemp
from nodes import VirtualTempC
from nodes import VirtualGeneric
from nodes import VirtualGarage

"""
Some shortcuts for udi interface components

- LOGGER: to create log entries
- Custom: to access the custom data class
- ISY:    to communicate directly with the ISY (not commonly used)
"""
LOGGER = udi_interface.LOGGER
LOG_HANDLER = udi_interface.LOG_HANDLER
Custom = udi_interface.Custom
ISY = udi_interface.ISY

# local constants
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

# Map device types to their respective node classes
DEVICE_TYPE_TO_NODE_CLASS = {
    'switch': VirtualSwitch,
    'temperature': VirtualTemp,
    'temperaturec': VirtualTempC,
    'temperaturecr': VirtualTempC,
    'generic': VirtualGeneric,
    'dimmer': VirtualGeneric,
    'garage': VirtualGarage,
}


class Controller(udi_interface.Node):
    id = 'controller'

    def __init__(self, polyglot, primary, address, name):
        """
        super
        self definitions
        data storage classes
        subscribes
        ready
        we exist!
        """
        super().__init__(polyglot, primary, address, name)
        # importand flags, timers, vars
        self.hb = 0 # heartbeat
        self.numNodes = 0

        # storage arrays & conditions
        self.n_queue = []
        self.queue_condition = Condition()
        self.last = 0.0

        # Events
        self.ready_event = Event()
        self.all_handlers_st_event = Event()
        self.stop_sse_client_event = Event()

        # startup completion flags
        self.handler_params_st = None
        self.handler_data_st = None
        self.handler_typedparams_st = None
        self.handler_typeddata_st = None
        self.handler_discover_st = None

        # Create data storage classes
        self.Notices         = Custom(polyglot, 'notices')
        self.Parameters      = Custom(polyglot, 'customparams')
        self.Data            = Custom(self.poly, 'customdata')
        self.TypedParameters = Custom(polyglot, 'customtypedparams')
        self.TypedData       = Custom(polyglot, 'customtypeddata')

        # Subscribe to various events from the Interface class.
        # The START event is unique in that you can subscribe to 
        # the start event for each node you define.

        self.poly.subscribe(self.poly.START,             self.start, address)
        self.poly.subscribe(self.poly.POLL,              self.poll)
        self.poly.subscribe(self.poly.LOGLEVEL,          self.handleLevelChange)
        self.poly.subscribe(self.poly.CUSTOMPARAMS,      self.parameterHandler)
        self.poly.subscribe(self.poly.CUSTOMDATA,        self.dataHandler)
        self.poly.subscribe(self.poly.STOP,              self.stop)
        self.poly.subscribe(self.poly.DISCOVER,          self.discover)
        self.poly.subscribe(self.poly.CUSTOMTYPEDDATA,   self.typedDataHandler)
        self.poly.subscribe(self.poly.CUSTOMTYPEDPARAMS, self.typedParameterHandler)
        self.poly.subscribe(self.poly.ADDNODEDONE,       self.node_queue)

        # Tell the interface we have subscribed to all the events we need.
        # Once we call ready(), the interface will start publishing data.
        self.poly.ready()

        # Tell the interface we exist.  
        self.poly.addNode(self, conn_status='ST')


    def start(self):
        """
        Called by handler during startup.
        """
        LOGGER.info(f"Virtual Devices PG3 NodeServer {self.poly.serverdata['version']}")
        self.Notices.clear()
        self.Notices['hello'] = 'Start-up'
        self.setDriver('ST', 1, report = True, force = True)

        self.last = 0.0
        # Send the profile files to the ISY if neccessary or version changed.
        self.poly.updateProfile()

        # Send the default custom parameters documentation file to Polyglot
        self.poly.setCustomParamsDoc()

        # Initializing a heartbeat
        self.heartbeat()

        # Wait for all handlers to finish
        LOGGER.warning(f'Waiting for all handlers to complete...')
        self.Notices['waiting'] = 'Waiting on valid configuration'
        self.all_handlers_st_event.wait(timeout=60)
        if not self.all_handlers_st_event.is_set():
            LOGGER.error("Timed out waiting for handlers to startup")
            self.setDriver('ST', 2) # start-up failed
            return        

        # Wait for discovery
        self.discover()
        while not self.handler_discover_st:
            time.sleep(1)

        self.Notices.delete('waiting')        
        LOGGER.info('Started Virtual Device NodeServer v%s', self.poly.serverdata)
        self.query()

        # signal to the nodes, its ok to start
        self.ready_event.set()

        # clear inital start-up message
        if self.Notices.get('hello'):
            self.Notices.delete('hello')
        
        LOGGER.info(f'exit {self.name}')


    def node_queue(self, data):
        '''
        node_queue() and wait_for_node_event() create a simple way to wait
        for a node to be created.  The nodeAdd() API call is asynchronous and
        will return before the node is fully created. Using this, we can wait
        until it is fully created before we try to use it.
        '''
        address = data.get('address')
        if address:
            with self.queue_condition:
                self.n_queue.append(address)
                self.queue_condition.notify()
                

    def wait_for_node_done(self):
        with self.queue_condition:
            while not self.n_queue:
                self.queue_condition.wait(timeout = 0.2)
            self.n_queue.pop()
            

    def dataHandler(self,data):
        LOGGER.debug(f'enter: Loading data {data}')
        if data is None:
            LOGGER.warning("No custom data")
        else:
            self.Data.load(data)
        self.handler_data_st = True
        self.check_handlers()


    def parameterHandler(self, params):
        """
        Called via the CUSTOMPARAMS event. When the user enters or
        updates Custom Parameters via the dashboard.
        """
        LOGGER.info('parmHandler: Loading parameters now')
        self.Parameters.load(params)
        self.handler_params_st = True
        LOGGER.info('parmHandler Done...')
        self.check_handlers()
        

    def typedParameterHandler(self, params):
        """
        Called via the CUSTOMTYPEDPARAMS event. This event is sent When
        the Custom Typed Parameters are created.  See the checkParams()
        below.  Generally, this event can be ignored.
        """
        LOGGER.debug('Loading typed parameters now')
        self.TypedParameters.load(params)
        LOGGER.debug(params)
        self.handler_typedparams_st = True
        self.check_handlers()


    def typedDataHandler(self, data):
        """
        Called via the CUSTOMTYPEDDATA event. This event is sent when
        the user enters or updates Custom Typed Parameters via the dashboard.
        'params' will be the full list of parameters entered by the user.
        """
        LOGGER.debug('Loading typed data now')
        if data is None:
            LOGGER.warning("No custom data")
        else:
            self.TypedData.load(data)
        LOGGER.debug(f'Loaded typed data {data}')
        self.handler_typeddata_st = True
        self.check_handlers()
        

    def check_handlers(self):
        """
        Once all start-up parameters are done then set event.
        """
        if (self.handler_params_st and self.handler_data_st and
            self.handler_typedparams_st and self.handler_typeddata_st):
            self.all_handlers_st_event.set()


    def _handle_json_device(self, key: str, val: str) -> Dict[str, Any] | None:
        """Parses a JSON device configuration, handling ID logic."""
        try:
            device = json.loads(val)
            if not isinstance(device, dict):
                raise TypeError("JSON content must be a dictionary.")

            if "id" not in device:
                device["id"] = key
                LOGGER.debug(f"no id: inserting id: {key} into device: {device}")
            elif device["id"] != key:
                device["id"] = key
                LOGGER.error(f"error id: {key} != deviceID: {device['id']}; fixed device: {device}")

            return device
        except (json.JSONDecodeError, TypeError) as ex:
            LOGGER.error(f"JSON parse error for key '{key}' with value '{val}': {ex}")
            return None


    def _handle_file_devices(self, filename: str) -> List[Dict[str, Any]] | None:
        """Loads and returns devices from a YAML file."""
        try:
            with open(filename, 'r') as f:
                dev_yaml = yaml.safe_load(f)

            if "devices" not in dev_yaml:
                LOGGER.error(f"Manual discovery file '{filename}' is missing 'devices' section.")
                return None

            LOGGER.info(f"File '{filename}' loaded successfully.")
            return dev_yaml["devices"]
        except FileNotFoundError as ex:
            LOGGER.error(f"checkParams: Failed to open {filename}: {ex}")
            return None
        except yaml.YAMLError as ex:
            LOGGER.error(f"checkParams: Failed to parse YAML content in {filename}: {ex}")
            return None


    def checkParams(self) -> bool:
        """
        Checks and processes device parameters from `self.Parameters`.
        """
        self.Notices.delete('config')
        self.devlist = []
        has_error = False

        for key, val in self.Parameters.items():
            if not key.isdigit():
                if key in ["devFile", "devfile"]:
                    if val:
                        devices_from_file = self._handle_file_devices(val)
                        if devices_from_file is not None:
                            self.devlist.extend(devices_from_file)
                        else:
                            has_error = True
                    else:
                        LOGGER.error('checkParams: devFile missing filename')
                        has_error = True
                else:
                    LOGGER.error(f"unknown keyfield: '{key}'")
                    has_error = True
                continue

            if val in {'switch', 'temperature', 'temperaturec', 'temperaturecr', 'generic', 'dimmer'}:
                name = f"{val} {key}"
                device = {'id': key, 'type': val, 'name': name}
                self.devlist.append(device)
            elif val:
                json_device = self._handle_json_device(key, val)
                if json_device:
                    self.devlist.append(json_device)
                else:
                    has_error = True

        if has_error:
            self.Notices['config'] = 'Bad configuration, please re-check.'
            LOGGER.info('checkParams finished with errors.')
            return False

        LOGGER.info('checkParams is complete')
        LOGGER.info(f'checkParams: self.devlist: {self.devlist}')
        return True
    
        
    def handleLevelChange(self, level):
        """
        Called via the LOGLEVEL event.
        """
        LOGGER.info('New log level: {}'.format(level))

        
    def poll(self, flag):
        """
        Short & Long polling, only heartbeat in Controller
        """
        # no updates until node is through start-up
        if not self.ready_event:
            LOGGER.error(f"Node not ready yet, exiting")
            return

        if 'longPoll' in flag:
            LOGGER.debug('longPoll (controller)')
            self.heartbeat()

            
    def query(self, command = None):
        """
        Query all nodes from the gateway.
        """
        LOGGER.info(f"Enter {command}")
        nodes = self.poly.getNodes()
        for node in nodes:
            nodes[node].reportDrivers()
        LOGGER.debug(f"Exit")


    def updateProfile(self,command = None):
        """
        Update the profile.
        """
        LOGGER.info(f"Enter {command}")
        st = self.poly.updateProfile()
        LOGGER.debug(f"Exit")
        return st


    def discover(self, command = None):
        """
        Call node discovery here. Called from controller start method
        and from DISCOVER command received from ISY.
        Calls checkParams, so can be used after update of devFile or config
        """
        LOGGER.info(command)
        self.checkParams()
        self.discoverNodes()
        LOGGER.debug("Exit")
        

    def _get_node_name(self, dev: Dict[str, Any]) -> str:
        """
        Helper to get the node name from a device definition.
        """
        if 'name' in dev:
            return dev['name']
        return f"{dev['type']} {dev['id']}"

    
    def discoverNodes(self):
        """
        Discovers, adds, updates, and removes nodes based on the device list.
        """
        self.handler_discover_st = False
        LOGGER.info("In Discovery...")

        current_nodes_ids = {node for node in self.poly.getNodes() if node != self.id}
        new_nodes_ids = set()

        # Step 1: Add or update new nodes
        for dev in self.devlist:
            if "id" not in dev or "type" not in dev:
                LOGGER.error(f"Invalid device definition: {json.dumps(dev)}")
                continue

            dev_id = str(dev["id"])
            dev_type = str(dev["type"])
            node_name = self._get_node_name(dev)

            node_class = DEVICE_TYPE_TO_NODE_CLASS.get(dev_type)
            if not node_class:
                LOGGER.error(f"Device type '{dev_type}' is not yet supported.")
                continue

            node_exists = self.poly.getNode(dev_id)
            if not node_exists:
                self.poly.addNode(node_class(self.poly, self.address, dev_id, node_name))
                self.wait_for_node_done()
            elif node_exists.name != node_name:
                node_exists.rename(node_name)

            new_nodes_ids.add(dev_id)

        # Step 2: Remove old nodes
        nodes_to_delete = current_nodes_ids - new_nodes_ids
        for node_id in nodes_to_delete:
            LOGGER.info(f"Deleting old node with id: '{node_id}'")
            self.poly.delNode(node_id) # Using delNode with id
            # Note: polyglot API handles deleteDB().

        if not nodes_to_delete and not (new_nodes_ids - current_nodes_ids):
            LOGGER.warning('Discovery NO NEW activity')

        self.numNodes = len(new_nodes_ids)
        self.setDriver('GV0', self.numNodes)        
        self.handler_discover_st = True
        LOGGER.info('Discovery complete.')

        
    def delete(self, command = None):
        """
        This is called by Polyglot upon deletion of the NodeServer. If the
        process is co-resident and controlled by Polyglot, it will be
        terminiated within 5 seconds of receiving this message.
        """
        LOGGER.info(command)
        self.setDriver('ST', 0, report = True, force = True)
        LOGGER.info('bye bye ... deleted.')

        
    def stop(self, command = None):
        """
        This is called by Polyglot when the node server is stopped.  You have
        the opportunity here to cleanly disconnect from your device or do
        other shutdown type tasks.
        """
        LOGGER.info(command)
        self.setDriver('ST', 0, report = True, force = True)
        self.Notices.clear()
        LOGGER.info('NodeServer stopped.')
        

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
        

    # Status that this node has. Should match the 'sts' section
    # of the nodedef file.
    drivers = [
        {'driver': 'ST', 'value': 1, 'uom': 25, 'name': "Controller Status"},
        {'driver': 'GV0', 'value': 0, 'uom': 107, 'name': "NumberOfNodes"},
    ]
    
    # Commands that this node can handle.  Should match the
    # 'accepts' section of the nodedef file.
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'UPDATE_PROFILE': updateProfile,
    }
