# -*- coding: utf-8 -*-
"""Fix merged comment+code lines in app.py"""

import re

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

fixed = 0
for i, line in enumerate(lines):
    # Check if this is a line with mojibake that contains actual code after the corruption
    if any(ord(c) > 127 for c in line) and not line.strip().startswith('#'):
        # Look for Python code patterns that indicate real code is here
        patterns = [r'\s{4,}resp\.', r'\s{4,}return ', r'\s{4,}db\.', r'\s{4,}logger\.']
        
        for pat in patterns:
            match = re.search(pat, line)
            if match:
                print(f"Line {i+1}: Found code pattern")
                # Extract from the match position
                code_part = line[match.start():]
                # Ensure proper indentation
                if not code_part.startswith('    '):
                    code_part = '    ' + code_part.lstrip()
                lines[i] = code_part
                fixed += 1
                break

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print(f"\nFixed {fixed} lines")

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
