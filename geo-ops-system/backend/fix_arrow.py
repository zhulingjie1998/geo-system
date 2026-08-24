# -*- coding: utf-8 -*-
"""修复最后一个错误：箭头字符"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 替换箭头字符
content = content.replace('→', '->')

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

# 验证
import ast
try:
    ast.parse(content)
    print("="*50)
    print("✓✓✓ 语法完全正确! app.py 修复成功! ✓✓✓")
    print("="*50)
except SyntaxError as e:
    print(f"✗ 第 {e.lineno} 行: {e.msg}")
    lines = content.split('\n')
    for j in range(max(0, e.lineno-3), min(e.lineno+4, len(lines))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {lines[j][:120]}")
