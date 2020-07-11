# Virtual Device Nodeserver
### A nodeserver for Universal Devices Isy

With this nodeserver you can create virtual switches, dimmers or temperature devices to be used in various applications.

The virtual switch and dimmer devices store their data in their variables, both value and init. You can add a virtual switch to a scene and that switch can be polled to determine if the scene is on or off.

The virtual temperature device allows you to extract temperature information from a node into a variable then display that as a device that can be put into a folder for other devices or apps.

![Virtual Node](https://github.com/markv58/github.io/blob/master/VirtualNode.png)
A simple program captures current temperature data from the ecobee nodeserver and displays that information as an individual device. By ungrouping the devices you could have a folder with only temperature information rather than searching through variables or multiple tabs.


### Updates

1.0.4 F to C and C to F conversions, Temp nodes send data to their state variables, previous value stored. Ditching the Dimmer node for Generic node, Dimmers move there.

1.0.3 Implemented a better work around for the celsius raw data conversion. Updated icons for nodes.

1.0.2 Added celsius temp node with raw data conversion when needed. Update Profile and restart Admin Console.

1.0.1 Prec bug fix, allows variable prec to be above 0. Update Profile and restart Admin Console.

1.0.0 Initial version
