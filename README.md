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

- I use REST to switch a virtual device from an ESP8266 device
- My Awning controller & heartbeat
- from Alexa I switch a virtual device
- The status of my daughter's goodnight routine
- inserted as part of scenes or programs for both status and control
- provide scene status if you make them part of a scene
- consolidate data with the temp devices, & I am looking to add a garage device
- delay devices can be used in place of timers

## Switches

You can add a virtual switch to a scene and that ON/OFF switch is polled to
determine if the scene is ON or OFF. Programs can read / set as any device.

## Dimmer or Generic

Percent of ON for a dimmer or generic.

## onDelay switch

If turned on when OFF or ON, ST status changes to TIMER, DON after delay seconds.
if turned on during TIMER, it will reset the TIMER.
If turned off during TIMER, it will ignore until TIMER done.
If turned off after TIMER it will change ST status to Off, and send DOF.
If turned fast off (DFOF) anytime it will change ST status to off, and send DFOF.
Ex usage: replaces timers and scene setting for changing from one scene to another.
Use two scenes, High the other Normal, intending High to be switched on for x-seconds,
then revert to Normal.  onDelay is responder in High and Controller in Normal.

## offDelay switch

If turned on when OFF or ON, ST to TIMER, then sends DON, then DOF after delay seconds.
if turned on during TIMER, it will reset the TIMER.
If turned off during TIMER it will change ST status to Off, and send DOF immediately.
Ex: replaces program timers used as a scene controller, for lights off after x seconds.
The scene is switched on by a switch or program & fires offDelay, after
x-seconds the scene is turned off.

## toggle

With parameters of timeOn & timeOFF, this device can be used to regularly
cycle a program or scene.
Once started it will be stopped with a DFOF as opposed to DOF, this is so as
to not cancel the device in a scene.
Ex: Obvious example is Christmas lights; another would be to fire a program at
regular intervals.

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
