# -*- coding: utf-8 -*-
"""Fix line 158 docstring with exact byte matching"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 158 (index 157) is the problematic docstring
print("Line 158:")
print(repr(lines[157]))

# Replace it with correct Chinese
old_line = lines[157]
new_line = '    """根据 IP 过去 24h 锁定次数决定本次冷却时长(秒)。include_current=1 表示即将触发的这一次也算进去。用于 record_lockout 后回扣。"""\n'

lines[157] = new_line

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("\nFixed! New line 158:")
print(repr(lines[157]))

# Check syntax
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"\n✗ Syntax Error at line {e.lineno}: {e.msg}")
    # Show context
    error_lines = content.split('\n')[max(0, e.lineno-3):e.lineno+3]
    for i, line in enumerate(error_lines):
        marker = ">>>" if i == (e.lineno - max(0, e.lineno-3) - 1) else "   "
        print(f"{marker} {e.lineno-2+i}: {line[:100]}")
