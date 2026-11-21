import json
import socket

with socket.create_connection(("localhost", 8800), timeout=5) as client:
    stream = client.makefile("rwb")
    line = stream.readline()
    data = json.loads(line.decode("utf-8"))

