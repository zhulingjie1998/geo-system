# -*- coding: utf-8 -*-
"""Fix multiple issues in app.py"""

import re

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Fix 1: Add _PUBLIC_API_PREFIXES = ( assignment
lines[105] = '_PUBLIC_API_PREFIXES = (\n'

# Find and add closing paren after tuple
for i in range(116, 125):
    if 'KB review share with token auth' in lines[i]:
        print("Found tuple end at line", i+1)
        lines.insert(i+1, ')\n')
        break

# Fix 2: F-strings with mojibake and unbalanced braces
for i, line in enumerate(lines):
    if ('f"' in line or "f'" in line) and any(ord(c) > 127 for c in line):
        # Check for unbalanced {
        if '{' in line:
            open_count = line.count('{')
            close_count = line.count('}')
            if open_count > close_count:
                print("Line", i+1, ": Unbalanced f-string, fixing...")
                # Extract variable name from {var}
                var_match = re.search(r'\{(\w+)\s*$', line.rstrip())
                if var_match:
                    var_name = var_match.group(1)
                    replacement = 'f"Too many attempts, try again in {' + var_name + '} min"'
                    new_line = re.sub(r'f"[^"]*"', replacement, line)
                    lines[i] = new_line + '\n'

# Fix 3: Remove remaining mojibake comments
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith('#') and any(ord(c) > 127 for c in line):
        lines[i] = '\n'

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("\nVerifying syntax...")
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
