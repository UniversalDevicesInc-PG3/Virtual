# Version History

#### see udi-Virtual-pg3.py for current work

3.1.25 \
DONE add onOnly device \
DONE update generic project files 
 
3.1.24 \
DONE configuration based optional overide initial default 
 
3.1.23 \
DONE add onDelay, offDelay, toggle switch, update documentation \
DONE magic number scrub 
 
3.1.22 \
DONE generic/dimmer static/dynamic behaviour 
 
3.1.21 \
DONE generic/dimmer to model dimmer ST & OL \
DONE name & address check using poly interface \
DONE consistent use of poly versus polyglot \
DONE fix nagging error check in main() \
DONE controller discover refactor \
DONE add notice for ISY authorized error (was only in logs) 
 
3.1.20 \
DONE fix controller ST "status" on at start, off at stop / delete, "control" still heartbeat \
DONE garage send CMDs, motor, motion, obstruction ; get naming consistent \
DONE standardize startup sequence \
DONE rewrite checkParams, Discovery \
DONE add NumberOfNodes \
DONE switch/generic/dimmer/temp(R/C): nodes use polyglot persistence, delete old db files \
DONE swtich cmd TOGGLE add \
DONE consolidate temp, tempC, tempRC into one module \
DONE temp variable writing now with shortPoll (only upon change, considers precision) \
DONE refactor function naming \
DONE refactor garage, fix persistence, sse client \
DONE backfeed garage improvements to switch(done), generic(done), temperature() 

3.1.15 \
DONE generic, dimmer, change ST to OL, memory of level for DON, DFON/DFOF, command

3.1.14 \
DONE commands for switches, generic, dimmer, garage

3.1.13 \
DONE prevent direct poll from re-running \
DONE add notice if comms check fails \
DONE clean-up & debug

3.1.12 \
DONE rewrite sse events collection

3.1.11 \
DONE poll on longPoll, events sse \
DONE add motor, door position \
DONE update docs \
TODO Bonjour discovery is sometimes slow

3.1.10 \
DONE rewrite switch, dimmer, temp, tempc, garage \
DONE docs \
DONE move db files to subfolder

3.1.9 \
DONE Garage device read status directly from Ratgdo through ESPHome RESTapi \
DONE update docs for garage Ratgdo integration \
FIX  switch st uom from 2 True/False to 25 On/Off \

3.1.8 \
DONE Garage device sends commands directly to Ratgdo through ESPHome RESTapi \
DONE Bonjour discovery of Ratgdo garage device

3.1.7 \
DONE Small refactors \
DONE redo environment

3.1.6 \
FIX better solution to markdown2 issue

3.1.5 repair docs due to markdown2 issue

3.1.4 docs updated for garage

3.1.3 new device 'garage' door (update to/from variables option)  

3.1.2 ISY name changes based on updates to config / YAML / JSON

3.1.1 YAML file option for configuration  
      JSON option for web based configuration  
      Discover button to update based on config updates  

3.1.0 move version history out of README to own file  
      update docs  

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
