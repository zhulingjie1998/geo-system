# -*- coding: utf-8 -*-
"""Fix: add missing closing parenthesis for _PUBLIC_API_PREFIXES tuple"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 106 (index 105) - mojibake comment
print("Line 106:", repr(lines[105][:80]))
lines[105] = '# Public API prefixes (no auth required for sharing + login + permission status)\n'

# Add closing parenthesis after line 119 (before @app.after_request)
# Line 119 is index 118, line 120 is empty (index 119), line 121 is @app.after_request (index 120)
# Insert ) after line 119
print("Line 119:", repr(lines[118]))
print("Line 120:", repr(lines[119]))
print("Line 121:", repr(lines[120]))

# Replace line 120 (empty) with closing paren
lines[119] = ')\n'

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
