"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

Controller class
"""

# std libraries
import json, logging
from threading import Event, Condition
from typing import Dict, Any, List

# external libraries
from udi_interface import Node, LOGGER, Custom, LOG_HANDLER
import yaml

# personal libraries
pass


# Nodes
from nodes import *

 # Map device types to their respective node classes
DEVICE_TYPE_TO_NODE_CLASS = {
    'switch': VirtualSwitch,
    'ononly': VirtualonOnly,
    'temperature': VirtualTemp,
    'temperaturec': VirtualTempC,
    'temperaturecr': VirtualTempC,
    'generic': VirtualGeneric,
    'dimmer': VirtualGeneric,
    'garage': VirtualGarage,
    'ondelay': VirtualonDelay,
    'offdelay': VirtualoffDelay,
    'toggle': VirtualToggle,
}


class Controller(Node):
    id = 'controller'

    def __init__(self, poly, primary, address, name):
        """
        super
        self definitions
        data storage classes
        subscribes
        ready
        we exist!
        """
        super().__init__(poly, primary, address, name)
        # importand flags, timers, vars
        self.hb = 0 # heartbeat
        self.numNodes = 0

        # storage arrays & conditions
        self.n_queue = []
        self.queue_condition = Condition()

        # Events & in
        self.ready_event = Event()
        self.all_handlers_st_event = Event()
        self.stop_sse_client_event = Event()
        self.discovery_in = False
        
        # startup completion flags
        self.handler_params_st = None
        self.handler_data_st = None
        self.handler_typedparams_st = None
        self.handler_typeddata_st = None

        # Create data storage classes
        self.Notices         = Custom(poly, 'notices')
        self.Parameters      = Custom(poly, 'customparams')
        self.Data            = Custom(poly, 'customdata')
        self.TypedParameters = Custom(poly, 'customtypedparams')
        self.TypedData       = Custom(poly, 'customtypeddata')

        # Subscribe to various events from the Interface class.
        # The START event is unique in that you can subscribe to 
        # the start event for each node you define.

        self.poly.subscribe(self.poly.START,             self.start, address)
        self.poly.subscribe(self.poly.POLL,              self.poll)
        self.poly.subscribe(self.poly.LOGLEVEL,          self.handleLevelChange)
        self.poly.subscribe(self.poly.CUSTOMPARAMS,      self.parameterHandler)
        self.poly.subscribe(self.poly.CUSTOMDATA,        self.dataHandler)
        self.poly.subscribe(self.poly.STOP,              self.stop)
        self.poly.subscribe(self.poly.DISCOVER,          self.discover_cmd)
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
            # start-up failed
            LOGGER.error("Timed out waiting for handlers to startup")
            self.setDriver('ST', 2) # start-up failed
            self.Notices['error'] = 'Error start-up timeout.  Check config & restart'
            return        

        # Discover and wait for discovery to complete
        discoverSuccess = self.discover_cmd()

        # first update from Gateway
        if not discoverSuccess:
            # start-up failed
            LOGGER.error(f'First discovery failed!!! exit {self.name}')
            self.Notices['error'] = 'Error first discovery.  Check config & restart'
            self.setDriver('ST', 2)
            return

        self.Notices.delete('waiting')        
        LOGGER.info('Started Virtual Device NodeServer v%s', self.poly.serverdata)
        self.query(command = f"{self.name}: STARTUP")

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
        the Custom Typed Parameters are created.
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


    def checkParams(self) -> bool:
        """
        Checks and processes device parameters from `self.Parameters`.
        """
        self.Notices.delete('config')
        self.devlist = []
        has_error = False

        for key, val in self.Parameters.items():
            if not key.isdigit():
                # handle config file
                if key.lower() == "devfile":
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
            
            # handle simple single device using DEVICE_TYPE_TO_NODE_CLASS
            if val in DEVICE_TYPE_TO_NODE_CLASS:
                name = self.poly.getValidName(f"{val} {key}")
                device = {'id': key, 'type': val, 'name': name}
                self.devlist.append(device)
            # handle json single device
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


    def handleLevelChange(self, level):
        """
        Called via the LOGLEVEL event, to handle log level change.
        """
        LOGGER.info(f'enter: level={level}')
        if level['level'] < 10:
            LOGGER.info("Setting basic config to DEBUG...")
            LOG_HANDLER.set_basic_config(True,logging.DEBUG)
        else:
            LOGGER.info("Setting basic config to WARNING...")
            LOG_HANDLER.set_basic_config(True,logging.WARNING)
        LOGGER.info(f'exit: level={level}')

        
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


    def discover_cmd(self, command = None):
        """
        Call node discovery here. Called from controller start method
        and from DISCOVER command received from ISY.
        Calls checkParams, so can be used after update of devFile or config
        """
        LOGGER.info(command)
        success = False
        if self.discovery_in:
            LOGGER.info('Discover already running.')
            return success

        self.discovery_in = True
        LOGGER.info("In Discovery...")

        if self.checkParams() and self._discover():
            success = True
            LOGGER.info("Discovery Success")
        else:
            LOGGER.error("Discovery Failure")
        self.discovery_in = False            
        return success

    
    def _discover(self):
        """
        Discover all nodes from the gateway.
        """
        success = False
        nodes_existing = self.poly.getNodes()
        LOGGER.debug(f"current nodes = {nodes_existing}")
        nodes_old = [node for node in nodes_existing if node != self.id]
        nodes_new = []

        try:
            self._discover_nodes(nodes_existing, nodes_new)
            self._cleanup_nodes(nodes_new, nodes_old)
            self.numNodes = len(nodes_new)
            self.setDriver('GV0', self.numNodes)
            success = True
            LOGGER.info(f"Discovery complete. success = {success}")
        except Exception as ex:
            LOGGER.error(f'Discovery Failure: {ex}', exc_info=True)            
        return success


    def _discover_nodes(self, nodes_existing, nodes_new):
        """
        Adds and updates nodes based on the device list.
        """
        for dev in self.devlist:
            if "id" not in dev or "type" not in dev:
                LOGGER.error(f"Invalid device definition: {dev}")
                continue
            
            dev_id = str(dev.get("id"))
            dev_type = str(dev.get("type"))
            node_name = self._get_node_name(dev)
            node_class = DEVICE_TYPE_TO_NODE_CLASS.get(dev_type)
            if not node_class:
                LOGGER.error(f"Device type '{dev_type}' is not yet supported.")
                continue

            nodes_new.append(dev_id)
            if dev_id not in nodes_existing:
                node = node_class(self.poly, self.address, dev_id, node_name)
                self.poly.addNode(node)
                self.wait_for_node_done()


    def _get_node_name(self, dev: Dict[str, Any]) -> str:
        """
        Helper to get the node name from a device definition.
        """
        if 'name' in dev:
            return self.poly.getValidName(dev.get('name'))
        return self.poly.getValidVame(f"{dev.get('type')} {dev.get('id')}")


    def _cleanup_nodes(self, nodes_new, nodes_old):
        """
        Delete all nodes which are not in the new configuration.
        """
        valid_class_names = {
            cls.__name__.lower() for cls in DEVICE_TYPE_TO_NODE_CLASS.values()
        }

        # Filter DB nodes whose nodeDefId matches any valid class name
        nodes_db_sub = [
            node for node in self.poly.getNodesFromDb()
            if node.get("nodeDefId", "").lower() in valid_class_names
        ]

        LOGGER.debug(f"db nodes = {nodes_db_sub}")

        # Get current nodes excluding self
        nodes_current = self.poly.getNodes()
        nodes_get = {addr: node for addr, node in nodes_current.items() if addr != self.id}
        existing_addresses = set(nodes_get.keys())

        # Filter DB nodes whose address is not in current nodes
        nodes_delete = [
            node for node in nodes_db_sub
            if node.get("address") not in existing_addresses
        ]

        LOGGER.info(f"old nodes = {nodes_old}")
        LOGGER.info(f"new nodes = {nodes_new}")
        LOGGER.info(f"pre-delete(get) nodes = {nodes_get}")
        LOGGER.info(f"nodes to delete = {nodes_delete}")

        # Delete stale nodes from current set
        for address in nodes_get:
            if address not in nodes_new:
                LOGGER.info(f"need to delete node {address}")
                self.poly.delNode(address)

        # Delete stale nodes from DB
        for node in nodes_delete:
            address = node.get("address")
            if address not in nodes_new:
                LOGGER.info(f"need to delete node {address}")
                self.poly.delNode(address)
                

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
        'DISCOVER': discover_cmd,
    }
