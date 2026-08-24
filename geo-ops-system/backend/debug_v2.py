# -*- coding: utf-8 -*-
"""Complete rewrite of app.py fixing all issues"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

# Read as raw bytes
with open(filepath, 'rb') as f:
    data = f.read()

# Check for BOM
if data[:3] == b'\xef\xbb\xbf':
    print("WARNING: BOM found at start!")
    data = data[3:]

# Check lines around 158
lines = data.split(b'\n')
print(f"Line 156 (def): {lines[155][:80]}")
print(f"Line 157 (docstring): {lines[156][:100]}")
print(f"Line 158 (n=): {lines[157][:80]}")

# Check for \r (carriage return)
for i in range(155, 160):
    if b'\r' in lines[i]:
        print(f"WARNING: Line {i+1} has \\r!")
        
# Show exact bytes at the error position (around '24h')
docstring_line = lines[156]
idx = docstring_line.find(b'24h')
if idx >= 0:
    print(f"\nBytes around '24h': {docstring_line[idx-5:idx+10].hex()}")
    print(f"Chars: {[chr(b) if 32 <= b < 127 else f'0x{b:02x}' for b in docstring_line[idx-5:idx+10]]}")
