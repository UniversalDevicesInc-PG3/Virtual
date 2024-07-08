# Virtual Device Nodeserver

## Plugin for Universal Devices Isy

The Virtual plugin is one way to take data from external sources and in turn use
these nodes of data more effectively.  The nodes become devices from which status
and control are possible in programs & as an included device in scenes.  It produces
a cleaner display in the AC and Remote tools.

With this nodeserver you can create virtual switches or other devices
 for use in user programs.

Devices store their status in a .db for retrieval on a restart.

## Example Virtual Device Uses

- I use REST to switch a virtual device from an 8266 device
    - My Awning controller & heartbeat
- from Alexa I switch a virtual device
    - The status of my daughter's goodnight routine
- inserted as part of scenes or programs for both status and control
- provide scene status if you make them part of a scene
- consolidate data with the temp devices, & I am looking to add a garage device

## Switches

You can add a virtual switch to a scene and that ON/OFF switch is polled to
determine if the scene is ON or OFF. Programs can read / set as any device. 

## Dimmer or Generic

Percent of ON for a dimmer or generic.

## Temperature

The virtual temperature device allows you to extract temperature information
using a program or from a variable.  This is then displayed as a device

### Pulling a temperature value from a variable

**Options:**

- Raw data converted to prec 1.
- Farenheit converted and displayed as Celsius and vice versa.
- Data Pushed to another variable.

## Garage

A virtual garage device for a garage door.  Can be populated from a Ratgdo device,
from Home Assistant, or from variables.  Commands can go to a Ratgdo device, or
variables, which can then be picked up by Home Assistant.

## Configuration

see [POLYGLOT_CONFIG.md][config]

## Version History

see [VersionHistory.md][versions]

[versions]: VersionHistory.md
[config]: POLYGLOT_CONFIG.md
