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

URL_EVENTS = 'http://{g}/events'
gateway = RATGDO

try:
    if False:
        with open('/Users/stephenjenkins/Projects/txt.json', 'r') as file:
            data = file.read().splitlines()
    else:
        sse = []
        url = URL_EVENTS.format(g=gateway)
        for n in range(10):
            try:
                print(f"GET: {url}")
                s = requests.Session()
                state = False
                with s.get(url,headers=None, stream=True, timeout=3) as gateway_sse:
                    for val in gateway_sse.iter_lines():
                        dval = val.decode('utf-8')
                        print(f"dval:{dval}")                        
                        if val:                            
                            if 'event: state' in dval:
                                print(f"{dval} == True")
                                state = True
                                continue
                            if state:
                                state = False
                                i = dict(data = dval.replace('data: ',''))
                                print(f"!! == {i}")
                                try:
                                    sse.append(json.loads(i['data']))
                                    print(f"success:{sse}")
                                except:
                                    print(f"noadd:{val}")
                                    pass
            except requests.exceptions.Timeout:
                print(f"see timeout error")
            except requests.exceptions.RequestException as e:
                print(f"sse error: {e}")

        print(sse)
        print("Done.")
except (KeyboardInterrupt, SystemExit):
    print(f"keyboard interupt")



