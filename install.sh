#!/usr/bin/env bash
# EISY/FreeBSD: pip may exit non-zero (resolver noise, pip version check)
# even when packages installed. PG3 treats non-zero install.sh as HTTP 500.
pip3 install -r requirements.txt --user --disable-pip-version-check
python3 -c "import udi_interface, yaml, aiohttp"

# Dynamic profiles: keep XML under profile.static/ but expose profile/ for installprofile.
# (Symlink avoids PG3 uploading a second copy while updateProfile() still finds nodedefs.xml.)
if [ -d profile ] && [ ! -L profile ]; then
  rm -rf profile.static
  mv profile profile.static
fi
if [ -d profile.static ] && [ ! -e profile ]; then
  ln -s profile.static profile
fi
