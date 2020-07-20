# Virtual Device Nodeserver
### A nodeserver for Universal Devices Isy

With this nodeserver you can create virtual switches, dimmers or temperature devices to be used in various applications.

The virtual switch and dimmer devices store their data in their variables, both value and init. You can add a virtual switch to a scene and that switch can be polled to determine if the scene is on or off.

The virtual temperature device allows you to extract temperature information from a node into a variable then display that as a device that can be put into a folder for other devices or apps.

![Virtual Node](https://github.com/markv58/github.io/blob/master/VirtualNode.png)
A simple program captures current temperature data from the ecobee nodeserver and displays that information as an individual device. By ungrouping the devices you could have a folder with only temperature information rather than searching through variables or multiple tabs.

Farenheit can be converted and displayed as Celsius and vice versa. 


### Updates

1.0.12 Bug fixes

1.0.11 Updated Temerature node to mirror options in the Temperature C node. Update Profile and restart the Admin Console after the update and restart.

1.0.10 Fix bug with Set Current resetting statistics.

1.0.9 Major re-working of the Temperature C node. The node will pull data from any variable, state or integer, value or init and push the same. Programs are no longer needed for input. All data and settings in the node are saved on a regular basis for retrieval if the nodeserver is restarted. This is a test update to check for bugs before migrating the methods into other nodes.

1.0.8 Updated the Temp node, added Highest, Lowest, Since Last Update and Convert Raw to Prec to mirror the TempC node. Update Profile and restart AC to see changes. Changed code for TempC node so a restart does not effect Highest and Lowest values.

1.0.7 Updated the Temp C node with added Highest and Lowest temps and a Since Last Update tracker.

1.0.6 Fixed a bug, worked on Temp nodes conversions to properly transfer current temp vals to previous after conversions and disallow repeat conversions. TempC node will not convert from raw if FtoC has been performed already. No node structure changes, programs will not be affected.

1.0.5 Fixed code that could stop Conv Raw to Prec

1.0.4 F to C and C to F conversions, Temp nodes send data to their state variables, previous value stored. Ditching the Dimmer node for Generic node, Dimmers move there.

1.0.3 Implemented a better work around for the celsius raw data conversion. Updated icons for nodes.

1.0.2 Added celsius temp node with raw data conversion when needed. Update Profile and restart Admin Console.

1.0.1 Prec bug fix, allows variable prec to be above 0. Update Profile and restart Admin Console.

1.0.0 Initial version
