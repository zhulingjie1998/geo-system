# -*- coding: utf-8 -*-
"""最终验证"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

import ast

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print(f"总行数: {len(lines)}")

try:
    ast.parse(content)
    print("\n" + "="*50)
    print("SUCCESS! app.py syntax is correct!")
    print("="*50)
except SyntaxError as e:
    print(f"\nERROR Line {e.lineno}: {e.msg}")
    for j in range(max(0, e.lineno-5), min(e.lineno+6, len(lines))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {lines[j][:120]}")
