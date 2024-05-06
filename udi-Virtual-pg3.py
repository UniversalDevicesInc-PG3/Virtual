#!/usr/bin/env python3
"""
This is a Plugin/NodeServer for Polyglot v3 written in Python3
modified from v3 template version by (Bob Paauwe) bpaauwe@yahoo.com
Refactored and improved from a PG2 plugin originally by Mark Vittes and
updated to PG3 by Bob Paauwe
It is a plugin for making virtual devices for use on Polyglot for EISY/Polisy

udi-Virtual-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

"""

import udi_interface
import sys

LOGGER = udi_interface.LOGGER

VERSION = '3.0.0'
"""
3.0.0
DONE add control ability to contact device
TODO refactored to modern template
TODO add garage door aggregate device

"""

from nodes import Controller

if __name__ == "__main__":
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
        polyglot.stop()
    except Exception as err:
        LOGGER.error('Excption: {0}'.format(err), exc_info=True)
    sys.exit(0)
