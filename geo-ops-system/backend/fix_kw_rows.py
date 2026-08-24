# -*- coding: utf-8 -*-
"""修复第1231-1246行的代码结构"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("修复前:")
for i in range(1230, 1250):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")

# 问题：第1242-1246行是孤立的字典内容，缺少 kw_rows = [
# 需要在第1241行后插入 kw_rows = [{

# 找到第1241行（空行），在其后插入
lines.insert(1241, '    kw_rows = [{\n')

# 删除原来的孤立行 (1242-1246，因为插入了一行，现在是1243-1247)
# 先删除这些行
del lines[1243:1248]  # 删除5行

print("\n修复后:")
for i in range(1230, 1250):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

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
