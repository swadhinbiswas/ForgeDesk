import re

with open("src/lib.rs", "r") as f:
    text = f.read()

events = []
depth = 0
for i, line in enumerate(text.split("\n")):
    if "event_loop.run" in line:
        print(f"run found at {i+1}")
        
    if "impl" in line:
        print(f"impl at {i+1}: {line}")
