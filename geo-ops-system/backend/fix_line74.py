# -*- coding: utf-8 -*-
"""Fix remaining encoding issues in app.py"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 74 (index 73) - the logger.warning with mojibake
print(f"Line 74 (index 73): {repr(lines[73][:100])}")

# Replace with correct Chinese
lines[73] = '    logger.warning("请立即登录后修改密码。此提示只在 log 中出现一次。")\n'

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("Fixed line 74!")

# Verify syntax
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"\n✗ Syntax Error at line {e.lineno}: {e.msg}")
    # Show context around error
    error_lines = content.split('\n')[max(0, e.lineno-3):e.lineno+2]
    for i, line in enumerate(error_lines):
        marker = ">>>" if i == (e.lineno - max(0, e.lineno-3) - 1) else "   "
        print(f"{marker} {e.lineno-2+i}: {line}")
