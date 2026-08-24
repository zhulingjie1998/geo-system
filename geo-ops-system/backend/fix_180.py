# -*- coding: utf-8 -*-
"""Fix remaining f-string at line 180"""

import re

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 180 (index 179)
print("Line 180:")
print(repr(lines[179]))

# This line has mojibake in the f-string with unbalanced braces
# Replace with English version
lines[179] = '                    return jsonify({"error": f"Too many login attempts, try again in {remaining_min} min"}), 429\n'

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("Fixed!")

# Verify syntax
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("✓ SYNTAX OK!")
except SyntaxError as e:
    print("✗ Error at line", e.lineno, ":", e.msg)
    for j in range(max(0, e.lineno-3), min(e.lineno+3, len(content.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(marker, j+1, ":", content.split('\n')[j][:100])
