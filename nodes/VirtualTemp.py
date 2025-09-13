"""
udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

VirtualTemp class
"""
# std libraries
import time, shelve
from typing import Any, Dict, Iterable, Optional, Tuple
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# external libraries
import udi_interface

# constants
LOGGER = udi_interface.LOGGER
ISY = udi_interface.ISY
TYPELIST = ['/set/2/',  #1
            '/init/2/', #2
            '/set/1/',  #3
            'init/1/'   #4
           ]

# Dispatch map to select the correct tag AND GETLIST index based on var_type.
# Using a dictionary for dispatch is more extensible and readable than a long if/elif chain.
_VARIABLE_TYPE_MAP = {
    # Key: ISY var_type, Value: (GETLIST_INDEX, XML_TAG)
    '1': ('/2/', 'val'),
    '2': ('/2/', 'init'),
    '3': ('/1/', 'val'),
    '4': ('/1/', 'init'),
}

@dataclass(frozen=True)
class FieldSpec:
    driver: Optional[str]  # e.g., "GV1" or None if not pushed to a driver
    default: Any           # per-field default

# Single source of truth for field names, driver codes, and defaults
FIELDS: dict[str, FieldSpec] = {
    "tempVal":         FieldSpec(driver="ST",  default=0.0), # 'ST'  : current temperature        
    "prevVal":         FieldSpec(driver="GV1", default=0.0), # 'GV1' : previous temperature
    "lastUpdateTime":  FieldSpec(driver="GV2", default=0.0), # 'GV2' : time since last update
    "highTemp":        FieldSpec(driver="GV3", default=None), # 'GV3' : high temperature     
    "lowTemp":         FieldSpec(driver="GV4", default=None), # 'GV4' : low temperature            
    "previousHigh":    FieldSpec(driver=None,  default=None), # bucket for previous high
    "previousLow":     FieldSpec(driver=None,  default=None), # bucket for previous low
    "prevAvgTemp":     FieldSpec(driver=None,  default=0.0), # bucket for previous avg
    "currentAvgTemp":  FieldSpec(driver="GV5", default=0.0), # 'GV5' : average of  high to low 
    "action1":         FieldSpec(driver="GV6", default=0), # 'GV6' : action1 push to or pull from variable   
    "action1type":     FieldSpec(driver="GV7", default=0), # 'GV7' : variable type integer or state
    "action1id":       FieldSpec(driver="GV8", default=0), # 'GV8' : variable id
    "action2":         FieldSpec(driver="GV9", default=0), # 'GV9' : action 2 push to or pull from variable  
    "action2type":     FieldSpec(driver="GV10", default=0),# 'GV10': variable type 2 int or state, curr or init
    "action2id":       FieldSpec(driver="GV11", default=0),# 'GV11': variable id 2   
    "RtoPrec":         FieldSpec(driver="GV12", default=0),# 'GV12': raw to precision
    "CtoF":            FieldSpec(driver="GV13", default=0),# 'GV13': Fahrenheit to Celsius
    "FtoC":            FieldSpec(driver="GV13", default=0),# 'GV13': Celsius to Fahrenheit
}

def _transform_value(raw: int | float, r_to_prec: int | bool, c_to_f: int | bool, f_to_c: int | bool) -> float | int:
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


class VirtualTemp(udi_interface.Node):
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
    
    def __init__(self, polyglot, primary, address, name, *, default_ovr: Optional[Dict[str, Any]] = None):
        """ Sent by the Controller class node.
        :param polyglot: Reference to the Interface class
        :param primary: Parent address
        :param address: This nodes address
        :param name: This nodes name

        class variables:
        self.prevVal, tempVal storage of last, current temperature value
        self.lastUpdateTime timestamp
        self.highTemp, lowTemp range of high temp, set to None on init
         self.previousHigh, previousLow storage of previous range
        self.prevAvgTemp, currentAvgTemp storage of averages
        self.action1, action2 none, push, pull
        self.action1id, action1id id of variable,  0=None, 1 - 400
        self.action1type, action2type  State var or init, Int var or init, 1 - 4
        self.RtoPrec Raw to precision conversion
        self.CtoF Celsius to Fahrenheit conversion

        subscribes:
        START: used to create/check/load DB file
        POLL: shortPoll for updates
        """
        super().__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.primary = primary
        self.controller = polyglot.getNode(self.primary)
        self.address = address
        self.name = name

        self._init_defaults(default_ovr)

        self.poly.subscribe(self.poly.START, self.start, address)
        

    def start(self):
        """
        Start node and retrieve persistent data
        """
        LOGGER.info(f'start: switch:{self.name}')

        # wait for controller start ready
        self.controller.ready_event.wait()

        # get persistent data from polyglot or depreciated: old db file, then delete db file
        self.load_persistent_data()

        self.isy = ISY(self.poly)
        self.lastUpdateTime = time.time()
        self.setDriver('GV2', 0.0)
        self.poly.subscribe(self.poly.POLL, self.poll)
        

    def _init_defaults(self, default_ovr: Optional[Dict[str, Any]] = None) -> None:
        """
        Build per-instance defaults from FIELDS, then overlay optional overrides
        """
        self._defaults: Dict[str, Any] = {field: spec.default for field, spec in FIELDS.items()}
        if default_ovr:
            for k, v in default_ovr.items():
                if k in FIELDS:
                    self._defaults[k] = v
                else:
                    LOGGER.warning("Ignoring unknown default override key: %s", k)
                    

    def poll(self, flag):
        """
        POLL event subscription above
        """
        if 'shortPoll' in flag and self.controller.ready_event:
            LOGGER.debug(f"shortPoll {self.name}")
            self.update()
            

    def update(self):
        """
        Called by shortPoll to update last update and action list.
        """
        _sinceLastUpdate = round(((time.time() - self.lastUpdateTime) / 60), 1)
        if _sinceLastUpdate < 1440:
                self.setDriver('GV2', _sinceLastUpdate)
        else:
                self.setDriver('GV2', 1440)
        if self.action1 == 2:
                self.pull_from_id(self.action1type, self.action1id)
        if self.action2 == 2:
                self.pull_from_id(self.action2type, self.action2id)


    def _apply_state(self, src: Dict[str, Any]) -> None:
        """
        Apply values from src; fall back to per-instance defaults
        """
        for field in FIELDS.keys():
            setattr(self, field, src.get(field, self._defaults[field]))
            

    def _push_drivers(self) -> None:
        """
        Push only fields that have a driver mapping
        """
        for field, spec in FIELDS.items():
            if spec.driver is not None:
                self.setDriver(spec.driver, getattr(self, field))
                

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
        try:
            with shelve.open(str(base), flag="r") as s:
                existing_data = s.get(key)
        except Exception as ex:
            LOGGER.error("[%s] Error opening/reading old shelve DB: %s", self.name, ex)
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
        # Ensure defaults are initialized (safe if called multiple times)
        if not hasattr(self, "_defaults"):
            self._init_defaults()

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
        data_to_store = {field: getattr(self, field) for field in FIELDS.keys()}
        self.controller.Data[self.name] = data_to_store
        LOGGER.debug("Values stored for %s: %s", self.name, data_to_store)


    def set_action1(self, command):
        """
        Based on program or admin console set action1
        """
        self.action1 = int(command.get('value'))
        self.setDriver('GV6', self.action1)
        self.store_values()
        

    def set_action1_id(self, command):
        """
        Based on program or admin console set action1 id
        """
        self.action1id = int(command.get('value'))
        self.setDriver('GV8', self.action1id)
        self.store_values()
        

    def set_action1_type(self, command):
        """
        Based on program or admin console set action1 type
        """
        self.action1type = int(command.get('value'))
        self.setDriver('GV7', self.action1type)
        self.store_values()
        

    def set_action2(self, command):
        """
        Based on program or admin console set action2
        """
        self.action2 = int(command.get('value'))
        self.setDriver('GV9', self.action2)
        self.store_values()
        

    def set_action2_id(self, command):
        """
        Based on program or admin console set action2 id
        """
        self.action2id = int(command.get('value'))
        self.setDriver('GV11', self.action2id)
        self.store_values()
        

    def set_action2_type(self, command):
        """
        Based on program or admin console set action2 type
        """
        self.action2type = int(command.get('value'))
        self.setDriver('GV10', self.action2type)
        self.store_values()
        

    def set_c_to_f(self, command):
        """
        Based on program or admin console set c_to_f flag
        """
        self.CtoF = int(command.get('value'))
        self.setDriver('GV13', self.CtoF)
        self.reset_stats()
        self.store_values()
        

    def set_f_to_c(self, command):
        """
        Based on program or admin console set f_to_c flag
        """
        self.FtoC = int(command.get('value'))
        self.setDriver('GV13', self.FtoC)
        self.reset_stats()
        self.store_values()


    def set_raw_to_prec(self, command):
        """
        Based on program or admin console set raw_to_prec flac
        """
        self.RtoPrec = int(command.get('value'))
        self.setDriver('GV12', self.RtoPrec)
        self.reset_stats()
        self.store_values()
        

    def push_the_value(self, type_segment: str | int, var_id: int | str) -> None:
        """
        Push self.tempVal to an ISY variable.
        type_segment can be any of:
          - '/set/2/', 'set/2', 'set/2/', '/init/1', etc. (as provided by TYPELIST)
        var_id should be a positive integer.
        """
        # Validate var_id
        try:
            vid = int(var_id)
        except (TypeError, ValueError):
            LOGGER.error("Invalid var_id: %r", var_id)
            return
        if vid <= 0:
            LOGGER.error("var_id must be positive, got: %s", vid)
            return

        # Normalize and validate type_segment
        # Expect tokens like ['set', '2'] or ['init', '1']
        seg = str(type_segment or "").strip().strip("/")
        tokens = [t for t in seg.split("/") if t]
        if len(tokens) < 2:
            LOGGER.error("Invalid type segment (expected 'set/2' or 'init/1'): %r", type_segment)
            return

        op, vtype = tokens[-2], tokens[-1]
        if op not in ("set", "init") or vtype not in ("1", "2"):
            LOGGER.error("Invalid op/type in segment: op=%r type=%r (segment=%r)", op, vtype, type_segment)
            return

        # Validate value to push
        value = getattr(self, "tempVal", None)
        if value is None:
            LOGGER.error("tempVal is None; nothing to push for var_id=%s", vid)
            return

        # Format value safely as a string; leave semantics unchanged
        # Note: if you know vtype == '1' must be integer, consider: value_str = str(int(round(value)))
        value_str = f"{value:.1f}" if isinstance(value, float) else str(value)

        # Build canonical path without double slashes
        path = f"/rest/vars/{op}/{vtype}/{vid}/{value_str}"
        LOGGER.info("Pushing to ISY %s", path)

        try:
            resp = self.isy.cmd(path)
            # Optional: log response for diagnostics
            rtxt = resp.decode("utf-8", errors="replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
            LOGGER.debug("ISY push response for %s: %s", path, rtxt)
        except Exception as exc:
            LOGGER.exception("ISY push failed for %s: %s", path, exc)


    def pull_from_id(self, var_type: int | str, var_id: int | str) -> None:
        """
        Pull a variable from ISY using GETLIST-style path segments,
        parse the XML, and update state if the transformed value changed.
        """
        try:
            vid = int(var_id)
        except (TypeError, ValueError):
            LOGGER.error("Invalid var_id: %r", var_id)
            return

        if vid == 0:
            LOGGER.debug("var_id is 0; skipping pull.")
            return

        vtype_str = str(var_type).strip()

        # Use dictionary dispatch to get both the GETLIST index and the XML tag.
        try:
            getlist_segment, tag_to_find = _VARIABLE_TYPE_MAP[vtype_str]
        except KeyError:
            LOGGER.error("Invalid or unsupported var_type: %r", vtype_str)
            return

        path = f"/rest/vars/get{getlist_segment}{vid}"

        # Fetch
        try:
            resp = self.isy.cmd(path)
        except Exception as exc:
            LOGGER.exception("ISY command failed for %s: %s", path, exc)
            return

        text = resp.decode("utf-8", errors="replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
        LOGGER.info("ISY response for %s: %s", path, text)

        # Parse XML based on the determined tag
        val_str: Optional[str] = None
        try:
            root = ET.fromstring(text)
            val_str = root.findtext(f".//{tag_to_find}")
            if val_str is None:
                LOGGER.error("No <%s> element in ISY response for %s", tag_to_find, path)
                return
            new_raw = int(val_str.strip())
        except ET.ParseError as exc:
            LOGGER.exception("Failed to parse XML for %s: %s", path, exc)
            return
        except ValueError as exc:
            LOGGER.exception("Value in <%s> is not an int for %s (val=%r): %s", tag_to_find, path, val_str, exc)
            return

        # Compute the transformed display value based on current flags
        new_display = _transform_value(new_raw,
                                      getattr(self, "RtoPrec", 0),
                                      getattr(self, "CtoF", 0),
                                      getattr(self, "FtoC", 0))

        # Update only if changed versus the currently stored transformed value
        current = getattr(self, "tempVal", None)
        if current != new_display:
            self.set_temp({"cmd": "data", "value": new_raw})
            LOGGER.info("Updated value for var_type=%s var_id=%s from %r to %r", vtype_str, vid, current, new_display)
        else:
            LOGGER.debug("No change for var_type=%s var_id=%s (value %r)", vtype_str, vid, new_display)
            

    def set_temp(self, command):
        """
        Set temperature based on actions set-up.
        """
        LOGGER.debug(command)
        self.setDriver('GV2', 0.0)
        self.lastUpdateTime = time.time()
        self.prevVal = self.tempVal
        self.setDriver('GV1', self.prevVal)
        self.tempVal = float(command.get('value'))

        if command.get('cmd') == 'data':
            self.tempVal = _transform_value(self.tempVal,
                                            getattr(self, "RtoPrec", 0),
                                            getattr(self, "CtoF", 0),
                                            getattr(self, "FtoC", 0))
            
        self.setDriver('ST', self.tempVal)
        self.check_high_low(self.tempVal)
        self.store_values()

        if self.action1 == 1:
            _type = TYPELIST[(self.action1type - 1)]
            self.push_the_value(_type, self.action1id)
            LOGGER.info('Action 1 Pushing')

        if self.action2 == 1:
            _type = TYPELIST[(self.action2type - 1)]
            self.push_the_value(_type, self.action2id)
            LOGGER.info('Action 2 Pushing')
            

    def check_high_low(self, value):
        """
        Move high & low temp based on current temp.
        """
        LOGGER.info(f"{value}, low:{self.lowTemp}, high:{self.highTemp}")

        if value is None:
            return

        # Save previous high/low
        self.previousHigh = self.highTemp
        self.previousLow = self.lowTemp

        # Update highTemp if needed
        if self.highTemp is None or value > self.highTemp:
            self.highTemp = value
            self.setDriver('GV3', value)

        # Update lowTemp if needed
        if self.lowTemp is None or value < self.lowTemp:
            self.lowTemp = value
            self.setDriver('GV4', value)

        # Update average if both high and low are set
        if self.highTemp is not None and self.lowTemp is not None:
            self.prevAvgTemp = self.currentAvgTemp
            self.currentAvgTemp = round((self.highTemp + self.lowTemp) / 2, 1)
            self.setDriver('GV5', self.currentAvgTemp)


    def reset_stats(self, command=None):
        """
        Command to reset stats for the device.
        """
        LOGGER.info(f'Resetting Stats: {command}')
        self.lowTemp = None
        self.highTemp = None
        self.prevAvgTemp = 0
        self.currentAvgTemp = 0
        self.prevTemp = None
        self.tempVal = None
        # Reset drivers
        for driver in ['GV1', 'GV3', 'GV4', 'GV5', 'ST']:
            self.setDriver(driver, 0)
        self.store_values()
        

    def query(self, command=None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        LOGGER.debug(command)
        self.reportDrivers()


    # Hints See: https://github.com/UniversalDevicesInc/hints
    #hint = [1,2,3,4]
    
    
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
        'setTemp': set_temp,
        'setAction1': set_action1,
        'setAction1id': set_action1_id,
        'setAction1type': set_action1_type,
        'setAction2': set_action2,
        'setAction2id': set_action2_id,
        'setAction2type': set_action2_type,
        'setCtoF': set_c_to_f,
        'setFtoC': set_f_to_c,
        'setRawToPrec': set_raw_to_prec,
        'resetStats': reset_stats,
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

