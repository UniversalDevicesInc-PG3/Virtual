"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

Controller class
"""

# std libraries
import time
import json
import yaml

# external libraries
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

        self.poly = polyglot
        self.primary = primary
        self.address = address
        self.name = name
        self.parseDelay = 0.1
        self.pullError = False
        self.pullDelay = 0.1


        self.n_queue = []
        self.last = 0.0
        self.no_update = False
        self.discovery = False
        self.valid_configuration = False
        self.parmDone = False

        # Create data storage classes to hold specific data that we need
        # to interact with.  
        self.Parameters = Custom(polyglot, 'customparams')
        self.Notices = Custom(polyglot, 'notices')
        self.TypedParameters = Custom(polyglot, 'customtypedparams')
        self.TypedData = Custom(polyglot, 'customtypeddata')

        # Subscribe to various events from the Interface class.
        #
        # The START event is unique in that you can subscribe to 
        # the start event for each node you define.

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.LOGLEVEL, self.handleLevelChange)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.parameterHandler)
        self.poly.subscribe(self.poly.CUSTOMTYPEDPARAMS, self.typedParameterHandler)
        self.poly.subscribe(self.poly.CUSTOMTYPEDDATA, self.typedDataHandler)
        self.poly.subscribe(self.poly.POLL, self.poll)
        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.DISCOVER, self.discover)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)

        # Tell the interface we have subscribed to all the events we need.
        # Once we call ready(), the interface will start publishing data.
        self.poly.ready()

        # Tell the interface we exist.  
        self.poly.addNode(self)

        '''
        node_queue() and wait_for_node_event() create a simple way to wait
        for a node to be created.  The nodeAdd() API call is asynchronous and
        will return before the node is fully created. Using this, we can wait
        until it is fully created before we try to use it.
        '''
    def node_queue(self, data):
        self.n_queue.append(data['address'])

    def wait_for_node_done(self):
        while len(self.n_queue) == 0:
            time.sleep(0.1)
        self.n_queue.pop()

    def start(self):
        self.Notices['hello'] = 'Start-up'

        self.last = 0.0
        # Send the profile files to the ISY if neccessary. The profile version
        # number will be checked and compared. If it has changed since the last
        # start, the new files will be sent.
        self.poly.updateProfile()

        # Send the default custom parameters documentation file to Polyglot
        # for display in the dashboard.
        self.poly.setCustomParamsDoc()

        # Initializing a heartbeat is an example of something you'd want
        # to do during start.  Note that it is not required to have a
        # heartbeat in your node server
        self.heartbeat(True)

        while self.valid_configuration is False:
            LOGGER.info('Start: Waiting on valid configuration')
            self.Notices['waiting'] = 'Waiting on valid configuration'
            time.sleep(5)
        self.Notices.delete('waiting')

        while not self.parmDone:
            LOGGER.info("Start: Waiting on first Discovery Completion")
            time.sleep(1)

        LOGGER.info('Started Virtual Device NodeServer v%s', self.poly.serverdata)
        self.query()
        self.Notices.delete('hello')

    """
    Called via the CUSTOMPARAMS event. When the user enters or
    updates Custom Parameters via the dashboard. The full list of
    parameters will be sent to your node server via this event.

    Here we're loading them into our local storage so that we may
    use them as needed.

    New or changed parameters are marked so that you may trigger
    other actions when the user changes or adds a parameter.

    NOTE: Be carefull to not change parameters here. Changing
    parameters will result in a new event, causing an infinite loop.
    """
    def parameterHandler(self, params):
        self.Parameters.load(params)
        LOGGER.info('parmHandler: Loading parameters now')
        if self.checkParams():
            self.discoverNodes()
            self.parmDone = True
        LOGGER.info('parmHandler Done...')

    def checkParams(self):
        params = self.Parameters
        self.devlist = []
        for key,val in params.items():
            a = key
            if a == "parseDelay":
                self.parseDelay = float(val)
            elif a == "pullDelay":
                self.pullDelay = float(val)
            elif a.isdigit():
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
        LOGGER.info('Pull Delay set to %s seconds, Parse Delay set to %s seconds', self.pullDelay, self.parseDelay)
        self.valid_configuration = True
        return True

        
    """
    Called via the CUSTOMTYPEDPARAMS event. This event is sent When
    the Custom Typed Parameters are created.  See the checkParams()
    below.  Generally, this event can be ignored.

    Here we're re-load the parameters into our local storage.
    The local storage should be considered read-only while processing
    them here as changing them will cause the event to be sent again,
    creating an infinite loop.
    """
    def typedParameterHandler(self, params):
        self.TypedParameters.load(params)
        LOGGER.debug('Loading typed parameters now')
        LOGGER.debug(params)

    """
    Called via the CUSTOMTYPEDDATA event. This event is sent when
    the user enters or updates Custom Typed Parameters via the dashboard.
    'params' will be the full list of parameters entered by the user.

    Here we're loading them into our local storage so that we may
    use them as needed.  The local storage should be considered 
    read-only while processing them here as changing them will
    cause the event to be sent again, creating an infinite loop.
    """
    def typedDataHandler(self, params):
        self.TypedData.load(params)
        LOGGER.debug('Loading typed data now')
        LOGGER.debug(params)

    """
    Called via the LOGLEVEL event.
    """
    def handleLevelChange(self, level):
        LOGGER.info('New log level: {}'.format(level))

            
    """
    Called via the POLL event.  The POLL event is triggerd at
    the intervals specified in the node server configuration. There
    are two separate poll events, a long poll and a short poll. Which
    one is indicated by the flag.  flag will hold the poll type either
    'longPoll' or 'shortPoll'.

    Use this if you want your node server to do something at fixed
    intervals.
    """
    def poll(self, flag):
        # pause updates when in discovery
        if self.discovery:
            LOGGER.info('Skipping poll while in Discovery')
        else:
            if 'longPoll' in flag:
                LOGGER.debug('longPoll (controller)')
                for node in self.poly.nodes():
                    if node != self:
                        node.getDataFromID()
                    time.sleep(float(self.pullDelay))
            else:
                LOGGER.debug('shortPoll (controller)')
 
    def query(self, command = None):
        """
        The query method will be called when the ISY attempts to query the
        status of the node directly.  You can do one of two things here.
        You can send the values currently held by Polyglot back to the
        ISY by calling reportDriver() or you can actually query the 
        device represented by the node and report back the current 
        status.
        """
        nodes = self.poly.getNodes()
        for node in nodes:
            nodes[node].reportDrivers()

    def updateProfile(self,command):
        LOGGER.info('update profile')
        st = self.poly.updateProfile()
        return st

    def discover(self, command = None):
        """
        Do shade and scene discovery here. Called from controller start method
        and from DISCOVER command received from ISY
        """
        self.checkParams()
        self.discoverNodes()

    def discoverNodes(self):
        if self.discovery:
            LOGGER.info('Discover already running.')
            return

        self.discovery = True
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
                self.poly.delNode(node)

        self.discovery = False
        if nodes_get == nodes_new:
            LOGGER.error('Discovery NO NEW activity')
        LOGGER.info('Discovery complete.')

    def delete(self):
        """
        This is called by Polyglot upon deletion of the NodeServer. If the
        process is co-resident and controlled by Polyglot, it will be
        terminiated within 5 seconds of receiving this message.
        """
        LOGGER.info('bye bye ... deleted.')

    def stop(self):
        """
        This is called by Polyglot when the node server is stopped.  You have
        the opportunity here to cleanly disconnect from your device or do
        other shutdown type tasks.
        """
        LOGGER.info('NodeServer stopped.')

    def heartbeat(self,init=False):
        """
        This is a heartbeat function.  It uses the
        long poll interval to alternately send a ON and OFF command back to
        the ISY.  Programs on the ISY can then monitor this and take action
        when the heartbeat fails to update.
        """
        LOGGER.debug('heartbeat: init={}'.format(init))
        if init is not False:
            self.hb = init
        LOGGER.debug('heartbeat: hb={}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0

    def removeNoticesAll(self, command = None):
        LOGGER.info('remove_notices_all: notices={}'.format(self.Notices))
        # Remove all existing notices
        self.Notices.clear()



    # Status that this node has. Should match the 'sts' section
    # of the nodedef file.
    drivers = [
        {'driver': 'ST', 'value': 1, 'uom': 2, 'name': "Controller Status"},
    ]
    
    # Commands that this node can handle.  Should match the
    # 'accepts' section of the nodedef file.
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'UPDATE_PROFILE': updateProfile,
        'REMOVE_NOTICES_ALL': removeNoticesAll,
    }
