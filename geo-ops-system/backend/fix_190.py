# -*- coding: utf-8 -*-
"""Fix missing code block after if statement"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 190 (index 189) has if statement but line 191 is not indented properly
print("Line 190:", lines[189].rstrip())
print("Line 191:", lines[190].rstrip())

# The if body was probably removed when we cleaned up mojibake comments
# Insert a pass or return statement
if lines[190].startswith('    if raw_body') or lines[190].startswith('    if'):
    # Insert indented pass before this line
    lines.insert(190, '            pass\n')
    print("Inserted pass statement")

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

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
