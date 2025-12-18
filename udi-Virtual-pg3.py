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
from udi_interface import LOGGER, Interface

# nodes
from nodes import Controller

VERSION = "3.1.25"
"""
3.1.25
DONE add onOnly device
DONE update generic project files
DONE Controller comments, refactor checkParams
DONE change hints for temperature devices
DONE testing added

3.1.24
DONE configuration based optional overide initial default

3.1.23
DONE add onDelay, offDelay, toggle switch, update documentation
DONE magic number scrub

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


previous updates:
see versionHistory.md

"""

if __name__ == "__main__":
    polyglot = None
    try:
        """
        Instantiates the Interface to Polyglot.

        * Optionally pass list of class names
          - PG2 had the controller node name here
        """
        polyglot = Interface([])
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
        control = Controller(
            polyglot, "controller", "controller", "Virtual Device Controller"
        )

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
        LOGGER.error(f"Excption: {err}", exc_info=True)
    sys.exit(0)
