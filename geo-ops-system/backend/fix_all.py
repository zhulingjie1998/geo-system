# -*- coding: utf-8 -*-
"""Comprehensive fix for all encoding issues in app.py"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Common mojibake patterns and their corrections
fixes = {
    # Line 93: 服务器内部错误
    '"鏈嶅姟鍣ㄥ唴閮ㄩ敊璇?': '"服务器内部错误"',
}

fixed_count = 0
for i, line in enumerate(lines):
    for old, new in fixes.items():
        if old in line:
            print(f"Line {i+1}: Fixed {old[:20]}... -> {new}")
            line = line.replace(old, new)
            fixed_count += 1
    lines[i] = line

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print(f"\nFixed {fixed_count} lines")

# Verify syntax
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"✗ Syntax Error at line {e.lineno}: {e.msg}")
    error_lines = content.split('\n')[max(0, e.linfo-3):e.lineno+2]
    for i, line in enumerate(error_lines):
        marker = ">>>" if i == (e.lineno - max(0, e.lineno-3) - 1) else "   "
        print(f"{marker} {e.lineno-2+i}: {line}")
