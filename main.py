import json
import socket

with socket.create_connection(("localhost", 8800), timeout=5) as client:
    stream = client.makefile("rwb")
    line = stream.readline()
    data = json.loads(line.decode("utf-8"))

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
        "buildings" : {}
    }
    #check if there is a random event
    solar_ok = event != "cloudy_weather"
    gen_ok = event != "generator_failure"
    batt_ok = event != "battery_failure"
    grid_ok = event != "grid_failure"

    total_load = 0
    for i in loads:
        total_load += i["load"]

    #check if there is enough solar power to meet the load
    if solar_ok and total_load <= MAX_SOLAR:
        for i in loads:
            allocation["buildings"] = {"solar" : i["load"], "battery" : 0, "gride" : 0}
        if battery < MAX_BATTERY:
            allocation["generator"] = MAX_BATTERY - battery
            battery = MAX_BATTERY
    return allocation;

