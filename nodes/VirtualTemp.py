"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

VirtualTemp class
"""
# std libraries
import time
from typing import Any, Dict, Optional

# external libraries
from udi_interface import LOGGER, ISY, Node

# local imports
from utils.node_funcs import (FieldSpec, load_persistent_data, store_values,
                              push_to_isy_var, pull_from_isy_var,
                              get_config_data)

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
    "tempVal":         FieldSpec(driver="ST",  default=None, data_type="state"), # 'ST'  : current temperature        
    "prevVal":         FieldSpec(driver="GV1", default=None, data_type="state"), # 'GV1' : previous temperature
    "lastUpdateTime":  FieldSpec(driver="GV2", default=0.0, data_type="state"), # 'GV2' : time since last update
    "highTemp":        FieldSpec(driver="GV3", default=None, data_type="state"), # 'GV3' : high temperature     
    "lowTemp":         FieldSpec(driver="GV4", default=None, data_type="state"), # 'GV4' : low temperature            
    "previousHigh":    FieldSpec(driver=None,  default=None, data_type="state"), # bucket for previous high
    "previousLow":     FieldSpec(driver=None,  default=None, data_type="state"), # bucket for previous low
    "prevAvgTemp":     FieldSpec(driver=None,  default=None, data_type="state"), # bucket for previous avg
    "currentAvgTemp":  FieldSpec(driver="GV5", default=None, data_type="state"), # 'GV5' : average of  high to low 
    "action1":         FieldSpec(driver="GV6", default=0, data_type="state"), # 'GV6' : action1 push to or pull from variable   
    "action1type":     FieldSpec(driver="GV7", default=0, data_type="state"), # 'GV7' : variable type integer or state
    "action1id":       FieldSpec(driver="GV8", default=0, data_type="state"), # 'GV8' : variable id
    "action2":         FieldSpec(driver="GV9", default=0, data_type="state"), # 'GV9' : action 2 push to or pull from variable  
    "action2type":     FieldSpec(driver="GV10", default=0, data_type="state"),# 'GV10': variable type 2 int or state, curr or init
    "action2id":       FieldSpec(driver="GV11", default=0, data_type="state"),# 'GV11': variable id 2   
    "RtoPrec":         FieldSpec(driver="GV12", default=0, data_type="state"),# 'GV12': raw to precision
    "CtoF":            FieldSpec(driver="GV13", default=0, data_type="state"),# 'GV13': Fahrenheit to Celsius
    "FtoC":            FieldSpec(driver="GV13", default=0, data_type="state"),# 'GV13': Celsius to Fahrenheit
}


class VirtualTemp(Node):
    id = 'virtualtemp'

    """ This class represents a simple virtual temperature sensor.
    This device can be populated directly or from variables.
    Conversion to/from raw or F/C is supported.  Finally, the data can
    be sent to a variable or used directly.  Programs can use the data
    as well.

    'setTemp'           : set temperature to specific number
    'setAction[1,2]'    : set Action 1,2 None, push, pull
    'setAction[1,2]id'  : set Action 1,2 id
    'setAction[1,2]type': set Action 1,2 type
    'setCtoF'           : set Celsius to Fahrenheit
    'setFtoC'           : set Fahrenheit to Celsius
    'setRawToPrec'      : set Raw To Precision
    'resetStats'        : reset Statistics
    """
    
    def __init__(self, poly, primary, address, name, *, default_ovr: Optional[Dict[str, Any]] = None):
        """ Sent by the Controller class node.
        :param polyglot: Reference to the Interface class
        :param primary: Parent address
        :param address: This nodes address
        :param name: This nodes name

        data[''] class variables:
        prevVal, tempVal storage of last, current temperature value
        lastUpdateTime timestamp
        highTemp, lowTemp range of high temp, set to None on init
        previousHigh, previousLow storage of previous range
        prevAvgTemp, currentAvgTemp storage of averages
        action1, action2 none, push, pull
        action1id, action1id id of variable,  0=None, 1 - 400
        action1type, action2type  State var or init, Int var or init, 1 - 4
        RtoPrec Raw to precision conversion
        CtoF Celsius to Fahrenheit conversion

        subscribes:
        START: used to create/check/load DB file
        POLL: shortPoll for updates
        """
        super().__init__(poly, primary, address, name)

        self.poly = poly
        self.primary = primary
        self.controller = poly.getNode(self.primary)
        self.address = address
        self.name = name

        # default variables and drivers
        self.data = {field: spec.default for field, spec in FIELDS.items()}

        self.poly.subscribe(self.poly.START, self.start, address)
        

    def start(self):
        """
        Start node and retrieve persistent data
        """
        LOGGER.info(f'start: switch:{self.name}')

        # wait for controller start ready
        self.controller.ready_event.wait()

        # get isy address
        self.isy = ISY(self.poly)
        
        # get persistent data from polyglot or depreciated: old db file, then delete db file
        load_persistent_data(self, FIELDS)

        # retrieve configuration data
        get_config_data(self, FIELDS)

        self._reset_time()

        # start polling & exit
        self.poly.subscribe(self.poly.POLL, self.poll)
        LOGGER.info(f"{self.name} exit start")
        

    def poll(self, flag):
        """
        POLL event subscription above
        """
        if 'shortPoll' in flag and self.controller.ready_event:
            LOGGER.debug(f"shortPoll {self.name}")
            self._update()
            

    def _update(self):
        """
        Called by shortPoll to update last update and action list.
        """
        _sinceLastUpdate = round(((time.time() - self.data['lastUpdateTime']) / 60), 1)
        if _sinceLastUpdate < 1440:
                self.setDriver('GV2', _sinceLastUpdate)
        else:
                self.setDriver('GV2', 1440)
        if self.data['action1'] == 1:
            push_to_isy_var(self, self.data['action1type'], self.data['action1id'], self.data['tempVal'])
        if self.data['action2'] == 1:
            push_to_isy_var(self, self.data['action2type'], self.data['action2id'], self.data['tempVal'])
        if self.data['action1'] == 2:
            var = pull_from_isy_var(self, self.data['action1type'], self.data['action1id'])
            if var: self.set_temp_cmd({"cmd": "data", "value": var})
        if self.data['action2'] == 2:
            var = pull_from_isy_var(self, self.data['action2type'], self.data['action2id'])
            if var: self.set_temp_cmd({"cmd": "data", "value": var})


    def set_action1_cmd(self, command):
        """
        Based on program or admin console set action1
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['action1'] = int(command.get('value'),0)
        self.setDriver('GV6', self.data['action1'])
        store_values(self)
        LOGGER.debug('Exit')
        

    def set_action1_id_cmd(self, command):
        """
        Based on program or admin console set action1 id
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['action1id'] = int(command.get('value'),0)
        self.setDriver('GV8', self.data['action1id'])
        store_values(self)
        LOGGER.debug('Exit')
        

    def set_action1_type_cmd(self, command):
        """
        Based on program or admin console set action1 type
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['action1type'] = int(command.get('value'),0)
        self.setDriver('GV7', self.data['action1type'])
        store_values(self)
        LOGGER.debug('Exit')
        

    def set_action2_cmd(self, command):
        """
        Based on program or admin console set action2
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['action2'] = int(command.get('value',0))
        self.setDriver('GV9', self.data['action2'])
        store_values(self)
        LOGGER.debug('Exit')
        

    def set_action2_id_cmd(self, command):
        """
        Based on program or admin console set action2 id
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['action2id'] = int(command.get('value',0))
        self.setDriver('GV11', self.data['action2id'])
        store_values(self)
        LOGGER.debug('Exit')
        

    def set_action2_type_cmd(self, command):
        """
        Based on program or admin console set action2 type
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['action2type'] = int(command.get('value'),0)
        self.setDriver('GV10', self.data['action2type'])
        store_values(self)
        LOGGER.debug("Exit")
        

    def set_c_to_f_cmd(self, command):
        """
        Based on program or admin console set c_to_f flag
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['CtoF'] = int(command.get('value'),0)
        self.setDriver('GV13', self.data['CtoF'])
        self.reset_stats_cmd()
        store_values(self)
        LOGGER.debug("Exit")
        

    def set_f_to_c_cmd(self, command):
        """
        Based on program or admin console set f_to_c flag
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['FtoC'] = int(command.get('value'),0)
        self.setDriver('GV13', self.data['FtoC'])
        self.reset_stats_cmd()
        store_values(self)
        LOGGER.debug("Exit")


    def set_raw_to_prec_cmd(self, command):
        """
        Based on program or admin console set raw_to_prec flac
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['RtoPrec'] = int(command.get('value',0))
        self.setDriver('GV12', self.data['RtoPrec'])
        self.reset_stats_cmd()
        store_values(self)
        LOGGER.debug('Exit')
        

    def set_temp_cmd(self, command):
        """
        Set temperature based on actions set-up.
        """
        LOGGER.debug(f"{self.name}, {command}")
        value = float(command.get('value'))

        if command.get('cmd') == 'data':
            newValue = self._transform_value(value,
                                       self.data.get('RtoPrec', 0),
                                       self.data.get('CtoF', 0),
                                       self.data.get('FtoC', 0))
            if newValue == self.data['tempVal']:
                return
            else:
                value = newValue
        LOGGER.info(f"{self.name}, {command}")
        self.setDriver('GV2', 0.0)
        self.data['lastUpdateTime'] = time.time()
        self.data['prevVal'] = self.data['tempVal']
        self.setDriver('GV1', self.data['prevVal'])            
        self.data['tempVal'] = value
        self.setDriver('ST', self.data['tempVal'])
        self._check_high_low(self.data['tempVal'])
        store_values(self)


    def _transform_value(self, raw: int | float, r_to_prec: int | bool,
                         c_to_f: int | bool, f_to_c: int | bool) -> float | int:
        """
        Transform raw value according to flags.
        r_to_prec: if truthy, treat raw as tenths (divide by 10).
        c_to_f: if truthy, convert Celsius to Fahrenheit and round to 1 decimal.
        """
        val: float | int = raw
        if r_to_prec:
            val = raw / 10  # becomes float
        if c_to_f:
            val = round(val * 1.8 + 32, 1)  # keep one decimal when converting to F
        if f_to_c:
            val = round((val - 32) / 1.8, 1)  # keep one decimal when converting to C
        return val
        

    def _check_high_low(self, value):
        """
        Move high & low temp based on current temp.
        """
        LOGGER.info(f"{value}, low:{self.data['lowTemp']}, high:{self.data['highTemp']}")

        if value is None:
            return

        # Save previous high/low
        self.data['previousHigh'] = self.data['highTemp']
        self.data['previousLow'] = self.data['lowTemp']

        # Update highTemp if needed
        if self.data['highTemp'] is None or value > self.data['highTemp']:
            self.data['highTemp'] = value
            self.setDriver('GV3', value)

        # Update lowTemp if needed
        if self.data['lowTemp'] is None or value < self.data['lowTemp']:
            self.data['lowTemp'] = value
            self.setDriver('GV4', value)

        # Update average if both high and low are set
        if self.data['highTemp'] is not None and self.data['lowTemp'] is not None:
            self.data['prevAvgTemp'] = self.data['currentAvgTemp']
            self.data['currentAvgTemp'] = round((self.data['highTemp'] + self.data['lowTemp']) / 2, 1)
            self.setDriver('GV5', self.data['currentAvgTemp'])
        LOGGER.debug('Exit')


    def reset_stats_cmd(self, command=None):
        """
        Command to reset stats for the device.
        """
        LOGGER.info(f"{self.name}, {command}")
        self.data['lowTemp'] = None
        self.data['highTemp'] = None
        self.data['prevAvgTemp'] = None
        self.data['currentAvgTemp'] = None
        self.data['prevTemp'] = None
        self.data['tempVal'] = None
        # Reset drivers
        for driver in ['GV1', 'GV3', 'GV4', 'GV5', 'ST']:
            self.setDriver(driver, 0)
        self._reset_time()
        store_values(self)
        LOGGER.debug('Exit')
        

    def _reset_time(self):
        """
        Reset the last update time to now
        """
        self.data['lastUpdateTime'] = time.time()
        self.setDriver('GV2', 0.0)


    def query(self, command=None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        LOGGER.info(f"{self.name}, {command}")
        self.reportDrivers()
        LOGGER.debug('Exit')


    hint = '0x010b0100'
    # home, controller, scene controller
    # Hints See: https://github.com/UniversalDevicesInc/hints


    """
    This is an array of dictionary items containing the variable names(drivers)
    values and uoms(units of measure) from ISY. This is how ISY knows what kind
    of variable to display. Check the UOM's in the WSDK for a complete list.
    UOM 2 is boolean so the ISY will display 'True/False'
    """
    drivers = [
               {'driver': 'ST', 'value': 0, 'uom': 17},   #current
               {'driver': 'GV1', 'value': 0, 'uom': 17},  #previous
               {'driver': 'GV2', 'value': 0, 'uom': 45},  #update time
               {'driver': 'GV3', 'value': 0, 'uom': 17},  #high
               {'driver': 'GV4', 'value': 0, 'uom': 17},  #low
               {'driver': 'GV5', 'value': 0, 'uom': 17},  #avg high - low
               {'driver': 'GV6', 'value': 0, 'uom': 25},  #action1 type
               {'driver': 'GV7', 'value': 0, 'uom': 25},  #variable type
               {'driver': 'GV8', 'value': 0, 'uom': 56},  #variable id
               {'driver': 'GV9', 'value': 0, 'uom': 25},  #action 2
               {'driver': 'GV10', 'value': 0, 'uom': 25}, #variable type
               {'driver': 'GV11', 'value': 0, 'uom': 56}, #variable id
               {'driver': 'GV12', 'value': 0, 'uom': 25}, #r to p
               {'driver': 'GV13', 'value': 0, 'uom': 25}, #f to c         
              ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
        'setTemp': set_temp_cmd,
        'setAction1': set_action1_cmd,
        'setAction1id': set_action1_id_cmd,
        'setAction1type': set_action1_type_cmd,
        'setAction2': set_action2_cmd,
        'setAction2id': set_action2_id_cmd,
        'setAction2type': set_action2_type_cmd,
        'setCtoF': set_c_to_f_cmd,
        'setFtoC': set_f_to_c_cmd,
        'setRawToPrec': set_raw_to_prec_cmd,
        'resetStats': reset_stats_cmd,
                }


###############
# Sub-classes #
###############
class VirtualTempC(VirtualTemp):
    id = 'virtualtempc'

    """
    This is an array of dictionary items containing the variable names(drivers)
    values and uoms(units of measure) from ISY. This is how ISY knows what kind
    of variable to display. Check the UOM's in the WSDK for a complete list.
    UOM 2 is boolean so the ISY will display 'True/False'
    """
    drivers = [
               {'driver': 'ST', 'value': 0, 'uom': 4},   #current
               {'driver': 'GV1', 'value': 0, 'uom': 4},  #previous
               {'driver': 'GV2', 'value': 0, 'uom': 45},  #update time
               {'driver': 'GV3', 'value': 0, 'uom': 4},  #high
               {'driver': 'GV4', 'value': 0, 'uom': 4},  #low
               {'driver': 'GV5', 'value': 0, 'uom': 4},  #avg high - low
               {'driver': 'GV6', 'value': 0, 'uom': 25},  #action1 type
               {'driver': 'GV7', 'value': 0, 'uom': 25},  #variable type
               {'driver': 'GV8', 'value': 0, 'uom': 56},  #variable id
               {'driver': 'GV9', 'value': 0, 'uom': 25},  #action 2
               {'driver': 'GV10', 'value': 0, 'uom': 25}, #variable type
               {'driver': 'GV11', 'value': 0, 'uom': 56}, #variable id
               {'driver': 'GV12', 'value': 0, 'uom': 25}, #r to p
               {'driver': 'GV13', 'value': 0, 'uom': 25}, #f to c
              ]

