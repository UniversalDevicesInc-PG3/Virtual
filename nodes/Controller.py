"""
This module defines the Controller class for the udi-Virtual-pg3 NodeServer/Plugin.

The Controller is the primary interface between the Polyglot platform and the
virtual devices. It manages device discovery, configuration, and overall
NodeServer lifecycle.

(C) 2025 Stephen Jenkins
"""

# std libraries
import json
import logging
from threading import Event, Condition
from typing import Dict, Any, List, Tuple

# external libraries
from udi_interface import Node, LOGGER, Custom, LOG_HANDLER
import yaml

# personal libraries
# none

# Nodes
from nodes.VirtualGeneric import VirtualGeneric
from nodes.VirtualGarage import VirtualGarage
from nodes.VirtualTemp import VirtualTemp, VirtualTempC
from nodes.VirtualSwitch import VirtualSwitch
from nodes.VirtualonOnly import VirtualonOnly
from nodes.VirtualonDelay import VirtualonDelay
from nodes.VirtualoffDelay import VirtualoffDelay
from nodes.VirtualToggle import VirtualToggle

# Mapping of device types to their respective node classes.
# This dictionary is used during discovery to instantiate the correct node type.
DEVICE_TYPE_TO_NODE_CLASS = {
    "switch": VirtualSwitch,
    "ononly": VirtualonOnly,
    "temperature": VirtualTemp,
    "temperaturec": VirtualTempC,
    "temperaturecr": VirtualTempC,
    "generic": VirtualGeneric,
    "dimmer": VirtualGeneric,
    "garage": VirtualGarage,
    "ondelay": VirtualonDelay,
    "offdelay": VirtualoffDelay,
    "toggle": VirtualToggle,
}


class Controller(Node):
    """
    The Controller class represents the main control node for the virtual devices.
    It handles the overall lifecycle of the NodeServer, including:
    - Initializing the Polyglot interface.
    - Managing custom parameters and data.
    - Discovering and cleaning up virtual device nodes.
    - Handling system-wide events like log level changes and heartbeats.
    """

    id = "controller"  # Unique identifier for the controller node.

    def __init__(self, poly, primary, address, name):
        """
        Initializes the Controller node.

        Args:
            poly (udi_interface.Polyglot): The Polyglot interface object.
            primary (str): The address of the primary node (this controller).
            address (str): The address of this controller node.
            name (str): The name of this controller node.
        """
        super().__init__(poly, primary, address, name)
        # importand flags, timers, vars
        self.hb = 0  # heartbeat
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
        self.Notices = Custom(poly, "notices")
        self.Parameters = Custom(poly, "customparams")
        self.Data = Custom(poly, "customdata")
        self.TypedParameters = Custom(poly, "customtypedparams")
        self.TypedData = Custom(poly, "customtypeddata")

        # Subscribe to various events from the Interface class.
        # The START event is unique in that you can subscribe to
        # the start event for each node you define.

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)
        self.poly.subscribe(self.poly.LOGLEVEL, self.handleLevelChange)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.parameterHandler)
        self.poly.subscribe(self.poly.CUSTOMDATA, self.dataHandler)
        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.DISCOVER, self.discover_cmd)
        self.poly.subscribe(self.poly.CUSTOMTYPEDDATA, self.typedDataHandler)
        self.poly.subscribe(self.poly.CUSTOMTYPEDPARAMS, self.typedParameterHandler)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)

        # Tell the interface we have subscribed to all the events we need.
        # Once we call ready(), the interface will start publishing data.
        self.poly.ready()

        # Tell the interface we exist.
        self.poly.addNode(self, conn_status="ST")

    def start(self):
        """
        Called by the Polyglot handler during NodeServer startup.
        This method performs initial setup, updates the profile, sets custom parameter documentation,
        starts the heartbeat, waits for all configuration handlers to complete, and initiates device discovery.
        """
        LOGGER.info(f"Virtual Devices PG3 NodeServer {self.poly.serverdata['version']}")
        self.Notices.clear()
        self.Notices["hello"] = "Start-up"
        self.setDriver("ST", 1, report=True, force=True)

        # Send the profile files to the ISY if neccessary or version changed.
        self.poly.updateProfile()

        # Send the default custom parameters documentation file to Polyglot
        self.poly.setCustomParamsDoc()

        # Initializing a heartbeat
        self.heartbeat()

        # Wait for all handlers to finish
        LOGGER.warning("Waiting for all handlers to complete...")
        self.Notices["waiting"] = "Waiting on valid configuration"
        self.all_handlers_st_event.wait(timeout=60)
        if not self.all_handlers_st_event.is_set():
            # start-up failed
            LOGGER.error("Timed out waiting for handlers to startup")
            self.setDriver("ST", 2)  # start-up failed
            self.Notices["error"] = "Error start-up timeout.  Check config & restart"
            return

        # Discover and wait for discovery to complete
        discoverSuccess = self.discover_cmd()

        # first update from Gateway
        if not discoverSuccess:
            # start-up failed
            LOGGER.error(f"First discovery failed!!! exit {self.name}")
            self.Notices["error"] = "Error first discovery.  Check config & restart"
            self.setDriver("ST", 2)
            return

        self.Notices.delete("waiting")
        LOGGER.info("Started Virtual Device NodeServer v%s", self.poly.serverdata)
        self.query(command=f"{self.name}: STARTUP")

        # signal to the nodes, its ok to start
        self.ready_event.set()

        # clear inital start-up message
        if self.Notices.get("hello"):
            self.Notices.delete("hello")

        LOGGER.info(f"exit {self.name}")

    def node_queue(self, data):
        """
        Queues a newly added node's address to signal its creation.
        This method is part of a mechanism to asynchronously wait for a node to be fully created
        after an `addNode()` API call, which returns before the node is ready.

        Args:
            data (dict): A dictionary containing node data, expected to have an 'address' key.
        """
        address = data.get("address")
        if address:
            with self.queue_condition:
                self.n_queue.append(address)
                self.queue_condition.notify()

    def wait_for_node_done(self):
        """
        Waits for a node to be added to the queue, indicating it has been created.
        This method works in conjunction with `node_queue` to ensure that operations
        on a node do not proceed until the node is fully initialized.
        """
        with self.queue_condition:
            while not self.n_queue:
                self.queue_condition.wait(timeout=0.2)
            self.n_queue.pop()

    def dataHandler(self, data):
        """
        Handles the CUSTOMDATA event, loading custom data into the controller.

        Args:
            data (dict): The custom data received from Polyglot.
        """
        LOGGER.debug(f"enter: Loading data {data}")
        if data is None:
            LOGGER.warning("No custom data")
        else:
            self.Data.load(data)
        self.handler_data_st = True
        self.check_handlers()

    def parameterHandler(self, params):
        """
        Handles the CUSTOMPARAMS event, loading custom parameters into the controller.
        This is triggered when a user enters or updates custom parameters via the dashboard.

        Args:
            params (dict): The custom parameters received from Polyglot.
        """
        LOGGER.info("parmHandler: Loading parameters now")
        self.Parameters.load(params)
        self.handler_params_st = True
        LOGGER.info("parmHandler Done...")
        self.check_handlers()

    def typedParameterHandler(self, params):
        """
        Handles the CUSTOMTYPEDPARAMS event, loading custom typed parameters into the controller.
        This event is sent when custom typed parameters are created or updated.

        Args:
            params (dict): The custom typed parameters received from Polyglot.
        """
        LOGGER.debug("Loading typed parameters now")
        self.TypedParameters.load(params)
        LOGGER.debug(params)
        self.handler_typedparams_st = True
        self.check_handlers()

    def typedDataHandler(self, data):
        """
        Handles the CUSTOMTYPEDDATA event, loading custom typed data into the controller.
        This event is sent when a user enters or updates custom typed data via the dashboard.

        Args:
            data (dict): The custom typed data received from Polyglot.
        """
        LOGGER.debug("Loading typed data now")
        if data is None:
            LOGGER.warning("No custom data")
        else:
            self.TypedData.load(data)
        LOGGER.debug(f"Loaded typed data {data}")
        self.handler_typeddata_st = True
        self.check_handlers()

    def check_handlers(self):
        """
        Checks if all startup handlers (parameters and data) have completed their processing.
        If all handlers are done, it sets the `all_handlers_st_event` to signal completion.
        """
        if (
            self.handler_params_st
            and self.handler_data_st
            and self.handler_typedparams_st
            and self.handler_typeddata_st
        ):
            self.all_handlers_st_event.set()

    def checkParams(self) -> bool:
        """
        Validates and processes device configurations from `self.Parameters`.
        It handles both direct device definitions and references to external configuration files (YAML).
        Populates `self.devlist` with parsed device information.

        Returns:
            bool: True if all parameters are processed without critical errors, False otherwise.
        """
        self.Notices.delete("config")
        self.devlist = []
        has_error = False

        for key, val in self.Parameters.items():
            new_devices, error = self._process_param(key, val)
            if new_devices:
                self.devlist.extend(new_devices)
            if error:
                has_error = True

        if has_error:
            self.Notices["config"] = "Bad configuration, please re-check."
            LOGGER.info("checkParams finished with errors.")
            return False

        LOGGER.info("checkParams is complete")
        LOGGER.info(f"checkParams: self.devlist: {self.devlist}")
        return True

    def _process_param(self, key: str, val: Any) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Processes a single parameter from the custom parameters.

        Args:
            key (str): The parameter key.
            val (Any): The parameter value.

        Returns:
            (List[Dict[str, Any]], bool): A tuple containing a list of processed devices and an error flag.
        """
        devices = []
        has_error = False

        # Handle special non-digit keys, like 'devfile' for external configuration.
        if not key.isdigit():
            if key.lower() == "devfile":
                if val:
                    devices_from_file = self._handle_file_devices(val)
                    if devices_from_file is not None:
                        devices.extend(devices_from_file)
                    else:
                        has_error = True
                else:
                    LOGGER.error(
                        "checkParams: devFile parameter is missing a filename."
                    )
                    has_error = True
            else:
                LOGGER.error(
                    f"Unknown configuration key: '{key}'. Non-digit keys are reserved."
                )
                has_error = True
            return devices, has_error

        # Handle simple device definitions (e.g., "1": "switch").
        if val in DEVICE_TYPE_TO_NODE_CLASS:
            name = self.poly.getValidName(f"{val} {key}")
            device = {"id": key, "type": val, "name": name}
            devices.append(device)
        # Handle complex device definitions in JSON format.
        elif val:
            json_device = self._handle_json_device(key, val)
            if json_device:
                devices.append(json_device)
            else:
                has_error = True

        return devices, has_error

    def _handle_file_devices(self, filename: str) -> List[Dict[str, Any]] | None:
        """
        Loads device configurations from a specified YAML file.

        Args:
            filename (str): The path to the YAML file containing device definitions.

        Returns:
            List[Dict[str, Any]] | None: A list of device dictionaries if successful, None otherwise.
        """
        try:
            with open(filename) as f:
                dev_yaml = yaml.safe_load(f)

            if "devices" not in dev_yaml:
                LOGGER.error(
                    f"Manual discovery file '{filename}' is missing 'devices' section."
                )
                return None

            LOGGER.info(f"File '{filename}' loaded successfully.")
            return dev_yaml["devices"]
        except FileNotFoundError as ex:
            LOGGER.error(f"checkParams: Failed to open {filename}: {ex}")
            return None
        except yaml.YAMLError as ex:
            LOGGER.error(
                f"checkParams: Failed to parse YAML content in {filename}: {ex}"
            )
            return None

    def _handle_json_device(self, key: str, val: str) -> Dict[str, Any] | None:
        """
        Parses a JSON string representing a single device configuration.
        It ensures the device has an 'id' and handles potential mismatches.

        Args:
            key (str): The key associated with the JSON string, used as a fallback for 'id'.
            val (str): The JSON string containing the device configuration.

        Returns:
            Dict[str, Any] | None: A dictionary representing the device if successful, None otherwise.
        """
        try:
            device = json.loads(val)
            if not isinstance(device, dict):
                raise TypeError("JSON content must be a dictionary.")

            if "id" not in device:
                device["id"] = key
                LOGGER.debug(f"no id: inserting id: {key} into device: {device}")
            elif device["id"] != key:
                device["id"] = key
                LOGGER.error(
                    f"error id: {key} != deviceID: {device['id']}; fixed device: {device}"
                )

            return device
        except (json.JSONDecodeError, TypeError) as ex:
            LOGGER.error(f"JSON parse error for key '{key}' with value '{val}': {ex}")
            return None

    def handleLevelChange(self, level):
        """
        Handles the LOGLEVEL event, adjusting the NodeServer's logging level.

        Args:
            level (dict): A dictionary containing the new log level.
        """
        LOGGER.info(f"enter: level={level}")
        if level["level"] < 10:
            LOGGER.info("Setting basic config to DEBUG...")
            LOG_HANDLER.set_basic_config(True, logging.DEBUG)
        else:
            LOGGER.info("Setting basic config to WARNING...")
            LOG_HANDLER.set_basic_config(True, logging.WARNING)
        LOGGER.info(f"exit: level={level}")

    def poll(self, flag):
        """
        Handles short and long poll events from Polyglot.
        Currently, it primarily triggers the heartbeat on long poll events.

        Args:
            flag (str): Indicates the type of poll event (e.g., 'longPoll').
        """
        # no updates until node is through start-up
        if not self.ready_event:
            LOGGER.error("Node not ready yet, exiting")
            return

        if "longPoll" in flag:
            LOGGER.debug("longPoll (controller)")
            self.heartbeat()

    def query(self, command=None):
        """
        Queries all nodes managed by this controller and reports their current driver states.

        Args:
            command (str, optional): The command that triggered the query. Defaults to None.
        """
        LOGGER.info(f"Enter {command}")
        nodes = self.poly.getNodes()
        for node in nodes:
            nodes[node].reportDrivers()
        LOGGER.debug("Exit")

    def discover_cmd(self, command=None):
        """
        Initiates the device discovery process.
        This method is called during controller startup and can also be triggered by a DISCOVER command from ISY.
        It re-evaluates parameters and performs the actual node discovery and cleanup.

        Args:
            command (str, optional): The command that triggered discovery. Defaults to None.

        Returns:
            bool: True if discovery was successful, False otherwise.
        """
        LOGGER.info(command)
        success = False
        if self.discovery_in:
            LOGGER.info("Discover already running.")
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

    def _discover(self) -> bool:
        """
        Performs the core discovery logic, adding new nodes and cleaning up old ones.

        Returns:
            bool: True if the discovery process completes without exceptions, False otherwise.
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
            self.setDriver("GV0", self.numNodes)
            success = True
            LOGGER.info(f"Discovery complete. success = {success}")
        except Exception as ex:
            LOGGER.error(f"Discovery Failure: {ex}", exc_info=True)
        return success

    def _discover_nodes(self, nodes_existing: Dict[str, Any], nodes_new: List[str]):
        """
        Iterates through the `devlist` and adds new nodes or ensures existing nodes are present.

        Args:
            nodes_existing (Dict[str, Any]): A dictionary of currently existing nodes.
            nodes_new (List[str]): A list to populate with the IDs of newly discovered or existing nodes.
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
        Retrieves a valid node name from a device definition, prioritizing a 'name' field
        or constructing one from 'type' and 'id'.

        Args:
            dev (Dict[str, Any]): The device dictionary.

        Returns:
            str: A valid name for the node.
        """
        if "name" in dev:
            return self.poly.getValidName(dev.get("name"))
        return self.poly.getValidVame(f"{dev.get('type')} {dev.get('id')}")

    def _cleanup_nodes(self, nodes_new: List[str], nodes_old: List[str]):
        """
        Deletes nodes that are no longer present in the new configuration.
        It compares the newly discovered nodes with previously existing nodes and removes stale ones.

        Args:
            nodes_new (List[str]): A list of addresses for currently active nodes.
            nodes_old (List[str]): A list of addresses for previously active nodes.
        """
        valid_class_names = {
            cls.__name__.lower() for cls in DEVICE_TYPE_TO_NODE_CLASS.values()
        }

        # Filter DB nodes whose nodeDefId matches any valid class name
        nodes_db_sub = [
            node
            for node in self.poly.getNodesFromDb()
            if node.get("nodeDefId", "").lower() in valid_class_names
        ]

        LOGGER.debug(f"db nodes = {nodes_db_sub}")

        # Get current nodes excluding self
        nodes_current = self.poly.getNodes()
        nodes_get = {
            addr: node for addr, node in nodes_current.items() if addr != self.id
        }
        existing_addresses = set(nodes_get.keys())

        # Filter DB nodes whose address is not in current nodes
        nodes_delete = [
            node
            for node in nodes_db_sub
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

    def delete(self, command=None):
        """
        Called by Polyglot when the NodeServer is deleted.
        This method performs cleanup tasks before the NodeServer process is terminated.

        Args:
            command (str, optional): The command that triggered the deletion. Defaults to None.
        """
        LOGGER.info(command)
        self.setDriver("ST", 0, report=True, force=True)
        LOGGER.info("bye bye ... deleted.")

    def stop(self, command=None):
        """
        Called by Polyglot when the NodeServer is stopped.
        This method allows for clean disconnection from devices and other shutdown tasks.

        Args:
            command (str, optional): The command that triggered the stop. Defaults to None.
        """
        LOGGER.info(command)
        self.setDriver("ST", 0, report=True, force=True)
        self.Notices.clear()
        LOGGER.info("NodeServer stopped.")

    def heartbeat(self):
        """
        Sends alternating ON/OFF commands to the ISY to indicate the NodeServer is active.
        This function is typically called during long poll intervals.
        """
        LOGGER.debug(f"heartbeat: hb={self.hb}")
        command = "DOF" if self.hb else "DON"
        self.reportCmd(command, 2)
        self.hb = not self.hb
        LOGGER.debug("Exit")

    """
    UOMs:
    25: index
    107: Raw 1-byte unsigned value

    Driver controls:
    ST: Status (Controller Status)
    GV0: Custom Control 0 (NumberOfNodes)
    """
    drivers = [
        {"driver": "ST", "value": 1, "uom": 25, "name": "Controller Status"},
        {"driver": "GV0", "value": 0, "uom": 107, "name": "NumberOfNodes"},
    ]

    """
    Commands that this node can handle.
    Should match the 'accepts' section of the nodedef file.
    """
    commands = {
        "QUERY": query,
        "DISCOVER": discover_cmd,
    }
