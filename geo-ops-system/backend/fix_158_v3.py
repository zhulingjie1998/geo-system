# -*- coding: utf-8 -*-
"""Fix line 158 with pure ASCII to avoid any encoding issues"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Replace with English docstring to avoid all CJK encoding issues
lines[157] = '    """Lockout cooldown based on IP lockout count in past 24h."""\n'

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("Fixed with English docstring!")

# Verify
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"✗ Error at line {e.lineno}: {e.msg}")
    # Show hex dump of problematic area
    error_line = content.split('\n')[e.lineno-1]
    print(f"Line content: {[hex(ord(c)) for c in error_line[:50]]}")
