# Virtual Device Controller
<!-- markdownlint-disable-file MD036 MD007 -->
See [README for manual][readme]

**NEED TO SELECT ISY ACCESS AND SAVE IN CONFIGURATION**
Required for variable write access

**After updating you MAY need to restart your Admin Console**

## Device Types & OPTIONAL config parameters with {range limits}

- switch
    - switch      {0=Off, 1=On}
- ononly
	- switch      {0=Off, 1=On}
- dimmer, generic
    - status      {0 - 100}
    - onlevel     {10 - 100}
    - onleveltype {0=STATIC, 1=DYNAMIC}
- ondelay
    - switch      {0=Off, 1=On}
    - delay       {0-99999}
- offdelay
    - switch      {0=Off, 1=On}
    - delay       {0-99999}
- toggle
    - switch      {0=Off, 1=On}
    - ondelay       {0-99999}
    - offdelay      {0-99999}
- temperature     ... *Farenheit units*
    - action1     {0=push-to-variable, 1=pull-from-variable}
    - action1type {1=val state, 2=init state, 3=val integer, 4=init integer}
    - action1id   {1-999)
    - action2     {0=push-to-variable, 1=pull-from-variable}
    - action2type {1=val state, 2=init state, 3=val integer, 4=init integer}
    - action2id   {1-999)
    - RtoPrec     {0=False, 1=True}
    - CtoF        {0=False, 1=True}
    - FtoC        {0=False, 1=True}
- temperaturec    ... *Celcius units*
    - same as temperature
- temperaturecr   ... *raw no-units DEPRECIATED AS SAME AS CELCIUS*
    - same as temperature
- garage
    - ratgdo      {True, False, ip address, local name}
    - lightT      {1=val state, 2=init state, 3=val integer, 4=init integer}
    - lightId     {1-999}
    - doorT       {1=val state, 2=init state, 3=val integer, 4=init integer}
    - doorId      {1-999}
    - dcommandT   {1=val state, 2=init state, 3=val integer, 4=init integer}
    − dcommandId  {1=val state, 2=init state, 3=val integer, 4=init integer}
    – motionT     {1=val state, 2=init state, 3=val integer, 4=init integer}
    – motionId    {1-999}
    – lockT       {1=val state, 2=init state, 3=val integer, 4=init integer}
    – lockId      {1-999}
    – obstructT   {1=val state, 2=init state, 3=val integer, 4=init integer}
    – obstructId  {1-999}
    – motorT      {1=val state, 2=init state, 3=val integer, 4=init integer}
    – motorId     {1-999}
    – positionT   {1=val state, 2=init state, 3=val integer, 4=init integer}
    – positionId  {1-999}

## Example Configurations

Three options for configuration.  **They can be mixed & matched**

### Standard Configuration

Key can be any positive **unique** integer,
duplicate Keys will create ghost nodes

````md
Key (var ID)    Value (device type)
  78          switch
  79          ononly
  80          dimmer
  81          generic
  82          ondelay
  83          offdelay
  84          toggle
  85          temperature
  86          temperaturec
  100         temperaturecr
````

### JSON Configuration

id is optional in the JSON string as well as the OPTIONAL configs like “delay”

```md
Key (var ID)    Value (device type)
  78          {"id": "10", "type": "switch", "name": "switch 10"}
  79          {"id": "12", "type": "ononly", "name": "switch 12"}
  80          {"type": "dimmer", "name": "main dimmer"}
  81          {"type": "generic", "name": "raw device"}
  82          {"type": "ondelay", "name": "living lt onDelay", "delay": 600}
  83          {"type": "offdelay", "name": "office lt offDelay", "delay": 60}
  84          {"type": "toggle", "name": "LTtoggle", "ondelay": 60, "offdelay": 5}
  85          {"type": "temperature", "name": "lake temperature"}
  86          {"id": "85", "type": "temperaturec", "name": "garden temp"}
  100         {"type": "temperaturecr", "name": "raw temp"}
  200         {"type": "garage", "name": "garage door", "ratgdo": "True"}
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

- YAML example below from the exampleConfigFile.yaml in package directory

```yaml
devices:

- id: 10
  type:  "switch"
  name: "TestSwitch"
- id: 15
  type:  "ononly"
  name: "TestonOnly"
- id: 20
  type:  "temperature"
  name: "TestTemp"
- id: 30
  type:  "dimmer"
  name: "TestDimmer 92"
- id: 40
  type:  "ondelay"
  name: "Living lt onDelay"
  delay: 600
- id: 50
  type:  "offdelay"
  name: "Office lt offDelay"
  delay: 60
- id: 60
  type:  "toggle"
  name: "Christmas lights toggle"
  ondelay: 6000
  ofdelay: 600
- id: 70
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
  motorT: 1
  motorId: 132
  positionT: 1
  positionId: 134
  motionT: 1
  motionId: 130
  lockT: 1
  lockId: 133
  obstructT: 1
  obstructId: 131
```

[readme]: https://github.com/sejgit/Virtual/blob/master/README.md
