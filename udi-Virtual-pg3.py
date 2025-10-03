#!/usr/bin/env python3
"""
This is a Plugin/NodeServer for Polyglot v3 written in Python3
modified from v3 template version by (Bob Paauwe) bpaauwe@yahoo.com
Refactored and improved from a PG2 plugin originally by Mark Vittes and
updated to PG3 by Bob Paauwe
It is a plugin for making virtual devices for use on Polyglot for EISY/Polisy

udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

"""

# std libraries
import sys

# external libraries
import udi_interface

LOGGER = udi_interface.LOGGER

VERSION = '3.1.23'
"""
3.1.23
DONE ondelay switch
DONE switch / ondelay / generic magic number removal

3.1.22
DONE generic/dimmer static/dynamic behaviour

3.1.21
DONE generic/dimmer to model dimmer ST & OL
DONE name & address check using poly interface
DONE consistent use of poly versus polyglot
DONE fix nagging error check in main()
DONE controller discover refactor
DONE add notice for ISY authorized error (was only in logs)

3.1.20
DONE fix controller ST "status" on at start, off at stop / delete, "control" still heartbeat
DONE garage send CMDs, motor, motion, obstruction ; get naming consistent
DONE standardize startup sequence
DONE rewrite checkParams, Discovery
DONE add NumberOfNodes
DONE switch/generic/dimmer/temp(R/C): nodes use polyglot persistence, delete old db files
DONE swtich cmd TOGGLE add
DONE consolidate temp, tempC, tempRC into one module
DONE temp variable writing now with shortPoll (only upon change, considers precision)
DONE refactor function naming
DONE refactor garage, fix persistence, sse client
DONE backfeed garage improvements to switch(done), generic(done), temperature()

3.1.15
DONE generic, dimmer, change ST to OL, memory of level for DON, DFON/DFOF, command

3.1.14
DONE commands for switches, generic, dimmer, garage

3.1.13
DONE prevent direct poll from re-running
DONE add notice if comms check fails
DONE clean-up & debug

3.1.12
DONE rewrite sse events collection

3.1.11
DONE poll on longPoll, events sse
DONE add motor, door position
DONE update docs
NOTE Bonjour discovery is sometimes slow

3.1.10
DONE rewrite switch, dimmer, temp, tempc, garage
DONE docs
DONE move db files to subfolder

3.1.9
DONE Garage device read status directly from Ratgdo through ESPHome RESTapi
DONE update docs for garage Ratgdo integration
DONE  switch st uom from 2 True/False to 25 On/Off

3.1.8
DONE Garage device sends commands directly to Ratgdo through ESPHome RESTapi
DONE Bonjour discovery of Ratgdo garage device

3.1.7
DONE Small refactors
DONE redo environment

3.1.6
DONE better solution to markdown2 issue

3.1.5
DONE repair docs due to markdown2 issue

3.1.4
DONE docs updated for garage

3.1.3
DONE: new device 'garage' door (update to/from variables option)  

3.1.2
DONE: ISY name changes based on updates to config / YAML / JSON

3.1.1
DONE: YAML file option for configuration  
DONE: JSON option for web based configuration  
DONE: Discover button to update based on config updates  

3.1.0
DONE: move version history out of README to own file
DONE: update docs  

3.0.1
DONE fix get value from variable

3.0.0
DONE add control ability to contact device
DONE refactored to modern template

previous updates:
see versionHistory.md

"""

from nodes import Controller

if __name__ == "__main__":
    polyglot = None
    try:
        """
        Instantiates the Interface to Polyglot.

        * Optionally pass list of class names
          - PG2 had the controller node name here
        """
        polyglot = udi_interface.Interface([])
        """
        Starts MQTT and connects to Polyglot.
        """
        polyglot.start(VERSION)
        polyglot.updateProfile()

        """
        Creates the Controller Node and passes in the Interface, the node's
        parent address, node's address, and name/title

        * address, parent address, and name/title are new for Polyglot
          version 3
        * use 'controller' for both parent and address and PG3 will be able
          to automatically update node server status
        """
        control = Controller(polyglot, 'controller', 'controller', 'Virtual Device Controller')

        """
        Sits around and does nothing forever, keeping your program running.

        * runForever() moved from controller class to interface class in
          Polyglot version 3
        """
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.warning("Received interrupt or exit...")
        """
        Catch SIGTERM or Control-C and exit cleanly.
        """
        if polyglot is not None:
            polyglot.stop()
    except Exception as err:
        LOGGER.error(f'Excption: {err}', exc_info=True)
    sys.exit(0)
