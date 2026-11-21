import json
import socket
import sys
import traceback

# Anything accidentally printed goes to stderr, never to stdout.
sys.stdout = sys.stderr

HOURS = 24
MAX_BATTERY = 100
MAX_SOLAR = 200
GEN_COST = 1.0
RECHARGE_SAME_HOUR = True


def num(value, default=0):
    """Return value if it is a real number, otherwise default."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return value


class Battery:
    def __init__(self, capacity):
        self.capacity = capacity
        self.level = 0

    def update(self, charge, discharge):
        self.level += charge - discharge
        self.level = max(0, min(self.capacity, self.level))


class Connection:
    """JSON messages over a socket, with or without newlines between them."""

    def __init__(self, host, port):
        self.client = socket.create_connection((host, port))
        self.buf = ""
        self.decoder = json.JSONDecoder()

    def receive(self):
        """Return the next message as a dict, or None if the server closed."""
        while True:
            text = self.buf.lstrip()
            if text:
                try:
                    msg, end = self.decoder.raw_decode(text)
                    self.buf = text[end:]
                    return msg
                except json.JSONDecodeError:
                    pass  # incomplete message, read more
            chunk = self.client.recv(65536)
            if not chunk:
                return None
            self.buf += chunk.decode("utf-8")

    def send(self, allocation):
        self.client.sendall((json.dumps(allocation) + "\n").encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.client.close()


class Controller:
    def __init__(self):
        self.battery = Battery(MAX_BATTERY)

    def decide(self, data, hour):
        """Never raises: on any problem, send a plain grid-only reply."""
        try:
            return self._decide(data, hour)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return self.safe_reply(data)

    def safe_reply(self, data):
        event = str(data.get("random_event", "none")) if isinstance(data, dict) else "none"
        grid_ok = "grid_failure" not in event
        loads = (data.get("loads") if isinstance(data, dict) else None) or []
        buildings = []
        for b in loads:
            load = num(b.get("load")) if isinstance(b, dict) else 0
            buildings.append({"solar": 0, "battery": 0,
                              "grid": load if grid_ok else 0})
        return {"generator": 0, "buildings": buildings}

    def _decide(self, data, hour):
        event = str(data.get("random_event", "none"))
        price = num(data.get("grid_price"), 0)
        loads = [
            {"load": num(b.get("load")), "type": b.get("type")}
            for b in (data.get("loads") or [])
        ]
        allocation = {
            "generator": 0,
            "buildings": []
        }
        # check if there is a random event
        solar_ok = "cloudy_weather" not in event
        gen_ok = "generator_failure" not in event
        batt_ok = "battery_failure" not in event
        grid_ok = "grid_failure" not in event

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
            discharge = max(0, min(level, residual_total))

        charge = 0
        if can_charge:
            kept = level - discharge if RECHARGE_SAME_HOUR else level
            charge = max(0, self.battery.capacity - kept)
        return discharge, charge

    def assign_battery_and_grid(self, solar, residual, discharge, grid_ok):
        """Split what solar couldn't cover between the battery and the grid."""
        used = [0] * len(residual)
        left = discharge
        for i in sorted(range(len(residual)), key=lambda k: residual[k]):
            used[i] = min(residual[i], left)
            left -= used[i]
        return [{"solar": solar[i], "battery": used[i],
                 "grid": residual[i] - used[i] if grid_ok else 0}
                for i in range(len(residual))]


controller = Controller()
with Connection("localhost", 8800) as connection:
    for hour in range(HOURS):
        data = connection.receive()
        if data is None:
            break
        print(hour, json.dumps(data), file=sys.stderr)
        connection.send(controller.decide(data, hour))