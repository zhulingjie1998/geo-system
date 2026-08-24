# -*- coding: utf-8 -*-
"""Find exact line causing syntax error by incremental parsing"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

import ast

# Try parsing incrementally
for i in range(155, 165):  # Around line 156-165
    try:
        # Try parsing just this line as an expression/statement
        code = ''.join(lines[:i+1])
        ast.parse(code)
        print(f"Lines 1-{i+1}: OK")
    except SyntaxError as e:
        print(f"Lines 1-{i+1}: ERROR at line {e.lineno}: {e.msg}")
        if e.lineno and e.lineno <= i+1:
            print(f"  Problematic line: {lines[e.lineno-1][:100].rstrip()}")
        break

# Also try compiling just lines around 158
print("\n--- Detailed check of lines 155-162 ---")
for i in range(154, 162):
    line = lines[i]
    # Check for non-printable characters
    has_issue = False
    for j, ch in enumerate(line):
        if ord(ch) < 32 and ch not in '\t\n\r':
            print(f"Line {i+1} pos {j}: control char 0x{ord(ch):02x}")
            has_issue = True
    if not has_issue:
        print(f"Line {i+1}: OK - {line.rstrip()[:80]}")
