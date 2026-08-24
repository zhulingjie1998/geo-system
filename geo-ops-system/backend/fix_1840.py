# -*- coding: utf-8 -*-
"""修复_parse_brand_list函数的docstring"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== 修复前 ===")
for i in range(1838, 1850):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")

# 问题：第1840-1844行是损坏的docstring
# 需要替换为正确的空docstring
new_docstring = [
    'def _parse_brand_list(raw):\n',
    '    """Parse brand list from various input formats."""\n',
]

print(f"\n替换第1839-1844行")
lines[1839:1845] = new_docstring

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("\n=== 修复后 ===")
for i in range(1838, 1850):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")

# 验证
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n✓✓✓ 语法正确! ✓✓✓")
except SyntaxError as e:
    print(f"\n✗ 第 {e.lineno} 行: {e.msg}")
    for j in range(max(0, e.lineno-3), min(e.lineno+4, len(content.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content.split(chr(10))[j][:100]}")
