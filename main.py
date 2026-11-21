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

def decide(data){
    global battery
    event = data["random_event"]
    forecast = data["forecast"]
    price = data["grid_price"]
    loads = data["loads"] 

    #check if there is a random event
    solar_ok = event != "cloudy_weather"
    gen_ok = event != "generator_failure"
    batt_ok = event != "battery_failure"
    grid_ok = event != "grid_failure"


}