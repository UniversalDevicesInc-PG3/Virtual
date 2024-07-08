# Virtual Device Controller

**NEED TO SELECT ISY ACCESS AND SAVE IN CONFIGURATION**  
Required for variable write access

**After updating you MAY need to restart your Admin Console**

## Device Types

- switch
- dimmer
- generic
- temperature     ... *Farenheit units*
- temperaturec    ... *Celcius units*
- temperaturecr   ... *raw no-units*
- garage

## Example Configurations

Three options for configuration.  **They can be mixed & matched**

### Standard Configuration

Key can be any positive **unique** integer,
duplicate Keys will create ghost nodes

````md
Key (var ID)    Value (device type)
  78              switch
  79              dimmer
  80              generic
  82              temperature
  85              temperaturec
  100             temperaturecr
````

### JSON Configuration

id is optional in the JSON string

```md
Key (var ID)    Value (device type)
  78              {"id": "10", "type": "switch", "name": "switch 10"}
  79              {"type": "dimmer", "name": "main dimmer"}
  80              {"type": "generic", "name": "raw device"}
  82              {"type": "temperature", "name": "lake temperature"}
  85              {"id": "85", "type": "temperaturec", "name": "garden temp"}
  100             {"type": "temperaturecr", "name": "raw temp"}
  200             {"type": "garage", "name": "garage door", "ratgdo": True}
```

### YAML Configuration

File name without path is within the node directory.
Careful this file is deleted with the node.
Better to use path and store within admin home directory.
Make sure file permissions are available to node.

```md
Key (var ID)    Value (device type)
  devFile         exampleConfigFile.yaml
  devFile         /home/admin/virtualdevice.yaml
```

## Conversions Available

- Raw Celsius data
- F to C  (TempC node convert Raw data before F to C)  
- C to F  
- Single precision conversion from Raw

## Discovery

- Discover button will add or remove nodes not in one of the configuration methods.

## Variable pull / push

- temperature devices have selection of variables available in the IoX node display
- garage device have selection in the configuration (JSON or YAML)
- note: **may add this feature to temperature devices if demand is there**

- YAML example below from the exampleConfigFile.yaml in package directory

```yaml
devices:

- id: 10
  type:  "switch"
  name: "TestSwitch"
- id: 20
  type:  "temperature"
  name: "TestTemp"
- id: 30
  type:  "dimmer"
  name: "TestDimmer 92"
- id: 40
  type:  "garage"
  name:  "Ratgdo"
  ratgdo: True # will find the Ratgdo device (slower startup)
  # ratgdo: False # no Ratgdo device
  # ratgdo: 10.0.1.41 # IP address (faster startup)
  
  # below are optional & only individually used if defined
  # each name refers to feature
  # type {1: state var, 2:state init, 3:integer var, 4:integer init}
  # Id number of variable
  # if ratgdo is True, or IP defined then only writes to these
  # if ratgdo is False then reads and writes to these
  lightT: 1
  lightId: 3
  doorT: 1
  doorId: 61
  commandT: 1
  commandId: 129
  motionT: 1
  motionId: 130
  lockT: 1
  lockId: 133
  obstructT: 1
  obstructId: 131
```
