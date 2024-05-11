# Version History

## see udi-Virtual-pg3.py for current work

3.0.1 fix get value from variable for Temperature devices

3.0.0 Add Control functionality to Switch device  
      Refactor plugin to modern PG3 template.

1.2.3 Bug fix.

1.2.2 Unlinked Switch and Generic/Dimmer from variable,
data and parameter storage to .db for retrieval on restart. Hints for Switch,
Generic/Dimmer added.
Brighten and Dim commands added to the Generic/Dimmer node.
Please Update Profile and restart the Admin Console.
No changes to the Temperature nodes.

1.2.1 Fixed bug that allowed value updates where the value had not changed.
When changing F to C, C to F or R to P the statistics are automatically reset.

1.2.0 Temperature Nodes - Cleaned up the code and removed logger details that
were no longer needed. Added a time stamp in the log that indicates when a variable
was last updated. The values are now only updated if there was a change since the
last check, the Since Last Update counter will continue to increase until an actual
change occurs.

1.0.20 Replaced parsing regex to more reliably and consistently pull in negative
numbers

1.0.19 Fixed possible error with parseDelay setting when setting float,  
set default parseDelay to .1

1.0.18 Fix the regex to parse negative numbers.

1.0.17 Logger info for debugging added.

1.0.16 Bug fix, error handling added

1.0.15 Bug fix

1.0.14 Cleaned up some code, fixed a bug that could corrupt the data, added Delete
Node db to clear bad data, similar to Reset Statistics but more thourogh. Any parameter
changes are saved immediately. This should be the last major update to the Temperature
Nodes pending the discovry of any other bugs. Update Profile and restart AC.

1.0.13 Corrected some problems with data storage and parameter display. Added drivers
to present current settings. Requires Update Profile.

1.0.12 Bug fixes. Update Profile and restart the AC for Temperature node changes.

1.0.11 Updated Temerature node to mirror options in the Temperature C node. Update
Profile and restart the Admin Console after the update and restart.

1.0.10 Fix bug with Set Current resetting statistics.

1.0.9 Major re-working of the Temperature C node. The node will pull data from any
variable, state or integer, value or init and push the same. Programs are no longer
needed for input. All data and settings in the node are saved on a regular basis
for retrieval if the nodeserver is restarted. This is a test update to check for
bugs before migrating the methods into other nodes.

1.0.8 Updated the Temp node, added Highest, Lowest, Since Last Update and Convert
Raw to Prec to mirror the TempC node. Update Profile and restart AC to see changes.
Changed code for TempC node so a restart does not effect Highest and Lowest values.

1.0.7 Updated the Temp C node with added Highest and Lowest temps and a Since Last
Update tracker.

1.0.6 Fixed a bug, worked on Temp nodes conversions to properly transfer current
temp vals to previous after conversions and disallow repeat conversions. TempC node
will not convert from raw if FtoC has been performed already. No node structure
changes, programs will not be affected.

1.0.5 Fixed code that could stop Conv Raw to Prec

1.0.4 F to C and C to F conversions, Temp nodes send data to their state variables,
previous value stored. Ditching the Dimmer node for Generic node, Dimmers move there.

1.0.3 Implemented a better work around for the celsius raw data conversion. Updated
icons for nodes.

1.0.2 Added celsius temp node with raw data conversion when needed. Update Profile
and restart Admin Console.

1.0.1 Prec bug fix, allows variable prec to be above 0. Update Profile and restart
Admin Console.

1.0.0 Initial version
