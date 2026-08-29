#!/usr/bin/env python3
"""Virtual Device NodeServer for Polyglot V3 on EISY/Polisy.

Virtual devices for use with Polyglot on EISY/Polisy.

(C) 2025 Stephen Jenkins

Version history: see CHANGELOG.md
"""

import sys

import udi_interface

from nodes.Controller import Controller

VERSION = "3.1.29"

if __name__ == "__main__":
    polyglot = None
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start(VERSION)
        Controller(polyglot, "controller", "controller", "Virtual Device Controller")
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        udi_interface.LOGGER.warning("Received interrupt or exit...")
        if polyglot is not None:
            polyglot.stop()
    except Exception:
        udi_interface.LOGGER.error("Fatal error starting plugin", exc_info=True)
    sys.exit(0)
