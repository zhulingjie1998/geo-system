# -*- coding: utf-8 -*-
"""Fix line 123 - unterminated triple-quoted string"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 123 (index 122) has the problematic docstring
print("Line 123:")
print(repr(lines[122]))

# Replace with English to avoid encoding issues
lines[122] = '    """Global security headers: HSTS / clickjacking / MIME sniff / Referrer policy."""\n'

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("\nFixed!")

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
    for i, line in enumerate(error_lines):
        marker = ">>>" if i == (e.lineno - max(0, e.lineno-3) - 1) else "   "
        print(f"{marker} {e.lineno-2+i}: {line[:100]}")
