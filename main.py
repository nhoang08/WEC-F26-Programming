import json
import socket

HOURS = 24
MAX_BATTERY = 100
MAX_SOLAR = 200
GEN_COST = 1.0              #TODO: confirm against the spec
RECHARGE_SAME_HOUR = True   #can the generator refill the battery in the same hour?
hour = 0


class Battery:
    def __init__(self, capacity):
        self.capacity = capacity
        self.level = 0

    def update(self, charge, discharge):
        self.level += charge - discharge


class Controller:
    def __init__(self):
        self.battery = Battery(MAX_BATTERY)

    def decide(self, data, hour):
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
        discharge, charge = self.plan_battery(hour, price, sum(residual), batt_ok, gen_ok, grid_ok)
        allocation["buildings"] = self.assign_battery_and_grid(solar, residual, discharge, grid_ok)
        allocation["generator"] = charge
        self.battery.update(charge, discharge)
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

    def plan_battery(self, hour, price, residual_total, batt_ok, gen_ok, grid_ok):
        """Return (discharge, charge). `charge` is the generator's output."""
        if not batt_ok:
            return 0, 0
        level = self.battery.level
        last_hour = hour == HOURS - 1
        can_charge = gen_ok and not last_hour

        discharge = 0
        if not grid_ok or last_hour or (can_charge and RECHARGE_SAME_HOUR and price > GEN_COST):
            discharge = min(level, residual_total)

        charge = 0
        if can_charge:
            kept = level - discharge if RECHARGE_SAME_HOUR else level
            charge = self.battery.capacity - kept
        return discharge, charge

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
    while hour < HOURS:
        line = stream.readline()
        if not line:
            break
        data = json.loads(line.decode("utf-8"))
        allocation = controller.decide(data, hour)
        stream.write((json.dumps(allocation) + "\n").encode("utf-8"))
        stream.flush()
        hour += 1