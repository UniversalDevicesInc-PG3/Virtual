#!/usr/bin/env bash
# EISY/FreeBSD: pip may exit non-zero (resolver noise, pip version check)
# even when packages installed. PG3 treats non-zero install.sh as HTTP 500.
pip3 install -r requirements.txt --user --disable-pip-version-check
python3 -c "import udi_interface, yaml, aiohttp"
