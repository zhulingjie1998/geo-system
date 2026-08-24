# -*- coding: utf-8 -*-
"""检查当前文件状态，只报告错误不修改"""

import ast

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print(f"总行数: {len(lines)}")

try:
    ast.parse(content)
    print("✓ 语法正确!")
except SyntaxError as e:
    print(f"\n✗ 第 {e.lineno} 行: {e.msg}")
    print(f"\n=== 错误附近代码 ===")
    for j in range(max(0, e.lineno-5), min(e.lineno+6, len(lines))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {lines[j][:120]}")
