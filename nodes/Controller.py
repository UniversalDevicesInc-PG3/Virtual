"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

Controller class
"""

# std libraries
import time, json, subprocess
from threading import Event, Condition

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
        self.handler_typedparams_st = None
        self.handler_typeddata_st = None
        self.handler_discover_st = None

        # Create data storage classes
        self.Parameters = Custom(polyglot, 'customparams')
        self.Notices = Custom(polyglot, 'notices')
        self.TypedParameters = Custom(polyglot, 'customtypedparams')
        self.TypedData = Custom(polyglot, 'customtypeddata')

        # Subscribe to various events from the Interface class.
        # The START event is unique in that you can subscribe to 
        # the start event for each node you define.

        self.poly.subscribe(self.poly.START,             self.start, address)
        self.poly.subscribe(self.poly.POLL,              self.poll)
        self.poly.subscribe(self.poly.LOGLEVEL,          self.handleLevelChange)
        self.poly.subscribe(self.poly.CUSTOMPARAMS,      self.parameterHandler)
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
        self.discoverNodes()
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
            

    def parameterHandler(self, params):
        """
        Called via the CUSTOMPARAMS event. When the user enters or
        updates Custom Parameters via the dashboard.
        """
        LOGGER.info('parmHandler: Loading parameters now')
        self.Parameters.load(params)
        while not self.checkParams():
            time.sleep(2)
        self._handler_params_st = True
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
        if (self.handler_params_st and self.handler_typedparams_st and self.handler_typeddata_st):
            self.discoverNodes()
            if self.handler_discover_st:
                self.all_handlers_st_event.set()


    def checkParams(self):
        self.Notices.delete('config')
        params = self.Parameters
        self.devlist = []
        for key,val in params.items():
            a = key
            if a.isdigit():
                if val in {'switch', 'temperature', 'temperaturec', 'temperaturecr', 'generic', 'dimmer'}:
                    name = str(val) + ' ' + str(key)
                    device = {'id': a, 'type': val, 'name': name}
                    self.devlist.append(device)
                elif val is not None:
                    try:
                        device = {}
                        device = json.loads(val)
                        LOGGER.debug(f'json device before loads: {device}, type: {type(device)}')
                        if "id" not in device:
                            device["id"] = a
                            LOGGER.debug(f'no id: inserting id: {a} into device: {device}')
                        if device["id"] != a:
                            device["id"] = a
                            LOGGER.error(f"error id: {a} != deviceID: {device['id']} fixed device: {device}")
                        self.devlist.append(device)
                    except Exception as ex:
                        LOGGER.error(f"JSON parse exception: {ex} for  key: {a} the value: {val} created exeption: {ex}" )
                        self.Notices['config'] = 'Bad configuration, please re-check.'
                        return False
            elif a == "devFile" or a == "devfile":
                if val is not None:
                    try:
                        f = open(val)
                    except Exception as ex:
                        LOGGER.error(f"CheckParams: Failed to open {val}: {ex}")
                        return False
                    try:
                        dev_yaml = yaml.safe_load(f.read())  # upload devfile into data
                        f.close()
                    except Exception as ex:
                        LOGGER.error(f"checkParams: Failed to parse {val} content: {ex}")
                        return False
                    if "devices" not in dev_yaml:
                        LOGGER.error(f"checkParams: Manual discovery file {val} is missing devices section")
                        return False
                    self.devlist.extend(dev_yaml["devices"])  # transfer devfile into devlist
                    LOGGER.info(f'file: {val} with content: {dev_yaml} transferred into self.devlist')
                else:
                    LOGGER.error('checkParams: devFile missing filename')
                    return False
            else:
                LOGGER.error(f'unknown keyfield: {a}')
                    
        LOGGER.info('checkParams is complete')
        LOGGER.info(f'checkParams: self.devlist: {self.devlist}')
        return True

        
    """
    Called via the LOGLEVEL event.
    """
    def handleLevelChange(self, level):
        LOGGER.info('New log level: {}'.format(level))
            
    def poll(self, flag):
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
        Do shade and scene discovery here. Called from controller start method
        and from DISCOVER command received from ISY
        """
        LOGGER.info(command)
        try:
            subprocess.call("rm db/*.db", shell=True)
            LOGGER.info("db directory cleaned-up")
        except Exception as e:
            LOGGER.error(f"Database delete Error: {e}")
        self.checkParams()
        self.discoverNodes()
        

    def discoverNodes(self):
        self.handler_discover_st = False
        LOGGER.info("In Discovery...")

        nodes = self.poly.getNodes()
        LOGGER.debug(f"current nodes = {nodes}")
        nodes_old = []
        for node in nodes:
            LOGGER.debug(f"current node = {node}")
            if node != self.id:
                nodes_old.append(node)

        nodes_new = []
        for dev in self.devlist:
            if ("id" not in dev or "type" not in dev):
                LOGGER.error("Invalid device definition: {json.dumps(dev)}")
                continue
            type = str(dev["type"])
            id = str(dev["id"])
            if "name" in dev:
                name = dev["name"]
            else:
                name = type + ' ' + id
            nodeExists = self.poly.getNode(id)
            if type == "switch":
                if not nodeExists:
                    self.poly.addNode(VirtualSwitch(self.poly, self.address, id, name))
                    self.wait_for_node_done()
                else:
                    if nodeExists.name != type + " " + id:
                        nodeExists.rename(name)
            elif type == 'temperature':
                if not self.poly.getNode(id):
                    self.poly.addNode(VirtualTemp(self.poly, self.address, id, name))
                    self.wait_for_node_done()
                else:
                    if nodeExists.name != type + " " + id:
                        nodeExists.rename(name)
            elif type == 'temperaturec' or type == 'temperaturecr':
                if not self.poly.getNode(id):
                    self.poly.addNode(VirtualTempC(self.poly, self.address, id, name))
                    self.wait_for_node_done()
                else:
                    if nodeExists.name != type + " " + id:
                        nodeExists.rename(name)
            elif type == 'generic' or type == 'dimmer':
                if not self.poly.getNode(id):
                    self.poly.addNode(VirtualGeneric(self.poly, self.address, id, name))
                    self.wait_for_node_done()
                else:
                    if nodeExists.name != type + " " + id:
                        nodeExists.rename(name)
            elif type == 'garage':
                if not self.poly.getNode(id):
                    self.poly.addNode(VirtualGarage(self.poly, self.address, id, name))
                    self.wait_for_node_done()
                else:
                    if nodeExists.name != type + " " + id:
                        nodeExists.rename(name)
            else:
                LOGGER.error(f"Device type {type} is not yet supported")
                continue
            nodes_new.append(id)

        # remove nodes which do not exist in gateway
        nodes = self.poly.getNodesFromDb()
        LOGGER.info(f"db nodes = {nodes}")
        nodes = self.poly.getNodes()
        nodes_get = {key: nodes[key] for key in nodes if key != self.id}
        LOGGER.info(f"old nodes = {nodes_old}")
        LOGGER.info(f"new nodes = {nodes_new}")
        LOGGER.info(f"pre-delete nodes = {nodes_get}")
        for node in nodes_get:
            if (node not in nodes_new):
                LOGGER.info(f"need to delete node {node}")
                node.deleteDB()
                self.poly.delNode(node)

        if nodes_get == nodes_new:
            LOGGER.warning('Discovery NO NEW activity')
        self.handler_discover_st = True
        LOGGER.info('Discovery complete.')

        
    def delete(self):
        """
        This is called by Polyglot upon deletion of the NodeServer. If the
        process is co-resident and controlled by Polyglot, it will be
        terminiated within 5 seconds of receiving this message.
        """
        self.setDriver('ST', 0, report = True, force = True)
        LOGGER.info('bye bye ... deleted.')

        
    def stop(self):
        """
        This is called by Polyglot when the node server is stopped.  You have
        the opportunity here to cleanly disconnect from your device or do
        other shutdown type tasks.
        """
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
