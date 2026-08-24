# -*- coding: utf-8 -*-
"""删除第2760行的TODO docstring"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")
print(f"\n第2759-2763行:")
for i in range(2758, 2764):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")

# 删除第2760行（index 2759）的 TODO docstring
if 'TODO: fix docstring' in lines[2759]:
    del lines[2759]
    print(f"\n✓ 删除了第2760行的TODO docstring")

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

# 验证
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n" + "="*50)
    print("✓✓✓ 语法完全正确! app.py 修复成功! ✓✓✓")
    print("="*50)
except SyntaxError as e:
    print(f"\n✗ 第 {e.lineno} 行: {e.msg}")
    for j in range(max(0, e.lineno-3), min(e.lineno+4, len(content.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content.split(chr(10))[j][:100]}")
