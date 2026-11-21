import socket
import json

battery = 0
pending = 0

with socket.create_connection(("localhost", 8800), timeout=30) as client:
    stream = client.makefile("rwb")

    while True:
        line = stream.readline()
        if not line:
            break

        line_str = line.decode("utf-8").strip()
        if not line_str:
            continue

        try:
            msg = json.loads(line_str)
        except json.JSONDecodeError:
            continue

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
        stream.write((json.dumps(reply) + "\n").encode("utf-8"))
        stream.flush()