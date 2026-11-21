import socket
import json
import sys

HOURS = 24
battery = 0
pending = 0
buf = ""
decoder = json.JSONDecoder()


def read_msg(client):
    global buf
    while True:
        text = buf.lstrip()
        if text:
            try:
                obj, end = decoder.raw_decode(text)
                buf = text[end:]
                return obj
            except json.JSONDecodeError:
                pass
        chunk = client.recv(65536)
        if not chunk:
            return None
        buf += chunk.decode("utf-8")


with socket.create_connection(("localhost", 8800)) as client:
    for hour in range(HOURS):
        msg = read_msg(client)
        if msg is None:
            break
        print(hour, json.dumps(msg), file=sys.stderr)

        event = str(msg.get("random_event", "none"))
        grid_ok = "grid_failure" not in event
        solar_left = 0 if "cloudy_weather" in event else 200
        battery_ok = "battery_failure" not in event
        gen_ok = "generator_failure" not in event

        battery += pending
        pending = 0

        buildings = []
        for b in msg["loads"]:
            load = b["load"]
            solar = bat = grid = 0
            if grid_ok:
                grid = load
            else:
                if b["type"] != "lecture_hall":
                    solar = min(load, solar_left)
                    solar_left -= solar
                if battery_ok:
                    bat = min(load - solar, battery)
                    battery -= bat
            buildings.append({"solar": solar, "battery": bat, "grid": grid})

        gen = (100 - battery) if (gen_ok and battery_ok) else 0
        pending = gen

        reply = {"buildings": buildings, "generator": gen}
        client.sendall((json.dumps(reply) + "\n").encode("utf-8"))