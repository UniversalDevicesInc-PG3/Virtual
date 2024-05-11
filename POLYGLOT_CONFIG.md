# Virtual Device Controller

**NEED TO SELECT ISY ACCESS AND SAVE IN CONFIGURATION**  
Required for variable write access

**After updating you MAY need to restart your Admin Console**

## Device Types

- switch
- dimmer
- generic
- temperature     ... *Farenheit units*
- temperaturec    ... *Celcius units*
- temperaturecr   ... *raw no-units*

## Example Configuration

````md
Key (var ID)    Value (device type)
  78              switch
  79              dimmer
  80              generic
  82              temperature  
  85              temperaturec
  100             temperaturecr
````

Key can be any positive unique integer, duplicate Keys will create ghost nodes  

## Conversions Available

- Raw Celsius data
- F to C  (TempC node convert Raw data before F to C)  
- C to F  
- Single precision conversion from Raw
