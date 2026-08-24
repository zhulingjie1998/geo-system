# -*- coding: utf-8 -*-
"""修复第192行附近的缩进问题"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 显示185-200行
print("当前代码:")
for i in range(184, 202):
    print(f"{i+1}: {lines[i][:90].rstrip()}")

# 问题：第192行 if raw_body: 的缩进不对，它应该在try块内
# 修复：调整缩进使其成为if语句（不是嵌套在try里）
line_192 = lines[191]
print(f"\n第192行原始: {repr(line_192)}")

# 将 if raw_body: 改为正确的缩进级别（与上面的if对齐）
if 'if raw_body:' in line_192:
    lines[191] = '        if raw_body:\n'
    print("修复了第192行缩进")

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

# 验证
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n✓ 语法正确!")
except SyntaxError as e:
    print(f"\n✗ 第 {e.lineno} 行错误: {e.msg}")
    for j in range(max(0, e.lineno-2), min(e.lineno+2, len(content.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content.split(chr(10))[j][:90]}")
