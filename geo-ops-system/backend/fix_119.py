# -*- coding: utf-8 -*-
"""Fix remaining issues around line 119-121"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 119 (index 118) - has mojibake in comment
print("Line 119:")
print(repr(lines[118]))

# Replace with clean comment
lines[118] = '    "/api/share/kb-review/",  # KB review share with token auth\n'

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
    print(f"✗ Error at line {e.lineno}: {e.msg}")
    error_lines = content.split('\n')[max(0, e.lineno-3):e.lineno+3]
    for j, ln in enumerate(error_lines):
        marker = ">>>" if j == (e.lineno - max(0, e.lineno-3) - 1) else "   "
        print(f"{marker} {e.lineno-2+j}: {ln[:100]}")
