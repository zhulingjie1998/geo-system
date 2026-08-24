# -*- coding: utf-8 -*-
"""Revert and re-analyze"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Revert: remove the ) we added on line 120
if lines[119].strip() == ')':
    lines[119] = '\n'
    print("Reverted line 120")

# Now let's check what's before _PUBLIC_API_PREFIXES
print("\nLines 100-122:")
for i in range(99, min(122, len(lines))):
    marker = ""
    line = lines[i]
    # Check for any non-printable characters
    for j, ch in enumerate(line):
        if ord(ch) < 32 and ch not in '\t\n\r':
            marker += f" [CTRL 0x{ord(ch):02x} at pos {j}]"
    print(f"{i+1}:{marker} {line[:90].rstrip()}")

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

# Check with Python parser what it thinks is wrong
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"\n✗ Error: {e.msg} at line {e.lineno}")
    print(f"Text at error: {repr(content.split(chr(10))[e.lineno-1][:80])}")
