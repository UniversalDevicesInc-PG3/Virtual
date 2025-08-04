import json
import requests

# ratdgo constants

RATGDO = "ratgdov25i-fad8fd"

BUTTON = "/binary_sensor/button"
LIGHT = "/light/light"
DOOR = "/cover/door"
LOCK_REMOTES = "/lock/lock_remotes"
MOTOR = "/binary_sensor/motor"
MOTION = "/binary_sensor/motion"
MOTOR = "/binary_sensor/motor"
OBSTRUCT = "/binary_sensor/obstruction"
TRIGGER = "/button/toggle_door/press"
EVENTS = "/events"

LOCK = "/lock"
UNLOCK = "/unlock"

OPEN = "/open"
CLOSE = "/close"
STOP = "/stop"

TURN_ON = "/turn_on"
TURN_OFF = "/turn_off"
TOGGLE = "/toggle"

url = f"http://{RATGDO}{EVENTS}"
ratgdo_event = []
try:
    print(f"GET: {url}")
    s = requests.Session()
    e = {}
    with s.get(url,headers=None, stream=True, timeout=3) as gateway_sse:
        for val in gateway_sse.iter_lines():
            dval = val.decode('utf-8')
            print(f"raw:{dval}")
            if val:                            
                if e:
                    try:
                        i = dict(event = e, data = dval.replace('data: ',''))
                    except:
                        i = dict(event = e, data = 'error')
                    ratgdo_event.append(i)
                    e = None
                else:
                    if 'event: ' in dval:
                        e = dval.replace('event: ','')
                        continue
                    else:
                        i = (dict(event = dval, data = None))
                        ratgdo_event.append(i)                    
except requests.exceptions.Timeout:
    print(f"see timeout error")
except requests.exceptions.RequestException as e:
    print(f"sse error: {e}")
except (KeyboardInterrupt, SystemExit):
    print(f"keyboard interupt")

for val in ratgdo_event:
    print(f"event: {val['event']}")
    print(f"data: {val['data']}")
    print()

# return ratgdo_event (not self)
# call with self.ratgdo_event = self.sseEvent()

