import json
import socket

MAX_BATTERY = 100
MAX_SOLAR = 200
battery = 0
hour = 0

def decide(data):
    global battery
    event = data["random_event"]
    forecast = data["forecast"]
    price = data["grid_price"]
    loads = data["loads"]
    allocation = {
        "generator":0,
        "buildings" : []
    }
    #check if there is a random event
    solar_ok = event != "cloudy_weather"
    gen_ok = event != "generator_failure"
    batt_ok = event != "battery_failure"
    grid_ok = event != "grid_failure"

    total_load = 0
    for i in loads:
        total_load += i["load"]

    total_solar_load = 0
    for i in loads:
        if(i["type"] != "lecture_hall"):
            total_solar_load += i["load"]

    #baseline: buy everything from the grid
    for i in loads:
        allocation["buildings"].append({"solar" : 0, "battery" : 0, "grid" : i["load"]})
    return allocation

with socket.create_connection(("localhost", 8800), timeout=5) as client:
    stream = client.makefile("rwb")
    while hour < 24:
        line = stream.readline()
        if not line:
            break
        data = json.loads(line.decode("utf-8"))
        allocation = decide(data)
        stream.write((json.dumps(allocation) + "\n").encode("utf-8"))
        stream.flush()
        hour += 1