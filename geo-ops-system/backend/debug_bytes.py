# -*- coding: utf-8 -*-
"""Debug: show raw bytes around line 158"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'rb') as f:
    data = f.read()

# Split by newline and find line 158
lines = data.split(b'\n')
print(f"Total lines (by bytes): {len(lines)}")
print(f"\nLine 157 (0-indexed, should be line 158):")
line = lines[157]
print(f"Length: {len(line)}")
print(f"Raw hex: {line[:100].hex()}")
print(f"As text: {line[:100]}")

# Check for any non-printable or weird characters
for i, b in enumerate(line):
    if b < 0x20 and b not in (0x09, 0x0a, 0x0d):  # Not tab, LF, CR
        print(f"Found control char at pos {i}: 0x{b:02x}")
    if b > 0x7e and b < 0xc0:  # Invalid UTF-8 continuation without start
        print(f"Invalid byte at pos {i}: 0x{b:02x}")
