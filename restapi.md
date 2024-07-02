# Ratgdo-ESPHome Restapi

http://ratgdov25i-fad8fd.local

[[https://esphome.io/web-api/index.html][ESPHome Rest api]]

Button: ON/OFF
/binary_sensor/button

Client ID: number
/number/client_id
/set?value=24

Closing duration: number in range
/number/closing_duration
/set?value=24

Door: state: OPEN/CLOSED current_operation: OPENING/CLOSING/IDLE value: number position: number
/cover/door
/open
/close
/stop
/toggle
/set?position=0&tilt=0

Dry contact close:
/binary_sensor/dry_contact_close

Dry contact light:
/binary_sensor/dry_contact_light

Dry contact open:
/binary_sensor/dry_contact_open

Firmware Version: date number
???

Learn: ON/OFF
/switch/learn
/turn_on
/turn_off
/toggle

Light: ON/OFF
/light/light
/turn_on
/turn_off
/toggle

Lock remotes: LOCKED/UNLOCKED
/lock/lock_remotes
/lock
/unlock

Motion: ON/OFF
/binary_sensor/motion

Motor: ON/OFF
/binary_sensor/motor

Obstruction: ON/OFF
/binary_sensor/obstruction

Opening duration: time in seconds
/number/opening_duration
/set?value=24

Openings: number
/sensor/openings

Paired devices: number
/sensor/paired_devices

Query openings: button
/button/query_openings/press

Query status: button
/button/query_status/press

Restart: button
/button/restart/press

Rolling code counter: number
/number/rolling_code_counter
/set?value=24

Safe mode boot: button
/button/safe_mode_boot/press

Sync: button
/button/sync/press

Toggle door: button
/button/toggle_door/press

