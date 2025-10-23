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

## Switch

You can add a virtual switch to a scene and that ON/OFF switch is polled to
determine if the scene is ON or OFF. Programs can read / set as any device.

## onOnly Switch

Same as Switch but will only send DON command.  Useful in a scene to make DON/DOF
device DON only.  Will recive and status both ON and OFF.

## Dimmer or Generic

Percent of ON for a dimmer or generic.

## offDelay switch

Usage: \
    Replaces programs simulating timers used to switch scene off after delay time.\
    For example you turn on a light scene which you want to turn off after x-seconds.\
    The scene is switched on by a switch/program & fires offDelay, after
    x-seconds the scene is turned off. \

if Switched: \
    On (DON) when ST Off/On, ST status set to TIMER, CMD (DON), after DUR (DOF).\
    On (DON) during ST TIMER, reset the time, CMD (DOF) sent AFTER DUR seconds. \
    Off during TIMER, ST status changes to Off, CMD DOF sent immediately. \
    Fast On / Off mirror On / Off

Set: \
  delay (DUR) to delay seconds for switch, after CMD DON wait to send DOF. \
  range 0 - 99999 seconds which gives you more than 24 hrs. \
  if 0, mostly acts like a regular switch. \

Status: \
  Off(0), On(1), TIMER(2) \
  When plugin is stopped, if ST is TIMER, ST will be set to On for persistence. \
  Using Thread timers to fire switch, so for now I am not showing a status of
  how long left in the timer. Trying to keep a low overhead. \
  
## onDelay switch

Usage: \
    Replaces programs simulating timers and scene trigger for transition
    from one scene to another. For example you turn on a high level light
    scene which you want to transition to a normal level later. \
    Use two scenes, one High, one Normal/Low, switch on High for x-seconds,
    after delay then transition to Normal/Low. \
    High scene:  onDelay is Responder, set delay (DUR) to x-seconds \
    Normal/Low scene: on Delay is Controller in Normal scene, sending
    appropriate commands to each device. \

If switched: \
    On (DON) when ST Off/On, ST status set to TIMER, CMD (DON) after DUR delay. \
    On (DON) during ST TIMER, reset the time, no CMD sent until DUR complete. \
    Off (DOF) during TIMER, ignore until TIMER done. \
    Off (DOF) when ST Off/On,  ST status set to Off, send DOF immediately. \
    Fast On (DFON) behaviour is equivalent to on (DON). \
    Fast Off (DFOF) anytime to set ST status to off, CMD (DFOF) sent immediately;
    this method to cancel is used to allow use and control in a scene. \

Set: \
  delay (DUR) to seconds switch will, after receiving DON, wait to CMD DON. \
  range 0 - 99999 seconds which gives you more than 24 hrs. \
  if 0, mostly acts like a regular switch. \

Status: \
  Off(0), On(1), TIMER(2) \
  When plugin is stopped, if ST is TIMER, ST set to On for persistence. \
  Using Thread timers to fire switch, so for now I am not showing a status of
  how long left in the timer.  Trying to keep a low overhead. \
  
## toggle oscillator

Usage: \
    Replaces anywhere you want a scene to oscillate On/OFF.  It does not need
    to be balanced, so allows you to be Off for long periods and On for a
    short one.  Can of course be used to trigger programs on a regular
    interval as well.  An obvious example is blinking Christmas lights.
    Another would be for attention getting or security flashing.
    Firing a program at regular intervals can be pretty useful.

If switched: \
    On (DON) when ST Off/On, ST status set to onTimer, CMD (DON) immediately. \
    On (DON) when ST onTimer/offTimer, timer reset,  CMD (DON) immediately. \
    Off (DOF) when ST onTimer/offTimer, no effect. \
    Off (DOF) when ST Off/On, ST status set to Off, CMD (DOF) immediately. \
    Fast On (DFON) same as On (DON). \
    Fast Off (DFOF) all ST, ST set to Off, CMD (DFOF), cancel further
    oscillations; this method to cancel is used to allow use and control in
    a scene. \

Set: \
  onDur (DUR) to seconds switch will, after sending DON, wait to CMD DOF. \
  offDur (GV0) to seconds switch will, after sending DOF, wait to send DON. \
  range 1 - 99999 seconds which gives you more than 24 hrs for each On / Off \
  if either timer <= 0, it will be reset to 1 \
  
Status: \
  Off(0), On(1), onTimer(2), offTimer(3)  \
  When plugin is stopped, if ST is onTimer, ST set to On for persistence. \
  When plugin is stopped, if ST is offTimer, ST set to Off for persistence. \
  Using Thread timers to fire switch, so for now I am not showing a status of
  how long left in the timers. Trying to keep a low overhead. \
  
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
