# -*- coding: utf-8 -*-
"""修复第2905行的未闭合三引号"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 修复第2905行 - 替换乱码文档字符串
for i in range(len(lines)):
    if i == 2904:  # 第2905行（0-indexed）
        indent = len(lines[i]) - len(lines[i].lstrip())
        # 用英文替换避免编码问题
        lines[i] = ' ' * indent + '"""Report PDF filename: brand_type_date.pdf."""\n'
        print(f"修复第{i+1}行")
        break

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

# 验证语法
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n" + "="*50)
    print("SUCCESS! app.py syntax is correct!")
    print("="*50)
except SyntaxError as e:
    print(f"\nERROR Line {e.lineno}: {e.msg}")
    content_lines = content.split('\n')
    for j in range(max(0, e.lineno-3), min(e.lineno+4, len(content_lines))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content_lines[j][:120]}")
