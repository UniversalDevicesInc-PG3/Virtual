
# Virtual Device Controller

### After updating always Update Profile from Controller Page and restart the Admin Console

Please enter the following to allow this nodeserver to access your ISY:

    Key             Value
    isy              xxx.xxx.xxx.xxx:port
    user             username
    password         password
    
    
There are 3 kinds of virtual devices, switch, dimmer and temperature. You will need to have a state variable for each entry and note the id number.

Temerature will be displayed as farenheit unless a 'c' is added. Raw data will be converted if 'cr' is added.

    Key (var ID)    Value (device type)
    78              switch
    79              dimmer
    82              temperature
    85              temperaturec    (will be displayed as celsius)
    86              temperaturecr   (will be displayed as corrected celsius when raw data is supplied)
    
    
    
