#!/usr/bin/env python3
"""Generate a realistic asciinema cast for dong demo."""
import json, subprocess, textwrap

# 1. Capture real output
result = subprocess.run(
    ['python3', '-m', 'dong_ai.cli', 'demo'],
    capture_output=True, text=True, cwd='/home/administrator/dong-ai', timeout=10
)
real_output = result.stdout + result.stderr

# 2. Build the cast file
cast = []
t = 0.0

# Header
header = {
    "version": 2,
    "width": 80,
    "height": 28,
    "timestamp": 1780772000,
    "idle_time_limit": 2,
    "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"}
}

# 3. Simulate typing "dong demo"
prompt = "\r\n\u001b[1m\u001b[38;5;33madministrator@dong\u001b[0m:\u001b[1m\u001b[38;5;141m~\u001b[0m$ "
typed_cmd = "dong demo"

# Show prompt
cast.append([t, "o", f"{prompt}"])
t += 0.3

# Type each character
for ch in typed_cmd:
    t += 0.08
    cast.append([t, "o", ch])

# Press enter
t += 0.3
cast.append([t, "o", "\r\n"])

# 4. Feed the output in sections with pauses
sections = [
    ("\n", 0.1),
    # Header box
    ("\u001b[1m╭─ Dong AI — Cross-Project Graph Memory Demo\u001b[0m ───────────────────╮\r\n", 0.4),
    ("\u001b[2m┊  No API key needed. No network calls. Demo data is local.\u001b[0m\r\n", 0.6),
    ("\u001b[2m┊  This is exactly how dong graph list / view works for real.\u001b[0m\r\n", 0.4),
    ("╰────────────────────────────────────────────────────────────────────────╯\r\n\r\n", 0.5),
    # Step 1
    ("\u001b[1mStep 1: What does the graph remember?\u001b[0m\r\n", 0.5),
    ("\u001b[2m    Two projects indexed (not stored as conversation history).\u001b[0m\r\n", 0.6),
    ("\r\n", 0.2),
]

# Capture output between sections by splitting at known markers
# I'll send the output line by line with pauses
lines = real_output.split('\n')
# Filter out empty leading lines
while lines and lines[0].strip() == '':
    lines.pop(0)

for i, line in enumerate(lines):
    # Add a slight pause at section boundaries
    if 'Step ' in line or 'Graph Memory' in line or '┌' in line or '└' in line:
        t += 0.8  # longer pause at section headers
    elif line.strip().startswith('function') or line.strip().startswith('class'):
        t += 0.04  # fast scroll for dense data
    elif line.strip().startswith('·') or line.strip().startswith('│') or line.strip().startswith('fn'):
        t += 0.03
    else:
        t += 0.1

    # Add the line
    sep = '\r\n' if i < len(lines) - 1 else ''
    cast.append([t, "o", f"{line}{sep}"])

# Final pause
t += 0.5

# 5. Show prompt again
cast.append([t, "o", f"\r\n{prompt}"])

# 6. Write the cast file
cast_path = '/tmp/dong-demo-real.cast'
with open(cast_path, 'w') as f:
    f.write(json.dumps(header) + '\n')
    for event in cast:
        f.write(json.dumps(event) + '\n')

print(f"Cast file: {cast_path}")
print(f"Duration: {t:.1f}s")
print(f"Events: {len(cast)}")
