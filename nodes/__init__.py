"""Node classes used by the Python template Node Server."""

from .VirtualSwitch import VirtualSwitch
from .VirtualonOnly import VirtualonOnly
from .VirtualTemp import VirtualTemp
from .VirtualTemp import VirtualTempC
from .VirtualGeneric import VirtualGeneric
from .VirtualGarage import VirtualGarage
from .VirtualonDelay import VirtualonDelay
from .VirtualoffDelay import VirtualoffDelay
from .VirtualToggle import VirtualToggle
from .Controller import Controller

__all__ = [
    "VirtualSwitch",
    "VirtualonOnly",
    "VirtualTemp",
    "VirtualTempC",
    "VirtualGeneric",
    "VirtualGarage",
    "VirtualonDelay",
    "VirtualoffDelay",
    "VirtualToggle",
    "Controller",
]
