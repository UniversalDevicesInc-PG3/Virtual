
# Virtual Device Controller

### After updating always Update Profile from Controller Page and restart the Admin Console

Please enter the following to allow this nodeserver to access your ISY:

    Key             Value
    isy              xxx.xxx.xxx.xxx:port
    user             username
    password         password
    
    
There are 3 kinds of virtual devices, switch, dimmer and temperature. You do not need to have a state variable for each entry.

Temerature will be displayed as farenheit unless a 'c' is added. 

Raw celsius data can be converted with an extra step in a program. F to C and C to F conversions are available. In the TempC node convert Raw data before the F to C conversion if nessecary otherwise there will be no Raw conversion.

    Key (var ID)    Value (device type)
    78              switch
    79              dimmer or generic
    82              temperature     (will be displayed as farenheit)
    85              temperaturec or temperaturecr   (will be displayed as celsius) (the r can be used to note raw data if you prefer)
    
Each Key must be unique, duplicate Keys will create ghost nodes.

Existing nodes are not effected by updates.
