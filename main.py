import json
import socket

MAX_BATTERY = 100
MAX_SOLAR = 200
hour = 0


class Controller:
    def __init__(self):
        self.battery = 0

    def decide(self, data):
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

        solar = self.assign_solar(loads, solar_ok)
        residual = [b["load"] - s for b, s in zip(loads, solar)]
        allocation["buildings"] = self.assign_battery_and_grid(solar, residual, 0, grid_ok)
        return allocation

    def assign_solar(self, loads, solar_ok):
        """Solar is free: fill non-lecture-hall buildings, smallest load first."""
        solar = [0] * len(loads)
        left = MAX_SOLAR if solar_ok else 0
        for i in sorted(range(len(loads)), key=lambda k: loads[k]["load"]):
            if loads[i]["type"] != "lecture_hall":
                solar[i] = min(loads[i]["load"], left)
                left -= solar[i]
        return solar

    def assign_battery_and_grid(self, solar, residual, discharge, grid_ok):
        """Split what solar couldn't cover between the battery and the grid."""
        used = [0] * len(residual)
        left = discharge
        for i in sorted(range(len(residual)), key=lambda k: residual[k]):
            used[i] = min(residual[i], left)
            left -= used[i]
        return [{"solar" : solar[i], "battery" : used[i],
                 "grid" : residual[i] - used[i] if grid_ok else 0}
                for i in range(len(residual))]

controller = Controller()
with socket.create_connection(("localhost", 8800), timeout=5) as client:
    stream = client.makefile("rwb")
    while hour < 24:
        line = stream.readline()
        if not line:
            break
        data = json.loads(line.decode("utf-8"))
        allocation = controller.decide(data)
        stream.write((json.dumps(allocation) + "\n").encode("utf-8"))
        stream.flush()
        hour += 1